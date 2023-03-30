from prompt_lib import *


# 构造一条summary记录
def create_summary(local_header: str, local_body_content: str) -> list:
    local_prompt = construct_prompt(local_header, local_body_content)  # 使用当前提问体构造prompt
    local_response = get_response(local_prompt)  # 向Open AI提问，获得回答
    local_summary = [local_response]
    return local_summary


# 获取summary列表的主体函数
# 根据最大提问体长度max_len，对输入的片段列表list的元素进行连缀，通过Open AI的API提问，并构造总结列表
# 总结列表output_summary_list中的每一个元素也是一个列表，该列表的元素依次是章节序号、总结对应的起始片段编号，终止片段编号，章节标题，总结内容
def summarize(input_list: list, max_len: int, prompt_header: str) -> list:
    output_summary_list = []  # 输出的总结列表，列表中的元素格式与输入列表一致
    chapter_num = input_list[0][0]  # 章节序号
    chapter_title = input_list[0][3]  # 章节标题
    start_index = input_list[0][1]  # 初始化提问体连缀body_content的第一个片段的编号
    end_index = input_list[0][2]  # 初始化提问体连缀body_content的最后一个片段的编号

    body_len = 0
    body_content = ''  # 通过将content_list记录的片段前后连缀得到
    for record in input_list:
        section_len = num_tokens_from_string(record[4])  # 计算每条片段（section）的长度
        if (body_len + section_len) <= max_len:  # 如果连缀后的长度依然小于提问体最大长度
            body_content += record[4]
            body_len += section_len
            end_index = record[2]  # 更新end_index
        else:  # 如果超过了提问体的最大长度
            # 先将当前的提问体投喂给Open AI，获取summary信息
            summary = create_summary(prompt_header, body_content)
            summary = [chapter_num, start_index, end_index, chapter_title] + summary
            output_summary_list.append(summary)  # 将当前的summary存储到chapter_summary_list中
            # 再构造新的提问体
            body_content = record[4]
            body_len = section_len
            start_index = record[1]  # 更新start_index
            end_index = record[2]  # 更新end_index

    # 将最后一个提问体投喂给Open AI，获取summary信息，并存储到chapter_summary_list中
    summary = create_summary(prompt_header, body_content)
    summary = [chapter_num, start_index, end_index, chapter_title] + summary
    output_summary_list.append(summary)

    return output_summary_list


# 迭代调用summarize的函数，用于对所有章节进行总结，每一轮迭代获取的总结内容都会放入all_summary_list，最后输出整章的总结
def iterative_summarize(prompt_header: str, max_len: int, input_summary_list: list,
                        all_summary_list: list) -> list:
    result_list = input_summary_list
    while len(result_list) > 1:  # 迭代调用summarize，直到生成只包含1个summary的list
        # print(result_list)  # debug用
        result_list = summarize(result_list, max_len, prompt_header)
        all_summary_list.extend(result_list)  # 将当前轮次的总结放入all_summary_list种
    all_summary_list.append(result_list[0])
    return result_list[0]


# 递归调用summarize的函数，用于对最原始的片段（segment）进行总结
def recursive_summarize(prompt_header: str, max_len: int, input_summary_list: list, all_summary_list: list):
    if len(input_summary_list) > 1:
        output_summary_list = summarize(input_summary_list, max_len, prompt_header)
        all_summary_list.extend(output_summary_list)  # 将当前层级的summary存储到总list中
        # print(output_summary_list)  # debug用

        # 递归调用本函数，生成更高层级的summary：
        recursive_summarize(prompt_header, max_len, output_summary_list, all_summary_list)


# 按章节编号对content_list进行分组，并将分组结果输出为dict
def list_2_dict(input_list: list) -> dict:
    output_dict = dict()  # 生成分组字典，字典中的每条记录，key为章节编号，value为该记录在list中的序号（可能不止1个）
    for i, s in enumerate([content[0] for content in input_list]):
        if s in output_dict:
            output_dict[s].append(i)
        else:
            output_dict[s] = [i]
    return output_dict


# 由chapter_summary调用，用于递归总结全书的内容
# 递归分为2个层面，规则是：
# 1）由精细到高级，每次将一个章节和它的子章节的内容做一遍递归总结，直到递归到根节点
# 2）对于1）中的每一次递归总结，同样进行递归，直到最后只生成1个总结记录
# tree：输入的全文各章节组成的树形dict，其中每个章节都是tree的一个节点，节点内的键value所对应的值是该章节的总结内容，其余键对应着子章节
def chapter_traverse(tree: dict, prompt_header: str, max_len: int, all_summary_list: list) -> list:
    if len(tree) > 1:  # 如果当前节点有子节点，递归遍历子节点
        input_summary_list = []
        for tree_key in tree.keys():
            # 跳过value键
            if tree_key == "value":  # 键为value，则直接将值填入input_summary_list
                input_summary_list.append(tree.get("value", ""))
                continue
            # 键不为value，则进入子节点，获取子节点的summary，然后填入input_summary_list
            child = tree[tree_key]
            input_summary_list.append(chapter_traverse(child, prompt_header, max_len, all_summary_list))
        summary = iterative_summarize(prompt_header, max_len, input_summary_list, all_summary_list)
    else:
        summary = tree.get("value", "")

    return summary


'''
建议外部调用summary_lib时，优先考虑直接调用以下面向用户需求的函数。在此之上的函数较为底层
'''


# 以章节划分，总结epub各章节的内容。input_list是由segment组成的全文片段list，总结内容都会放入total_summary_list
# recursive参数是关键选项：True的情况下，程序会进行递归总结，即：总结若干句原文的内容，形成一段总结文字，再以新的总结文字为基础，继续生成总结，
# 直到将整章内容总结为一段话为止。如果为False，则只会进行最浅层的总结，即按照章节文字的顺序，若干句总结为一段文字，不会进一步做递归。
def segment_summary(prompt_header: str, max_len: int, input_list: list, all_summary_list: list, recursive=False):
    index_dict = list_2_dict(input_list)
    for chapter_order, index_nums in index_dict.items():  # 遍历每个章节
        # 使用章节信息，构造用于输入summarize函数的列表
        input_segment_list = [[chapter_order, index_num, index_num,
                               input_list[index_num][2], input_list[index_num][3]] for index_num in index_nums]
        # 生成最初步的summary
        primary_summary_list = summarize(input_segment_list, max_len, prompt_header)

        # 将最初步的summary放入total_summary_list中
        all_summary_list.extend(primary_summary_list)

        if recursive:
            # 在最初步summary的基础上递归生成更高层级的summary
            recursive_summarize(prompt_header, max_len, primary_summary_list, all_summary_list)

        # print(primary_summary_list)  # debug用


# 以每个章节的总结文字为起始，递归地总结全书的内容，input_list是由segment组成的全文片段list，总结内容都会放入total_summary_list
def chapter_summary(prompt_header: str, max_len: int, input_list: list, all_summary_list: list):
    # 按章节编号对input_list进行分组
    index_dict = list_2_dict(input_list)

    # 首先找出每个章节对应的summary
    chapter_start_end = [(str(value[0]) + '-' + str(value[-1])) for value in index_dict.values()]
    chapter_summary_list = [summary for summary in all_summary_list
                            if (str(summary[1]) + '-' + str(summary[2])) in chapter_start_end]

    # 然后基于index_dict构造递归树index_tree，仅保留key，不保留index_dict的value
    index_tree = {}
    for key in index_dict.keys():
        sections = key.split(".")  # 将key按照"."进行分割，得到一个列表
        node = index_tree
        for section in sections:
            if section not in node:  # 如果当前级别不存在，创建一个空字典
                node[key] = {}
                node = node[key]
            else:
                node = node[section]
        summary = [s for s in chapter_summary_list if s[0] == key][0]
        node["value"] = summary  # 将当前key对应的summary设置为该节点的value

    # 遍历由全书章节构成的index_tree
    book_summary = chapter_traverse(index_tree, prompt_header, max_len, all_summary_list)  # 最后获取全书的总结
    all_summary_list.append(book_summary)


# 打开输出文件并将summary写入到csv文件中
def write_summary_to_csv(csv_name: str, input_summary_list: list):
    with open(csv_name, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["chapter number", "start segment", "end segment", "chapter title", "summary"])  # 写入表头
        for row in input_summary_list:  # 循环写入每一行
            writer.writerow(row)


# 从csv文件中读取summary信息
def read_summary_from_csv(csv_name: str) -> list:
    output_summary_list = []
    with open(csv_name, 'r') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # 跳过表头
        for row in reader:  # 循环读取每一行
            output_summary_list.append(row)
    return output_summary_list

import sys
import copy
import re
from ebooklib import ITEM_DOCUMENT, epub
from bs4 import BeautifulSoup as Bs


def search_node(order: str, node, tree: list):
    if isinstance(node, list):  # 尚未出现node为list类型的情况；这段为预留的处理代码
        for j in range(0, len(node)):
            sub_order = order + '.' + str(j)
            search_node(sub_order, node[j], tree)
    elif isinstance(node, tuple):  # tuple类型只包含2个元素，第1个是节点代表的章节的href，第2个是list类型，是它所包含的子章节
        element = [order, node[0].href, node[0].title, list()]
        tree.append(element)
        sub_nodes = node[1]  # tuple下的list元素的所有子章节
        for j in range(0, len(sub_nodes)):
            sub_order = order + '.' + str(j)
            search_node(sub_order, sub_nodes[j], tree)
    else:  # 当上一级为list、tuple类型时，递归调用会进入此处，在此向tree加入章节的基本信息：包括章节序号、href、章节名称和后续用于存储内容的空list
        element = [order, node.href, node.title, list()]
        tree.append(element)


#  解析epub toc列表中的href，将其按照#
def parse_href(local_href: str) -> list[str, str]:
    if len(local_href.split('#')) == 1:
        address = local_href
        sharp_value = ''
    else:
        address = local_href.split('#')[0]
        sharp_value = local_href.split('#')[1]
    return [address, sharp_value]


#  name：epub文件的名称+完整存放路径；max_len：切分后内容的最大长度，默认为100，不小于50；
#  content_tag：epub文件中正文段落所在的tag，有默认值，也可以自行指定；
#  输出为一个带有章节信息、且全书内容切分为不超过max_len字符串片段的列表
#  输出列表的每个元素均为一个列表，依次包含章节序号、章节所处的epub资源名称，章节标题和片段内容
def epub_parser(name: str, max_len: int = 100, content_tag=None) -> list[str, str, str, str]:
    # 被认为是包含了正文的tag
    if content_tag is None:  # 默认包含下面这些tags，用户也可以自行指定
        content_tag = ['p', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']

    if max_len < 50:  # 切分字符串不能太短，否则无法有效的上下文供Open AI理解
        max_len = 50

    # 1. 遍历并存储epub中各章节的基本信息、跳转位置（toc）
    ebook = epub.read_epub(name)
    content_list = []
    for i in range(0, len(ebook.toc)):
        search_node(str(i), ebook.toc[i], content_list)

    # 2. 遍历全书，把各个章节的内容分开存放到content_list中
    items = list(ebook.get_items())  # epub的item列表
    if len(content_list) == 1:  # 如果整本书只有1个章节，则一次性获取全书所有段落放入到content_list中
        paragraphs = []
        try:  # 如果该操作失败，直接抛出错误，退出程序
            for i in items:
                if i.get_type() == ITEM_DOCUMENT:
                    item_paras = [re.sub(r"[\n\t\r]+", ",", tag.text) for tag in
                                  Bs(i.content, "html.parser").findAll(content_tag) if not tag.text.isspace()]
                    paragraphs.extend(item_paras)
            content_list[0][3].extend(paragraphs)
        except (KeyboardInterrupt, Exception) as e:
            print(e)
            sys.exit(0)
    else:  # 如果有多个章节
        # 首先获取epub中的所有内容
        files = [item.file_name for item in items if item.get_type() == ITEM_DOCUMENT]  # 资源名称
        original_contents = [str(Bs(item.content, "html.parser")) for item in items
                             if item.get_type() == ITEM_DOCUMENT]  # 资源文件里的原始内容

        for i in range(0, len(content_list)):
            # 获取本章节和下一章节的起始位置
            [file_start, params_start] = parse_href(content_list[i][1])
            # 当遍历到index最后一行时，file_end选取files列表里最后一个元素，params_end则被设置为空，此时才能把直到文档末尾的所有p标签全部加上
            [file_end, params_end] = parse_href(content_list[i + 1][1]) if not i == len(content_list) - 1 \
                else [files[-1], '']

            # 获取起始位置对应的item序号
            start_list = [k for k in range(0, len(files)) if files[k] == file_start]
            end_list = [k for k in range(0, len(files)) if files[k] == file_end]

            # 将p标签添加到paragraphs变量中
            if len(start_list) != 0 and len(end_list) != 0:  # 如果起始和终止item都被找到
                start_num = start_list[0]
                end_num = end_list[0]
                paragraphs = []
                if start_num == end_num:  # 如果起始和终止item是同一个：
                    soup = Bs(original_contents[start_num], "html.parser")
                    # 找到起始和终止位置的tag
                    start_tag = soup.find(content_tag) if len(params_start) == 0 else soup.find(id=params_start)
                    end_tag = None if len(params_end) == 0 else soup.find(id=params_end)

                    # 找到起始和终止位置tag的编号
                    tag_list = soup.findAll()
                    tmp = [k for k in range(0, len(tag_list)) if tag_list[k] == start_tag]
                    start_point = tmp[0] if len(tmp) != 0 else 0
                    tmp = [k for k in range(0, len(tag_list)) if tag_list[k] == end_tag]
                    end_point = tmp[0] if len(tmp) != 0 else len(tag_list)

                    #  将起始-终止范围内的p标签添加到paragraphs变量中
                    for k in range(start_point, end_point):
                        if not tag_list[k].text.isspace():
                            # 将\n\t\r等连续出现的1-n个制表符替换为1个逗号
                            paragraphs.append(re.sub(r"[\n\t\r]+", ",", tag_list[k].text))

                else:
                    for k in range(start_num, end_num + 1):
                        soup = Bs(original_contents[k], "html.parser")
                        if k == start_num:
                            if len(params_start) == 0:  # 如果params_start是个空字符串
                                paragraphs.extend([re.sub(r"[\n\t\r]+", ",", tag.text) for tag in
                                                   soup.findAll(content_tag) if not tag.text.isspace()])
                            else:
                                start_tag = soup.find(id=params_start)
                                if not start_tag.text.isspace():
                                    # 先将包含id属性的标签放入paragraphs list中
                                    paragraphs.append(re.sub(r"[\n\t\r]+", ",", start_tag.text))
                                # 再将这之后所有标签添加到paragraphs数组
                                paragraphs.extend([re.sub(r"[\n\t\r]+", ",", tag.text) for tag in start_tag.
                                                  find_all_next(content_tag) if not tag.text.isspace()])
                        elif k == end_num:
                            if len(params_end) == 0:  # 如果params_end是个空字符串
                                pass
                            else:
                                end_tag = soup.find(id=params_end)
                                paragraphs.extend([re.sub(r"[\n\t\r]+", ",", tag.text) for tag in end_tag.
                                                  find_all_previous(content_tag, reverse=True)
                                                   if not tag.text.isspace()])
                        else:  # 既不是起始item，又不是终止item，则直接把所有能找到的p标签添加到paragraphs数组
                            paragraphs.extend([re.sub(r"[\n\t\r]+", ",", tag.text) for tag in soup.findAll(content_tag)
                                               if not tag.text.isspace()])

                content_list[i][3].extend(paragraphs)  # 将paragraphs存入index_tree
                # print(paragraphs)  # debug用

            else:  # break如果未获取起始或终止位置的item，说明程序检索出错，直接退出
                raise Exception(
                    'Internal error of the epub file, the referred html document in toc list is not found in '
                    'item list')

    # 3. 面向embedding，切分content_list中的章节内容，切分后的每个元素都不超过最大长度max_len
    cursor = 0  # 用于记录当且迭代位置的游标
    while cursor < len(content_list):
        index = content_list[cursor]
        content = index[3]  # 获取当前章节的内容

        split_list = []  # 存储按最大长度MAX_LEN拆分后的content
        sentence = ''  # 中间变量，最大长度为MAX_LEN的章节片段，每个sentence都会被存入到split_list
        for segment in content:  # 对于章节内容下的每个片段（对应原epub文件中的每个tag）
            if len(str(segment)) <= max_len:  # 如果这个片段的整体长度没有超过最大值
                if len(sentence+str(segment)) <= max_len:  # 如果该片段长度+当前sentence的总长不超过最大值
                    sentence += str(segment)  # 将该片段连缀到当前sentence的尾部
                else:  # 否则直接将该片段设置为一个新的sentence，同时将之前的sentence存入split_list内
                    split_list.append(copy.deepcopy(sentence))
                    sentence = str(segment)
            else:  # 如果片段本身超过最大值，则直接对其切分
                delimiters = '.?!;。？！；'  # 分隔符选用了中英双语的句号、问号、感叹号和分号（这里默认每句话长度不会超过MAX_LEN）
                regex_pattern = '|'.join(map(re.escape, delimiters))  # 转义分隔符并连接成正则表达式
                regex_pattern = '(?<=' + regex_pattern + ')'
                sub_strs = re.split(regex_pattern, str(segment))
                for sub_str in sub_strs:
                    if len(sentence+str(sub_str)) <= max_len:  # 如果该切分字符串长度+当前sentence的总长不超过最大值
                        sentence += sub_str  # 将该切分字符串连缀到当前sentence的尾部
                    else:  # 如果切分字符串长度超过最大值，则将其设置为一个新的sentence，同时将之前的sentence存入split_list内
                        split_list.append(copy.deepcopy(sentence))
                        sentence = sub_str

        if sentence not in split_list:  # 如果最后生成的sub_list没有被添加到split_list中
            split_list.append(sentence)

        content_info = index[:3]  # 获取前3个元素
        content_list.pop(cursor)  # 先删除cursor指向的元素
        for sentence in split_list:  # 然后将split_list里的元素逐一添加到content_list里
            new_content = copy.deepcopy(content_info)
            new_content.append(sentence)
            content_list.insert(cursor, new_content)
            cursor += 1

    return content_list

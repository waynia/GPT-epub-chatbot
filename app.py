import os
import re
from flask import Flask, render_template, request, make_response, redirect, url_for, jsonify, flash
from flask_caching import Cache
import chardet
from summary_lib import *
from embedding_lib import compute_doc_embeddings
from book_parser import epub_parser
from config import EMBEDDING_MODEL


app = Flask(__name__)
app.secret_key = 'chat-bot-with-epub-context'  # 可以设置为任何值
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["ALLOWED_EXTENSIONS"] = {"epub"}

# 背景内容的持久化。persistence为False时，表示每次处理用户提问，都直接从服务器硬盘读取背景内容；反之说明，背景内容放入内存中，可以提升回复速度
app.config['persistence'] = True
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# 记录上传epub的名字
app.config['book_name'] = ''


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


# 判断Open AI Key是否在cookie中，如果在，则将其再次赋予openai.api_key
def api_key_in_cookie():
    if request.cookies.get("openai_key") is None:
        return False
    else:
        openai.api_key = request.cookies.get("openai_key")
        return True


def parse_book(file_path, recursive=False):
    #  每次对于上传的epub文件做分析之前，都重新从客户端的cookie中读取Open AI Key，以避免用户主动删除导致程序出错
    if api_key_in_cookie():  # 如果在cookie中未找到Open AI Key则直接返回；理论上不会出现这种情况
        return None

    # 首先调用OpenAI API总结全书内容，生成保存总结内容的csv
    csv_file = file_path.rsplit(".", 1)[0] + ".csv"
    if not os.path.exists(csv_file):
        flash('Start to create the summary csv file for this uploaded book. This may take a long time.')
        header = '用不超过' + str(SUMMARY_LEN) + '字总结这段文字：'
        header_len = num_tokens_from_string(header)  # 提问头长度
        body_max_len = MAX_SECTION_LEN - header_len  # 提问体最大长度
        content_list = epub_parser(file_path)  # 内容列表中的每条记录，都是全文的一个片段
        total_summary_list = []  # 存储全书的总结内容，包括每若干个片段，每章，直到全书
        segment_summary(header, body_max_len, content_list, total_summary_list, recursive)  # 递归总结每个章节的内容
        chapter_summary(header, body_max_len, content_list, total_summary_list)  # 递归总结全书的内容
        write_summary_to_csv(csv_file, total_summary_list)  # 将总结内容保存到硬盘中

    # 然后调用OpenAI API计算每个总结内容的embedding
    embedding_file = file_path.rsplit(".", 1)[0] + '_embedding.csv'
    if not os.path.exists(embedding_file):
        flash('Start to create the embedding csv file for summary list. This may take a long time.')
        summary_list = read_summary_from_csv(csv_file)
        # 生成用于计算embedding的data frame
        column_names = ["chapter number", "start segment", "end segment", "chapter title", "summary"]
        df = pd.DataFrame(summary_list, columns=column_names)
        last_column_name = df.columns[-1]  # 将最后一列移动到第一列
        df = df[[last_column_name] + [col for col in df.columns if col != last_column_name]]
        # 计算embedding
        summary_dict = compute_doc_embeddings(df, EMBEDDING_MODEL)
        # 将计算得到的embedding写入csv
        save_embeddings(embedding_file, 'index', summary_dict)

    # 最后判断embedding文件是否生成
    if os.path.exists(embedding_file):
        flash('The summary csv file for this uploaded book has been successfully created.')
    else:  # 如果最后未生成embedding文件，则返回None；理论上不会出现这种情况
        flash('The summary csv file for this uploaded book failed to create.')


def check_api_key(api_key):
    openai.api_key = api_key

    try:
        openai.Model.list()
        return True
    except openai.error.AuthenticationError:
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def custom_secure_filename(filename):
    # 允许字母、数字、下划线、汉字、点和短横线，同时将其他字符替换为短横线（-）
    filename = re.sub(r'[^.\w\u4e00-\u9fa5-]', '-', filename)
    filename = re.sub(r'-+', '-', filename)  # 移除连续的短横线
    filename = filename.strip('-')  # 移除文件名开始和结束处的短横线
    # 限制文件名长度
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        name = name[:max_length - len(ext)]
        filename = name + ext

    return filename


# 判断uploads文件夹下是否有embedding文件，且embedding.csv文件和.csv文件成对出现
# 一般而言，在用户可以调用process_unit的情况下，是满足该条件的，在此判断是为了避免服务器上直接删除导致的错误
def check_embedding_file_integrity():
    uploads_folder = os.path.join(app.root_path, 'uploads')
    count = 0
    for filename in os.listdir(uploads_folder):
        if filename.endswith("_embedding.csv"):
            count += 1
    if count == 0:
        return False

    # 然后判断.csv和_embedding.csv是否成对出现
    csv_files = set()
    embedding_csv_files = set()
    for file_name in os.listdir(uploads_folder):
        if file_name.endswith('.csv'):
            if file_name.endswith('_embedding.csv'):
                base_name = file_name[:-len('_embedding.csv')]
                embedding_csv_files.add(base_name)
            else:
                base_name = file_name[:-len('.csv')]
                csv_files.add(base_name)

    # 检查是否所有的xxx.csv都有对应的xxx_embedding.csv
    paired_files = csv_files == embedding_csv_files
    return paired_files


@app.route("/check_api_key", methods=["POST"])
def check_api_key_route():
    api_key = request.form.get("api_key")
    is_valid = check_api_key(api_key)
    return jsonify({"is_valid": is_valid})


#  用于判断embedding.csv文件是否存在，存在返回true，不存在返回false
def has_embedding_file():
    uploads_folder = os.path.join(os.getcwd(), 'uploads')
    for file in os.listdir(uploads_folder):
        if file.endswith("_embedding.csv"):
            return True
    return False


#  用于返回uploads文件夹下第一个embedding.csv文件的完整路径
def find_first_embedding_file():
    folder_path = os.path.join(os.getcwd(), 'uploads')
    for file in os.listdir(folder_path):
        if file.endswith("_embedding.csv"):
            return os.path.join(folder_path, file)
    return None


@app.route("/check_csv_file", methods=["GET"])
def check_csv_file():
    if has_embedding_file():
        return jsonify({"csv_exists": True})
    else:
        return jsonify({"csv_exists": False})


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "file" in request.files:  # 处理上传的epub书籍
            file = request.files["file"]
            if file and allowed_file(file.filename):
                mode = request.form.get('mode', None)  # 获取总结epub文件的模式，simple或者recursive

                filename = custom_secure_filename(file.filename)
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(file_path)
                if mode == "simple":  # mode为simple，不使用递归总结
                    parse_book(file_path, False)
                elif mode == "recursive":  # mode为recursive，使用递归总结
                    parse_book(file_path, True)
                else:  # 其余情况，也不使用递归总结。一般而言不会出现这种情况
                    parse_book(file_path, False)
                resp = make_response(redirect(url_for("index")))
                return resp
        else:  # 处理用户输入的Open AI Key
            openai_key = request.form["input1"]
            resp = make_response(redirect(url_for("index")))
            resp.set_cookie("openai_key", openai_key)
            return resp

    openai_key = request.cookies.get("openai_key")  # 处理传给html的openai_key参数
    if has_embedding_file():  # 处理传给html的embedding_file参数
        embedding_file = find_first_embedding_file()
    else:
        embedding_file = None

    folder_path = os.path.join(os.getcwd(), 'uploads')  # 处理传给html的title参数
    for file in os.listdir(folder_path):
        if file.endswith("_embedding.csv"):
            app.config['book_name'] = file[:-len('_embedding.csv')]  # 将找到的embedding.csv文件的名称传递到前端
            break
    book_name = app.config['book_name']

    button_text = "Upload book" if openai_key else "Input key"
    placeholder_text = "Drop your epub book here" if openai_key else "Enter your OpenAI Key"
    return render_template("index.html", button_text=button_text, openai_key=openai_key, embedding_file=embedding_file,
                           placeholder_text=placeholder_text, book_name=book_name)


# 从服务器uploads文件夹里获取所有背景文字，及其embedding信息
def get_context_for_prompt():
    # 先遍历所有embedding文件，并合并为一个embedding。该处需改善，添加书名信息
    context_list = []
    context_embeddings = {}
    uploads_folder = os.path.join(app.root_path, 'uploads')
    for filename in os.listdir(uploads_folder):
        if filename.endswith('_embedding.csv'):
            csv_path = os.path.join(uploads_folder, filename)
            document_embeddings = load_embeddings(csv_path)

            base_name = filename[:-len('_embedding.csv')]
            csv_file_path = os.path.join(uploads_folder, f"{base_name}.csv")
            try:  # 检测文件编码，目前只能对中文特殊处理，且采用的是粗暴的gb18030识别方案，未来需改进
                with open(csv_file_path, 'rb') as f:
                    result = chardet.detect(f.read())
                csv_df = pd.read_csv(csv_file_path, encoding=result['encoding'], header=0)
            except UnicodeDecodeError as e:
                print(e)  # debug用
                csv_df = pd.read_csv(csv_file_path, encoding='gb18030', header=0)

            # 提取最后一列内容并替换dict变量的key
            new_embeddings = {}
            for idx, row in csv_df.iterrows():
                new_key = row[-1]
                if idx in document_embeddings:
                    new_embeddings[new_key] = document_embeddings.pop(idx)
            context_list.append(new_embeddings)
    # 构建完整的embedding列表
    for c in context_list:
        context_embeddings.update(c)

    return context_embeddings


@app.route('/process_input', methods=['POST'])
def process_input():
    #  每次对于上传的epub文件做分析之前，都重新从客户端的cookie中读取Open AI Key，以避免用户主动删除导致程序出错
    if not api_key_in_cookie():  # 如果在cookie中未找到Open AI Key则直接返回；理论上不会出现这种情况
        return redirect(url_for('index'))

    # 判断用户输入是否为空
    user_input = request.form['user_input']
    if user_input.isspace():
        return jsonify({"response": "Not valid input."})

    # 判断uploads文件夹中是否存在embedding文件，且embedding.csv文件和.csv文件成对出现
    if not check_embedding_file_integrity():
        return jsonify({"response": "Error in context files on the server."})

    # 获取回答用的背景内容
    if not app.config["persistence"]:  # 如果Flask程序被设置为非持久化，则每次获取背景文字，都从uploads中读取数据。不推荐
        context_embeddings = get_context_for_prompt()
    else:  # 如果已经设置为持久化
        if cache.get("context") is None:  # 如果此前程序没有获取过背景内容，那么第一次会从硬盘中读取，然后存入cache中
            context_embeddings = get_context_for_prompt()
            cache.set("context", context_embeddings)
        else:  # 如果此前程序获取了背景内容，则从cache中读取
            context_embeddings = cache.get("context")

    # 然后生成背景文字
    header = """请基于下面给定的背景文字回复用户输入,如果答案不包含在背景文字中，请说“我不知道”\n\n背景文字:\n """
    most_relevant_document_sections = embedding_relevance(user_input, context_embeddings, EMBEDDING_MODEL)
    chosen_sections = []
    chosen_sections_len = 0
    separator_len = num_tokens_from_string(SEPARATOR)
    for _, section_index in most_relevant_document_sections:  # Add contexts until we run out of space.
        if isinstance(section_index, str):  # 如果是字符串，则直接赋值给document_section
            document_section = section_index  # 返回正确结果时，section_index是str类型
            chosen_sections.append(SEPARATOR + document_section.replace("\n", " "))
            token_count = num_tokens_from_string(document_section)
            chosen_sections_len += token_count + separator_len
        else:  # 一般而言，不会出现这种情况
            return jsonify({"response": "Error in finding context"})
        if chosen_sections_len > MAX_SECTION_LEN:
            break

    # 最后生成prompt并输出给GPT，获取回答
    if chosen_sections_len == 0:  # 一般而言，不会出现这种情况
        return jsonify({"response": "Error in finding context"})
    else:  # 根据prompt，调用GPT生成回答并返回页面
        prompt = header + "".join(chosen_sections) + "\n\n 用户输入: " + user_input
        gpt_response = get_response(prompt)
        # 检查字符串是否以"？\n\n答案: "开头，这是目前OpenAI输出的response的开头，有时候前面也不会出现
        filtered_response = re.sub(r'^(\?|\n|？|Answer: |答案|：|:|\s)+', '', gpt_response)
        return jsonify({"response": filtered_response})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

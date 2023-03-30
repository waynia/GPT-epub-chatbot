import time
import pandas as pd
import numpy as np
import openai
import csv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff


#  为每一条记录生成一个embedding
def compute_doc_embeddings(local_df: pd.DataFrame, model: str) -> dict[str, list[float]]:
    content_column_name = local_df.columns[0]  # 获取上下文具体内容所在列的表头名称
    output = {}
    for local_ind, local_r in local_df.iterrows():
        local_content = local_r[content_column_name]
        embedding = get_embedding(local_content, model)
        output[str(local_ind)] = embedding
        time.sleep(0.02)
        status = str(local_ind) + ' embedding process finished'
        print(status)

    return output


#  text：提交给openai的prompt内容。model：计算embedding所用到的openai模型。
#  输出变量是一个1536个分量的float类型list。
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(8))
def get_embedding(text: str, model: str) -> list[float]:
    local_result = openai.Embedding.create(model=model, input=text)
    return local_result["data"][0]["embedding"]


#  f_name：待读取的csv文件名称
#  输出变量为dict类型，包含str类型的索引，和float类型的list（在pandas中被称为series）。
def load_embeddings(f_name: str) -> dict[str, list[float]]:
    local_df = pd.read_csv(f_name, header=0)
    f_index = local_df.columns[0]  # 读取csv文件第一列的列名（即：待读取csv文件第一行第一列）
    max_dim = max([int(c) for c in local_df.columns if c != f_index])
    return {
        r.name: [r[str(d)] for d in range(max_dim + 1)] for _, r in local_df.iterrows()
    }


#  f_name：写入硬盘的embedding文件名。f_index：索引的表头名称（对应csv文件第一行第一列）。
#  local_dict：embedding数据，每行由1个str类型的索引，和紧随其后的float类型的list（在pandas中被称为series）所组成。
def save_embeddings(f_name: str, f_index: str, local_dict: dict[str, list[float]]):
    fieldnames = [f_index]
    for d in range(1536):
        fieldnames.append(str(d))

    # 打开输出文件并创建CSV写入器
    with open(f_name, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # 写入表头
        writer.writerow(fieldnames)
        # 循环写入每一行
        for key, value in local_dict.items():
            value = list(map(str, value))
            row = [key] + value
            writer.writerow(row)


#  使用余弦，计算两个float类型list的相似度
def vector_similarity(x: list[float], y: list[float]) -> float:
    sim = float(np.dot(np.array(x), np.array(y)))
    return sim


#  query：提交给openai的prompt内容。contexts：从csv中读取的所有提前准备好的prompt的embedding，作为投喂给openai的上下文。
#  model：计算embedding所用到的openai模型。
#  输出变量为dict类型，每行的float变量代表query与提前准备好的prompt的相似度，str变量是该行对应的索引，行数与contexts相等
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(8))
def embedding_relevance(query: str, contexts: dict[str, np.array], model: str) -> list[(float, str)]:
    query_embedding = get_embedding(query, model)

    document_similarities = sorted([
        (vector_similarity(query_embedding, doc_embedding), doc_index) for doc_index, doc_embedding in contexts.items()
    ], reverse=True)

    return document_similarities

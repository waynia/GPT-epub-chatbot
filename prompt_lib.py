import tiktoken
from embedding_lib import *
from config import *


# 计算每个str对应的token数量。
def num_tokens_from_string(string: str, encoding_name: str = ENCODING) -> int:
    local_encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(local_encoding.encode(string))
    return num_tokens


# prompt_header：提问头，一般为一些通用的提示，比如“总结下文：”。body：提问体，是提问的具体内容
# 输出为str类型的变量，记录构造的提问prompt。
def construct_prompt(header: str, body: str) -> str:
    prompt = header + SEPARATOR + body
    total_len = num_tokens_from_string(prompt)
    if total_len <= MAX_SECTION_LEN:
        return prompt
    else:
        return "Too long question, try to shorten it!"


# question：输入的提问。context_embeddings：所有上下文的embedding，用于计算和输入提问之间的相关性。
# local_df：上下文的具体内容。prompt_header：向openai提问时，用于指定上下文和回答规则的提示词。
# 输出为str类型的变量，记录构造的提问prompt。
def construct_prompt_with_context(question: str, context_embeddings: dict, local_df: pd.DataFrame, header: str) -> str:
    most_relevant_document_sections = embedding_relevance(question, context_embeddings, EMBEDDING_MODEL)

    chosen_sections = []
    chosen_sections_len = 0
    # chosen_sections_indexes = []
    separator_len = num_tokens_from_string(SEPARATOR)
    content_column_name = local_df.columns[0]  # 获取上下文具体内容所在列的表头名称
    for _, section_index in most_relevant_document_sections:  # Add contexts until we run out of space.
        item = local_df.loc[section_index][content_column_name]
        if isinstance(item, str):  # 如果是字符串，则直接赋值给document_section
            document_section = item  # 返回正确结果时，local_df.loc[section_index][content_column_name]是str类型
            chosen_sections.append(SEPARATOR + document_section.replace("\n", " "))
            token_count = num_tokens_from_string(document_section)
            chosen_sections_len += token_count + separator_len
        elif isinstance(item, dict):  # 如果是dict，说明question和作为先验知识的上下文无关，此时会返回多个数值相近但与提问不相关的结果
            # document_section = local_df.loc[section_index][content_column_name][0]
            break
        else:  # 暂时未遇到其它情况，可以先设置直接退出
            break

        if chosen_sections_len > MAX_SECTION_LEN:
            break

        # chosen_sections_indexes.append(str(section_index))
    if chosen_sections_len == 0:
        return "Q: " + question + "\n A:"
    else:
        return header + "".join(chosen_sections) + "\n\n Q: " + question + "\n A:"


# 向openai提交提问的prompt，返回str类型的响应。
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def get_response(local_prompt: str) -> str:
    response = openai.Completion.create(
        prompt=local_prompt,
        **COMPLETIONS_API_PARAMS
    )
    return response["choices"][0]["text"].strip(" \n")


# prompt_lib库中，带有上下文提问时的入口函数
# query：str类型的用户提问内容。local_df：上下文的具体内容。
# local_document_embeddings：所有上下文的embedding，用于计算和输入提问之间的相关性。
# prompt_header：向openai提问时，用于指定上下文和回答规则的提示词。
# show_prompt：控制是否在命令行输出向openai提问的完整内容。
# 输出内容是str类型的变量，返回由openai生成的带有上下文知识的回答
def answer_query_with_context(
        query: str,
        local_df: pd.DataFrame,
        local_document_embeddings: dict[str, np.array],
        header: str,
        show_prompt: bool = True
) -> str:

    local_prompt = construct_prompt_with_context(
        query,
        local_document_embeddings,
        local_df,
        header
    )

    if show_prompt:
        print(local_prompt)

    return get_response(local_prompt)

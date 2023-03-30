COMPLETIONS_MODEL = "text-davinci-003"
EMBEDDING_MODEL = "text-embedding-ada-002"
ENCODING = "gpt2"  # encoding for text-davinci-003
SEPARATOR = "\n* "  # 相邻2条上下文之间的分隔符
MAX_SECTION_LEN = 2048  # 提问时提交的上下文的总长度，以token数量为单位
SUMMARY_LEN = 200  # 总结文字的总长度，以token数量为单位
COMPLETIONS_API_PARAMS = {
    "temperature": 0.0,  # 0.0 gives the most predictable, factual answer.
    "max_tokens": 300,
    "model": COMPLETIONS_MODEL,
}

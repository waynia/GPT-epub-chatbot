## 说明 | [English](https://github.com/waynia/GPT-epub-chatbot/blob/main/readme.md)

### 程序安装

#### 1. 在命令行中，运行 pip install -r requirements.txt

#### 2. 进入项目所在目录，打开命令行窗口，运行 flask run

#### 3. 在浏览器中打开http://127.0.0.1:5000

### 程序的实现原理

这个工具是基于ChatGPT实现的电子书解析与对话工具。包括使用flask实现的[简易GUI对话界面](https://github.com/waynia/Chat-GUI)，解析电子书的Web界面：

1）第一次打开界面，用户需要输入自己的OpenAI API Key，程序会将其保存在Cookie中，并向用户提供了一种删除该Key的方式。程序会调用OpenAI的函数对API Key的有效性进行验证，确保该Key可用。

2）在API Key有效的前提下，epub文件上传按钮可见，用户点击按钮或拖放epub文件到GUI界面，程序会将文件上传到uploads文件夹中，此后程序会依次执行全书内容分段抽取、递归总结、text-embedding计算，该过程会生成一个与上传文件名称相同的csv文件，存储总结内容，还会生成一个与上传文件名称相同的_embedding.csv文件，存储text-embedding数值。该过程完成后，就可以使用程序围绕这本书的细节和主要思想开展对话了。

3）此时用户可以在界面下方输入框中输入任何文字，程序在后台调用process_input函数遍历uploads文件夹下的所有csv文件，然后对输入文字进行分析，根据similarity获取背景文字作为回答预料，调用Open AI API生成答案，再返回给GUI界面。

4）对话记录可以点击界面中的链接下载。

5）程序尚未实现memory功能。
![效果示意](https://user-images.githubusercontent.com/49633741/228787095-c9d33f23-21ef-470d-9009-a14a262866a2.png)

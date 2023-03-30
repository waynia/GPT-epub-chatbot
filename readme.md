## Readme | [说明](https://github.com/waynia/GPT-epub-chatbot/blob/main/readme-zh_CN.md)

### Installation
pip install -r requirements.txt

Open http://127.0.0.1:5000 in your browser

### How the Program Works

This tool is an e-book parsing and conversation tool based on ChatGPT. It includes a [simple GUI conversation interface](https://github.com/waynia/Chat-GUI) implemented using Flask, and a web interface for parsing e-books:

1 Upon first opening the interface, the user needs to enter their OpenAI API Key. The program will save it in a cookie and provide a way for the user to delete the key. The program calls OpenAI's function to validate the API Key's effectiveness, ensuring it's usable.

2 With a valid API Key, the epub file upload button becomes visible. Users can click the button or drag and drop an epub file onto the GUI interface. The program will upload the file to the "uploads" folder. Subsequently, the program will perform the following tasks in sequence: extract content from the entire book, perform recursive summarization, and compute text-embeddings. This process generates a csv file with the same name as the uploaded file, storing summarized content, and a *_embedding.csv file, storing text-embedding values. After this process is completed, the program can be used to engage in conversations surrounding the details and main ideas of the book.

3 At this point, users can enter any text in the input box at the bottom of the interface. The program calls the process_input function in the background to traverse all csv files in the "uploads" folder and analyze the entered text. It retrieves background text as answer material based on similarity, calls the OpenAI API to generate an answer, and returns it to the GUI interface.

4 Conversation records can be downloaded by clicking the link on the interface.

5 The program does not yet implement conversation retention or memory features.
![效果示意](https://user-images.githubusercontent.com/49633741/228787169-73c8b0d3-6cd6-4860-adaf-d066c368c69a.png)

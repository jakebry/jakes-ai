from flask import Flask, request, jsonify
from jakes_ai_assistant import ask_gpt
from flask_cors import CORS
import os
import ast
import astunparse

app = Flask(__name__)
CORS(app)

@app.route('/ask', methods=['POST'])
def ask():
    # Get the user's question and file content from the request
    question = request.json.get('question')
    fileContent = request.json.get('fileContent')

    # Parse Python code into an AST and convert it back into code
    if fileContent is not None:
        try:
            tree = ast.parse(fileContent)
            fileContent = astunparse.unparse(tree)
        except:
            return jsonify({'response': 'Failed to parse Python code'})

    # Get the response from the bot
    response = ask_gpt(question, fileContent)

    # Return the response
    return jsonify({'response': response})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=8080, debug=True) #hello
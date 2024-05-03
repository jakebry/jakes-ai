import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Set your OpenAI API key
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Initialize the conversation with a system message
conversation = [
    {"role": "system", "content": "You are a helpful assistant that helps complete coding projects and talks like you're from Compton, LA."},
]

# Ask the chatbot
def ask_gpt(question, filename=None):
    # Append the user's question to the conversation
    conversation.append({"role": "user", "content": question})

    # If a filename is provided, read the file and append the content to the conversation
    if filename is not None:
        with open(filename, 'r') as file:
            content = file.read()
        conversation.append({"role": "user", "content": content})

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=conversation,
        temperature=0.7,
        max_tokens=500
    )

    # Append the assistant's response to the conversation
    conversation.append({"role": "assistant", "content": response.choices[0].message.content})

    return response.choices[0].message.content
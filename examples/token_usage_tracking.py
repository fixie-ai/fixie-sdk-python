import os

import requests
import tiktoken
from dotenv import load_dotenv

# Set the API key and Agent ID from our .env file
load_dotenv()
FIXIE_API_KEY = os.getenv("FIXIE_API_KEY")
AGENT_ID = os.getenv("FIXIE_AGENT_ID")

# Set up our global variables for capturing our stats
num_conversations = 0
num_messages = 0
len_conversations = 0
num_tokens = 0


def num_tokens_from_string(string: str) -> int:
    # Set up our tokenizer
    encoding = tiktoken.get_encoding("cl100k_base")

    num_tokens = len(encoding.encode(string))
    return num_tokens


def get_convo_turns(conversation: dict):
    global num_messages
    global len_conversations
    global num_tokens
    num_convo_messages = 0
    num_convo_chars = 0
    num_convo_tokens = 0

    for turn in conversation["turns"]:
        num_convo_messages += len(turn["messages"])

        for message in turn["messages"]:
            num_messages += 1
            if turn["state"] == "done":
                if (
                    turn["role"] == "assistant"
                    and message["kind"] == "functionResponse"
                ):
                    len_conversations += len(message["response"])
                    num_tokens += num_tokens_from_string(message["response"])

                    num_convo_chars += len(message["response"])
                    num_convo_tokens += num_tokens_from_string(message["response"])
                elif message["kind"] == "text" and (
                    turn["role"] == "assistant" or turn["role"] == "user"
                ):
                    len_conversations += len(message["content"])
                    num_tokens += num_tokens_from_string(message["content"])

                    num_convo_chars += len(message["content"])
                    num_convo_tokens += num_tokens_from_string(message["content"])

    print(f"\tTotal conversation messages\t{num_convo_messages}")
    print(f"\tTotal conversation characters\t{num_convo_chars}")
    print(f"\tTotal conversation tokens\t{num_convo_tokens}")


try:
    response = requests.get(
        f"https://api.fixie.ai/api/v1/agents/{AGENT_ID}/conversations",
        headers={"Authorization": f"Bearer {FIXIE_API_KEY}"},
    )

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()["conversations"]
        num_conversations = len(data)

        print(f"Agent {AGENT_ID} has {num_conversations} conversations.")
        print(f"\nConversation messages and token details are as follows:")

        for element in data:
            print(f"\nConversation ID: {element['id']}")
            print(f"------------------------------------------------------------")
            print(f"\tTotal conversation turns\t{len(element['turns'])}")

            get_convo_turns(element)

        # Display our final stats for the agent
        print(f"\n\nFinal stats for agent {AGENT_ID}:")
        print(f"============================================================")
        print(f"\tTotal Conversations\t{num_conversations}")
        print(f"\tTotal Agent Messages\t{num_messages}")
        print(f"\tTotal Characters\t{len_conversations}")
        print(f"\tTotal LLM Tokens\t{num_tokens}")
        print(f"============================================================")

    else:
        print(f"Request failed with status code {response.status_code}")

except Exception as e:
    print(e)

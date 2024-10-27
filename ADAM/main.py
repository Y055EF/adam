import os
from groq import Groq
import chromadb
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_cohere import CohereEmbeddings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client


def throw_if_missing(obj: object, keys: list[str]) -> None:
    """
    Throws an error if any of the keys are missing from the object

    Parameters:
        obj (object): Object to check
        keys (list[str]): List of keys to check

    Raises:
        ValueError: If any keys are missing
    """
    missing = [key for key in keys if key not in obj or not obj[key]]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

__dirname = os.path.dirname(os.path.abspath(__file__))
static_folder = __dirname
def get_static_file(file_name: str) -> str:
    """
    Returns the contents of a file in the static folder

    Parameters:
        file_name (str): Name of the file to read

    Returns:
        (str): Contents of static/{file_name}
    """
    file_path = os.path.join(static_folder, file_name)

    return file_path

def file_search(query: str):
    """
    Searches the knowledge base for a given query.

    Args:
        query (str): The query to search for in the knowledge base.

    Returns:
        str: The results of the search query.
    """
    docs = retriever.invoke(query)
    result = ""
    for i in docs:
        result = result + i.page_content + "\n\n----------------------------------\n\n"
    return result


def email_supervisor(context,summary):
    """
    Sends an email to the supervisor with a summary of the customer inquiry.

    Args:
        summary (str): The summary of the customer inquiry.

    Returns:
        dict: A dictionary containing the status and message of the email sending process.
    """
    sender_email = "adamtree010@outlook.com"  # Replace with your ProtonMail address
    sender_password = os.getenv("SENDER_PASSWORD")  # Replace with your ProtonMail password
    receiver_email = "youssef.khames67@gmail.com"
    
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = "Customer Inquiry Summary"

    body = f"Here's a summary of the customer inquiry:\n\n{summary}"
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp-mail.outlook.com",587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        context.log("Email sent successfully")
        return "Email sent successfully"
    except Exception as e:
        context.log(f"Failed to send email: {str(e)}")
        return f"Failed to send email: {str(e)}"


def capture_info(context,id: str,name: str , email :str, phone: str, notes: str):
    """
    Capture a lead and add it to the database.

    Args:
        messenger_id (str): The messenger ID of the lead.
        name (str): Name of the lead.
        email (str): Email of the lead.
        phone (str): Phone number of the lead.
        notes (str): Additional information about the lead.

    Returns:
        dict: A dictionary containing the status and message of the operation.
    """
    lead_data = {
        'name': name,
        'email': email,
        'phone': phone,
        'notes': notes
    }
    try:
        supa_client.table('leads').update(lead_data).eq('messenger_id', id).execute()
        context.log("Lead captured successfully")
        return "info captured successfully"
    except Exception as e:
        context.log("Failed to capture lead, error: " + str(e))
        return "Failed to capture info, appologize to the customer and file a complain to the supervisor"





tools=[{
        "type": "function",  # This adds the solar calculator as a tool
        "function": {
            "name": "file_search",
            "description":
            "Searches the knowledge base for a given query, use this tool with plain english question when you need information about to respond to the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type":
                        "string",
                        "description":
                        "The query to search for in the knowledge base"
                    },
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",  # This adds the solar calculator as a tool
        "function": {
            "name": "email_supervisor",
            "description":
            "send a summary of the conversation for the supervisor to intervine with customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type":
                        "string",
                        "description":
                        "summary of the conversation between you and the customer, especialy his pain points and questions, use it when the customer wants to escilate the situation to a the superviser"
                    },
                },
                "required": ["summary"]
            }
        }
    },
    {
        "type": "function",  # This adds the info capture as a tool
        "function": {
            "name": "capture_info",
            "description":
            "Capture customer details and save to database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the customer."
                    },
                    "phone": {
                        "type": "string",
                        "description": "Phone number of the customer."
                    },
                    "email": {
                        "type": "string",
                        "description": "email address of the customer."
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional information about the customer, write what brought him and a summary of the conversation"
                    }
                },
                "required": ["name", "phone", "email", "notes"]
            }
        }
    }
]

def setup_env(context):
    context.log("setup started")
    global MODEL, prompt, embeddings, supa_client, db, retriever, tools, client, Client

    throw_if_missing(
        os.environ,
        [
            "GROQ_API_KEY",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "COHERE_API_KEY",
            "SENDER_EMAIL",
            "SENDER_PASSWORD"
        ],
    )
    
    embeddings = CohereEmbeddings( 
        cohere_api_key=os.getenv("COHERE_API_KEY"),
        model="embed-english-v3.0",
    )
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supa_client= create_client(url, key)
    Client = chromadb.Client()
    client = Groq(
        api_key=os.environ.get("GROQ_API_KEY")
    )
    
    
    MODEL = "llama3-groq-70b-8192-tool-use-preview"
    prompt_path = get_static_file("prompt.txt")
    knowledge_path = get_static_file("knowledge.md")
    db_dir = get_static_file("knowledge")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt = f.read()

    if os.path.exists(db_dir):
        context.log('DB exists')
    else:
        with open(knowledge_path, 'r', encoding='utf-8') as f:
            file = f.read()
        docs = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=400).split_text(file)
        Chroma.from_texts(docs, embeddings, persist_directory=db_dir) 
        context.log("DB created")

    db = Chroma(persist_directory=db_dir, embedding_function=embeddings)
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 3})
    context.log('retriever ready')
    




def chat_history(context, messenger_id) -> list:
    data=supa_client.table('leads').select('chat_history').eq('messenger_id',messenger_id).execute()
    if not data.data == [] and data.data[0]['chat_history']:
        chat_history = json.loads(data.data[0]['chat_history'])
        return chat_history
    else:
        supa_client.table('leads').insert({'messenger_id':messenger_id,'chat_history':"[]"}).execute()
        context.log("New id has been saved")
        return []



def response(context,messenger_id,input)->str:

    convo = chat_history(context,messenger_id)
    convo.append({"role": "system", "content": prompt})
    convo.append({"role": "user", "content": input})
    response = client.chat.completions.create(
        model=MODEL, # LLM to use
        messages=convo, # Conversation history
        stream=False,
        tools=tools, # Available tools (i.e. functions) for our LLM to use
        tool_choice="auto", # Let our LLM decide when to use tools
        temperature=0.3 # Maximum number of tokens to allow in our response
    )
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls
    if tool_calls:
        context.log("tool needed")
        convo.append(response_message)
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            if function_name == "capture_info":
                context.log(f"trying to call capture_info with {function_args}")
                function_response = capture_info(context,id=messenger_id,name=function_args["name"], email=function_args["email"], phone=function_args["phone"], notes=function_args["notes"])
            elif function_name == "email_supervisor":
                context.log(f"trying to call email_supervisor with {function_args}")
                function_response = email_supervisor(context,summary=function_args["summary"])
            else:
                context.log(f"trying to call file_search with {function_args}")
                function_response = file_search(
                    function_args["query"]
                )
            # Add the tool response to the conversation
            convo.append(
                {
                    "tool_call_id": tool_call.id, 
                    "role": "tool", # Indicates this message is from tool use
                    "name": function_name,
                    "content": function_response,
                }
            )
        # Make a second API call with the updated conversation
        second_response = client.chat.completions.create(
            model=MODEL, # LLM to use
            messages=convo, # Conversation history
            stream=False,
            tools=tools, # Available tools (i.e. functions) for our LLM to use
            tool_choice="auto", # Let our LLM decide when to use tools
            temperature=0.3 # Maximum number of tokens to allow in our response
        )
        # Return the final response
        return second_response.choices[0].message.content

    convo.append({"role": "assistant", "content": response_message.content})
    supa_client.table('leads').update({'chat_history': json.dumps(convo)}).eq('messenger_id',messenger_id).execute()
    return response_message.content




def main(context):
    setup_env(context)
    data = json.loads(context.req.body_raw)
    messenger_id = data.get('messenger_id')
    user_input = data.get('message', '')

    if not messenger_id:
        context.log("Error: Missing messenger_id")
        return context.error("Error", "Missing messenger_id")
    elif not user_input:
        context.log("Error: Missing a message")
        return context.error("error", "Missing a message")
    else:
        context.log(f"Received message: ({user_input}) for thread ID: ({messenger_id})")

    assistant_response = response(context, messenger_id, user_input)
    context.log(f"assistant responded: {assistant_response}")
    return context.res.json({"assistant_response": assistant_response})

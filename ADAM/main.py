from langchain_groq import ChatGroq
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_cohere import CohereEmbeddings
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

import os
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

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
llm = ChatGroq(api_key=GROQ_API_KEY,model="llama3-groq-70b-8192-tool-use-preview", temperature=0)
embeddings = CohereEmbeddings( 
    cohere_api_key=COHERE_API_KEY,
    model="embed-english-v3.0",
)
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supa_client= create_client(url, key)

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

__dirname = os.path.dirname(os.path.abspath(__file__))
static_folder = os.path.join(__dirname, "../ADAM")



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

def create_db(knowledge_path, db_dir):
    if not os.path.exists(knowledge_path):
        print("No KB found")
        return False
    if os.path.exists(db_dir):
        print('DB exists')
        return True
    with open(knowledge_path, 'r', encoding='utf-8') as f:
        file = f.read()
    docs = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=400).split_text(file)
    Chroma.from_texts(docs, embeddings, persist_directory=db_dir) 
    print("DB created")
    return True

knowledge_path = get_static_file('knowledge.md')
db_dir = get_static_file('dbs\\knowledge')
create_db(knowledge_path,db_dir)
db = Chroma(persist_directory=db_dir, embedding_function=embeddings)
retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 3})


@tool
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



@tool
def email_supervisor(summary):
    """
    Sends an email to the supervisor with a summary of the customer inquiry.

    Args:
        summary (str): The summary of the customer inquiry.

    Returns:
        dict: A dictionary containing the status and message of the email sending process.
    """
    sender_email = SENDER_EMAIL  # Replace with your ProtonMail address
    sender_password = SENDER_PASSWORD  # Replace with your ProtonMail password
    receiver_email = "academiccommittee1@gmail.com"
    
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
        print("Email sent successfully")
        return {"status": "success", "message": "Email sent successfully"}
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return {"status": "error", "message": f"Failed to send email: {str(e)}"}

current_messenger_id = None

@tool
def capture_info(name: str , email :str, phone: str, notes: str):
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
    global current_messenger_id
    if current_messenger_id is None:
        print("Error: Missing messenger_id")
        return {"status": "error", "message": "Failed to capture info, appologize to the customer and file a complain to the supervisor"}
    try:
        supa_client.table('leads').update(lead_data).eq('messenger_id', current_messenger_id).execute()
        print("Lead captured successfully")
        return {"status": "success", "message": "info captured successfully"}
    except Exception as e:
        print("Failed to capture lead, error: " + str(e))
        return {"status": "error", "message": "Failed to capture info, appologize to the customer and file a complain to the supervisor"}

tools = [file_search, capture_info, email_supervisor]

prompt_path = get_static_file('prompt.txt')
with open(prompt_path, 'r', encoding='utf-8') as f:
    prompt = f.read()

p = ChatPromptTemplate.from_messages(
    [
        ("system", f"{prompt}"),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)

agent = create_openai_tools_agent(llm=llm,tools=tools,prompt=p)
agent_executor = AgentExecutor(agent=agent, tools=tools)

def main(context):

    data = json.loads(context.req.body_raw)
    messenger_id = data.get('messenger_id')
    user_input = data.get('message', '')

    if not messenger_id:
        print("Error: Missing messenger_id")
        return context.error("Error", "Missing messenger_id")
    elif not user_input:
        print("Error: Missing a message")
        return context.error("error", "Missing a message")
    else:
        print(f"Received message: ({user_input}) for thread ID: ({messenger_id})")

    global current_messenger_id
    current_messenger_id = messenger_id
    data=supa_client.table('leads').select('chat_history').eq('messenger_id',messenger_id).execute()

    if data.data != [] and data.data[0]['chat_history']:
        json_string = data.data[0]['chat_history']
        chat_history = [
            globals()[msg["type"]](content=msg["content"])
            for msg in json.loads(json_string)
        ]
        if len(chat_history) > 30:
            chat_history = chat_history[2:]
        print("previous chat history found and loaded")
    else:
        chat_history = []
        json_string = json.dumps([{"type": type(msg).__name__, "content": msg.content} for msg in chat_history])
        supa_client.table('leads').insert({'messenger_id':messenger_id,'chat_history':chat_history}).execute()
        print("New id has been saved")
        
    result = agent_executor.invoke(
        {
            "input": user_input,
            "chat_history": chat_history,
        }
    )
    chat_history.append(HumanMessage(content=user_input))
    chat_history.append(AIMessage(content=result["output"]))
    json_string = json.dumps([{"type": type(msg).__name__, "content": msg.content} for msg in chat_history])
    supa_client.table('leads').update({'chat_history': json_string}).eq('messenger_id',messenger_id).execute()
    return context.res.json({"assitant_response": result['output']})


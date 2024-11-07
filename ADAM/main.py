import os
import json
from openai import OpenAI
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client
import tiktoken
import time


static_folder = os.path.dirname(os.path.abspath(__file__))
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supa_client= create_client(url, key)
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

model = "gpt-4o-mini-2024-07-18"
prompt_path = os.path.join(static_folder,"prompt.txt")
knowledge_path =os.path.join(static_folder,"knowledge.md")
enc = tiktoken.encoding_for_model("gpt-4o")
with open(prompt_path, 'r', encoding='utf-8') as f:
    prompt = f.read()

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

def create_assistant(context,client,assistant_name):


  # If there is an assistant.json file already, then load that assistant
    if not supa_client.table('assistants').select('assistant_id').eq('name',assistant_name).execute().data == []:
        assistant_id = supa_client.table('assistants').select('assistant_id').eq('name',assistant_name).execute().data[0]['assistant_id']
        return assistant_id
    else:
        file = client.files.create(file=open(knowledge_path, "rb"),
                                    purpose='assistants',)
        hash = hashlib.md5(f.read()).hexdigest()
        vector_store = client.beta.vector_stores.create(
                name="knowledge",
                file_ids=[file.id]
                )
        assistant = client.beta.assistants.create(
            name="Adam",
            instructions=prompt,
            temperature = 0.3,
            model=model,
            tools=tools,
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}}
            )
        supa_client.table('leads').insert({'name':assistant_name,'assistant_id': assistant.id,'vector_id': vector_store.id,'file_id': file.id,'hash': hash}).execute()
        # Create a new assistant.json file to load on future runs


        assistant_id = assistant.id

        return assistant_id
        
def update_knowlege(context, client, file_path,assistant_name):  
    hash_data = supa_client.table('assistants').select('hash').eq('name',assistant_name).execute()
    if hash_data.data == []:
        stored_hash =  hash_data.data[0]['hash']
    else:
        stored_hash = ''
    with open(file_path, 'rb') as f:
        current_hash = hashlib.md5(f.read()).hexdigest()


    if current_hash != stored_hash:
        context.log("The knowledge.md file has changed, Updating...")    
        
        vector_store_id = supa_client.table('assistants').select('vector_id').eq('name',assistant_name).execute().data[0]['vector_id']
        file_id = supa_client.table('assistants').select('file_id').eq('name',assistant_name).execute().data[0]['file_id']
        
        if stored_hash != '':
            client.files.delete(file_id)
        
        file = client.files.create(
            file=open(knowledge_path, "rb"),
            purpose='assistants',
        )
        client.beta.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file.id
        )

        supa_client.table('assistants').update({'hash_file':current_hash}).eq('name',assistant_name).execute()
        supa_client.table('assistants').update({'file_id':file.id}).eq('name',assistant_name).execute()
        context.log("knowledge base has been updated")
    else:
        context.log("file has not changed")

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


def supa_threads(messenger_id):
    data=supa_client.table('leads').select('thread_id').eq('messenger_id',messenger_id).execute()
    if not data.data == []:
        return data.data[0]['thread_id']
    else:
        return None


tools=[{
        "type": "file_search",  # This adds the solar calculator as a tool

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





def response(context,messenger_id,user_input,assistant_id):
    if supa_threads(messenger_id):
        thread_id = supa_threads(messenger_id)
        context.log("previous thread found and loaded")
    else:
        thread = client.beta.threads.create()
        thread_id =thread.id
        supa_client.table('leads').insert({'messenger_id':messenger_id,'thread_id': thread_id}).execute()
        context.log("id has been saved")
   
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_input
    )

    
    while True:
        run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id=assistant_id)
        if run.status == 'completed':
            break
        elif run.status == 'requires_action':
            context.log("using an action")
        # Handle the function call
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                if tool_call.function.name == "email_supervisor":
                    context.log("trying to email_supervisor")
                    arguments = json.loads(tool_call.function.arguments)
                    output = email_supervisor(context, arguments["summary"])
                    try:
                        client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id,
                                                                    run_id=run.id,
                                                                    tool_outputs=[{
                                                                        "tool_call_id":tool_call.id,
                                                                        "output":json.dumps(output)
                                                                    }])
                        context.log("action succeeded")
                    except Exception as e:
                        context.log(f"failed to submit tool: {e}")
                elif tool_call.function.name == "capture_info":
                    context.log("trying to capture_info")
                    arguments = json.loads(tool_call.function.arguments)
                    output = capture_info(messenger_id=messenger_id, name=arguments["name"],phone=arguments["phone"],email=arguments["email"],notes=arguments["notes"])
                    try:
                        client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id,
                                                                    run_id=run.id,
                                                                    tool_outputs=[{
                                                                        "tool_call_id":tool_call.id,
                                                                        "output":json.dumps(output)
                                                                    }])
                        context.log("action succeeded")
                    except Exception as e:
                        context.log(f"failed to submit tool: {e}")
        else:
            context.log(run.status)
        time.sleep(0.5)  # Wait for a second before checking again

    # Retrieve and return the latest message from the assistant
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    response = messages.data[0].content[0].text.value

    context.log(f"Assistant response: {response}")
    return response



def main(context):
    throw_if_missing(
        os.environ,
        [
            "OPENAI_API_KEY",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "COHERE_API_KEY",
            "SENDER_EMAIL",
            "SENDER_PASSWORD"
        ],
    )
    assistant_id = create_assistant(context,client,'Adam')
    update_knowlege(context,client,knowledge_path,'Adam')
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
    assistant_response = response(context, messenger_id, user_input,assistant_id)
    context.log(f"assistant responded: {assistant_response}")
    return context.res.json({"assistant_response": assistant_response})
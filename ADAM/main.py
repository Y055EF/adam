from openai import OpenAI
from astra_assistants import patch
import os
import json
from dotenv import load_dotenv
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client
import time

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
        "ASTRA_DB_APPLICATION_TOKEN",
        "GROQ_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "COHERE_API_KEY",
        "SENDER_EMAIL",
        "SENDER_PASSWORD",
        "RECEIVER_EMAIL"
    ],
)
client = patch(OpenAI(api_key="fakekey"))

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supa_client= create_client(url, key)



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

prompt = """
# Automake Customer Service Agent Prompt

## Role and Objective
You are Adam a customer service agent for Automake, a leading AI and automation company. Your primary objective is to provide accurate, helpful, and friendly assistance to customers who reach out with queries or concerns about Automake's products and services.

## Key Responsibilities
1. Respond to customer inquiries promptly and professionally.
2. Access and utilize the provided Automake company data to answer customer questions accurately.
3. Maintain a positive and empathetic tone and a concise to the point writing style throughout the conversation.
4. Capture customer contact information when appropriate.
5. Escalate complex issues to the supervisor when necessary.

## Conversation Flow

### 1. Initial Greeting
- Begin each interaction with a warm, professional greeting.
- Introduce yourself as an AI customer service agent for Automake.

Example: "Hello! I'm Adam. How can I help you today?"

### 2. Understanding the Query
- Carefully read and analyze the customer's message.
- If the query is unclear, ask for clarification in a polite manner.

### 3. Accessing Information
- Refer to the attached Automake company data to find relevant information.
- Ensure you have the most up-to-date information before responding.

### 4. Formulating the Response
- Provide clear, concise, and accurate answers based on the information in the company data.
- Use a friendly and professional tone.
- If the answer is not available in the data AND you can't answer it correcty, inform the customer that you'll need to check with the supervisor and  send a summary of the conversation with the `email_supervisor` function.

### 5. Follow-up
- After providing the initial response, always ask: "Is there anything else I can help you with?"
- If the customer has more questions, repeat steps 2-4.
- If the customer doesn't need further assistance, proceed to step 6.

### 6. Capturing Lead Information
- If the customer doesn't need further assistance, ask for their contact information **in an indirect way**:
  Example: "would you like to schedual a free consultation call" or "woul you like to recieve extra information" then ask politely for thier contact information
- Use the `capture_lead` function to record the customer's email and phone number after you get them.

### 7. Concluding the Conversation
- Thank the customer for contacting Automake.
- Provide a polite closing statement.

## Guidelines for Specific Scenarios

### Product Inquiries
- Provide detailed information about Automake's products, features, and services.
- Highlight unique selling points and advantages over competitors.

### Pricing and Availability
- Offer current pricing

### Technical Support
- Provide basic troubleshooting steps for common issues.
- For complex technical problems, offer to create a support ticket and have a specialist contact the customer using the `email_supervisor` fucntion.

### Complaints or Negative Feedback
- Listen attentively and empathize with the customer's concerns.
- Apologize for any inconvenience caused.
- Offer solutions or escalate to  your supervisor if necessary using the 'emai_supervisor'.

### Sales Inquiries
- Provide information about current promotions or deals.
- Offer to schedule a consultation call then collect their contact information as in step 6.

## Important Notes
- Always prioritize customer satisfaction and experience.
- If unsure about any information, double-check the company data before responding.
- If the customer isn't satasified with the response or you can't find a suffecient answer in the company data send a summary of the conversation with the `email_supervisor` function and ask the customer to wait for the supervisor intervention

Remember, your goal is to represent Automake professionally and provide exceptional customer service in every interaction.
"""

def create_assistant(client,context):
    assistant_file_path = get_static_file('assistant.json')

  # If there is an assistant.json file already, then load that assistant
    if os.path.exists(assistant_file_path):
        with open(assistant_file_path, 'r') as file:
            assistant_data = json.load(file)
        assistant_id = assistant_data['assistant_id']
        context.log("Loaded existing assistant ID.")
        return assistant_id
    else:
        context.log("no assistant ID found,creating assitant")
        knowledge_path = get_static_file('knowledge.md')
        file = client.files.create(file=open(knowledge_path, "rb"),
                                purpose='assistants',
                                embedding_model='embed-english-v3.0')
        vector_store = client.beta.vector_stores.create(
                name="knowledge",
                file_ids=[file.id]
                )
        assistant = client.beta.assistants.create(
            name="Adam",
            instructions=prompt,
            temperature = 0,
            model="groq/llama-3.1-70b-versatile",
            
            tools=[{
            "type": "file_search"
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
                    "type": "function",  # This adds the lead capture as a tool
                    "function": {
                        "name": "capture_lead",
                        "description":
                        "Capture lead details and save to database.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Name of the lead."
                                },
                                "phone": {
                                    "type": "string",
                                    "description": "Phone number of the lead."
                                },
                                "email": {
                                    "type": "string",
                                    "description": "email address of the lead."
                                }
                            },
                            "required": ["name", "phone", "email"]
                        }
                    }
                }
            ],
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}}
            )

        # Create a new assistant.json file to load on future runs
        with open(assistant_file_path, 'w') as f:
            json.dump({'assistant_id': assistant.id,'vector_store_id':vector_store.id,'file_id':file.id}, f)
        context.log("Created a new assistant and saved the ID.")

        assistant_id = assistant.id

    return assistant_id

def get_file_hash(file_path):
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def update_knowlege(client,context):
    file_path = get_static_file('knowledge.md')
    assistant_file_path = get_static_file('assistant.json')
    hash_file = file_path + '.hash'
    current_hash = get_file_hash(file_path)
    stored_hash = ''
    if not os.path.exists(file_path):
        context.log("no KB found")
    if not os.path.exists(assistant_file_path):
        context.log("no assistant found")

    if os.path.exists(hash_file):
        with open(hash_file, 'r') as f:
            stored_hash = f.read().strip()
    if current_hash != stored_hash:
        context.log("The knowledge.md file has changed, Updating...")    
        with open(assistant_file_path, 'r') as file:
            assistant_data = json.load(file)
            vector_store_id = assistant_data['vector_store_id']
            
            if stored_hash != '':
                file_id = assistant_data["file_id"]
                client.files.delete(file_id)
            
            file = client.files.create(
                file=open(file_path, "rb"),
                purpose='assistants',
                embedding_model='embed-english-v3.0'
            )
            client.beta.vector_stores.files.create(
                vector_store_id=vector_store_id,
                file_id=file.id
            )
            vector_store = client.beta.vector_stores.retrieve(
                vector_store_id=vector_store_id
            )
            assistant_data['file_id'] =file.id
            with open(assistant_file_path, 'w') as file:
                json.dump(assistant_data, file)
            with open(hash_file, 'w') as f:
                f.write(current_hash)
            context.log("knowledge base has been updated")
            return vector_store
    else:
        context.log("file has not changed")
        



def supa_threads(messenger_id):
    data=supa_client.table('threads').select('thread_id').eq('messenger_id',messenger_id).execute()
    if not data.data == []:
        return data.data[0]['thread_id']
    else:
        return None
 


def capture_lead(context, messenger_id, **kwargs):
    supa_client.table('leads').insert({
        'name': kwargs.get('name'), 
        'email': kwargs.get('email'), 
        'phone': kwargs.get('phone'), 
        'messenger_id': messenger_id
    }).execute()
    context.log(f"Updated messenger_DB.csv with information for messenger_id: {messenger_id}")
    return {"status": "success", "message": "lead has been captured successfully"}

def email_supervisor(context, summary):
    sender_email = os.environ.get("SENDER_EMAIL")   # Replace with your ProtonMail address
    sender_password = os.environ.get("SENDER_PASSWORD")  # Replace with your ProtonMail password
    receiver_email = os.environ.get("RECEIVER_EMAIL")
    
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = "Customer Inquiry Summary"

    body = f"Here's a summary of the customer inquiry:\n\n{summary}"
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp-mail.outlook.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        context.log("Email sent successfully")
        return {"status": "success", "message": "Email sent successfully"}
    except Exception as e:
        context.log(f"Failed to send email: {str(e)}")
        return {"status": "error", "message": f"Failed to send email: {str(e)}"}


def main(context):
    context.log(context.req)
    print(context.req)
    update_knowlege(client,context)
    assistant_id = create_assistant(client,context)
    data = json.loads(context.req.body_raw)
    messenger_id = data.get('messenger_id')
    user_input = data.get('message', '')

    if not messenger_id:
        context.log("Error: Missing messenger_id")
        return context.error("Missing messenger_id")
    elif not user_input:
        context.log("Error: Missing a message")
        return context.error("Missing a message"),
    else:
        context.log(f"Received message: {user_input} for thread ID: {messenger_id}")
    
    if supa_threads(messenger_id):
        thread_id = supa_threads(messenger_id)
        context.log("previous thread found and loaded")
    else:
        thread = client.beta.threads.create()
        thread_id =thread.id
        supa_client.table('threads').insert({'messenger_id':messenger_id,'thread_id': thread_id}).execute()
        context.log("id has been saved")
   
    message = client.beta.threads.messages.create(
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
                    output = email_supervisor(context,arguments["summary"])
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
                elif tool_call.function.name == "capture_lead":
                    context.log("trying to capture_lead")
                    arguments = json.loads(tool_call.function.arguments)
                    output = capture_lead(context,messenger_id=messenger_id,thread_id=thread_id, name=arguments["name"],phone=arguments["phone"],email=arguments["email"])
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
    return context.res.json({"assitant_response": response})


import openai
import json
import logging
import os
import requests
from flask import Flask, request, Response, jsonify 
from flask_restful import Resource, Api
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
api = Api(app)

Response.access_control_allow_origin = "*"

openai.api_key = os.environ['OPENAI_API_KEY']
openai.organization = os.environ['Organization']

response = ''
system_message = f"""
    You are a customer service assistant for managed services of a company. \
    Respond in a friendly and helpful tone, with concise answers in not more than 100 words. \
    For any user request for raising a service request do not make ANY assumptions about what values to use for the required parameters inside function_descriptions. \
    Ask for clarification if a users request is ambiguous and the required function_descriptions parameter values are not provided by the user. \
    Answer ONLY with the facts. \
    Include reputable source filenames and document names along with their URLs for reference. \
    For tabular information return it as an html table. Return in markdown format.
    """
messages = [{"role": "system", "content": system_message}]
function_descriptions = [
    {
        "name": "set_mailbox_quota",
        "description": """
        Raise a service request for setting the mailbox quota of a user on exchange online with the following parameters -
        email id, issue warning quota, prohibit email send quota, and prohibit email receive quota.
        """,
        "parameters": {
            "type": "object",
            "properties": {
                "emailid": {
                    "type": "string",
                    "description": "The email id of the user whose mailbox quota is to be changed",
                    },
                "issue_warning_quota": {
                    "type": "string",
                    "description": "The mailbox size limit at which a quota warning notification is sent to the user",
                    },
                "prohibit_send_quota": {
                    "type": "string",
                    "description": "The mailbox size limit beyond which the user cannot send emails",
                    },
                "prohibit_receive_quota": {
                    "type": "string",
                    "description": "The mailbox size limit beyond which the user cannot receive emails",
                    }
            },
            "required": ["emailid", "issue_warning_quota", "prohibit_send_quota", "prohibit_receive_quota"],
        }
    },
    {
        "name": "get_shared_mailbox",
        "description": """
        Raise a shared mailbox service request with the following parameters -
        Shared Mailbox name, mailbox alias, email id, permissions for full access, send as, and Calendar Access.
        """,
        "parameters": {
            "type": "object",
            "properties": {
                "shared_mailbox_name": {
                    "type": "string",
                    "description": "The name of the shared mailbox", #e.g., Employee Onboarding, Payroll Processing, Trainings",
                    },
                "alias": {
                    "type": "string",
                    "description": "The required alias for the shared mailbox", #e.g., Onboardings, Payroll, trainings",
                    },
                "email_id": {
                    "type": "string",
                    "description": "The required email id for the shared mailbox",
                    },
                "owner": {
                    "type": "string",
                    "description": "Email id of the intended owner for the shared mailbox",
                    },
                "full_access": {
                    "type": "string",
                    "description": "Is full access required for the shared mailbox", # "e.g., yes, no",
                    "enum": ["yes", "no"]
                    },
                "send_as": {
                    "type": "string",
                    "description": "Is send as required for the shared mailbox", #e.g., yes, no",
                    "enum": ["yes", "no"]
                    },
                "calendar_access": {
                    "type": "string",
                    "description": "Is calendar access required for the shared mailbox", # e.g., yes, no",
                    "enum": ["yes", "no"]
                    }
            },
            "required": ["shared_mailbox_name", "alias", "email_id", "owner", "full_access", "send_as", "calendar_access"],
        }
    }
]


def get_shared_mailbox(shared_mailbox_name, alias, email_id, owner, full_access, send_as, calendar_access):
    """Create a shared mailbox with the users input"""
    shared_mailbox = {
      "shared_mailbox_name": shared_mailbox_name,
      "alias": alias,
      "email_id": email_id,
      "owner": owner,
      "full_access": full_access,
      "send_as": send_as,
      "calendar_access": calendar_access
      }
    response = requests.post(
        "https://d64986a4-a285-4f1a-b77c-8b7f87bed388.webhook.eus.azure-automation.net/webhooks?token=7i3NRlFtavoPKWPvh7%2fPhw1bbtWpPGSvIt3WPW1HZH8%3d",
        data = json.dumps(shared_mailbox)
        )
    return response

def set_mailbox_quota(emailid, issue_warning_quota, prohibit_send_quota, prohibit_receive_quota):
    """Set mailbox quota for the user"""
    mailbox_quota = {
      "emailid": emailid,
      "issue_warning_quota": issue_warning_quota,
      "prohibit_send_quota": prohibit_send_quota                                                                    ,
      "prohibit_receive_quota": prohibit_receive_quota,
      }
    response = requests.post(
        "https://6779d4d5-f434-47f3-a2e7-dc378700a4a9.webhook.cid.azure-automation.net/webhooks?token=NzsHCC%2f%2fV%2bI358Ly%2b%2foTeMHI%2f6H8HzBJi5e4UbvVIkM%3d",
        data = json.dumps(mailbox_quota)
        )
    return response

def get_results():
    # Step 2: Answer the user question
    response = openai.ChatCompletion.create(
        model = "gpt-3.5-turbo-0613",
        messages = messages,
        functions = function_descriptions,
        function_call = "auto", #{"name": funcname}
    )
    responsemessage = response.choices[0].message
    logging.info(responsemessage)
    if "content" in responsemessage and "function_call" not in responsemessage:
      logging.info("Content is available as a first step")
      messages.append(
        {
            "role": responsemessage["role"],
            "content": responsemessage["content"],
        }
      )
      return responsemessage
    else:
      logging.info("arguments is available as a final step")
      return finalprocess(responsemessage)
    
def finalprocess(response):
  if response.get("function_call"):
    function_name = str(response["function_call"]["name"]) #eval(firstoutput.function_call.name)

    available_functions = {
          "get_shared_mailbox": get_shared_mailbox,
          "set_mailbox_quota": set_mailbox_quota
      }

    function_to_call = available_functions[function_name]
    function_args = json.loads(response["function_call"]["arguments"])
    function_response = function_to_call(**function_args)
    messages.append( # extend conversation with assistant's reply
        {
          "role": response["role"],
          "name": response["function_call"]["name"],
          "content": response["function_call"]["arguments"],
        }
    )
    messages.append(
      {
          "role": "function",
          "name": function_name,
          "content": json.dumps(str(function_response)),
      }
    )  # extend conversation with function response

    second_response = openai.ChatCompletion.create(
            model = "gpt-3.5-turbo-0613",
            messages = messages,
        )
    return second_response["choices"][0]["message"]

@app.route("/getresponse", methods=["POST", "GET"])
def getresponse():
    query = request.args.get('query')
    logging.info("query from the user received - "+ query)
    messages.append(
        {"role": "user", "content": query}
    )
    response = get_results()
    return response
    
if __name__ == "__main__":
    app.run()
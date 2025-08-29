import traceback
import openai
import json
import os
import uuid
import azure.cognitiveservices.speech as speechsdk

from flask import Response
from io import BytesIO
from bs4 import BeautifulSoup
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.global_config import env_mode

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.language.conversations import ConversationAnalysisClient
from app.utils.conf_path import str_configpath
from app.utils.generalMethods import dct_error
from app.utils.prompt_templates import text_to_psql,table_data_to_summary,dashboard_analysis_prompt

ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)

str_azure_endpoint = ins_cfg.get(env_mode, 'AZURE_OPENAI_ENDPOINT')
str_azure_api_key = ins_cfg.get(env_mode, 'AZURE_OPENAI_API_KEY')
speech_key, service_region = "6cp3JBY7lCeBb5M5bnXUzKn7OKBVDRdKgT6mzyzziIipS6uWnhU2JQQJ99BAACYeBjFXJ3w3AAAYACOGVq8j", "eastus"

# Initialize the Azure Conversation Analysis client
client = ConversationAnalysisClient(
    endpoint=str_azure_endpoint,
    credential=AzureKeyCredential(str_azure_api_key)
)



azure_chat_client = openai.AzureOpenAI(
    azure_endpoint=str_azure_endpoint,
    api_key=str_azure_api_key,
    api_version="2024-05-01-preview",
)

class aiService:
    @staticmethod
    def get_message_summary(request):
        try:
            
            dct_request = request.json
            strAction = dct_request["strAction"]
            if strAction.upper() =='SUMMARY':
                dct_summaries = {"strTitle":"","strNarrative":"","strResolution":"","strSentiment":""}
                arrMessages = dct_request["arrMessages"]
                if not arrMessages:
                    dct_error("No enough Conversation to generate"),400
                # Initialize a dictionary to store the strSender and strReceiver
                dct_sender_receiver = {}

                # Counter for customer and agent suffixes
                int_customer_count = 1
                int_agent_count = 1

                # Format messages for Azure API
                lst_conversation_items = []
                for i, message in enumerate(arrMessages):
                    strSender = message["strSender"]
                    blnIncoming=message["blnIncoming"]
                    strReceiver = message["strReceiver"]
                    strMessage = BeautifulSoup(message["strMessage"],features="html5lib").get_text()
                    # Assign roles (adjust this as needed for your use case)
                    if blnIncoming :
                        str_role = "Customer"
                        sender_key = f"Customer_{int_customer_count}"
                        receiver_key = f"Agent_{int_agent_count}"

                        # Update the dictionary for incoming messages
                        dct_sender_receiver[strSender] = sender_key
                        dct_sender_receiver[strReceiver] = receiver_key

                        # Increment counts
                        int_customer_count += 1
                        int_agent_count += 1
                    else:
                        str_role = "Agent"
                        sender_key = f"Agent_{int_agent_count}"
                        receiver_key = f"Customer_{int_customer_count}"

                        # Update the dictionary for outgoing messages
                        dct_sender_receiver[strSender] = sender_key
                        dct_sender_receiver[strReceiver] = receiver_key

                        # Increment counts
                        int_customer_count += 1
                        int_agent_count += 1

                    lst_conversation_items.append({
                        "text": strMessage,
                        "id": str(i + 1),
                        "role": str_role,
                        "participantId": strSender
                    })

                task = {
                    "displayName": "Analyze conversation from request payload",
                    "analysisInput": {
                        "conversations": [
                            {
                                "conversationItems": lst_conversation_items,
                                "modality": "text",
                                "id": "conversation1",
                                "language": "en"
                            }
                        ]
                    },
                    "tasks": [
                        {
                            "taskName": "Summary task",
                            "kind": "ConversationalSummarizationTask",
                                "parameters": {
                                "summaryAspects": [
                                "chapterTitle",
                                "resolution",
                                "issue"

                                ]
                            }
                        }
                    ]
                }

                try:
                    # Submit the conversation analysis request
                    response = client.begin_conversation_analysis(task=task)
                    rst_response = response.result()
                except HttpResponseError as e:
                    if "Request Payload sent is too large" in str(e):
                        return dct_error("Can't summarize , conversation too long."), 400
                    

                # Process and return the results
                lst_task_results = rst_response["tasks"]["items"]

                for dct_task in lst_task_results:
                    dct_task_result = dct_task["results"]
                    if dct_task_result["errors"]:
                        continue
                    else:
                        conversation_result = dct_task_result["conversations"][0]
                        if conversation_result["warnings"]:
                            continue
                        else:
                            lst_task_summaries = conversation_result["summaries"]
                            
                            for dct_summary in lst_task_summaries:
                                if dct_summary['aspect']=='resolution':
                                    dct_summaries["strResolution"] = dct_summary['text']
                                if dct_summary['aspect']=='issue':
                                    dct_summaries["strNarrative"] = dct_summary['text']
                                if dct_summary['aspect']=='chapterTitle':
                                    dct_summaries["strTitle"] = dct_summary['text']

                            break
                        
                # sentimental analysis from conversation
                str_conversation = ''
                for i, message in enumerate(arrMessages):
                    blnIncoming=message["blnIncoming"]
                    strMessage = BeautifulSoup(message["strMessage"],features="html5lib").get_text()
                    if blnIncoming:
                        str_conversation = str_conversation + f'Customer : [{strMessage}] \n'
                    else:
                        str_conversation = str_conversation + f'Agent : [{strMessage}] \n'
                # query template
                lst_messages = [{
                "role": "user",
                "content": f"""
                Analyze the sentiment of the following email conversation and respond with either "positive", "negative", or "neutral". Only provide one of these three words as your response.

                Email Conversation:
                {str_conversation}
                """
                }]
                
                str_sentiment = 'Inconclusive' # default
                try:
                    completion = azure_chat_client.chat.completions.create(model="gpt-4o",messages=lst_messages)
                    str_sentiment =  completion.choices[0].message.content
                except Exception:
                    pass
                finally:
                    dct_summaries['strSentiment'] = str_sentiment
                    
                return dct_summaries
            
            elif strAction.upper() =='AUDIT-1':
                arrMessages = dct_request["arrMessages"]
                # audit the full  conversation
                str_conversation = ''
                for i, message in enumerate(arrMessages):
                    blnIncoming=message["blnIncoming"]
                    strMessage = BeautifulSoup(message["strMessage"],features="html5lib").get_text()
                    if blnIncoming:
                        str_conversation = str_conversation + f'Customer : [{strMessage}]  timestamp :{message.get("strTimeAndDate")} \n'
                    else:
                        str_conversation = str_conversation + f'Support : [{strMessage}] timestamp :{message.get("strTimeAndDate")} \n'
                

                str_template = """You are an expert email conversation auditor. Below is an email conversation. Please carefully review the conversation and provide a detailed audit based on the following key criteria. The response should be in the JSON format provided. Response should be in simple English.Response should not be in markdown format.

                Email Conversation:
                <str_email_conversation>

                Audit Criteria:

                1. Tone and Language: Evaluate if the tone is professional, respectful, and appropriate for the context. Is the language clear and courteous?

                2. Accuracy of Information: Analyze the correctness of the information provided. Are the details factually accurate and well-supported?

                3. Escalation Protocol: Check if the issue was escalated appropriately when necessary. Was the right protocol followed for addressing the concern at the correct level?

                4. Timeliness: Assess the response time(Initial,Average). Was the email sent promptly, addressing the issue within an acceptable timeframe?

                5. Customer Concerns Addressed: Examine if the customer’s concerns were fully understood and addressed. Are there any overlooked issues that should have been acknowledged?

                6. Empathy and Apology: Determine if empathy was conveyed, especially in situations involving complaints or dissatisfaction. If an error occurred, was there an appropriate apology?

                7. Consistency: Review whether the information and messaging remained consistent throughout the conversation.

                8. Clarity of the Resolution: Evaluate the clarity of the proposed solution. Was the resolution communicated in a way that is easy to understand?

                Score: Based on given criterias give a score in 40, 5 score for each criteria.
                
                Response Format:

                {
                    "Tone and Language": "",
                    "Accuracy of Information": "",
                    "Escalation Protocol": "",
                    "Timeliness": "",
                    "Customer Concerns Addressed": "",
                    "Empathy and Apology": "",
                    "Consistency": "",
                    "Clarity of the Resolution": "",
                    "Score":""
                }"""
                # query template
                lst_messages = [{
                "role": "user",
                "content": str_template.replace('<str_email_conversation>',str_conversation)
                }]
                
                dct_response = {}
                try:
                    completion = azure_chat_client.chat.completions.create(model="gpt-4o",messages=lst_messages)
                    print(completion.choices[0].message.content)
                    dct_response =  json.loads(completion.choices[0].message.content)
                except Exception:
                    pass
                finally:
                    if not dct_response:
                        dct_response = {"Error":"Unable to reach AI server- Kindly re-audit"}
                    return dct_response

            elif strAction.upper() == 'AUDIT-2':
                arrMessages = dct_request["arrMessages"]
                # audit the full  conversation
                str_conversation = ''
                for i, message in enumerate(arrMessages):
                    blnIncoming=message["blnIncoming"]
                    strMessage = BeautifulSoup(message["strMessage"],features="html5lib").get_text()
                    if blnIncoming:
                        str_conversation = str_conversation + f'Customer : [{strMessage}]  timestamp :{message.get("strTimeAndDate")} \n'
                    else:
                        str_conversation = str_conversation + f'Support : [{strMessage}] timestamp :{message.get("strTimeAndDate")} \n'
                

                str_template = """You are an expert email conversation auditor. Below is an email conversation. Please carefully review the conversation and provide a detailed audit based on the following key criteria. The response should be in the JSON format provided. Response should be in simple English.Response should not be in markdown format.

                Email Conversation:
                <str_email_conversation>

                Audit Criteria:

                    1. Introduction to Customer Communication
                    - Importance of timely and effective communication.
                    - Overview of customer expectations.

                    2. Acknowledgment Email
                    - Was an acknowledgment email sent confirming receipt of the request?
                    - Did the acknowledgment include a clear subject line and content thanking the customer?
                    - Was an estimated timeline for resolution provided?

                    3. Initial Case Assignment and Analysis
                    - Was the case assigned to a team member promptly?
                    - Did the initial analysis start within 15 minutes of assignment?
                    - Was there an attempt to resolve the issue within 45 minutes?

                    4. Communication During Delays
                    - Was the customer informed promptly about any delays?
                    - Did the communication acknowledge the delay and provide a revised timeline?
                    - Was assistance from a supervisor sought during delays?

                    5. Bug Identification Process
                    - Was the bug identified and communicated to the customer on the same day?
                    - Was a delivery date provided for bug resolution?
                    - Was the development lead contacted for an acceptable delivery date?

                    6. Change Request (CR) Communication
                    - Was the customer informed that the request is being processed?
                    - Was a follow-up timeline provided (within 7 working days)?
                    - Did the CR communication use the correct subject line and outline the next steps?

                    7. Bug’s Delivery
                    - Was the team following up daily on bug deliveries?
                    - Was the customer informed once the bug was resolved, with solution notes provided?
                    - Did the team receive acknowledgment from the customer?

                    8. Follow-Up on Customer Responses
                    - Did the team follow up after 2 days if no customer response was received?
                    - Were reminders sent, and was the case closed appropriately if there was no response after 3 reminders?
                    - Were appropriate communication channels (call, email) used for follow-up?

                    9. Closing Cases
                    - Were all cases closed with proper documentation?
                    - Was the final email clear, summarizing the issue, resolution steps, and case closure?
                    - Were the FAQ and case logs updated?

                    10. Best Practices for Email Communication
                    - Was the language clear and concise?
                    - Was the tone professional and personalized (e.g., using the customer’s name)?
                    - Was consistency in messaging maintained throughout the conversation?

                    11. Unresolved Support Issues
                    - Were unresolved cases escalated to the HOD or supervisor?
                    - Did the team receive approval to keep unresolved cases pending?

                    12. Information to be Passed/CSG Knowledge Gap
                    - Was any communication from the development side handled properly?
                    - Were unresolved issues escalated for approval if they remained with the representative?

                    13. Conclusion
                    -Confirm that the importance of following these steps was reinforced to the team.
                    -Evaluate if there were any efforts to encourage continuous improvement and feedback on communication practices.
                
                    Score: Based on given criterias give a score in 65, 5 score for each criteria.
                Response Format:

                {
                    "Introduction to Customer Communication": "",
                    "Acknowledgment Email": "",
                    "Initial Case Assignment and Analysis": "",
                    "Communication During Delays": "",
                    "Bug Identification Process": "",
                    "Change Request (CR) Communication": "",
                    "Bug’s Delivery": "",
                    "Follow-Up on Customer Responses": "",
                    "Closing Cases":"",
                    "Best Practices for Email Communication":"",
                    "Unresolved Support Issues":"",
                    "Information to be Passed/CSG Knowledge Gap":"",
                    "Conclusion":""
                }
                """
                # query template
                lst_messages = [{
                "role": "user",
                "content": str_template.replace('<str_email_conversation>',str_conversation)
                }]
                
                dct_response = {}
                try:
                    completion = azure_chat_client.chat.completions.create(model="gpt-4o",messages=lst_messages)
                    dct_response =  json.loads(completion.choices[0].message.content)
                except Exception:
                    pass
                finally:
                    if not dct_response:
                        dct_response = {"Error":"Unable to reach AI server- Kindly re-audit"}
                    return dct_response

            else:
                str_summary=dct_request["strSummary"]
                lst_messages = [{
                "role": "user",
                "content": """You are an AI assistant that generates FAQs from a given summary.
                               Avoid answering questions related to specific people.
                               Focus only on the issue, cause, and resolution.
                               Structure the response in JSON format as [{"strQuestion": "strAnswer"}].
                               Don't answer in markdown format.

                               Summary:
                               <summary>
   
                               Generate the FAQ based on the summary provided, excluding any questions about individuals.
                               Examples:
   
                               Example 1:
                               If the summary says:
                               "The system crashed due to insufficient memory allocation."
   
                               The output should be:
                               [{ "strQuestion": "Why did the system crash?", "strAnswer": "The system crashed due to insufficient memory allocation." }]
   
                               Example 2:
                               If the summary says:
                               "The application faced a slow response time because of database locking issues."
   
                               The output should be:
                               [{ "strQuestion": "Why was the application responding slowly?", "strAnswer": "The application was responding slowly due to database locking issues." }]""".replace('<summary>',str_summary)
                }]
                completion = azure_chat_client.chat.completions.create(model="gpt-4o",messages=lst_messages)
                dct_response = {}
                try:
                    dct_response =  json.loads(completion.choices[0].message.content)
                except Exception:
                    pass
                finally:
                    if not dct_response:
                        dct_response = {"Error":"please re-generate!"}
                    return dct_response
                

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to generate"), 400
        
    @staticmethod
    def speech_synthesize(request):
        try:
            """text to speech"""
            message = request.json.get('message')
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)


            # Set the voice name, refer to https://aka.ms/speech/voices/neural for full list.
            speech_config.speech_synthesis_voice_name = "en-US-AmandaMultilingualNeural"
            
            # setup file config
            # Temporarily store it in the 'tmp_azure_speech' folder, then delete it afterward.
            str_temp_azure_speech_path = "tmp_azure_speech"
            os.makedirs(str_temp_azure_speech_path, exist_ok=True)
            file_path = os.path.join(str_temp_azure_speech_path, f"{str(uuid.uuid4())}.wav")
            file_config = speechsdk.audio.AudioOutputConfig(filename=file_path)

            # Creates a speech synthesizer using the default speaker as audio output.
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=file_config)

            audio = synthesizer.speak_text_async(message).get()
            audio_bytes = audio.audio_data
                    
            def generate_audio_chunks():
                chunk_size = 8192  # Optimized for faster streaming
                buffer = BytesIO(audio_bytes)
                while True:
                    chunk = buffer.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

            # Return the audio as a response using the generator to stream the data
            return Response(
                generate_audio_chunks(),
                content_type='audio/mp3',
                headers={
                    "Content-Disposition": "inline; filename=synthesized_audio.mp3",
                    "Cache-Control": "no-cache"
                }
            )
        except Exception:
            traceback.print_exc()
        finally:
            if os.path.isfile(file_path):os.remove(file_path)

    @staticmethod
    def speech_recognition(request):
        try:
            """speech to text"""
            
            # Extract audio file from the request
            file_path = ""
            file = request.files.get('audio')
            if not file:
                return dct_error("No audio"),400
            
            # setup file config
            # Temporarily store it in the 'tmp_azure_speech' folder, then delete it afterward.
            str_temp_azure_speech_path = "tmp_azure_speech" 
            os.makedirs(str_temp_azure_speech_path, exist_ok=True)
            file_path = os.path.join(str_temp_azure_speech_path, f"{str(uuid.uuid4())}.wav")
            file.save(file_path)
            
            # setup speech config
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
            speech_config.speech_recognition_language = "en-IN"
            audio_config = speechsdk.audio.AudioConfig(filename=file_path)

            languages = ["en-IN", "en-US", "en-KE"]
            auto_detect_source_language_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=languages)
            
            # Create a speech recognizer
            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config,auto_detect_source_language_config=auto_detect_source_language_config)

            result = recognizer.recognize_once_async().get()
            # Use recognize_once for synchronous recognition
            return result.text

        except Exception:
            traceback.print_exc()
        
        finally:
            if os.path.isfile(file_path):os.remove(file_path)

    @staticmethod
    def text_to_psql(request,user_id):
        try:
            user_id = 1828
            """text to psql"""
            dct_request = request.json
            str_query = dct_request.get('query')
            str_psql = dct_request.get('str_psql')
            str_error = dct_request.get('str_error')
            if str_psql and str_error:
                str_query = f"""Analyze the given PSQL query and Error Message then Generate corrected PSQL query.  
                
                            ## Given PostgreSQL Query: 
                            ```sql {str_psql}```  

                            ## Error Message:  
                            ```{str_error}``` 
                            
                            ### Output:

                            - PSQL string only

                            - PSQL query based on the provided request.

                            [Generated SQL query]
                            """
            
            system_prompt = text_to_psql.replace('$user_id',str(dct_request.get('user_id'))).replace('$user_sso_id',str(user_id))
            messages = [{"role": "system","content": system_prompt},
                        {"role": "user","content": str_query}]
            completion = azure_chat_client.chat.completions.create(model="gpt-4o",messages=messages,temperature=0.3)
            result = completion.choices[0].message.content
            

            if '```json' in result:
                result = json.loads(result.strip("```json\n").strip("```").strip().replace("\n", " "))
            
            else:
                result = result.strip("```sql\n").strip("```").strip().replace("\n", " ")
            return {"result":result}
        
        except Exception:
            traceback.print_exc()

    @staticmethod
    def table_data_to_summary(request):
        try:
            """table_data_to_summary"""
            dct_request = request.json
  
            prompt = table_data_to_summary.replace('$user_question',dct_request.get('str_message')) \
                                          .replace('$previous_summary',dct_request.get('previous_summary') or '') \
                                          .replace('$current_chunk',str(dct_request.get('current_chunk')))  
            messages = [{"role": "user","content": prompt}]
            completion = azure_chat_client.chat.completions.create(model="gpt-4o",messages=messages,temperature=0.3)
            result = completion.choices[0].message.content
            return result
        
        except Exception:
            traceback.print_exc()
            return "An error Occured , please try again later."
        

    @staticmethod
    def dashboard_summary(request):
        try:
            """dashboard_summary"""
            dct_request = request.json
  
            prompt = dashboard_analysis_prompt.replace('$_dashboard_data',dct_request.get('str_dashboard_context'))
            
            messages = [{"role": "user","content": prompt}]
            completion = azure_chat_client.chat.completions.create(model="gpt-4o",messages=messages,temperature=0.3)
            result = completion.choices[0].message.content
            return result
        
        except Exception:
            traceback.print_exc()
            return "An error Occured , please try again later."

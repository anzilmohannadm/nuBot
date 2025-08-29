import pydub  
import requests
import traceback
import io
import uuid
import pytz
import logging
import asyncio
import soundfile as sf
import speech_recognition as sr
from datetime import datetime,timedelta
from app.utils.generalMethods import create_cursor
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.global_config import env_mode
from app.utils.conf_path import str_configpath
from app.service.chat_service import chatServices
from app.agents import agent_handler
from app.agents.utils.general_methods import set_agent_config


# Configure logging to print only to console
logging.basicConfig(level=logging.INFO)

ins_configuration = ConfigParserCrypt()
ins_configuration.read(str_configpath)

str_azure_endpoint = ins_configuration.get(env_mode, 'AZURE_OPENAI_ENDPOINT')
str_azure_api_key = ins_configuration.get(env_mode, 'AZURE_OPENAI_API_KEY')
str_model_deployment = ins_configuration.get(env_mode, 'AZURE_OPENAI_DEPLOYMENT_ID')


class whatsappServices():

    @staticmethod
    def get_media_url(str_access_token,media_id):
        headers = {
            "Authorization": f"Bearer {str_access_token}",
        }
        url = f"https://graph.facebook.com/v16.0/{media_id}/"
        response = requests.get(url, headers=headers)
        return response.json()["url"]

    @staticmethod
    def download_media_file(str_access_token,media_url):
        headers = {
            "Authorization": f"Bearer {str_access_token}",
        }
        response= requests.get(media_url,headers=headers)
        return response.content

    @staticmethod
    def recognize_audio(audio_bytes):
        recognizer = sr.Recognizer()
        audio_text = recognizer.recognize_google(audio_bytes, language="en-US")
        return audio_text

    @staticmethod
    def convert_audio_bytes(audio_bytes):
        ogg_audio = pydub.AudioSegment.from_ogg(io.BytesIO(audio_bytes))
        ogg_audio = ogg_audio.set_sample_width(4)

        wav_bytes = ogg_audio.export(format="wav").read()
        audio_data, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="int32")
        sample_width = audio_data.dtype.itemsize
        audio = sr.AudioData(audio_data, sample_rate, sample_width)
        return audio

    @staticmethod    
    def mark_read_and_typing(body,str_access_token):
        try:
            value = body["entry"][0]["changes"][0]["value"]
            phone_number_id = value["metadata"]["phone_number_id"]
            message_id = value["messages"][0]["id"]

            url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
            headers = {
                "Content-type": "application/json",
                "Authorization": f"Bearer {str_access_token}",
            }
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
                "typing_indicator": {"type": "text"}
            }
            requests.post(url, json=payload, headers=headers)
        except Exception as e:
            traceback.print_exc()

    @staticmethod
    def send_message(body,reply_message,str_access_token):
        try:
            value = body["entry"][0]["changes"][0]["value"]
            phone_number_id = value["metadata"]["phone_number_id"]
            from_number = value["messages"][0]["from"]
            message_id = body["entry"][0]["changes"][0]["value"]["messages"][0]["id"]

            url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
            headers = {
                "Content-type": "application/json",
                "Authorization": f"Bearer {str_access_token}",
            }
            data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": from_number,
                "type": "text",
                "context": {"message_id": message_id},
                "text": {"body": reply_message},
            }
            return requests.post(url, json=data, headers=headers)
        except Exception as e:
            traceback.print_exc()

    @staticmethod
    def process_whatsapp_incoming_message(ins_db,body,int_bot_id,str_tenancy_id,str_access_token,str_bot_uuid,int_bot_created_user_id,str_bot_type,bln_agent,dct_agent):
        try:
            # message body contains the msg user sends
            message_body = body["entry"][0]["changes"][0]["value"]["messages"][0]

            # The variable 'message' will be sent to the model for processing.
            # Checking if the received message is a text message.
            if message_body["type"] == "text":
                message= message_body["text"]["body"]

            # Checking if the received message is an audio message,converting the audio into a text
            elif message_body["type"] == "audio":
                audio_id = message_body["audio"]["id"]
                audio_url=whatsappServices.get_media_url(str_access_token,audio_id)
                audio_bytes=whatsappServices.download_media_file(str_access_token,audio_url)
                audio_data=whatsappServices.convert_audio_bytes(audio_bytes)
                message=whatsappServices.recognize_audio(audio_data)

            else:
                message="invalid input"

            with create_cursor(ins_db) as cr:
                # This represents the user who sent the message.
                from_number = body["entry"][0]["changes"][0]["value"]["messages"][0]["from"]

                # This ID represents the phone number that received the incoming message(the display number means the onboarded number )
                display_phone_number_id = body["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]

                # 'conversation_expires_at' is a timestamp that indicates when the conversation is considered expired.
                # Each user has a unique 'conversation_expires_at' value for messages sent to the onboarded number.Valid for 24hrs
                # fetching the vchr_socket_id ,by using WHERE condition on vchr_display_phone_number_id and vchr_recipient_phone_number(user number) then we can ensure that the user has sent msg to the display_phone_number(onboarded number)
                # Then Checks that 'conversation_expires_at' has not expired(i.e., the conversation is still active (conversation live only for 24hrs))

                cr.execute("""SELECT 
                                vchr_socket_id,
                                vchr_agent_thread 
                            FROM 
                                tbl_chat_history 
                            WHERE
                                vchr_display_phone_number_id = %s 
                            AND 
                                vchr_recipient_phone_number =%s
                            AND 
                                conversation_expires_at > NOW()
                            ORDER BY 
                                tim_created DESC
                            LIMIT 1""",(display_phone_number_id,from_number),)

                rst_socket_id = cr.fetchone() or {}
                str_session_id = rst_socket_id.get('vchr_socket_id')
                str_agent_thread = rst_socket_id.get('vchr_agent_thread') or str(uuid.uuid4()) if bln_agent else None

                if not bln_agent:
                    # Fetch embedding and memory context,The memory context is session-specific, meaning it applies only to the current session.
                    # When new session started after an 24hrs, it doesnt know past memory
                    embedding_context, memory_context, _, _= asyncio.run(chatServices.fetch_embedding_and_memory_context_live_chat_context(str_tenancy_id=str_tenancy_id,
                                                                                                                            str_bot_id=str_bot_uuid,
                                                                                                                            message=message,
                                                                                                                            user_id_for_memory=int_bot_created_user_id,
                                                                                                                            bln_live_chat=None,
                                                                                                                            str_session_id=None,
                                                                                                                            lancedb_uuid_order=None,
                                                                                                                            memory_session=str_session_id))
                    # if not any bot is select for an onboarded number , will sent an default msg
                    if int_bot_id:
                        prompt = asyncio.run(chatServices.generate_prompt(
                                                            message=message,
                                                            instruction = 'Please format your response using WhatsApp markdown(Covert GPT markdown to Whatsapp markdown)',
                                                            bot_type = str_bot_type,
                                                            embedding_context = embedding_context,
                                                            memory_context = memory_context,
                                                            live_chat_context = None,
                                                            user_id = None,
                                                            int_bot_id=None,
                                                            ins_db=None)
                                                        )
                        completion= asyncio.run(chatServices.generate_ai_response([{'role': 'user', 'content': prompt}]))
                        int_input_token_usage=completion.usage.prompt_tokens
                        int_output_token_usage=completion.usage.completion_tokens
                        reply_message = completion.choices[0].message.content
                    else:
                        # This is the default response if no bot selected
                        reply_message = (
                            "Kindly choose a bot to continue. We’ll provide a personalized response as soon as you’ve made your selection!\n\n"
                            "📌 Follow these steps to access your WhatsApp bot in NuBot:\n\n"
                            "1️⃣ **Open the NuBot App** – Launch the NuBot application on your device.\n"
                            "2️⃣ **Go to the Integration Module** – Click on 'Integrations' from the left-side menu.\n"
                            "3️⃣ **Select WhatsApp** – Choose WhatsApp as your integration channel.\n"
                            "4️⃣ **Pick Your Bot** – Select the bot linked to your onboarded WhatsApp number.\n\n"
                            "🔹 **Navigation:** `NuBot App → Integrations → WhatsApp → Select Bot (Onboarded WhatsApp Number)`"
                        )
                else:
                    int_input_token_usage=0
                    int_output_token_usage=0
                    dct_config = set_agent_config(dct_agent,str_agent_thread,str_bot_type,body,str_access_token)
                    agent = agent_handler.get(str_bot_type)
                    reply_message = asyncio.run(agent.run_agent(message,dct_config,body,str_access_token)) if agent else "Invalid Message"

                # send message
                api_response = whatsappServices.send_message(body,reply_message,str_access_token)
                # inserting into the tbl_bot_log ,if the status code is 200 and a bot ID is available for the onboarded number.
                # we are not adding the fk_bint_conv_id ,reason is conv_id we get only from the  status webhook
                if api_response.status_code == 200 and int_bot_id is not None:

                    # message_id will get only in response of 'send_message'
                    message_id = api_response.json()["messages"][0]["id"]

                    cr.execute("""
                                INSERT INTO tbl_bot_log (tim_timestamp, vchr_sender, vchr_user_message, vchr_bot_response,
                                                        fk_bint_bot_id, bint_input_token_usage, bint_output_token_usage,vchr_whatsapp_msg_id,vchr_thread_id)
                                                        VALUES (NOW(), %s, %s, %s, %s, %s, %s,%s,%s)
                            """,(from_number,message,reply_message,int_bot_id,int_input_token_usage,int_output_token_usage,message_id,str_agent_thread))
                    ins_db.commit()

                elif api_response.status_code != 200:
                    logging.info(api_response.text)
                elif int_bot_id is None:
                    logging.info("No bot assigned")

        except Exception as e:
            traceback.print_exc()
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def manage_whatsapp_status_update(body,ins_db,int_bot_id,str_tenancy_id,str_bot_uuid,int_bot_created_user_id,bln_agent):
        try:
            str_conversational_id = str(uuid.uuid4())
            message_id = body["entry"][0]["changes"][0]["value"]["statuses"][0]["id"]
            status = body["entry"][0]["changes"][0]["value"]["statuses"][0]["status"]
            recipient_id = body["entry"][0]["changes"][0]["value"]["statuses"][0]["recipient_id"]
            display_phone_number_id = body["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
            with create_cursor(ins_db) as cr:

                if status == 'sent':
                    # Checking if the conversation already exists in the chat history  
                    cr.execute("""
                            SELECT 
                                vchr_socket_id
                            FROM 
                                tbl_chat_history 
                            WHERE
                                vchr_display_phone_number_id = %s 
                            AND 
                                vchr_recipient_phone_number =%s
                            AND 
                                conversation_expires_at > NOW()
                            ORDER BY 
                                tim_created DESC
                            LIMIT 1""",(display_phone_number_id,recipient_id),)
                    
                    rst_socket_id = cr.fetchone()

                    if not rst_socket_id: # If conversation does not exist, create a new one 

                        # Set conversation expiration to 24 hours from now
                        kolkata_tz = pytz.timezone('Asia/Kolkata')
                        current_time = datetime.now(kolkata_tz)
                        conversation_expires_at = current_time + timedelta(hours=24)

                        # Fetching the user ID who created the bot
                        cr.execute("SELECT fk_bint_created_user_id FROM tbl_bots WHERE pk_bint_bot_id =%s LIMIT 1",(int_bot_id,))
                        rst_bot_created_user_id=cr.fetchone()[0]  

                        cr.execute("SELECT vchr_thread_id FROM tbl_bot_log WHERE vchr_whatsapp_msg_id = %s",(message_id,))
                        rst_thread = cr.fetchone()
                        str_thread_id = ""
                        if rst_thread:
                            str_thread_id = rst_thread['vchr_thread_id']
                        # Inserting new conversation entry into the database
                        # conversation_expires_at is only applicable for whatsapp chat
                        cr.execute("""
                            INSERT INTO tbl_chat_history (
                                fk_bint_bot_id,
                                fk_bint_user_id, 
                                vchr_conversation_title,
                                vchr_socket_id,
                                vchr_display_phone_number_id,
                                vchr_recipient_phone_number,
                                conversation_expires_at,
                                tim_created,
                                bln_whatsapp,
                                vchr_agent_thread)
                            VALUES (%s, %s, %s, %s,%s,%s,%s, NOW(),TRUE,%s) RETURNING pk_bint_conversation_id
                            """, (int_bot_id,
                                    rst_bot_created_user_id,
                                    f"Message From '{recipient_id}'",
                                    str_conversational_id,
                                    display_phone_number_id,
                                    recipient_id,
                                    conversation_expires_at,
                                    str_thread_id))

                        # Fetching the new conversation ID
                        rst_pk_bint_conversation_id = cr.fetchone()[0]

                        cr.execute(
                            "UPDATE tbl_bot_log SET fk_bint_conversation_id = %s WHERE vchr_whatsapp_msg_id = %s",
                            (rst_pk_bint_conversation_id,message_id)
                        )

                    else: # If conversation exists, update the table tbl_bot_log
                        
                        cr.execute("""
                            SELECT 
                                pk_bint_conversation_id
                            FROM 
                                tbl_chat_history 
                            WHERE
                                vchr_display_phone_number_id = %s 
                            AND 
                                vchr_recipient_phone_number =%s
                            AND 
                                conversation_expires_at > NOW()
                            ORDER BY 
                                tim_created DESC
                            LIMIT 1""",(display_phone_number_id,recipient_id),)
                        
                        rst_pk_bint_conversation_id = cr.fetchone()[0]

                        # Fetching pk_bint_conversation_id from tbl_chat_history and update it on the tbl_bot_log
                        # Because we get only the conversational_id from the status webhook,
                        # We dont get the conversational_id in the message webhook, Thats why we updating the tbl_bot_log  on later (means in here 👇)
                        # Update the fk_bint_conversation_id in tbl_bot_log,Using the pk_bint_conversation_id from tbl_chat_history

                        cr.execute(
                            "UPDATE tbl_bot_log SET fk_bint_conversation_id = %s WHERE vchr_whatsapp_msg_id = %s",
                            (rst_pk_bint_conversation_id,message_id)
                        )

                    if not bln_agent:
                        # For Whtasapp Memory ,Fetching messages from tbl_bot_log using the message id from the status webhook
                        cr.execute("SELECT vchr_user_message,vchr_bot_response FROM tbl_bot_log WHERE vchr_whatsapp_msg_id = %s",(message_id,)) 
                        rst_chat=cr.fetchone()

                        if rst_chat :  # If messages exist, add them to memory
                            message=rst_chat['vchr_user_message']
                            response=rst_chat['vchr_bot_response']
                            chatServices.add_to_memory(str_tenancy_id=str_tenancy_id,
                                                    str_bot_id=str_bot_uuid,
                                                    user_id_for_memory=int_bot_created_user_id,
                                                    str_session_id=rst_socket_id['vchr_socket_id'],
                                                    message=message,
                                                    response=response)
        except Exception as e:
            traceback.print_exc()

        finally:
            if ins_db:
                ins_db.commit()
                ins_db.close()



import json
import random
import string
import traceback
import uuid
import lancedb
from datetime import timedelta
from app.schema import MemoryModel
from app.utils.generalMethods import dct_error,create_cursor,get_tenancy_id


class shareChatService:
    @staticmethod
    def share_chat(dct_request, dct_headers, ins_db, user_id):
        try:
            with create_cursor(ins_db) as cr:
                # Extract payload
                int_bot_id = dct_request.get("intBotId")
                int_shared_user_id = dct_request.get("intSharedUserId")
                int_conversation_id = dct_request.get("intConversationId")

                # Fetch the original chat history for the chat
                cr.execute("""
                    SELECT fk_bint_bot_id, vchr_socket_id,fk_bint_user_id, vchr_conversation_title, tim_created
                    FROM tbl_chat_history
                    WHERE pk_bint_conversation_id = %s
                """, (int_conversation_id,))
                original_chat = cr.fetchone()

                if not original_chat:
                    return dct_error("Original conversation not found"), 400

                cr.execute("""
                SELECT vchr_user_name
                FROM tbl_user
                WHERE pk_bint_user_id = %s
                """, (user_id,))
                sharing_user = cr.fetchone()

                if not sharing_user:
                    return dct_error("Sharing user not found"), 400

                shared_user_name = sharing_user['vchr_user_name']

                # Generate a random session ID with letters and digits
                session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

                #  a new entry in chat history for the shared chat
                cr.execute("""
                    INSERT INTO tbl_chat_history (fk_bint_bot_id, fk_bint_user_id, vchr_conversation_title,vchr_socket_id, tim_created,bln_shared, fk_bint_shared_user_id)
                    VALUES (%s, %s, %s, %s, NOW(), TRUE, %s) RETURNING pk_bint_conversation_id
                """, (original_chat['fk_bint_bot_id'], int_shared_user_id, original_chat['vchr_conversation_title'],session_id,original_chat['fk_bint_user_id']))
                new_conversation_id = cr.fetchone()[0]


                # Fetch the original bot logs for the chat
                cr.execute("""
                    SELECT tim_timestamp, vchr_user_message, vchr_bot_response,
                        fk_bint_bot_id, bint_input_token_usage, bint_output_token_usage, arr_reference_id
                    FROM tbl_bot_log
                    WHERE fk_bint_conversation_id = %s
                """, (int_conversation_id,))
                original_logs = cr.fetchall()

                # new entry in the bot logs for the shared chat
                log_values = [
                (
                    log['tim_timestamp'], 
                    shared_user_name, 
                    log['vchr_user_message'], 
                    log['vchr_bot_response'],
                    log['fk_bint_bot_id'], 
                    log['bint_input_token_usage'], 
                    log['bint_output_token_usage'], 
                    new_conversation_id, 
                    json.dumps(log['arr_reference_id'])
                )
                for log in original_logs
                ]

                        
                cr.executemany("""
                            INSERT INTO tbl_bot_log (tim_timestamp, vchr_sender, vchr_user_message, vchr_bot_response,
                                                    fk_bint_bot_id, bint_input_token_usage, bint_output_token_usage,
                                                    fk_bint_conversation_id, arr_reference_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, log_values)

                # Fetch the original memory for the chat
                str_query = """
                    SELECT vchr_azure_resource_uuid 
                    FROM tbl_bots
                    WHERE pk_bint_bot_id = %s
                """
                cr.execute(str_query, (int_bot_id,))  
                str_bot_unique_id = cr.fetchone()[0]
                str_tenancy_id = get_tenancy_id(dct_headers)
                
                # connect to lancedb table
                db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_bot_unique_id}/lancedb",read_consistency_interval=timedelta(seconds=0))
                try:
                    memory_table = db_lance.open_table("memory")
                except ValueError:
                    table = db_lance.create_table("memory", schema = MemoryModel, exist_ok = True)
            
                result=memory_table.search().where(    f"user_id = '{user_id}' AND sid = '{original_chat['vchr_socket_id']}'").limit(memory_table.count_rows()).to_list()
    
                for record in result:
                    text_data = record.get('text', [])
                    text_json = json.loads(text_data)
                    role = text_json.get('role', '')
                    content = text_json.get('content', '')
                    memory_table.add([{"id": str(uuid.uuid4()),
                               "user_id": str(int_shared_user_id),
                               "sid": session_id,
                               "text": json.dumps({'role': role,
                                                   'content': content})}])
           
                ins_db.commit()

        except Exception as ex:
            traceback.print_exc()

        finally:
            if ins_db:
                ins_db.close()



    
                

   
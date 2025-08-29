
import traceback
import lancedb
from app.schema import MemoryModel,LiveChatModel
from app.utils.executor import executor
from app.utils.generalMethods import dct_error, dct_response,create_cursor,get_tenancy_id,convert_time_to_client_timezone,optimize_lancedb
from datetime import timedelta


class chatHistoryService:

    @staticmethod
    def get_chat_history_titles(request, ins_db):
        try:
            with create_cursor(ins_db) as cr:
                # Extract payload
                dct_request = request.json
                int_bot_id = dct_request["intBotId"]
                int_user_id = dct_request["intUserId"]
                bln_all_chat = dct_request.get("blnAllChat", False)
                str_where_condition = 'AND ch.fk_bint_user_id = %s'% int_user_id
                
                # Check for `blnAllChat` and `ADMIN` user group
                if bln_all_chat:
                    # Fetch user group for the user
                    cr.execute("select 1 FROM tbl_user WHERE pk_bint_user_id = %s AND fk_bint_user_group_id in (1,3)",(int_user_id,))
                    rst_admin = cr.fetchone()
                    
                    if not rst_admin:
                        return dct_error("No Permission"),400
                        # Fetch all chat history for the bot
                    str_where_condition = ''


                cr.execute("""
                    SELECT ch.pk_bint_conversation_id, 
                           ch.vchr_conversation_title, 
                           ch.vchr_socket_id, 
                           ch.tim_created,
                           ch.bln_shared,
                           su.vchr_user_name AS shared_user,
                           ch.fk_bint_user_id,
                           u.vchr_user_name AS user
                    FROM tbl_chat_history ch
                    LEFT JOIN tbl_user u ON ch.fk_bint_user_id = u.pk_bint_user_id
                    LEFT JOIN tbl_user su ON ch.fk_bint_shared_user_id = su.pk_bint_user_id
                    WHERE ch.chr_document_status = 'N'
                    AND ch.fk_bint_bot_id = %s
                    %s
                    AND ch.bln_whatsapp !=TRUE
                    ORDER BY ch.pk_bint_conversation_id DESC
                """% (int_bot_id,str_where_condition))
                rst = cr.fetchall()
                
                # Process results
                arr_titles = []
                for record in rst:
                    dct_chat_history = {
                        "intConversationId": record['pk_bint_conversation_id'],
                        "strTitle": record['vchr_conversation_title'],
                        "strSocketId": record['vchr_socket_id'],
                        "timeCreated": convert_time_to_client_timezone(record['tim_created']).strftime("%a, %d %b %Y at %I:%M %p"),
                        "blnShared":record['bln_shared'],
                        "strSharedBy":record['shared_user'] or ''
                    }
                    if bln_all_chat:
                        dct_chat_history["intUserId"] = record['fk_bint_user_id']  # Add username
                        dct_chat_history["strUserName"] = record['user'] or ''
                    arr_titles.append(dct_chat_history)
                
                return {"arrUserHistory": arr_titles}, 200

        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
    
        finally:
            if ins_db:
                ins_db.close()



    @staticmethod
    def get_chat_history_conversation(request, ins_db, user_id):
        try:
            with create_cursor(ins_db) as cr:
                # Extract payload
                dct_request = request.json
                int_bot_id = dct_request["intBotId"]
                int_conversation_id=dct_request["intConversationId"]

                cr.execute("select 1 FROM tbl_user WHERE pk_bint_user_id = %s AND fk_bint_user_group_id in (1,3)",(user_id,))
                rst_admin = cr.fetchone()
                    
                if not rst_admin:
                    cr.execute("""
                        SELECT 1  
                        FROM tbl_chat_history 
                        WHERE chr_document_status = 'N'
                        AND pk_bint_conversation_id = %s 
                        AND fk_bint_user_id = %s
                    """, (int_conversation_id,user_id))
                    rst_conversation = cr.fetchone()
                    if not rst_conversation:
                        return dct_error("No Permission"),400
                
                
                # # Set the cursor to return dictionaries
                cr.execute("""
                        SELECT 
                                ch.pk_bint_conversation_id,
                                u.vchr_user_name,
                                ch.vchr_conversation_title,
                                ARRAY_AGG(
                                    json_build_object(
                                        'intChatId', bl.pk_bint_chat_id,
                                        'strMessage', bl.vchr_user_message,
                                        'strResponse', bl.vchr_bot_response,
                                        'arrReference', bl.arr_reference_id,
                                        'strFeedBack',COALESCE(bl.vchr_feedback,''),
                                        'strComment',bl.vchr_comment,
                                        'strAttachmentFileName', ca.vchr_attachment_name,
                                        'strFileExtension', 
                                            CASE 
                                                WHEN ca.vchr_attachment_name IS NOT NULL THEN split_part(ca.vchr_attachment_name, '.', array_length(string_to_array(ca.vchr_attachment_name, '.'), 1))
                                                
                                            END
                                    ) ORDER BY bl.pk_bint_chat_id
                                ) AS arr_logs
                            FROM tbl_chat_history ch
                            LEFT JOIN tbl_user u ON ch.fk_bint_user_id = u.pk_bint_user_id
                            LEFT JOIN tbl_bot_log bl ON bl.fk_bint_conversation_id = ch.pk_bint_conversation_id AND bl.chr_document_status = 'N'
                            LEFT JOIN tbl_chat_attachment_bot_log_mapping att_map ON att_map.fk_bint_chat_id = bl.pk_bint_chat_id
                            LEFT JOIN tbl_chat_attachment ca ON ca.pk_bint_attachment_id = att_map.fk_bint_attachment_id
                            WHERE ch.chr_document_status = 'N'
                            AND ch.pk_bint_conversation_id = %s
                            AND ch.fk_bint_bot_id = %s
                            GROUP BY 
                                ch.pk_bint_conversation_id,
                                u.vchr_user_name,
                                ch.vchr_conversation_title
                            
                """, (int_conversation_id,int_bot_id))

                rst=cr.fetchone()


                dct_source = {
                    "intConversationId": rst["pk_bint_conversation_id"],
                    "strUser": rst["vchr_user_name"],
                    "strTitle": rst["vchr_conversation_title"],
                    "arrLogs": rst["arr_logs"]
                }

            


            # Return the titles in response
            return {"objConv":dct_source}, 200
        
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
        
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def delete_chat_history(request, ins_db):
        dct_request = request.json
        int_conversation_id = dct_request["intConversationId"]
        int_bot_id = dct_request["intBotId"]
        str_tenancy_id = get_tenancy_id(request.headers)
     
        try:
            with create_cursor(ins_db) as cr:
                str_query = """
                    SELECT vchr_azure_resource_uuid 
                    FROM tbl_bots
                    WHERE pk_bint_bot_id = %s
                """
                cr.execute(str_query, (int_bot_id,))  # Add a trailing comma to make it a tuple
                str_bot_unique_id = cr.fetchone()[0]

                cr.execute("SELECT vchr_socket_id FROM tbl_chat_history WHERE pk_bint_conversation_id = %s", (int_conversation_id,))
                socket_row = cr.fetchone()

                if not socket_row:
                    print(f"No chat history found for conversation ID {int_conversation_id}.")
                    return

                socket_id = socket_row['vchr_socket_id'] 
                # Delete any attachment records in one query.
                cr.execute(
                    "DELETE FROM tbl_chat_attachment WHERE vchr_socket_id = %s RETURNING 1", 
                    (socket_id,)
                )
                # bln_attachment is True if any row was deleted.
                bln_attachment = cr.fetchone() is not None
           
                cr.execute("UPDATE tbl_bot_log SET chr_document_status = 'D' WHERE fk_bint_conversation_id = %s", (int_conversation_id,))
                cr.execute("UPDATE tbl_chat_history SET chr_document_status = 'D' WHERE pk_bint_conversation_id = %s", (int_conversation_id,))
                ins_db.commit()

                # delete from LanceDB
                executor.submit(chatHistoryService.delete_from_lancedb,str_tenancy_id,str_bot_unique_id,socket_id,bln_attachment)

            return dct_response("success", "chat history deleted successfully"), 200

        except Exception as ex:
            traceback.print_exc()

        finally:
            if ins_db:
                ins_db.close()


    @staticmethod
    def rename_chat_history(request, ins_db):
        dct_request = request.json
        int_conversation_id = dct_request["intConversationId"]
        str_title = dct_request["strTitle"]
       
        try:
            with create_cursor(ins_db) as cr:
                cr.execute("UPDATE tbl_chat_history SET vchr_conversation_title = %s WHERE pk_bint_conversation_id = %s", (str_title, int_conversation_id))                

                
                ins_db.commit()

            return dct_response("success", "chat history renamed successfully"), 200

        except Exception as ex:
            traceback.print_exc()

        finally:
            if ins_db:
                ins_db.close()
    
    @staticmethod
    def delete_from_lancedb(str_tenancy_id,str_bot_unique_id,socket_id,bln_attachment):
        #Connecting to lancedb
        db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_bot_unique_id}/lancedb",read_consistency_interval=timedelta(seconds=0))        

        #Opening lancedb table named memory
        try:
            memory_table = db_lance.open_table("memory")
        except ValueError:
            memory_table = db_lance.create_table("memory", schema = MemoryModel, exist_ok = True)


        #Deleting source from lancedb memory table using socket id  
        memory_table.delete( where=f"sid = '{socket_id}'",)

        if bln_attachment:
            #Opening lancedb table named live_chat
            try:
                live_chat_table = db_lance.open_table("live_chat")
            except ValueError:
                live_chat_table = db_lance.create_table("live_chat", schema = LiveChatModel, exist_ok = True)


            #Deleting source from lancedb memory table using file name  
            live_chat_table.delete( where=f"sid = '{socket_id}'",)
        
        # optimize
        executor.submit(optimize_lancedb,str_tenancy_id,str_bot_unique_id,"memory")
        if bln_attachment:
            executor.submit(optimize_lancedb,str_tenancy_id,str_bot_unique_id,"live_chat")
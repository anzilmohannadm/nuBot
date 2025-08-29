import os
import traceback
import pytz
import calendar
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.utils.generalMethods import dct_get_response,dct_error, create_cursor, convert_time_to_client_timezone,dct_response,get_tenancy_id

class botLogService:    
   @staticmethod
   def get_all_conversation(request, ins_db, user_id):
    try:
        
        with create_cursor(ins_db) as cr:
           dct_request = request.json
           int_page_offset = dct_request["objPagination"]["intPageOffset"]
           int_page_limit = dct_request["objPagination"]["intPerPage"]
           int_offset = int_page_offset * int_page_limit
           str_start_date = dct_request['objFilter'].get('strStartDate')
           str_end_date = dct_request['objFilter'].get('strEndDate')
           int_bot_id = dct_request['objFilter'].get('intBotId')
           str_feedback = dct_request['objFilter'].get('strFeedback')

           # Prepare the date range conditions
           lst_main_condition = []
           str_main_where_clause = ''
           lst_sub_condition = []
           str_sub_where_clause = ''
           if str_start_date and str_end_date:
               start_date = datetime.strptime(str_start_date, '%d/%m/%Y').date()
               end_date = datetime.strptime(str_end_date, '%d/%m/%Y').date() + timedelta(days=1) - timedelta(seconds=1)
               lst_main_condition.append("ch.tim_created BETWEEN '%s' AND '%s'" % (start_date, end_date))
   
           if int_bot_id:
              lst_main_condition.append("ch.fk_bint_bot_id = %d" % int_bot_id)
              lst_sub_condition.append("fk_bint_bot_id = %d" % int_bot_id)
            

           if str_feedback != "ALL":
                if str_feedback == "NEGATIVE":
                    lst_main_condition.append("lgc.int_down >= 1")
                else:
                    lst_main_condition.append("lgc.int_up >= 1")
            
           if lst_main_condition:
                str_main_where_clause = ' AND '+' AND '.join(lst_main_condition)
           if lst_sub_condition:
                str_sub_where_clause = ' AND '+' AND '.join(lst_sub_condition)
                                 
           str_query = """WITH LogCounts AS (
                                                SELECT 
                                                    fk_bint_conversation_id,
                                                    COUNT(CASE WHEN vchr_feedback = 'POSITIVE' THEN 1 END) AS int_up,
                                                    COUNT(CASE WHEN vchr_feedback = 'NEGATIVE' THEN 1 END) AS int_down,
                                                    COUNT(CASE WHEN vchr_comment IS NOT NULL THEN 1 END) AS int_comment
                                                FROM tbl_bot_log
                                                WHERE chr_document_status = 'N'
                                                %s
                                                GROUP BY fk_bint_conversation_id
                                            )
                                            SELECT DISTINCT
                                                ch.pk_bint_conversation_id, 
                                                b.pk_bint_bot_id,
                                                b.vchr_bot_name,
                                                u.vchr_user_name,
                                                ch.vchr_conversation_title,
                                                ch.tim_created,
                                                ch.json_embedd,
                                                ch.bln_whatsapp,
                                                lgc.int_up,
                                                lgc.int_down,
                                                lgc.int_comment,
                                                COUNT(*) OVER() AS int_total_count
                                            FROM tbl_chat_history ch
                                            LEFT JOIN LogCounts lgc ON lgc.fk_bint_conversation_id = ch.pk_bint_conversation_id
                                            LEFT JOIN tbl_bots b ON b.pk_bint_bot_id = ch.fk_bint_bot_id
                                            LEFT JOIN tbl_user u ON u.pk_bint_user_id = ch.fk_bint_user_id
                                            LEFT JOIN tbl_bot_view_permissions vp ON b.pk_bint_bot_id = vp.fk_bint_bot_id AND vp.fk_bint_user_id = %s
                                            WHERE ch.chr_document_status = 'N' 
                                            AND b.chr_document_status = 'N'
                                            AND (b.fk_bint_created_user_id = %s OR vp.fk_bint_user_id IS NOT NULL)
                                            %s
                                            ORDER BY ch.pk_bint_conversation_id DESC
                                            LIMIT %s OFFSET %s"""%(str_sub_where_clause,user_id,user_id, str_main_where_clause,int_page_limit, int_offset)
           cr.execute(str_query)
           rst = cr.fetchall()
           arr_list = []
           int_total_count = 0
   
           if rst:
               int_total_count = rst[0]["int_total_count"]  # Total count in the current result
               int_serial = int_offset + 1
               for record in rst:
                   dct_log =  {
                       "slNo":int_serial,
                       "intConversationId":record["pk_bint_conversation_id"],
                       "strBotName": record["vchr_bot_name"],
                       "strSender" : record['vchr_user_name'] or '',
                       "strTitle" : record["vchr_conversation_title"],
                       "strTime" : convert_time_to_client_timezone(record["tim_created"]).strftime("%a, %d %b %Y at %I:%M %p") if record["tim_created"] else "",
                       "intUp" : record['int_up'],
                       "intDown" : record['int_down'],
                       "intComment" : record['int_comment'],
                       }
                   if record['json_embedd']:
                       dct_log["dct_embedd_data"] = record['json_embedd']
                   if record["bln_whatsapp"]:
                        dct_log["blnWhatsapp"] = record["bln_whatsapp"]
                   arr_list.append(dct_log)
                   int_serial += 1

        return (
            dct_get_response(
                int_total_count, int_page_offset, int_page_limit, arr_list
            ),
            200,
        )
           
    except Exception as ex:
        traceback.print_exc()
        return dct_error(str(ex)), 400
    finally:
       if ins_db:
          ins_db.close()
    
          
   @staticmethod
   def conversation_logs(request, ins_db, user_id):
    try:
            
        with create_cursor(ins_db) as cr:
           dct_request = request.json
           int_conversation_id = dct_request['intConversationId']
                    
           str_query = """SELECT  
                                lg.pk_bint_chat_id,
                                lg.vchr_sender,
                                b.pk_bint_bot_id,
                                b.vchr_bot_name,
                                lg.vchr_user_message,
                                lg.vchr_bot_response,
                                lg.tim_timestamp,
                                lg.arr_reference_id,
                                lg.vchr_feedback,
                                lg.vchr_comment,
                                ca.vchr_attachment_name
                          FROM tbl_bot_log lg 
                          LEFT JOIN tbl_chat_history ch on lg.fk_bint_conversation_id = ch.pk_bint_conversation_id
                          LEFT JOIN tbl_bots b ON b.pk_bint_bot_id = lg.fk_bint_bot_id
                          LEFT JOIN tbl_bot_view_permissions vp ON b.pk_bint_bot_id = vp.fk_bint_bot_id AND vp.fk_bint_user_id = %s
                          LEFT JOIN tbl_bot_edit_permissions ep ON b.pk_bint_bot_id = ep.fk_bint_bot_id AND ep.fk_bint_user_id = %s
                          LEFT JOIN tbl_chat_attachment_bot_log_mapping att_map ON att_map.fk_bint_chat_id = lg.pk_bint_chat_id
                          LEFT JOIN tbl_chat_attachment ca ON ca.pk_bint_attachment_id = att_map.fk_bint_attachment_id
                          WHERE b.chr_document_status = 'N' 
                          AND lg.chr_document_status = 'N' 
                          AND ch.chr_document_status = 'N' 
                          AND ch.pk_bint_conversation_id = %s
                          AND (b.fk_bint_created_user_id = %s OR vp.fk_bint_user_id IS NOT NULL)
                          
                          ORDER BY 
                                 ch.pk_bint_conversation_id DESC """ % (user_id,user_id,int_conversation_id,user_id)
   
           cr.execute(str_query)
           rst = cr.fetchall()
           dct_bot_log = {}
           if rst:
               dct_bot_log["arrLogs"] = [
                   {'intChatId': record['pk_bint_chat_id'],
                    'strSender': record['vchr_sender'],
                    'intBotId':record['pk_bint_bot_id'],
                    'strBotName': record['vchr_bot_name'],
                    'strMessage': record['vchr_user_message'],
                    'strResponse': record['vchr_bot_response'],
                    'arrReference': record['arr_reference_id'],
                    'strFeedBack': record['vchr_feedback'] or '',
                    'strComment': record['vchr_comment'],
                    'strAttachmentFileName': record['vchr_attachment_name'] or '',  # Handle NULL values
                    'strFileExtension': os.path.splitext(record['vchr_attachment_name'])[1][1:] if record['vchr_attachment_name'] else ''
                    }
                   
               for record in rst ]
            
        

        return dct_bot_log ,200
           
    except Exception as ex:
        traceback.print_exc()
        return dct_error(str(ex)), 400
    finally:
       if ins_db:
          ins_db.close()    
    
          
            

   @staticmethod
   def get_token_cost(request,ins_db,user_id):
    try:
        
        def number_to_short_form(num):
            if num < 1000:
                return str(num)
            elif 1000 <= num < 1_000_000:
                return f"{num / 1000:.1f}K"
            elif 1_000_000 <= num < 1_000_000_000:
                return f"{num / 1_000_000:.1f}M"
            else:
                return f"{num / 1_000_000_000:.1f}B"

        with create_cursor(ins_db) as cr:
            dct_request = request.json
            str_start_date= dct_request['objFilter'].get("strStartDate")
            str_end_date= dct_request['objFilter'].get("strEndDate")

            int_bot_id = dct_request['objFilter'].get('intBotId')
            
    
            # Prepare the date range conditions
            lst_condition = []
            
            if str_start_date and str_end_date:
                    str_start_date = datetime.strptime(str_start_date, "%d/%m/%Y").strftime("%Y-%m-%d")
                    str_end_date = datetime.strptime(str_end_date, "%d/%m/%Y").strftime("%Y-%m-%d")
                    lst_condition.append("date(l.tim_timestamp) >='%s' AND date(l.tim_timestamp) <='%s'" % (str_start_date, str_end_date))
            
            if int_bot_id:
                lst_condition.append("l.fk_bint_bot_id = %d" % int_bot_id) 

            str_where_clause = f"AND {' AND '.join(lst_condition) }"  if lst_condition else ''
            
            #bln_cost_view_access only 'TRUE' when only a tenant need to show the cost details else it will be false
            cr.execute("SELECT vchr_settings_value FROM tbl_settings WHERE vchr_settings_name = 'TENANT_COST_VIEW_ACCESS' LIMIT 1")
            
            bln_cost_view_access=cr.fetchone()[0]
            
            str_query = """SELECT 
                                b.pk_bint_bot_id,
                                b.vchr_bot_name AS bot_name,
                                b.vchr_icon,
                                b.tim_created,
                                b.tim_modified,
                                SUM(l.bint_input_token_usage) AS total_input_token_usage,
                                SUM(l.bint_output_token_usage) AS total_output_token_usage,
                                ARRAY_AGG( DISTINCT l.fk_bint_conversation_id) AS conversation_ids
                            FROM tbl_bot_log l
                            LEFT JOIN tbl_bots b ON l.fk_bint_bot_id = b.pk_bint_bot_id
                            LEFT JOIN tbl_bot_view_permissions vp ON b.pk_bint_bot_id = vp.fk_bint_bot_id AND vp.fk_bint_user_id = %s
                            LEFT JOIN tbl_bot_edit_permissions ep ON b.pk_bint_bot_id = ep.fk_bint_bot_id AND ep.fk_bint_user_id = %s
                            WHERE b.chr_document_status = 'N' AND (b.fk_bint_created_user_id = %s OR vp.fk_bint_user_id IS NOT NULL)
                            %s
                            GROUP BY 
                                b.pk_bint_bot_id,
                                b.vchr_bot_name,
                                b.vchr_icon,
                                b.tim_created,
                                b.tim_modified
                            ORDER BY 
                                b.vchr_bot_name DESC
                            """ % (user_id,user_id,user_id,str_where_clause)
                            
            
    
            cr.execute(str_query)
            rst = cr.fetchall()
            
            # Create a list of dictionaries for each record
            lst_default_bot_id = []
            arr_list = []
            
            #if bln_cost_view_access is TRUE then only that tenant can view the cost 
            if bln_cost_view_access =="TRUE":
                
                for record in rst:
                    input_tokens = int(record.get('total_input_token_usage', 0) or 0)
                    output_tokens = int(record.get('total_output_token_usage', 0) or 0)

                    lst_default_bot_id.append(record["pk_bint_bot_id"])
                    
                    # Calculate cost
                    cost = (input_tokens / 1000) * 0.21084438 + (output_tokens / 1000) * 0.8433376

                    # Add the formatted dictionary to the list
                    arr_list.append({
                        "intBotId":record["pk_bint_bot_id"],
                        "strBotName": record['bot_name'],
                        "strIcon":record['vchr_icon'],
                        "timCreated":convert_time_to_client_timezone(record['tim_created']).strftime("%a, %d %b %Y at %I:%M %p"),
                        "timModified":convert_time_to_client_timezone(record['tim_modified']).strftime("%a, %d %b %Y at %I:%M %p") if record['tim_modified'] else None,
                        "intInputTokenUsage": number_to_short_form(input_tokens),
                        "intOutputTokenUsage": number_to_short_form(output_tokens),
                        "intConversationalCount":len(record["conversation_ids"]),
                        "strCost": f"₹ {cost:.2f}"
                    })
            else:
                for record in rst:
                    input_tokens = int(record.get('total_input_token_usage', 0) or 0)
                    output_tokens = int(record.get('total_output_token_usage', 0) or 0)

                    lst_default_bot_id.append(record["pk_bint_bot_id"])

                    # Add the formatted dictionary to the list
                    arr_list.append({
                        "intBotId":record["pk_bint_bot_id"],
                        "strBotName": record['bot_name'],
                        "strIcon":record['vchr_icon'],
                        "timCreated":convert_time_to_client_timezone(record['tim_created']).strftime("%a, %d %b %Y at %I:%M %p"),
                        "timModified":convert_time_to_client_timezone(record['tim_modified']).strftime("%a, %d %b %Y at %I:%M %p") if record['tim_modified'] else None,
                        "intInputTokenUsage": number_to_short_form(input_tokens),
                        "intOutputTokenUsage": number_to_short_form(output_tokens),
                        "intConversationalCount":len(record["conversation_ids"]),
                        "strCost": "₹ 0.00"
                    })
    
                
            if lst_default_bot_id and not int_bot_id:   
                str_default_bot_clause = f"and b.pk_bint_bot_id not in ({','.join(map(str,lst_default_bot_id))})"
                
                default_bot_query=""" 
                                    SELECT 
                                        b.pk_bint_bot_id, 
                                        b.vchr_bot_name, 
                                        b.vchr_icon, 
                                        b.tim_created,
                                        b.tim_modified
                                    FROM 
                                        tbl_bots b
                                    LEFT JOIN tbl_bot_view_permissions vp 
                                        ON b.pk_bint_bot_id = vp.fk_bint_bot_id AND vp.fk_bint_user_id = %s
                                    LEFT JOIN tbl_bot_edit_permissions ep 
                                        ON b.pk_bint_bot_id = ep.fk_bint_bot_id AND ep.fk_bint_user_id = %s
                                    WHERE
                                        b.chr_document_status = 'N' 
                                        AND (b.fk_bint_created_user_id = %s OR vp.fk_bint_user_id IS NOT NULL)
                                    %s
                                    """ % (user_id,user_id,user_id,str_default_bot_clause)
                                    
                cr.execute(default_bot_query)
                rst_default_bot=cr.fetchall()
                
                for record in rst_default_bot:
                    arr_list.append({
                        "intBotId":record["pk_bint_bot_id"],
                        "strBotName": record['vchr_bot_name'],
                        "strIcon":record['vchr_icon'],
                        "timCreated":convert_time_to_client_timezone(record['tim_created']).strftime("%a, %d %b %Y at %I:%M %p"),
                        "timModified":convert_time_to_client_timezone(record['tim_modified']).strftime("%a, %d %b %Y at %I:%M %p") if record['tim_modified'] else None,
                        "intInputTokenUsage": 0,
                        "intOutputTokenUsage": 0,
                        "intConversationalCount": 0,
                        "strCost": "₹ 0.00"
                    })
                
                
            
            # if no result in rst ,return the values as zero
            if not rst:
                if int_bot_id:
                    default_bot_query = """
                        SELECT 
                            pk_bint_bot_id, 
                            vchr_bot_name, 
                            vchr_icon, 
                            tim_created 
                        FROM 
                            tbl_bots 
                        WHERE 
                            pk_bint_bot_id = %s
                    """
                    cr.execute(default_bot_query, (int_bot_id,))
                    default_bot = cr.fetchone()
                    arr_list = [{
                        "intBotId": default_bot["pk_bint_bot_id"],
                        "strBotName": default_bot["vchr_bot_name"],
                        "strIcon": default_bot["vchr_icon"],
                        "timCreated": convert_time_to_client_timezone(default_bot["tim_created"]).strftime("%a, %d %b %Y at %I:%M %p"),
                        "timModified": None,
                        "intInputTokenUsage": 0,
                        "intOutputTokenUsage": 0,
                        "intConversationalCount": 0,
                        "strCost": "₹ 0.00"
                    }]
                else:
                    default_bot_query=""" 
                                SELECT 
                                    pk_bint_bot_id, 
                                    vchr_bot_name, 
                                    vchr_icon, 
                                    tim_created 
                                FROM 
                                    tbl_bots b
                                LEFT JOIN tbl_bot_view_permissions vp
                                    ON b.pk_bint_bot_id = vp.fk_bint_bot_id AND vp.fk_bint_user_id = %s
                                LEFT JOIN tbl_bot_edit_permissions ep
                                    ON b.pk_bint_bot_id = ep.fk_bint_bot_id AND ep.fk_bint_user_id = %s
                                WHERE 
                                    b.chr_document_status = 'N' 
                                    AND (b.fk_bint_created_user_id = %s OR vp.fk_bint_user_id IS NOT NULL)
                                """ % (user_id,user_id,user_id)
                                
                    cr.execute(default_bot_query)
                    rst_default_bot=cr.fetchall()
                    
                    for record in rst_default_bot:
                        arr_list.append({
                            "intBotId": record["pk_bint_bot_id"],
                            "strBotName": record["vchr_bot_name"],
                            "strIcon": record["vchr_icon"],
                            "timCreated": convert_time_to_client_timezone(record["tim_created"]).strftime("%a, %d %b %Y at %I:%M %p"),
                            "timModified": None,
                            "intInputTokenUsage": 0,
                            "intOutputTokenUsage": 0,
                            "intConversationalCount": 0,
                            "strCost": "₹ 0.00"
                        })
        
        return arr_list,200
        
    except Exception as ex:
        traceback.print_exc()
        return dct_error(str(ex)), 400
    finally:
        if ins_db:
            ins_db.close()
            

   @staticmethod
   def save_feedback(request,ins_db):
    try:

        with create_cursor(ins_db) as cr:
            dct_request = request.json
            int_chat_id=dct_request["intChatId"]
            str_feedback=dct_request["strFeedBack"]
            
            cr.execute("UPDATE tbl_bot_log  SET vchr_feedback = %s WHERE pk_bint_chat_id = %s",(str_feedback,int_chat_id))
            ins_db.commit()
        
        return dct_response("success", "feedback updated successfully"), 200
        
    except Exception as ex:
        traceback.print_exc()
        return dct_error(str(ex)), 400
    finally:
        if ins_db:
            ins_db.close()
    
   @staticmethod
   def post_comment(request,ins_db):
    try:
        with create_cursor(ins_db) as cr:
            dct_request = request.json
            int_chat_id=dct_request["intChatId"]
            str_comment=dct_request["strComment"]
            
            cr.execute("UPDATE tbl_bot_log  SET vchr_comment = %s WHERE pk_bint_chat_id = %s",(str_comment,int_chat_id))
            ins_db.commit()
        
        return dct_response("success", "Comment updated successfully"), 200
        
    except Exception as ex:
        traceback.print_exc()
        return dct_error(str(ex)), 400
    finally:
        if ins_db:
            ins_db.close()
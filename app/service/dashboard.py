import traceback
import calendar
import pytz
from collections import defaultdict

from datetime import datetime
from app.utils.generalMethods import dct_error,create_cursor
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class dashboardService:
    @staticmethod
    def number_to_short_form(num):
                if num < 1000:
                    return f" {num:.2f}"
                elif 1000 <= num < 1_000_000:
                    return f"{num / 1000:.1f}K"
                elif 1_000_000 <= num < 1_000_000_000:
                    return f"{num / 1_000_000:.1f}M"
                else:
                    return f"{num / 1_000_000_000:.1f}B"
    
    @staticmethod
    def view_dashboard(request, ins_db):
        try:
            
            with create_cursor(ins_db) as cr:
                # Extract payload
                dct_request = request.json
                int_bot_id = dct_request["intBotId"]
                str_criteria = dct_request["strCriteria"]
                str_start_date= dct_request["strStartDate"]
                str_end_date= dct_request["strEndDate"]
                
                def validate_date(date_str):
                    try:
                        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        return None
            

                str_start_date = validate_date(str_start_date)
                str_end_date = validate_date(str_end_date)
                
                #bln_cost_view_access only 'TRUE' when only a tenant need to show the cost details else it will be false
                cr.execute("SELECT vchr_settings_value FROM tbl_settings WHERE vchr_settings_name = 'TENANT_COST_VIEW_ACCESS' LIMIT 1")
                bln_cost_view_access=cr.fetchone()[0]
                cr.execute("""
                                SELECT
                                    pk_bint_chat_id,
                                    tim_timestamp,
                                    vchr_sender,
                                    bint_input_token_usage,
                                    bint_output_token_usage,
                                    fk_bint_conversation_id
                                FROM
                                    tbl_bot_log
                                WHERE
                                    fk_bint_bot_id = %s
                                    AND date(tim_timestamp) >=%s AND date(tim_timestamp) <=%s 
                                    
                                ORDER BY tim_timestamp
                            """,(int_bot_id,str_start_date,str_end_date))
                
                rst= cr.fetchall()
                
                #=========================================================
                
                
                #TOKEN_USAGE_BY_TIME
                if str_criteria.upper() == 'TOKEN_USAGE_BY_TIME':
                    dct_response={}
                    dct_response["TOKEN_USAGE_BY_TIME"] = {"yaxisData": [], "xaxisData": []}

                    dct_token_usage=defaultdict(int)
                    
                    for record in rst:
                        
                        timestamp = record['tim_timestamp'].strftime('%Y-%m-%dT%H:00:00.000Z')
                        total_token_usage = record['bint_input_token_usage']+record['bint_output_token_usage']
                        dct_token_usage[timestamp]+= total_token_usage # Add token usage to the corresponding key
                    
                    dct_response["TOKEN_USAGE_BY_TIME"]["xaxisData"] =  list(dct_token_usage.keys())
                    dct_response["TOKEN_USAGE_BY_TIME"]["yaxisData"] =  list(dct_token_usage.values())# Set the y-axis data to the token usage values

                    return dct_response,200
                
                #=========================================================
                
                #TOKEN_USAGE_BY_USER
                if str_criteria.upper() == 'TOKEN_USAGE_BY_USER': 
                    
                    dct_response={}
                    dct_response["TOKEN_USAGE_BY_USER"] = {"yaxisData": [], "xaxisData": []}
                    
                    cr.execute("""SELECT DISTINCT u.pk_bint_user_id, u.vchr_user_name as user_name
                            FROM tbl_bots b
                            LEFT JOIN tbl_bot_edit_permissions ep ON ep.fk_bint_bot_id = b.pk_bint_bot_id
                            LEFT JOIN tbl_bot_view_permissions vp ON vp.fk_bint_bot_id = b.pk_bint_bot_id
                            LEFT JOIN tbl_user u ON u.pk_bint_user_id = b.fk_bint_created_user_id
                                                        OR u.pk_bint_user_id = ep.fk_bint_user_id
                                                        OR u.pk_bint_user_id = vp.fk_bint_user_id
                            WHERE b.pk_bint_bot_id = %s;""",(int_bot_id,))
                    
                    users=cr.fetchall()

                    lst_users = [record["user_name"] for record in users]
                    dct_token_usage = {i:0 for i in lst_users}
                        
                    for record in rst:
                    
                        str_user_name=record["vchr_sender"]
                        total_token_usage=record['bint_input_token_usage']+record['bint_output_token_usage']


                        if str_user_name not in dct_token_usage: # handle non user : sid
                            dct_token_usage[str_user_name] = 0
                        dct_token_usage[str_user_name]+= total_token_usage  
                    
                    dct_response["TOKEN_USAGE_BY_USER"]["yaxisData"] =  list(dct_token_usage.values())
                    dct_response["TOKEN_USAGE_BY_USER"]["xaxisData"] = list(dct_token_usage.keys())
                    
                    return dct_response
                
                #=========================================================
                
                #TOKEN_COST_USAGE_BY_USER
                    
                if str_criteria.upper() == 'TOKEN_COST_USAGE_BY_USER':
                    
                    dct_response={}
                    dct_response["TOKEN_COST_USAGE_BY_USER"] = {"yaxisData": [], "xaxisData": []}
                    
                    
                    #if bln_cost_view_access is TRUE then only that tenant can view the cost 
                    if bln_cost_view_access == "TRUE":
                        
                        cr.execute("""SELECT DISTINCT u.pk_bint_user_id, u.vchr_user_name as user_name
                                FROM tbl_bots b
                                LEFT JOIN tbl_bot_edit_permissions ep ON ep.fk_bint_bot_id = b.pk_bint_bot_id
                                LEFT JOIN tbl_bot_view_permissions vp ON vp.fk_bint_bot_id = b.pk_bint_bot_id
                                LEFT JOIN tbl_user u ON u.pk_bint_user_id = b.fk_bint_created_user_id
                                                            OR u.pk_bint_user_id = ep.fk_bint_user_id
                                                            OR u.pk_bint_user_id = vp.fk_bint_user_id
                                WHERE b.pk_bint_bot_id = %s;""",(int_bot_id,))
                        
                        users=cr.fetchall()  # Fetch all the users interacting with the bot

                        lst_users = [record["user_name"] for record in users] # Extract the user names
                        dct_token_usage = {i:0 for i in lst_users}  # Initialize token cost usage for each user, initialy it is zero then we add values to it using the key username
                            
                            
                        for record in rst:
                            
                            str_user_name=record["vchr_sender"]
                            input_token_usage=record['bint_input_token_usage']
                            output_token_usage=record['bint_output_token_usage']

                            cost = (input_token_usage / 1000) * 0.21084438 + (output_token_usage / 1000) * 0.8433376

                            if str_user_name not in dct_token_usage: # handle none user : socket sid as user
                                dct_token_usage[str_user_name] = 0
                            dct_token_usage[str_user_name]+= cost
                            
                        dct_response["TOKEN_COST_USAGE_BY_USER"]["xaxisData"] = list(dct_token_usage.keys())
                        dct_response["TOKEN_COST_USAGE_BY_USER"]["yaxisData"] =  list(f"₹ {dashboardService.number_to_short_form(value)}" for value in dct_token_usage.values())
                        
                        return dct_response
                    
                    else:
                        
                        cr.execute("""SELECT DISTINCT u.pk_bint_user_id, u.vchr_user_name as user_name
                                FROM tbl_bots b
                                LEFT JOIN tbl_bot_edit_permissions ep ON ep.fk_bint_bot_id = b.pk_bint_bot_id
                                LEFT JOIN tbl_bot_view_permissions vp ON vp.fk_bint_bot_id = b.pk_bint_bot_id
                                LEFT JOIN tbl_user u ON u.pk_bint_user_id = b.fk_bint_created_user_id
                                                            OR u.pk_bint_user_id = ep.fk_bint_user_id
                                                            OR u.pk_bint_user_id = vp.fk_bint_user_id
                                WHERE b.pk_bint_bot_id = %s;""",(int_bot_id,))
                        
                        users=cr.fetchall()  # Fetch all the users interacting with the bot

                        lst_users = [record["user_name"] for record in users] # Extract the user names
                        dct_token_usage = {i:"₹ 0.00" for i in lst_users}  # Initialize token cost usage for each user, initialy it is zero then we add values to it using the key username
                            
                        dct_response["TOKEN_COST_USAGE_BY_USER"]["xaxisData"] = list(dct_token_usage.keys())
                        dct_response["TOKEN_COST_USAGE_BY_USER"]["yaxisData"] =  list(dct_token_usage.values())
                        
                        return dct_response
                    
                #======================================================================
                
                #TOKEN_COST_BY_TIME
                if str_criteria.upper() == 'TOKEN_COST_BY_TIME':
                    
                    dct_response={}
                    dct_response["TOKEN_COST_BY_TIME"] = {"yaxisData": [], "xaxisData": []}
                    dct_token_usage=defaultdict(int)
                    
                    #if bln_cost_view_access is TRUE then only that tenant can view the cost 
                    if bln_cost_view_access =="TRUE":

                        for record in rst:
                            
                            timestamp = record['tim_timestamp'].strftime('%Y-%m-%dT%H:00:00.000Z')
                            input_token_usage=record['bint_input_token_usage']
                            output_token_usage=record['bint_output_token_usage']
                            
                            cost = (input_token_usage / 1000) * 0.21084438 + (output_token_usage / 1000) * 0.8433376
                            dct_token_usage[timestamp]+=cost
                                  
                        dct_response["TOKEN_COST_BY_TIME"]["xaxisData"] =  list(dct_token_usage.keys())
                        dct_response["TOKEN_COST_BY_TIME"]["yaxisData"] =  list(f"₹ {value:.2f}" for value in dct_token_usage.values())

                        return dct_response,200
                    
                    else:
                        
                        for record in rst:
                            timestamp = record['tim_timestamp'].strftime('%Y-%m-%dT%H:00:00.000Z')
                            dct_token_usage[timestamp]="₹ 0.00"
                        
                        dct_response["TOKEN_COST_BY_TIME"]["xaxisData"] =  list(dct_token_usage.keys())
                        dct_response["TOKEN_COST_BY_TIME"]["yaxisData"] =  list(dct_token_usage.values())

                        return dct_response,200
                
                #============================================================================  
                
                #CONVERSATION_BY_USER
                if str_criteria.upper() == 'CONVERSATION_BY_USER':    
                    
                    dct_response={}
                    dct_response["CONVERSATION_BY_USER"] = {"yaxisData": [], "xaxisData": []}
                    
                    cr.execute("""SELECT DISTINCT u.pk_bint_user_id, u.vchr_user_name as user_name
                            FROM tbl_bots b
                            LEFT JOIN tbl_bot_edit_permissions ep ON ep.fk_bint_bot_id = b.pk_bint_bot_id
                            LEFT JOIN tbl_bot_view_permissions vp ON vp.fk_bint_bot_id = b.pk_bint_bot_id
                            LEFT JOIN tbl_user u ON u.pk_bint_user_id = b.fk_bint_created_user_id
                                                        OR u.pk_bint_user_id = ep.fk_bint_user_id
                                                        OR u.pk_bint_user_id = vp.fk_bint_user_id
                            WHERE b.pk_bint_bot_id = %s;""",(int_bot_id,))
                    
                    users=cr.fetchall()

                    lst_users = [record["user_name"] for record in users] 
    
                    dct_token_usage = {i:set() for i in lst_users}

                    for record in rst:  
                        str_user_name = record["vchr_sender"]
                        conversation_id = record["fk_bint_conversation_id"]
                        
                        if str_user_name in lst_users and conversation_id:
                            dct_token_usage[str_user_name].add(conversation_id)
                    
                    # Prepare x-axis (user names) and y-axis (count of unique conversation IDs)
                    dct_response["CONVERSATION_BY_USER"]["xaxisData"] = list(dct_token_usage.keys())
                    dct_response["CONVERSATION_BY_USER"]["yaxisData"] = list(len(conversations) for conversations in dct_token_usage.values())
                    
                    return dct_response


                        
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
        
        finally: 
            if ins_db:
                ins_db.close
    
    
    @staticmethod
    def get_overview_data(request, ins_db,user_id):
        try:

            with create_cursor(ins_db) as cr:
                dct_request = request.json
                str_start_date= dct_request['objFilter'].get("strStartDate")
                str_end_date= dct_request['objFilter'].get("strEndDate")
                int_bot_id = dct_request['objFilter'].get('intBotId') 
                
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
                                b.vchr_bot_name ,
                                b.vchr_icon,
                                b.tim_created,
                                b.tim_modified,
                                SUM(l.bint_input_token_usage) AS total_input_token_usage,
                                SUM(l.bint_output_token_usage) AS total_output_token_usage,
                                COUNT(CASE WHEN l.vchr_feedback = 'POSITIVE' THEN 1 END) AS total_positive_count,
                                COUNT(CASE WHEN l.vchr_feedback = 'NEGATIVE' THEN 1 END) AS total_negative_count,
                                COUNT(l.vchr_comment) as int_comment,
                                ARRAY_AGG(DISTINCT l.fk_bint_conversation_id) AS conversation_ids
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
                                b.pk_bint_bot_id ASC
                            """ % (user_id,user_id,user_id,str_where_clause)
                
                            
                cr.execute(str_query)
                rst = cr.fetchall()
                arr_list=[]
                lst_default_bot_id=[]
                
                #if bln_cost_view_access is TRUE then only that tenant can view the cost 
                if bln_cost_view_access=="TRUE":
                    
                    for record in rst:
                        input_tokens = int(record.get('total_input_token_usage', 0) or 0)
                        output_tokens = int(record.get('total_output_token_usage', 0) or 0)
                        
                        lst_default_bot_id.append(record["pk_bint_bot_id"])
                        
                        cost = (input_tokens / 1000) * 0.21084438 + (output_tokens / 1000) * 0.8433376
                        arr_list.append({
                            "intBotId":record["pk_bint_bot_id"],
                            "strBotName": record["vchr_bot_name"],
                            "intInputTokenUsage": dashboardService.number_to_short_form(input_tokens),
                            "intOutputTokenUsage": dashboardService.number_to_short_form(output_tokens),
                            "intTotalTokenUsage": dashboardService.number_to_short_form(input_tokens+output_tokens),
                            "intConversationalCount":len(record["conversation_ids"]),
                            "intup":record["total_positive_count"],
                            "intDown":record["total_negative_count"],
                            "int_comment": record['int_comment'],
                            "strCost": f"₹ {cost:.2f}"
                            
                        })
                    
                else:
                    
                    for record in rst:
                        input_tokens = int(record.get('total_input_token_usage', 0) or 0)
                        output_tokens = int(record.get('total_output_token_usage', 0) or 0)
                        
                        lst_default_bot_id.append(record["pk_bint_bot_id"])
                        
                        arr_list.append({
                            "intBotId":record["pk_bint_bot_id"],
                            "strBotName": record["vchr_bot_name"],
                            "intInputTokenUsage": dashboardService.number_to_short_form(input_tokens),
                            "intOutputTokenUsage": dashboardService.number_to_short_form(output_tokens),
                            "intTotalTokenUsage": dashboardService.number_to_short_form(input_tokens+output_tokens),
                            "intConversationalCount":len(record["conversation_ids"]),
                            "intup":record["total_positive_count"],
                            "intDown":record["total_negative_count"],
                            "int_comment": record['int_comment'],
                            "strCost":  "₹ 0.00"
                        })
                    
                if lst_default_bot_id and not int_bot_id :
                    
                    str_default_bot_clause = f"and b.pk_bint_bot_id not in ({','.join(map(str,lst_default_bot_id))})"
                    
                    default_bot_query=""" SELECT 
                                          b.pk_bint_bot_id, 
                                          b.vchr_bot_name, 
                                          b.vchr_icon, 
                                          b.tim_created 
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
                            "strBotName": record["vchr_bot_name"],
                            "intInputTokenUsage": 0,
                            "intOutputTokenUsage": 0,
                            "intTotalTokenUsage": 0,
                            "intConversationalCount":0,
                            "intup":0,
                            "intDown":0,
                            "int_comment": 0,
                            "strCost":  "₹ 0.00"
                    })
               
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
                        
                        arr_list.append({
                            "intBotId":default_bot["pk_bint_bot_id"],
                            "strBotName": default_bot["vchr_bot_name"],
                            "intInputTokenUsage": 0,
                            "intOutputTokenUsage": 0,
                            "intTotalTokenUsage": 0,
                            "intConversationalCount":0,
                            "intup":0,
                            "intDown":0,
                            "int_comment": 0,
                            "strCost":  "₹ 0.00"
                        
                        })
                    else:    
                        default_bot_query=""" 
                                    SELECT 
                                        b.pk_bint_bot_id, 
                                        b.vchr_bot_name, 
                                        b.vchr_icon, 
                                        b.tim_created 
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
                                "intBotId":record["pk_bint_bot_id"],
                                "strBotName": record["vchr_bot_name"],
                                "intInputTokenUsage": 0,
                                "intOutputTokenUsage": 0,
                                "intTotalTokenUsage": 0,
                                "intConversationalCount":0,
                                "intup":0,
                                "intDown":0,
                                "int_comment": 0,
                                "strCost":  "₹ 0.00"
                                
                            })
        
                return arr_list
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
        
        finally: 
            if ins_db:
                ins_db.close

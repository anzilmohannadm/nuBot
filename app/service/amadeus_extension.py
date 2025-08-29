import psycopg2
import traceback
import hashlib
import random
import smtplib
import jwt
import openai
from flask import jsonify
from email.mime.text import MIMEText
from datetime import datetime,timedelta,timezone
from app.utils.generalMethods import create_cursor
from app.utils.prompt_templates import amadeus_ai_rule_analyser_prompt
from app.utils.executor import executor
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.conf_path import str_configpath
from app.utils.global_config import env_mode

# configuration
ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)


# email configuration to send OTP
EMAIL_ADDRESS = ins_cfg.get(env_mode, 'smtp_email')
EMAIL_PASSWORD = ins_cfg.get(env_mode, 'smtp_password')
SECRET_KEY = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_SECRET_KEY')

# azure openai configuration
azure_api_key = ins_cfg.get(env_mode, 'AZURE_OPENAI_API_KEY')
azure_endpoint = ins_cfg.get(env_mode, 'AZURE_OPENAI_ENDPOINT')
azure_deployment = ins_cfg.get(env_mode, 'AZURE_OPENAI_DEPLOYMENT_ID')
azure_api_version = "2024-08-01-preview"

DB_HOST = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_HOST')
DB_NAME = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_NAME')
DB_USER = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_USER')
DB_PASSWORD = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_PASSWORD')
DB_PORT = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_PORT')

# azure openai client connection
client = openai.AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version,
            azure_deployment=azure_deployment
        )

class amadeusExtensionService:
    @staticmethod
    def register_user(request):
        try:
            dct_request = request.json
            str_email = dct_request.get("email")
            str_user_name = dct_request.get("username")
            str_password = dct_request.get("password")
            str_comapny = dct_request.get("companyname")
            str_phone = dct_request.get("phonenumber")
            int_city = dct_request.get("city")

            # check mandatory details
            if any(not data for data in [str_email,str_user_name,str_password,str_comapny,str_phone,int_city]): 
                return {"message": "Mandatory Information Missing"}, 400
            
            ins_db=psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
            with create_cursor(ins_db) as cr:
                cr.execute("SELECT 1 FROM tbl_user WHERE vchr_email = %s",(str_email,))
                rst_user = cr.fetchone()
                if rst_user:
                    return {"message": "User Already Exist"}, 400

                hashed_password = hashlib.sha256(str_password.encode()).hexdigest()
                int_otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                cr.execute("""
                           INSERT INTO tbl_user (vchr_user_name,
                                                 vchr_email,
                                                 vchr_hashed_password,
                                                 vchr_company,
                                                 vchr_phone,
                                                 fk_city_id,
                                                 int_otp 
                                                 )
                            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING pk_bint_user_id
                           """,(str_user_name,str_email,hashed_password,str_comapny,str_phone,int_city,int(int_otp)))
                
                int_user_id = cr.fetchone()[0]
                # Setting Free Trial Plan for the newly created user
                cr.execute("""
                    INSERT INTO tbl_user_subscription_details (
                        fk_bint_user_id,
                        vchr_sub_name,
                        bint_available_credits,
                        tim_start_sub,
                        tim_end_sub
                    )
                    VALUES (%s, %s, %s, NOW(), NOW() + INTERVAL '2 months')
                """, (int_user_id, 'FREE_TRIAL', 10000))
                ins_db.commit()
                amadeusExtensionService.send_otp_email(str_email,int_otp)
                return {'message': 'OTP sent to email', 'email': str_email}, 200
            
        
        except:
            traceback.print_exc()
            return {"message": "Registration Failed"}, 400
        
        finally:
            if ins_db:ins_db.close()

    @staticmethod
    def verify_otp(request):
        try:
            dct_request = request.json
            str_email = dct_request.get("email")
            int_otp = dct_request.get('otp')
            

            ins_db=psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
            
            with create_cursor(ins_db) as cr:
                cr.execute("SELECT 1 FROM tbl_user WHERE vchr_email = %s AND int_otp = %s",(str_email,int_otp))
                rst_user = cr.fetchone()
                if not rst_user:
                    return {"message": "Invalid OTP"}, 400


                # OTP verified, generate token and update database
                token = jwt.encode({
                    'email': str_email,
                    'exp': datetime.utcnow() + timedelta(hours=24)
                }, SECRET_KEY).decode('utf-8')
                
                cr.execute("UPDATE tbl_user SET bln_otp_verified = true WHERE vchr_email = %s",(str_email,))
                ins_db.commit()
                return {'token': token}, 200

            
        except Exception:
            traceback.print_exc()
            return {"message": "OTP verification Failed"}, 400

        finally:
            if ins_db:ins_db.close()
        

    @staticmethod
    def user_login(request):
        try:
            dct_request = request.json
            str_email = dct_request.get("email")
            str_password = dct_request.get('password')

            if not str_email or not str_password:
                return {'message': 'Email and password are required'}, 400


            ins_db=psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
            
            with create_cursor(ins_db) as cr:
                hashed_password = hashlib.sha256(str_password.encode()).hexdigest()
                cr.execute("SELECT bln_otp_verified FROM tbl_user WHERE vchr_email = %s AND vchr_hashed_password = %s",(str_email,hashed_password))
                rst_user = cr.fetchone()
                if not rst_user:
                    return {'message': 'Invalid credentials'}, 401
                
                if not rst_user['bln_otp_verified']:
                    int_otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                    cr.execute("""UPDATE tbl_user SET int_otp = %s WHERE vchr_email = %s""",(int(int_otp),str_email))
                    ins_db.commit()
                    amadeusExtensionService.send_otp_email(str_email,int_otp)
                    return {'message': 'OTP sent to email', 'email': str_email} , 200
                

                token = jwt.encode({
                    'email': str_email,
                    'exp': datetime.utcnow() + timedelta(hours=24)
                }, SECRET_KEY).decode('utf-8')
                
                return {'token': token}, 200

            
        except Exception:
            traceback.print_exc()
            return {"message": "OTP verification Failed"}, 400

        finally:
            if ins_db:ins_db.close()  
    
    @staticmethod
    def send_otp_email(email, otp):
        msg = MIMEText(f"Your OTP for registration is: {otp}")
        msg["Subject"] = "OTP Verification"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = email
        
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
        except Exception as e:
            return str(e)

    @staticmethod
    def generate_ai_response(request,ins_db,user_id):
        try:
            dct_request = request.json
            str_data = dct_request.get('strQuery')
            str_question = dct_request.get('strPrompt')
            if not str_data:
                return {"message": "No data to Generate"}, 400
            
            str_system_prompt = amadeus_ai_rule_analyser_prompt.replace('$_str_data',str_data)
            messages = [{'role':'system','content':str_system_prompt}]
            if str_question:
                messages.append({'role':'user','content':str_question})
            
            # Reduce user credit by 1 for a promt and a response  
            with create_cursor(ins_db) as cr:
                
                # Checking subscription plan is active
                cr.execute("""
                            SELECT 1 
                            FROM tbl_user_subscription_details
                            WHERE fk_bint_user_id = %s
                            AND tim_start_sub <= now() 
                            AND tim_end_sub >= now()
                            AND bint_available_credits !=0 ;
                            """,
                            (user_id,))
                
                rst_subscription_is_active = cr.fetchone() 
                
                if not rst_subscription_is_active:
                    return {"error": "Subscription has expired. Please renew to continue using the service."},400
                
                cr.execute("""
                            UPDATE tbl_user_subscription_details 
                            SET bint_available_credits = bint_available_credits - 1 
                            WHERE fk_bint_user_id = %s AND tim_start_sub <= now()
                            AND tim_end_sub >= now();
                            """,
                            (user_id,))
                
                ins_db.commit()
                
                response = client.chat.completions.create(
                            model=azure_deployment,
                            messages=messages,
                            temperature=0.3)
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                
                str_response = response.choices[0].message.content
                executor.submit(amadeusExtensionService.save_to_logs,user_id,str_data,str_question,str_response,prompt_tokens,completion_tokens)
                return {"message": str_response}
        
        except Exception:
            traceback.print_exc()
            return {"message": "Unable to Generate"}, 400

        finally:
            if ins_db:ins_db.close() 


    @staticmethod
    def get_city(request):
        try:
            str_key = request.json.get("strAutoComplete")
            ins_db=psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
            
            with create_cursor(ins_db) as cr:
                cr.execute("""
                    SELECT 
                        ct.id AS city_id,
                        ct.name AS city_name,
                        ct.country_code,
                        cy.name AS country_name,
                        cy.phonecode AS phone_code
                    FROM tbl_city ct
                    INNER JOIN tbl_country cy ON ct.country_id = cy.id
                    WHERE ct.name ILIKE %s
                    ORDER BY 
                        CASE 
                            WHEN ct.name ILIKE %s THEN 0
                            ELSE 1
                        END,
                        ct.name
                    LIMIT 10
                """, (f'%{str_key}%', f'{str_key}%',))
                rst_city = cr.fetchall()
                lst_city = [dict(record) for record in rst_city]

                return lst_city,200
            
        except Exception:
            traceback.print_exc()
            return {"message": "Unable to load"}, 400
        
        finally:
            if ins_db:ins_db.close() 


    @staticmethod
    def delete_user(request,ins_db):
        try:
            dct_request = request.json
            str_email = dct_request.get('strEmail')
            
            with create_cursor(ins_db) as cr:
                cr.execute("DELETE FROM tbl_user WHERE vchr_email = %s",(str_email,))
                ins_db.commit()

                return {"message": "User deleted successfully"}, 200
            
        except Exception:
            traceback.print_exc()
            return {"message": "Unable to delete user"}, 400
        
        finally:
            if ins_db:ins_db.close() 


    @staticmethod
    def save_to_logs(user_id,str_data,str_question,str_response,prompt_tokens,completion_tokens):
        try:
            ins_db=psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
            
            with create_cursor(ins_db) as cr:
                cr.execute("""INSERT INTO tbl_logs (fk_bint_user_id,vchr_data,vchr_question,vchr_response,bint_input_token_usage,bint_output_token_usage,tim_created)
                              VALUES (%s,%s,%s,%s,%s,%s,'NOW()')""",(user_id,str_data,str_question,str_response,prompt_tokens,completion_tokens))
                ins_db.commit()
                return 
            
        except Exception:
            traceback.print_exc()
            return 
        
        finally:
            if ins_db:ins_db.close() 
            
    @staticmethod
    def get_all_logs(request,ins_db,user_id):
        try:
            
            with create_cursor(ins_db) as cr:
                # Check user permission (only amadeus admin can access)
                cr.execute("SELECT bln_admin FROM tbl_user WHERE pk_bint_user_id = %s",(user_id,))
                rst_users_permission = cr.fetchone()[0]
                if not rst_users_permission:
                    return {"error":"No Permission"},400
                dct_request = request.json
                str_start_date = dct_request['objFilter'].get('strStartDate')
                str_end_date = dct_request['objFilter'].get('strEndDate')
                int_user_id = dct_request['objFilter'].get('intUserId')
                
                int_page_offset = dct_request["objPagination"].get("intPageOffset")
                int_page_limit = dct_request["objPagination"].get("intPerPage")
                int_offset = int_page_offset * int_page_limit
                lst_filters=[]
                
                str_query="""SELECT 
                                    u.vchr_user_name,
                                    u.vchr_company,
                                    l.vchr_data, 
                                    l.vchr_question,
                                    l.vchr_response,
                                    l.bint_input_token_usage,
                                    l.bint_output_token_usage,
                                    l.tim_created 
                                FROM 
                                    tbl_logs l
                                JOIN 
                                    tbl_user u 
                                ON 
                                    l.fk_bint_user_id = u.pk_bint_user_id"""
                
                if str_start_date and str_end_date:
                    str_date_filter = f"date(tim_created) >= '{str_start_date}' AND date(tim_created) <= '{str_end_date}' "
                    lst_filters.append(str_date_filter)
                
                if int_user_id :
                    str_user_filter = f"l.fk_bint_user_id = {int_user_id}"
                    lst_filters.append(str_user_filter)
                if lst_filters:
                    str_query += ' WHERE ' + ' AND '.join(lst_filters)  
                
                # Add pagination to the query
                str_query += " ORDER BY l.tim_created DESC LIMIT %s OFFSET %s " % (int_page_limit, int_offset)
            
                cr.execute(str_query)
                rst_logs = cr.fetchall()
                
                if not rst_logs:
                    return {"error":"No records Found"},400
                arr_logs = []
                
                
                int_serial = int_offset
                for record in rst_logs:
                    int_serial +=1
                    cost = (record['bint_input_token_usage'] / 1000) * 0.21084438 + (record['bint_output_token_usage'] / 1000) * 0.8433376
                    dct_log = {
                        "slNo": int_serial,
                        "strUserName":record["vchr_user_name"], 
                        "strCompany":record["vchr_company"],
                        "strData":record["vchr_data"] , 
                        "strQuestion": record["vchr_question"], 
                        "strResponse": record["vchr_response"], 
                        "tim_created":record["tim_created"],
                        "strCost": f"₹ {cost:.2f}"
                        }
                    arr_logs.append(dct_log)
                    
                return jsonify(arr_logs)
            
        except Exception:
            traceback.print_exc()
            return 
        
        finally:
            if ins_db:ins_db.close() 
    @staticmethod
    def get_all_users(ins_db,user_id):
        try:
            with create_cursor(ins_db) as cr:
                # Check user permission (only amadeus admin can access)
                cr.execute("SELECT bln_admin FROM tbl_user WHERE pk_bint_user_id = %s",(user_id,))
                rst_permission = cr.fetchone()[0]
                if not rst_permission:
                    return {"error":"No Permission"},400
            
                
                cr.execute("SELECT pk_bint_user_id,vchr_user_name  FROM tbl_user")
                rst_users = cr.fetchall()
                users = [{"intUserId": row[0], "strUserName": row[1]} for row in rst_users]
                return jsonify(users)
        except Exception as e:
            traceback.print_exc()
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def check_permissions(ins_db,user_id):
        try:
            with create_cursor(ins_db) as cr:
                cr.execute("SELECT bln_admin FROM tbl_user WHERE pk_bint_user_id = %s",(user_id,))
                rst_users = cr.fetchone()[0]
                if not rst_users:
                    return {"error":"No Permission"},400
        except Exception:
            traceback.print_exc()
        finally:
            if ins_db:
                ins_db.close()     
                
    @staticmethod            
    def get_user_sub_details(ins_db,user_id):
        try:           
            with create_cursor(ins_db) as cr :
                cr.execute("SELECT * FROM tbl_user_subscription_details WHERE fk_bint_user_id = %s LIMIT 1",(user_id,))
                rst_user_sub_details = cr.fetchone()
                
                tim_end_sub = rst_user_sub_details.get('tim_end_sub').strftime('%d/%m/%Y') 
                tim_start_sub = rst_user_sub_details.get('tim_start_sub').strftime('%d/%m/%Y')
                
                dct_user_sub_details = {'strSubName':rst_user_sub_details['vchr_sub_name'],
                        'intCreditsUsed':int(f"{rst_user_sub_details['bint_available_credits']}"),
                        'timEndSub':tim_end_sub,
                        'timStartSub':tim_start_sub
                        }
                return jsonify(dct_user_sub_details)
                
        except Exception:
            traceback.print_exc()
        finally:
            if ins_db:
                ins_db.close()
    
        
    @staticmethod            
    def get_all_users_sub_details(request,ins_db,user_id):
        
        try:
            dct_request = request.json
            int_user_id = dct_request.get('intUserId')
            
            with create_cursor(ins_db) as cr :
                # Check user permission (only amadeus admin can access)
                cr.execute("SELECT bln_admin FROM tbl_user WHERE pk_bint_user_id = %s",(user_id,))
                rst_permission = cr.fetchone()[0]
                if not rst_permission:
                    return {"error":"No Permission"},400
                
                str_query = """
                            SELECT 
                                usd.vchr_sub_name,
                                usd.tim_start_sub,
                                usd.tim_end_sub,
                                usd.fk_bint_user_id,
                                usd.bint_available_credits,
                                u.vchr_email,
                                u.vchr_user_name 
                            FROM 
                                tbl_user_subscription_details usd
                            LEFT JOIN
                                tbl_user u
                            ON 
                                usd.fk_bint_user_id = u.pk_bint_user_id """ 
                                
                if int_user_id:
                    str_query += f"WHERE usd.fk_bint_user_id = {int_user_id}"
                    
                cr.execute(str_query)
                    
                rst_user_sub_details = cr.fetchall()
                
                if not rst_user_sub_details:
                    return {"error":"No records Found"},400
                arr_user_sub_details = []
                serial_count = 0
                for record in rst_user_sub_details:
                    tim_end_sub = record['tim_end_sub'].strftime('%d/%m/%Y') 
                    tim_start_sub = record['tim_start_sub'].strftime('%d/%m/%Y')
                    serial_count+=1
                    dct_user_sub_details = {
                        
                            'slNo': serial_count,
                            'strUserName':record['vchr_user_name'],
                            'strSubName':record['vchr_sub_name'],
                            'strEmailId':record['vchr_email'],
                            'intCreditsUsed':int(f"{record['bint_available_credits']}"),
                            'timEndSub':tim_end_sub,
                            'timStartSub':tim_start_sub,
                            'intUserId' :record['fk_bint_user_id']
                            }
                    arr_user_sub_details.append(dct_user_sub_details)
                return jsonify(arr_user_sub_details)
                
        except Exception:
            traceback.print_exc()
        finally:
            if ins_db:
                ins_db.close()
                
    @staticmethod
    def update_subscription(request,ins_db,user_id):
        try:
            dct_request = request.json
            str_sub_name = dct_request.get('strSubName')
            int_user_id = dct_request.get('intUserId')
            
            # str_today_date refer to start date
            str_today_date = datetime.now(timezone.utc) 
            
            with create_cursor(ins_db) as cr:
                # Only Amadeus admin update the subscription
                cr.execute("SELECT bln_admin FROM tbl_user WHERE pk_bint_user_id = %s",(user_id,))
                rst_permission = cr.fetchone()[0]
                if not rst_permission:
                    return {"error":"No Permission"},400
                
                cr.execute(""" 
                            SELECT bint_available_credits, tim_start_sub,tim_end_sub 
                            FROM tbl_user_subscription_details 
                            WHERE fk_bint_user_id = %s LIMIT 1;
                            """,(int_user_id,))
                
                rst_sub_details = cr.fetchone()
            
                # Checking the subscription is expired or not , if subscription date is Expired then update the tim_start_sub to today's date
                if rst_sub_details['tim_end_sub'] < str_today_date:
                    if str_sub_name == 'Basic / Free':
                        int_credits_to_add = 10000
                        str_end_date = str_today_date + timedelta(days=60)
                        
                    if str_sub_name == 'Silver':
                        int_credits_to_add = 20000
                        str_end_date = str_today_date + timedelta(days=180)
                        
                    if str_sub_name == 'Gold':
                        int_credits_to_add = 999999
                        str_end_date = str_today_date + timedelta(days=365)
                        
                    cr.execute("""UPDATE tbl_user_subscription_details
                                SET vchr_sub_name = %s ,
                                tim_start_sub = %s,
                                tim_end_sub = %s,
                                bint_available_credits = %s
                            WHERE fk_bint_user_id = %s""",
                            (
                            str_sub_name,
                            str_today_date,
                            str_end_date,
                            int_credits_to_add,
                            int_user_id
                        ))
                    ins_db.commit()
                else:
                    # if Subscription is not expired 
                    if str_sub_name == 'Basic / Free':
                        int_credits_to_add = rst_sub_details['bint_available_credits'] + 10000
                        str_end_date = str_today_date + timedelta(days=60)
                        
                    if str_sub_name == 'Silver':
                        int_credits_to_add = rst_sub_details['bint_available_credits'] + 20000
                        str_end_date = str_today_date + timedelta(days=180)
                        
                    if str_sub_name == 'Gold':
                        int_credits_to_add = rst_sub_details['bint_available_credits'] + 999999
                        str_end_date = str_today_date + timedelta(days=365)
                        
                    cr.execute("""UPDATE tbl_user_subscription_details
                            SET vchr_sub_name = %s ,
                            tim_start_sub = %s,
                            tim_end_sub = %s,
                            bint_available_credits = %s
                        WHERE fk_bint_user_id = %s""",
                        (
                        str_sub_name,
                        str_today_date,
                        str_end_date,
                        int_credits_to_add,
                        int_user_id
                    ))
                    ins_db.commit()
                    
            return {"message": "User subscription updated successfully."},200

    
        except Exception:
            traceback.print_exc()
            
        finally:
            if ins_db:
                ins_db.close()
        
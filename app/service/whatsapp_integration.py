from flask import jsonify,Response
import requests
import traceback
import lancedb 
import base64
import json
from app.utils.generalMethods import get_tenancy_id,create_cursor,dct_error,dct_response
from app.schema.lancedb import EmbeddedWhatsappAccounts
from app.service.whatsapp_services import whatsappServices
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.executor import executor
from datetime import timedelta
from app.utils.conf_path import str_configpath
from app.utils.global_config import env_mode


ins_configuration = ConfigParserCrypt()
ins_configuration.read(str_configpath)

VERIFY_TOKEN = ins_configuration.get(env_mode, 'WHATSAPP_VERIFY_TOKEN')
APP_ID = ins_configuration.get(env_mode, 'WHATSAPP_APP_ID')

# set a global list to keep incoming whatsapp message ids, used to avoid retry from hooks calls.
lst_message_ids = []

class whatsappWebhook:

    @staticmethod
    def handle_verification(request): 
        try:
            mode = request.args.get('hub.mode')
            token = request.args.get('hub.verify_token')
            challenge = request.args.get('hub.challenge')
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return Response(challenge, 200,{'Content-Type': 'text/plain'})
            return "Forbidden", 403
        except Exception as e:
            print(f"Error sending message: {e}")

    @staticmethod
    def handle_message_event(request,ins_db):
        try:
            body = request.get_json()
            if body.get("object"):
                #getting phone number id 
                phone_number_id = body["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
                
                #using phone number id (onboarded number id) fetching details ,bot id and access_token etc,
                #if no bot selected replay on a default  message
                #the access token is required for verifying and interacting with Meta's API.
                
                with create_cursor(ins_db) as cr:
                    cr.execute("""SELECT 
                                    b.pk_bint_bot_id,
                                    b.vchr_azure_resource_uuid,
                                    wbm.vchr_tenancy_id,
                                    wbm.vchr_access_token,
                                    b.vchr_bot_type,
                                    b.fk_bint_created_user_id,
                                    b.bln_agent,
                                    b.json_config
                                FROM tbl_bots as b 
                                    RIGHT JOIN tbl_whatsapp_bussiness_mapping as wbm
                                    ON b.pk_bint_bot_id = wbm.fk_bint_bot_id  
                                WHERE wbm.vchr_phone_number_id = %s""",(phone_number_id,))
                    
                    rst_bot_details=cr.fetchone()
                    # If no bot details are found for the given phone number ID, return an error response
                    if not rst_bot_details:
                        return dct_error('Bot details not found'),400
                    
                    int_bot_id=rst_bot_details['pk_bint_bot_id'] #bot id
                    str_bot_uuid=rst_bot_details['vchr_azure_resource_uuid'] #bot uuid 
                    str_tenancy_id=rst_bot_details['vchr_tenancy_id'] #tenancy id (enancy id is required because we dont know the onboarded number is under which tenant)
                    str_access_token=rst_bot_details['vchr_access_token'] 
                    str_bot_type=rst_bot_details['vchr_bot_type']
                    int_bot_created_user_id=rst_bot_details['fk_bint_created_user_id']
                    bln_agent = rst_bot_details['bln_agent']
                    dct_agent = rst_bot_details['json_config']
                    # This is specifically checking for the message webhook.
                    if (
                            body.get("entry")
                            and body["entry"][0].get("changes")
                            and body["entry"][0]["changes"][0].get("value")
                            and body["entry"][0]["changes"][0]["value"].get("messages")
                            and body["entry"][0]["changes"][0]["value"]["messages"][0]
                        ):
                        # avoid retry same message from whatsapp apis
                        message_id = body["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
                        if message_id in lst_message_ids:
                            return
                        else:
                            lst_message_ids.append(message_id)
                            
                        # Mark the received WhatsApp message as read using the provided access token  
                        executor.submit(whatsappServices.mark_read_and_typing,body,str_access_token)

                        whatsappServices.process_whatsapp_incoming_message(
                            ins_db,body,int_bot_id,str_tenancy_id,str_access_token,str_bot_uuid,int_bot_created_user_id,str_bot_type,bln_agent,dct_agent
                        )
                        # finally remove from ids
                        if message_id in lst_message_ids:
                            lst_message_ids.remove(message_id)
                            
                    # This is specifically checking for the status webhook.
                    if (
                            body.get("entry")
                            and body["entry"][0].get("changes")
                            and body["entry"][0]["changes"][0].get("value")
                            and body["entry"][0]["changes"][0]["value"].get("statuses")
                            and body["entry"][0]["changes"][0]["value"]["statuses"][0]
                            and body["entry"][0]["changes"][0]["value"]["statuses"][0].get("conversation")
                        ) and int_bot_id is not None:
                       
                       whatsappServices.manage_whatsapp_status_update(body,ins_db,int_bot_id,str_tenancy_id,str_bot_uuid,int_bot_created_user_id,bln_agent)
            else:
                return (
                    jsonify({"status": "error", "message": "Not a WhatsApp API event"}),
                    404,
                ) 
                
        except Exception as e :
            traceback.print_exc()
            
        finally:
            if ins_db:
                ins_db.close()
            
    
    @staticmethod
    def add_embedded_signup_details(request,ins_db):
        try:
            
            dct_request=request.json
            str_code = dct_request['strCode']
            str_tenancy_id = get_tenancy_id(request.headers)
            cr = create_cursor(ins_db)
            
            # Request access token
            dct_access_token = requests.get(
                    "https://graph.facebook.com/v17.0/oauth/access_token",
                    params={
                        "client_id":ins_configuration.get(env_mode, 'WHATSAPP_APP_ID'),
                        "client_secret":ins_configuration.get(env_mode, 'WHATSAPP_APP_SECRET'),
                        "code":str_code ,
                    }
            )
            
            if dct_access_token.status_code == 200:                
                dct_access_token = dct_access_token.json()
                access_token = dct_access_token.get("access_token", "").replace("Bearer ", "")
                # system user token from the nucore servie 
                headers = {'Authorization':ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN'),
                       "Content-Type": "application/json" }
                
                dct_debug_token_response = requests.get(
                            "https://graph.facebook.com/v17.0/debug_token",
                            headers=headers,
                            params={
                                "input_token": access_token
                                }
                            )
                
                if dct_debug_token_response.status_code == 200:
                    dct_debug_token_response = dct_debug_token_response.json()

                    str_waba_id = dct_debug_token_response['data']['granular_scopes'][0]['target_ids'][0]
                    
                    #to get all onboarded number details under a waba id
                    dct_phone_details = requests.get(
                            f"https://graph.facebook.com/v17.0/{str_waba_id}/phone_numbers",
                            params={"access_token":access_token}
                    )
                    dct_phone_details = dct_phone_details.json()
                    
                    for record in dct_phone_details['data']:
                        dct_waba_details = {
                                "strPhoneNumberId" : record['id'],
                                "strName":record['verified_name'],
                                "strVerificationStatus" : record['code_verification_status'],
                                "strQualityRating":record["quality_rating"],
                                "strPhoneNumber":record['display_phone_number'].replace(' ','').replace('+',''),
                                "strWabaId":str_waba_id
                        }

                         # Check if phone number already exists
                        cr.execute("SELECT * FROM tbl_whatsapp_bussiness_mapping WHERE vchr_phone_number_id = %s AND vchr_phone_number = %s",(record['id'],dct_waba_details['strPhoneNumber']))
                        rst_already_exist=cr.fetchone()
                        
                        if not rst_already_exist:
                            
                            # Store in LanceDB
                            db_lance = lancedb.connect(f"lancedb/whatsapp",read_consistency_interval=timedelta(seconds=0))
                            try:
                                table = db_lance.open_table("embedded_whatsapp_accounts")
                            except ValueError:
                                table = db_lance.create_table("embedded_whatsapp_accounts", schema = EmbeddedWhatsappAccounts, exist_ok = True)
        
                            #keeping onboarded number id and tenency id for get ins_db
                            table.add([{"phone_number_id":dct_waba_details['strPhoneNumberId'],"tenancy_id":str_tenancy_id}])
                            
                            cr.execute("""INSERT INTO tbl_whatsapp_bussiness_mapping(
                                                vchr_waba_id,
                                                vchr_phone_number_id,
                                                vchr_tenancy_id,
                                                vchr_access_token,
                                                vchr_phone_number,
                                                vchr_verified_name,
                                                vchr_account_status,
                                                vchr_quality_rating,
                                                tim_timestamp) 
                                                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,NOW())""",
                                                (
                                                dct_waba_details['strWabaId'],
                                                dct_waba_details['strPhoneNumberId'],
                                                str_tenancy_id,
                                                access_token,
                                                dct_waba_details['strPhoneNumber'],
                                                dct_waba_details['strName'],
                                                dct_waba_details['strVerificationStatus'],
                                                dct_waba_details['strQualityRating']
                                                )
                                        )
                            
                            ins_db.commit()
                            
                            return {'strPhoneNumberId': record['id'],'strWabaId':str_waba_id}, 200
        

        except Exception as e:
            traceback.print_exc()
            print(f"Error while adding accounts in lancedb: {e}")
        finally:
            if ins_db:
                ins_db.close()
                    
    @staticmethod
    def get_all_embedded_accounts(ins_db):
        try:
            with create_cursor(ins_db) as cr:
                cr.execute("""SELECT 
                                wbm.vchr_waba_id,
                                wbm.vchr_phone_number_id,
                                wbm.vchr_phone_number,
                                wbm.fk_bint_bot_id,
                                wbm.vchr_verified_name,
                                wbm.vchr_account_status,
                                wbm.vchr_about,
                                wbm.vchr_address,
                                wbm.vchr_profile_picture,
                                wbm.vchr_quality_rating,
                                b.vchr_bot_name ,
                                b.vchr_icon,
                                b.bln_agent
                            FROM 
                                tbl_whatsapp_bussiness_mapping wbm 
                            LEFT JOIN
                                tbl_bots b ON b.pk_bint_bot_id = wbm.fk_bint_bot_id  """)
                rst_waba_details=cr.fetchall()
                lst_waba_details=[]
                for record in rst_waba_details:
                    dct_waba_details={
                        "strWabaId":record["vchr_waba_id"],
                        "strPhoneNumberId":record["vchr_phone_number_id"],
                        "strPhoneNumber":record["vchr_phone_number"],
                        "strVerifiedName":record["vchr_verified_name"],
                        "strAccountStatus":record["vchr_account_status"],
                        "strQualityRating":record["vchr_quality_rating"],
                        "strAbout":record["vchr_about"],
                        "strAddress":record["vchr_address"],
                        "strProfilePicture":record["vchr_profile_picture"] if record["vchr_profile_picture"] else "assets/images/no-profile.png"
                        
                    }
                    if record["fk_bint_bot_id"] or record["vchr_bot_name"] or record["vchr_icon"]:
                        dct_waba_details["objBotDetails"] = {
                            "intBotId":record["fk_bint_bot_id"],
                            "strBotName":record["vchr_bot_name"],
                            "strIcon":record["vchr_icon"],
                            "blnAgent":record["bln_agent"]
                        }    
                    lst_waba_details.append(dct_waba_details)
                    
                return {"arrWabaDetails":lst_waba_details}
        except Exception:
            traceback.print_exc()
            
    @staticmethod
    def assign_bot_to_onboarded_number(request,ins_db):
        try:
            dct_request=request.json
            strPhoneNumberId=dct_request["strPhoneNumberId"]
            intBotId=dct_request["intBotId"]
            with create_cursor(ins_db) as cr:
                cr.execute("SELECT 1 FROM tbl_whatsapp_bussiness_mapping WHERE vchr_phone_number_id = %s",(strPhoneNumberId,))
                rst_phonenumber_id=cr.fetchone()
                if not rst_phonenumber_id:
                    return dct_error("No record found")
                else:
                    cr.execute("UPDATE tbl_whatsapp_bussiness_mapping SET fk_bint_bot_id=%s WHERE  vchr_phone_number_id =%s",(intBotId,strPhoneNumberId))
                    ins_db.commit()
                return dct_response(200,'successfully updated')
            
        except Exception as e:
            traceback.print_exc()
        finally:
            if ins_db:
                ins_db.close()
        
    @staticmethod
    def enable_two_factor_authentication(request,ins_db,user_id):
        try:
            dct_request = request.json
            str_phone_number_id = dct_request['strPhoneNumberId']
            str_waba_id = dct_request['strWabaId']
            str_two_factor = dct_request['strTwoFactorCode']
            
            with create_cursor(ins_db) as cr:
                cr.execute("UPDATE tbl_whatsapp_bussiness_mapping SET vchr_two_factor_code = %s WHERE vchr_phone_number_id = %s",(str_two_factor,str_phone_number_id))
                ins_db.commit()
                dct_two_factor_code = {
                                    "messaging_product": "whatsapp",
                                    "pin": str_two_factor
                                    }
                
                headers = {'Authorization':ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN'),
                            "Content-Type": "application/json" }

                response = requests.post(
                            f"https://graph.facebook.com/v17.0/{str_phone_number_id}/register",
                            headers=headers,
                            json=dct_two_factor_code)
                
                if response.status_code != 200:
                    return dct_response(400, f"Failed to register: {response.text}")

                response = requests.post(
                        f"https://graph.facebook.com/v17.0/{str_waba_id}/subscribed_apps",
                        headers=headers
                        )
                if response.status_code == 200:
                    return dct_response(200, "Registered successfully")
                else:
                    return dct_response(400, f"Failed to subscribe apps: {response.text}")
                
        except Exception as msg:
            traceback.print_exc()
        finally:
            if ins_db:
                ins_db.close()
                
    @staticmethod
    def update_profile_settings(request,ins_db,user_id):
        try:
            dct_request = request.json
            str_phone_number_id = dct_request['strPhoneNumberId']
            str_about = dct_request['strAbout']
            str_profile_picture_base_64=dct_request['strProfilePicture']
            str_image_type = dct_request["strMimeType"]
            str_profile_picture_name=dct_request["strDisplayPictureName"]
            str_address=dct_request['strAddress']

            with create_cursor(ins_db) as cr:
                cr.execute("""SELECT 
                                vchr_profile_picture,
                                vchr_about,
                                vchr_address
                            FROM 
                                tbl_whatsapp_bussiness_mapping
                            WHERE 
                                vchr_phone_number_id = %s
                                """,(str_phone_number_id,))
                
                rst_profile_details=cr.fetchone()
                # Update About Section: Check if there are no existing profile details OR the stored 'About' is None OR the new 'About' value is different from the stored one.  
                # The reason for this check is that after onboarding a new number (via embedded signup), its profile settings—profile picture, 'About', and address—are empty (returned as None from the db).  
                # So If 'rst_profile_details' is empty, we need to update it with the provided payload.(THis checking is following in all the updates of profile settings)
                
                if not rst_profile_details or rst_profile_details['vchr_about'] is None or str_about != rst_profile_details['vchr_about']:

                    if  str_about and str_about.strip() !="":
                        print("updating vchr_about")
                        cr.execute("""UPDATE 
                                        tbl_whatsapp_bussiness_mapping
                                    SET 
                                        vchr_about = %s
                                    WHERE 
                                        vchr_phone_number_id = %s
                                    """,(str_about,str_phone_number_id,))
                        
                        ins_db.commit()
                        
                        headers = {'Authorization':ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN')}
                        dct_about = {
                                    "messaging_product": "whatsapp",
                                    "about": str_about
                                }
                    
                        about_update_response = requests.post(f"https://graph.facebook.com/v22.0/{str_phone_number_id}/whatsapp_business_profile",
                                                headers=headers,
                                                json=dct_about)
                        if about_update_response.status_code !=200:
                            return dct_error("About update failed"),400
                        
                # Update Address Section
                if not rst_profile_details or rst_profile_details['vchr_address'] is None or str_address != rst_profile_details['vchr_address']: 
                    if  str_address and str_address.strip() !="":
                        
                        print("updating vchr_address")
                        cr.execute("""UPDATE 
                                        tbl_whatsapp_bussiness_mapping
                                    SET 
                                        vchr_address = %s
                                    WHERE 
                                        vchr_phone_number_id = %s
                                    """,(str_address,str_phone_number_id,))
                        ins_db.commit()
                        headers = {'Authorization':ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN'),
                                    "Content-Type": "application/json" }
                        
                        dct_address = {
                                    "messaging_product": "whatsapp",
                                    "address": f"{str_address}"
                                    }
                        
                        address_update_response=requests.post(f"https://graph.facebook.com/v22.0/{str_phone_number_id}/whatsapp_business_profile",
                                                headers=headers,
                                                json=dct_address)
                        
                        if address_update_response.status_code !=200:
                            return dct_error("Address update failed"),400
                        
                    
                # Update Profile Picture
                if not rst_profile_details or rst_profile_details['vchr_profile_picture'] is None or str_profile_picture_base_64 != rst_profile_details['vchr_profile_picture']:
                    
                    if str_profile_picture_base_64 and str_profile_picture_base_64.strip() != "" and str_profile_picture_base_64 != 'assets/images/no-profile.png':
                        print("update profile picture")
                        cr.execute("""UPDATE 
                                        tbl_whatsapp_bussiness_mapping
                                    SET 
                                        vchr_profile_picture = %s
                                    WHERE 
                                        vchr_phone_number_id = %s
                                    """,(str_profile_picture_base_64,str_phone_number_id,))
                        ins_db.commit()
                        
                        # Decode base64 image into binary
                        imgae_file_in_binary = base64.b64decode(str_profile_picture_base_64.split(",")[1])
                        file_length=str(len(imgae_file_in_binary))
                        
                        headers = {'Authorization':ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN'),
                                    "Content-Type": "application/json" }
                        
                        #STEP 1: Upload Session (TO GET THE UPLOADED_SESSION_ID )
                        upload_url = f"https://graph.facebook.com/v22.0/{APP_ID}/uploads"
                        params = {
                            "file_name": str_profile_picture_name,
                            "file_length": file_length,
                            "file_type": str_image_type,
                            "access_token": ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN').replace("Bearer","").strip()
                        }
                        
                        """
                        Sample Response
                        {"id": "upload:<UPLOAD_SESSION_ID>"}
                        """
                        response = requests.post(upload_url, params=params)
                        
                        if response.status_code != 200:
                            return dct_error("Failed to get upload session id"), 400
                        
                        # Extract Upload Session ID
                        upload_response = response.json()
                        upload_session_id = upload_response["id"].split(":")[1]  

                            
                        #STEP 2: Uploading the file 
                        upload_url = f"https://graph.facebook.com/v22.0/upload:{upload_session_id}"

                        headers = {
                            "Authorization": f"OAuth {ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN').replace('Bearer','').strip()}",
                            "file_offset": "0"
                        }

                        """ Sample Response(this is the data for file handle)
                            {"h": "2:c2FtcGxl..."}"""
                               
                        response = requests.post(upload_url, headers=headers, data=imgae_file_in_binary)
                        
                        if response.status_code != 200:
                            return dct_error("Profile picture file upload failed"), 400

                        upload_response = response.json()
                        file_handle = upload_response.get("h")
                            
                        
                        #STEP 3: update profile picture using the file_handle
                        profile_url = f"https://graph.facebook.com/v22.0/{str_phone_number_id}/whatsapp_business_profile"

                        data = {
                            "messaging_product": "whatsapp",
                            "profile_picture_handle": file_handle  
                        }
                        
                        headers = {'Authorization':ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN'),
                                    "Content-Type": "application/json" }
                        
                        response = requests.post(profile_url, headers=headers, json=data)
                        if response.status_code != 200:
                            return dct_error("Profile picture update failed"), 400


                        
            return dct_response(200,"Updated Successfully ")
                                                                
                     
        except Exception as e :
            traceback.print_exc()
        finally:
            if ins_db:
                ins_db.close()
                
    @staticmethod
    def create_template(request,ins_db,user_id):
        try:
            dct_request = request.json
            str_template_name = dct_request.get('strTemplateName')
            str_category = dct_request.get('strCategory')
            bln_category_change = dct_request.get('blnCategoryChange')
            str_language = dct_request.get('strLanguageCode')
            json_components = dct_request.get('arrTemplateComponents') or []
            str_phone_id = dct_request.get('strPhoneNumberId')

            with create_cursor(ins_db) as cr:
                
                if str_phone_id:
                    cr.execute(""" SELECT * FROM tbl_whatsapp_bussiness_mapping WHERE vchr_phone_number_id = %s""",(str_phone_id,))
                    rst_waba_details = cr.fetchone()
                    if not rst_waba_details:
                        return dct_error("Phone id is not Valid!!")
                else:
                    return dct_error("Phone is required!!!")
                

                headers = {'Authorization': ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN') }
                json_data = {

                    "name":str_template_name,
                    'language':str_language,
                    "category":str_category,
                    "components":json_components,
                    "allow_category_change":bln_category_change,

                }

                
                response = requests.post(
                                f"https://graph.facebook.com/v22.0/{rst_waba_details['vchr_waba_id']}/message_templates",
                                headers = headers,
                                json=json_data
                            )
                print(response.text)
                if response.status_code == 200:
                    json_response = response.json()

                    cr.execute(""" INSERT INTO tbl_whatsapp_templates( 
                                        vchr_template_name, 
                                        vchr_category, 
                                        bln_allow_category_change, 
                                        vchr_language, 
                                        arr_components, 
                                        fk_bint_whatsapp_bussiness_mapping_id,
                                        vchr_template_status,
                                        vchr_whatsapp_template_id,
                                        tim_created)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s,NOW())""",(str_template_name,
                                                                    json_response['category'],
                                                                    bln_category_change,
                                                                    str_language,
                                                                    json.dumps(json_components),
                                                                    rst_waba_details['pk_bint_whatsapp_bussiness_mapping_id'],
                                                                    json_response['status'],
                                                                    json_response['id']))

                    return dct_response("success","Template created successfully"),200
                
                else:
                    json_response = response.json()
                    if json_response.get('error'):
                        return dct_error(json_response.get('error')['error_user_msg']),400
                    else:
                        return dct_error(json_response),400

        except Exception as msg:
            traceback.print_exc()
            return dct_error(str(msg)),400
            
        finally:
            if ins_db:
                ins_db.commit()
                ins_db.close()
            
        
    @staticmethod
    def get_all_tempaltes(request,ins_db):
        try:
            dct_request = request.json
            
            with create_cursor(ins_db) as cr:
                cr.execute(""" SELECT * FROM tbl_whatsapp_bussiness_mapping WHERE vchr_phone_number_id = %s""",(dct_request['strPhoneNumberId'],))
                
                rst_waba_details = cr.fetchone()
                if not rst_waba_details:
                    return dct_error("Phone id is not Valid!!")
                
                cr.execute(""" SELECT 
                                    vchr_template_name 
                                FROM 
                                    tbl_whatsapp_templates 
                                WHERE 
                                    fk_bint_whatsapp_bussiness_mapping_id 
                                    = 
                                (
                                SELECT
                                    pk_bint_whatsapp_bussiness_mapping_id 
                                FROM 
                                    tbl_whatsapp_bussiness_mapping
                                WHERE  
                                    vchr_phone_number_id = %s
                                    
                                )""",(dct_request['strPhoneNumberId'],))
                
                rst_template_details = cr.fetchall()
                if not rst_template_details:
                    return dct_error("No Record Found"),400
                
                dct_params = {
                    "fields":"name,status,components,language,quality_score,category"
                    
                }
                
                headers = {'Authorization': ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN')}
                response = requests.get(
                                f"https://graph.facebook.com/v22.0/{rst_waba_details['vchr_waba_id']}/message_templates",
                                headers = headers,
                                params=dct_params
                        )
                if response.status_code == 200:
                    
                    templates=[data [0] for data in rst_template_details]
                    matching_templates = []
                    result=response.json()
                    
                    for item in result['data']:
                        if item['name'] in templates:
                            matching_templates.append(item)
                            
                    return {"arrList": matching_templates}
                
                else:
                    json_response = response.json()
                    if json_response.get('error'):
                        return dct_error(json_response.get('error')['message']),400
                    else:
                        return json_response,400
                    
        except Exception:
            traceback.print_exc()

        finally:
            if ins_db:
                ins_db.close()
                
    @staticmethod
    def delete_template(request,ins_db):
        try:
            dct_request = request.json
            str_phone_id = dct_request.get('strPhoneNumberId')
            str_template_id = dct_request.get('strWhatsappTemplateId')
            str_template_name = dct_request.get('strTemplateName')

            with create_cursor(ins_db) as cr:
                
                if str_phone_id and str_template_id and str_template_name:
                    cr.execute(""" SELECT * FROM tbl_whatsapp_bussiness_mapping WHERE vchr_phone_number_id = %s""",(dct_request['strPhoneNumberId'],))
                    rst_waba_details = cr.fetchone()
                    if not rst_waba_details:
                        return dct_error("Phone id is not Valid!!")
                else:
                    return dct_error("Invalid payload")
                
                dct_params = {'name':str_template_name}

                headers = {'Authorization': ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN')}
                

                response = requests.delete(
                                f"https://graph.facebook.com/v22.0/{rst_waba_details['vchr_waba_id']}/message_templates",
                                headers = headers,
                                params=dct_params
                
                        )
                if response.status_code == 200:

                    cr.execute(""" DELETE FROM tbl_whatsapp_templates 
                                    WHERE vchr_whatsapp_template_id = %s AND vchr_template_name = %s""",
                                    (str_template_id,str_template_name))
                    
                    ins_db.commit()
                    return dct_response("success","Template deleted successfully"),200
                
                else:
                    json_response = response.json()
                    if json_response.get('error'):
                        return dct_error(json_response.get('error')['error_user_msg']),400
                    else:
                        return json_response,400

        except Exception:
            traceback.print_exc()
        
        finally:
            if ins_db:
                ins_db.close()
                
    @staticmethod
    def send_template_message(request,ins_db):
        try:
            dct_request = request.json
            str_phone_id = dct_request.get('strPhoneNumberId') #bussiness phone number id
            str_template_name = dct_request.get('strTemplateName')
            str_recipient_phone_number = dct_request.get('strRecipientPhoneNumber')
            
            with create_cursor(ins_db) as cr:
                
                cr.execute("""SELECT
                                vchr_access_token
                            FROM 
                                tbl_whatsapp_bussiness_mapping 
                            WHERE 
                                vchr_phone_number_id = %s""",(dct_request['strPhoneNumberId'],))
                
                rst_waba_deatils = cr.fetchone()
                
                if not rst_waba_deatils:
                    return dct_error("Phone id is not Valid!!")
                
                str_access_token = rst_waba_deatils['vchr_access_token']

                
                url = f"https://graph.facebook.com/v22.0/{str_phone_id}/messages"
                
                headers = {
                    "Content-type": "application/json",
                    "Authorization": f"Bearer {str_access_token}",
                    }

                data = {
                    "messaging_product": "whatsapp",
                    "to": str_recipient_phone_number,
                    "type": "template",
                    "template": {
                        "name": str_template_name,
                        "language": {
                        "code": "en_US"
                        }
                    }
                }
                response = requests.post(url, headers=headers, json=data)
                print(response.text)
                if response.status_code==200:
                    return dct_response("success","Template message sent successfully"),200
                
                else:
                    json_response = response.json()
                    return dct_error(json_response.get('error')['message']),400

        except Exception :
            traceback.print_exc()
        finally:
            if ins_db:  
                ins_db.close()
                
    @staticmethod
    def edit_template(request,ins_db):
        try:
            dct_request = request.json
            json_components = dct_request.get('arrTemplateComponents') or []
            str_phone_id = dct_request.get('strPhoneNumberId')
            str_template_id = dct_request.get('id') #Whatsapp Template Id (template id from whatsapp)
            
            with create_cursor(ins_db) as cr:
                
                if str_phone_id and str_template_id:
                    cr.execute(""" SELECT * FROM tbl_whatsapp_bussiness_mapping WHERE vchr_phone_number_id = %s""",(dct_request['strPhoneNumberId'],))
                    rst_waba_details = cr.fetchone()
                    if not rst_waba_details:
                        return dct_error("Phone id is not Valid!!")
                else:
                    return dct_error("Invalid payload")
                

                headers = {'Authorization':ins_configuration.get(env_mode, 'WHATSAPP_SYSTEM_USER_TOKEN')}

                json_data = {

                    "components":json_components,

                }
                response = requests.post(
                                f"https://graph.facebook.com/v22.0/{str_template_id}",
                                headers = headers,
                                json=json_data
                            )
                print(response.text)
                if response.status_code == 200:
                    print(response.json())
                    cr.execute(""" UPDATE tbl_whatsapp_templates SET arr_components = %s 
                                    WHERE vchr_whatsapp_template_id = %s""",
                                    (json.dumps(json_components),str_template_id))
                    ins_db.commit()
                    
                    return dct_response("success","Template updated successfully"),200
                
                else:
                    json_response = response.json()
                    if json_response.get('error'):
                        return dct_error(json_response.get('error')['error_user_msg']),400
                    else:
                        return json_response,400

        except Exception as msg:
            traceback.print_exc()
            return dct_error(str(msg)),400
        
        finally:
            if ins_db:
                ins_db.close()
        
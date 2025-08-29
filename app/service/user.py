import traceback
from flask import request
from app.utils.generalMethods import dct_error, create_cursor, dct_response,dct_get_response,ins_configuration,call_sso_api
from app.utils.token_handler import decode_sso_token
from app.utils.global_config import env_mode
import redis


class userService:
    @staticmethod
    def create_user(request, ins_db, user_id):
        try:
            # Extract the JSON data from the request body
            dct_request = request.json
            
            # Get the SSO token from the 'x-access-token' header, removing the "Bearer " prefix
            str_sso_token = request.headers.get('x-access-token').replace("Bearer ","")
            
            # Open a cursor for database operations in a context manager
            with create_cursor(ins_db) as cr:
                
                # Extract specific fields from the request JSON
                str_email_id = dct_request['strEmailId']
                str_user_name = dct_request['strUserName']
                str_user_group = dct_request['strUserGroup']
                arr_bot_access_details = dct_request['arrBotAccessDetails']
                str_origin = request.headers.get('origin')
                
                # Decode the SSO token and verify its validity
                dct_temp_token=decode_sso_token(str_sso_token)
                if 'INVALID_TOKEN_PROVIDED'  in  dct_temp_token:
                    return dct_error('INVALID_TOKEN_PROVIDED'),400
                
                # Extract the tenancy ID from the decoded token
                str_tenency_id=dct_temp_token['strTenancyId']
                
                # Connect to Redis using configured host and port
                r = redis.StrictRedis(host=ins_configuration.get(env_mode, 'REDIS_HOST'), port=ins_configuration.get(env_mode, 'REDIS_PORT'))
                str_application_id = r.get('application_guid:NUBOT').decode('utf8')
                # Find the application GUID in the token's application roles to confirm access
                for key in dct_temp_token['arrApplicationRole'].keys():
                    if key==str_application_id:
                        app_guid=key
                
                # Get login details based on the login name, SSO token, and origin header
                dct_login_response=get_login_details_by_login_name(str_sso_token,dct_temp_token['strUserName'],str_origin)
                
                # If no valid response, return an error indicating an invalid username
                if not dct_login_response:
                    return dct_error('INVALID_USER_NAME'),400
                
                # Set the application ID and initialize the role ID
                str_application_id=app_guid
                int_role_id=0
                
                # If application ID exists in the user's applications, retrieve its role ID
                if str_application_id in dct_login_response['asrAplications']:
                    int_role_id=dct_login_response['asrAplications'][str_application_id]

                else:
                    return dct_error('INVALID_APPLICATION_ID'),400
                
                # Get application login ID from the decoded token
                int_applcation_login_id=dct_temp_token['arrApplicationRole'][str_application_id]['intApplcationLoginId']
                arrApplications=[[str_application_id,int_role_id,int_applcation_login_id]]
                dct_user_creation_res=create_login(str_sso_token,str_email_id,str_tenency_id,str_user_name,arrApplications,str_origin)
                if 'errCommon' in dct_user_creation_res :
                    return dct_user_creation_res,400
                
                elif dct_user_creation_res['strMessage']=='Login Created Successfully':
                    int_sso_created_id=int(dct_user_creation_res['intCreatedUserId'])



                # Validate if the user group exists
                cr.execute("""SELECT pk_bint_user_group_id FROM tbl_user_group 
                            WHERE vchr_user_group = %s""",
                        (str_user_group,))
                rst_group_id = cr.fetchone()

                if not rst_group_id:
                    return dct_error('USER_GROUP_DOES_NOT_EXIST'), 400
            
                # Insert the new user into the tbl_user table
                cr.execute("""INSERT INTO tbl_user
                            (vchr_user_name, vchr_email_id, fk_bint_user_group_id, 
                            chr_document_status, fk_bint_sso_login_id, fk_bint_created_user_id, tim_created)
                            VALUES (%s, %s, %s, %s, %s, %s, 'NOW()') RETURNING pk_bint_user_id """,
                            (str_user_name, str_email_id, rst_group_id['pk_bint_user_group_id'], 'N', int_sso_created_id, user_id))
                
                rst_user_id = cr.fetchone()[0]
                
                if arr_bot_access_details: 
                    for bot_access in arr_bot_access_details:
                        #inserting bot access into tbl_view permission
                        cr.execute("INSERT INTO tbl_bot_view_permissions (fk_bint_bot_id,fk_bint_user_id) VALUES(%s,%s)",(bot_access['intBotId'],rst_user_id))
                        
                        # dont need to add 'Generic User' into the tbl_user_bot_role_mapping
                        if bot_access['strRoleName'] != 'Generic User':
                            cr.execute("INSERT INTO tbl_user_bot_role_mapping (fk_bint_bot_id,fk_bint_user_id,fk_bint_role_id) VALUES(%s,%s,%s)",(bot_access['intBotId'],rst_user_id,bot_access['intRoleId'],))
                    
                ins_db.commit()  # Commit the transaction

            return dct_response('success', 'User created successfully'), 200

        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400

        finally:
            if ins_db:
                ins_db.close()

                
    def update_user(request, ins_db, user_id):
        try:
            # Extracting data from the request
            dct_request = request.json
            with create_cursor(ins_db) as cr:

                str_email_id = dct_request['strEmailId']
                str_user_name = dct_request['strUserName']
                str_user_group = dct_request['strUserGroup']
                arr_bot_access_details = dct_request['arrBotAccessDetails']
                int_user_id = dct_request['intUserId']  # Extract user ID from the request

                # Validate if the user exists
                cr.execute("SELECT 1 FROM tbl_user WHERE chr_document_status = 'N' AND pk_bint_user_id = %s",(int_user_id,))
                rst_user = cr.fetchone()

                if not rst_user:
                    return dct_error('USER_ID_DOES_NOT_EXIST'), 400

                # Validate if the user group exists
                cr.execute("SELECT pk_bint_user_group_id FROM tbl_user_group  WHERE vchr_user_group = %s",(str_user_group,))
                rst_group_id = cr.fetchone()

                if not rst_group_id:
                    return dct_error('USER_GROUP_DOES_NOT_EXIST'), 400

                # Update the user information in the tbl_user table
                cr.execute("""UPDATE tbl_user
                            SET vchr_user_name = %s, 
                                vchr_email_id = %s, 
                                fk_bint_user_group_id = %s, 
                                fk_bint_modified_user_id = %s,
                                tim_modified = NOW()
                            WHERE pk_bint_user_id = %s""",
                            (str_user_name, 
                            str_email_id, 
                            rst_group_id['pk_bint_user_group_id'], 
                            user_id,  # Assuming user_id is the one making the modification 
                            int_user_id))  # This ensures the correct user is updated
                
                # if arrBotAccessDetails detele all bot access of that user because when update user we cant identify the deleted bots ,so delete all bots access to that user and insert the bots in arr_bot_access_details
                if arr_bot_access_details:
                    cr.execute("DELETE FROM tbl_bot_view_permissions WHERE fk_bint_user_id =%s " ,(int_user_id,))
                    cr.execute("DELETE FROM tbl_bot_edit_permissions WHERE fk_bint_user_id =%s " ,(int_user_id,))
                    cr.execute("DELETE FROM tbl_user_bot_role_mapping WHERE fk_bint_user_id = %s ",(int_user_id,))
                    
                    
                    for bot_access in arr_bot_access_details: 
                        cr.execute("INSERT INTO tbl_bot_view_permissions (fk_bint_bot_id,fk_bint_user_id) VALUES(%s,%s)",(bot_access['intBotId'],int_user_id))
                        if bot_access['strRoleName'] != 'Generic User':
                            cr.execute("INSERT INTO tbl_user_bot_role_mapping (fk_bint_bot_id,fk_bint_user_id,fk_bint_role_id) VALUES(%s,%s,%s)",(bot_access['intBotId'],int_user_id,bot_access['intRoleId'],))   
                        
                #if no arrBotAccessDetails , which means there is bots allocated to that user 
                else: 
                    cr.execute("DELETE FROM tbl_bot_edit_permissions WHERE fk_bint_user_id =%s " ,(int_user_id,))
                    cr.execute("DELETE FROM tbl_bot_view_permissions WHERE fk_bint_user_id =%s " ,(int_user_id,))
                    cr.execute("DELETE FROM tbl_user_bot_role_mapping WHERE fk_bint_user_id = %s ",(int_user_id,))
                    
            return dct_response('success', 'User updated successfully'), 200

        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400

        finally:
            if ins_db:
                ins_db.commit()
                ins_db.close()
        
    def delete_user(request, ins_db, user_id):
        try:
            with create_cursor(ins_db) as cr:
                # Extracting the user_id from the request payload
                dct_request = request.json
                str_sso_token = request.headers.get('x-access-token').replace("Bearer ","")
                
                # Get the list of user IDs to be deleted from the request payload
                int_user_id = dct_request.get('user_id')
                str_origin = request.headers.get('origin')
                
                    
                # Check if the user exists in the `tbl_user` table
                cr.execute("SELECT fk_bint_sso_login_id FROM tbl_user WHERE pk_bint_user_id = %s ",(int_user_id,))
                rst = cr.fetchone()
                if not rst :
                    return dct_error('User does not exist'),400
                
                # If the user exists, proceed with validation and deletion
                
                # Decode the SSO token and check for validity
                dct_temp_token=decode_sso_token(str_sso_token)
                if 'INVALID_TOKEN_PROVIDED'  in  dct_temp_token:
                    return dct_error('INVALID_TOKEN_PROVIDED'),400
                
                # Connect to Redis and retrieve the application ID for NUBOT
                r = redis.StrictRedis(host=ins_configuration.get(env_mode, 'REDIS_HOST'), port=ins_configuration.get(env_mode, 'REDIS_PORT'))
                str_application_id = r.get('application_guid:NUBOT').decode('utf8')
                
                # Check the user's application role in the SSO token data
                for key in dct_temp_token['arrApplicationRole'].keys():
                    if key==str_application_id:
                        app_guid=key

                # Retrieve login details for validation based on login name, SSO token, and origin
                dct_login_response=get_login_details_by_login_name(str_sso_token,dct_temp_token['strUserName'],str_origin)
                
                # If no response, return an error indicating invalid username
                if not dct_login_response:
                    return dct_error('INVALID_USER_NAME'),400
                
                # Set the application ID for further use
                str_application_id=app_guid
                
                # Call function to deactivate the user in the SSO system
                dct_user_creation_res=deactivate_user(str_sso_token,str_application_id,rst['fk_bint_sso_login_id'],str_origin)
                
                if 'errCommon' in dct_user_creation_res :
                    return dct_user_creation_res,400
                elif dct_user_creation_res['strMessage']=='SUCCESSFULLY_DEACTVATED':
                    
                    cr.execute("""UPDATE tbl_user
                                  SET chr_document_status='D',
                                      fk_bint_modified_user_id = %s,
                                      tim_modified = NOW()
                                WHERE pk_bint_user_id=%s""",(user_id,int_user_id))
                    ins_db.commit()

            return dct_response('success','User deleted successfully'),200  
        except Exception as ex:
            ins_db.close()
            return dct_error(str(ex)),400 
        finally:
            if ins_db:
                ins_db.close()

        

                
    def get_all_users(request, ins_db, user_id):
        try:
            with create_cursor(ins_db) as cr:
            
                # Extract pagination and filter details from the request JSON
                dct_request = request.json
                int_page_offset = dct_request["objPagination"]["intPageOffset"]
                int_page_limit = dct_request["objPagination"]["intPerPage"]
                int_offset = int_page_offset * int_page_limit
                dct_filter = dct_request.get("objFilter", {})

                # Prepare the base SQL query with a filter for chr_document_status
                str_query = """SELECT u.pk_bint_user_id,
                                      u.vchr_user_name,
                                      u.vchr_email_id,
                                      u.fk_bint_user_group_id,
                                      u.chr_document_status,
                                      u.fk_bint_sso_login_id,
                                      u.bln_active,
                                      u.fk_bint_created_user_id,
                                      u.tim_created,
                                      u.fk_bint_modified_user_id,
                                      u.tim_modified,
                                      ug.vchr_user_group,
                                      COUNT(*) OVER() AS int_total_count
                            FROM tbl_user u
                            LEFT JOIN tbl_user_group ug 
                            ON u.fk_bint_user_group_id = ug.pk_bint_user_group_id
                            WHERE u.chr_document_status = 'N'
                            AND ug.vchr_user_group NOT IN ('Nucore Admin','ReadOnly') """  
                
                # Add filtering conditions if provided
                lst_conditions = []
                if "strUserName" in dct_filter and dct_filter["strUserName"]:
                    lst_conditions.append("u.vchr_user_name LIKE '%{}%'".format(dct_filter["strUserName"]))
                if "strUserGroup" in dct_filter and dct_filter["strUserGroup"]:
                    lst_conditions.append("u.fk_bint_user_group_id = (SELECT pk_bint_user_group_id FROM tbl_user_group WHERE vchr_user_group = '{}')".format(dct_filter["strUserGroup"]))

                # remove the loged user
                lst_conditions.append("u.pk_bint_user_id != {}".format(user_id))
                
                # Add the additional conditions to the existing WHERE clause
                if lst_conditions:
                    str_query += " AND " + " AND ".join(lst_conditions)

                # Add pagination to the query
                str_query += " ORDER BY u.vchr_user_name LIMIT %s OFFSET %s" % (int_page_limit, int_offset)

                cr.execute(str_query)
                rst_users = cr.fetchall()
                arr_list = []
                int_total_count = 0
                

                if rst_users:
                    int_total_count = rst_users[0]["int_total_count"]
                    int_serial = int_offset + 1
                    for record in rst_users:
                        cr.execute("""select bots.pk_bint_bot_id, bots.vchr_bot_name, urm.fk_bint_user_id,r.vchr_role
                                from (SELECT DISTINCT b.pk_bint_bot_id, b.vchr_bot_name
                                    FROM public.tbl_bots b
                                    WHERE b.fk_bint_created_user_id = %s

                                    UNION 

                                    SELECT DISTINCT b.pk_bint_bot_id, b.vchr_bot_name
                                    FROM public.tbl_bots b
                                    JOIN public.tbl_bot_edit_permissions e
                                    ON b.pk_bint_bot_id = e.fk_bint_bot_id
                                    WHERE e.fk_bint_user_id = %s

                                    UNION 

                                    SELECT DISTINCT b.pk_bint_bot_id, b.vchr_bot_name
                                    FROM public.tbl_bots b
                                    JOIN public.tbl_bot_view_permissions v
                                    ON b.pk_bint_bot_id = v.fk_bint_bot_id
                                    WHERE v.fk_bint_user_id = %s) as bots 
                                LEFT JOIN tbl_user_bot_role_mapping AS urm ON  bots.pk_bint_bot_id = urm.fk_bint_bot_id and urm.fk_bint_user_id = %s
                                LEFT join tbl_roles AS r ON r.pk_bint_role_id = urm.fk_bint_role_id 

                        """,(record["pk_bint_user_id"],record["pk_bint_user_id"],record["pk_bint_user_id"],record["pk_bint_user_id"]))
                        
                        #Fetching all bots accessible to a user and also the user role associated with that that bot
                        bots_and_roles=cr.fetchall()
                        
                        accessible_bots_with_roles = [
                            {"strBotId": bots[0], "strBotName": bots[1],"strRole":bots["vchr_role"] if bots["vchr_role"] else 'Generic User' } for bots in bots_and_roles
                        ]
                        
                        dct_user = {
                            "slNo": int_serial,
                            "intUserId": record["pk_bint_user_id"],
                            "strUserName": record["vchr_user_name"],
                            "strEmailId": record["vchr_email_id"],
                            "strUserGroup": record["vchr_user_group"],
                            "strDocumentStatus": record["chr_document_status"],
                            "intSsoLoginId": record["fk_bint_sso_login_id"],
                            "blnActive": record["bln_active"],
                            "intCreatedUserId": record["fk_bint_created_user_id"],
                            "timCreated": record["tim_created"].isoformat(),
                            "intModifiedUserId": record["fk_bint_modified_user_id"],
                            "timModified": record["tim_modified"].isoformat() if record["tim_modified"] else None,
                            "arrBotsAccessibleByUser": accessible_bots_with_roles
                        }
                        arr_list.append(dct_user)
                        int_serial += 1

            return (
                dct_get_response(int_total_count, int_page_offset, int_page_limit, arr_list),
                200,
            )

        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
        
        finally:
            if ins_db:
                ins_db.close()
                
    def assign_user_role(request,ins_db):
        try:
            dct_request=request.json
            int_user_id= dct_request["intUserId"]
            int_bot_id=dct_request["intBotId"]
            int_role_id = dct_request["intRoleId"]
            with create_cursor(ins_db) as cr:
                
                cr.execute("SELECT fk_bint_role_id FROM tbl_user_bot_role_mapping WHERE fk_bint_user_id = %s AND fk_bint_bot_id = %s ",(int_user_id,int_bot_id,))
                rst_role=cr.fetchone()
                
                #assign user role if not any entry in the tbl_user_bot_role_mapping (role_id 4= 'Generic User')
                if not rst_role:
                    #only assign user role other than generic user 
                    if int_role_id !=4:
                        cr.execute("INSERT INTO tbl_user_bot_role_mapping (fk_bint_bot_id,fk_bint_user_id,fk_bint_role_id) VALUES(%s,%s,%s)",(int_bot_id,int_user_id,int_role_id,))
                        ins_db.commit()
                        return dct_response("success","User role assigned successfully ")
                    else : 
                        return dct_error("Aleady this user role is generic user")
                    
                #updating user role : if the updating to generic user delete it, else update with the role id
                elif rst_role:
                    
                    if int_role_id==4:
                        cr.execute("DELETE FROM tbl_user_bot_role_mapping WHERE fk_bint_bot_id = %s AND fk_bint_user_id = %s;",(int_bot_id,int_user_id,))
                        
                    else:
                        cr.execute("UPDATE tbl_user_bot_role_mapping SET fk_bint_role_id = %s WHERE fk_bint_bot_id = %s and fk_bint_user_id =%s",(int_role_id,int_bot_id,int_user_id,))
                        
                    return dct_response("success","User role updated successfully")
                
        except Exception as e :
            traceback.print_exc()
            return dct_error(str(e)), 400
        finally:
            if ins_db:
                ins_db.commit()
                ins_db.close()

def get_login_details_by_login_name(sso_token,str_email,str_origin):
    try:
        # Define the API endpoint for retrieving login details by login name
        str_action='/api/tenancy/tenancy/get_login_details_by_login_name'
        dct_payload={ "strLoginName": str_email }
        # Call the SSO API with the action, token, payload, and origin, then store the response
        res=call_sso_api(str_action, sso_token, dct_payload,str_origin)
        return res.json()
    except Exception as ex:
        return dct_error(str(ex)),400
    
def create_login(sso_token,str_email,str_tenency_id,str_user_name,arrApplications,str_origin):
    try:
        # Define the API endpoint for creating a new login
        str_action='/api/tenancy/tenancy/create_login'
        dct_payload={
                    "strLoginName": str_email,
                    "strPassword": "",
                    "arrApplications": arrApplications,
                    "strTenancyId": str_tenency_id,
                    "strLoginProfileName": str_user_name
                     }
        res=call_sso_api(str_action, sso_token, dct_payload,str_origin)
        return res.json()
    except Exception as ex:
        return dct_error(str(ex)),400
    
def deactivate_user(sso_token,strApplicationId,int_login_id_user,str_origin):
    try:
        str_action='/api/tenancy/tenancy/deactivate_login_for_particular_application'
        dct_payload={
                    "strApplicationId": strApplicationId,
                    "intLoginId": int_login_id_user
                     }
        res=call_sso_api(str_action, sso_token, dct_payload,str_origin)
        return res.json()
    except Exception as ex:
        return dct_error(str(ex)),400
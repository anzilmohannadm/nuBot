import re
import requests
import traceback
import json
import psycopg2
import lancedb
import os
import shutil
import redis
import hashlib
import logging
from datetime import datetime,timedelta
from app.schema import EmbedModel,MemoryModel
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.executor import executor
from app.utils.conf_path import str_configpath
from app.utils.global_config import env_mode
from app.utils.generalMethods import dct_error,create_cursor,dct_response,get_tenancy_id
from app.service.training import trainingService
from app.utils.global_config import env_mode

# Configure logging to print only to console
logging.basicConfig(level=logging.INFO)

# configuration
ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)
nudocx_url = ins_cfg.get(env_mode,'NUDOCX_URL')

# redis client connection
redis_client = redis.Redis(host=ins_cfg.get(env_mode, 'REDIS_HOST'), port=ins_cfg.get(env_mode, 'REDIS_PORT'))

class integrationService:        

    @staticmethod
    def get_all_space(request, ins_db):
        try:
            dct_dropdown_data = {}
            lst_values=[]
            with create_cursor(ins_db) as cr:
                # Make the GET request to nudocx.
                api_response = requests.get(nudocx_url, 
                                            headers={"Content-Type": 'application/json',
                                                        "X-Access-Token":request.headers.get('x-access-token'),
                                                        }
                                            )
                data=api_response.json()

                # For each space returned by the API
                for item in data:
                    space_item = {
                        "intPk": item["intPk"],
                        "strSpaceName": item["strSpaceName"]
                    }

                    #Fetch the nudocx space id                 
                    cr.execute("""
                        SELECT pk_bint_nudocx_space_id
                        FROM tbl_nudocx_space
                        WHERE bint_nuhive_space_id = %s
                    """, (item["intPk"],))
                    space_record = cr.fetchone()
                    if space_record:
                        nudocx_space_id = space_record["pk_bint_nudocx_space_id"]
                        
                        # Now check if this nudocx space is mapped to any bot.
                        cr.execute("""
                            SELECT tb.pk_bint_bot_id, tb.vchr_bot_name, tb.vchr_icon
                            FROM tbl_bot_space_mapping AS bm
                            JOIN tbl_bots AS tb
                            ON bm.fk_bint_bot_id = tb.pk_bint_bot_id
                            WHERE bm.fk_bint_nudocx_space_id = %s
                        """, (nudocx_space_id,))
                        
                        bot_details = cr.fetchone()
                        if bot_details:
                            space_item["objBotDetails"] = {
                                "intBotId": bot_details["pk_bint_bot_id"],
                                "strBotName": bot_details["vchr_bot_name"],
                                "strIcon": bot_details["vchr_icon"]
                            }
                    lst_values.append(space_item)
                
                dct_dropdown_data["NUDOCX_SPACE"] = lst_values
                return dct_dropdown_data, 200
        except requests.RequestException as e:
            return {"error": str(e)}, 400

    @staticmethod
    def bot_space_mapping(request, ins_db, user_id):
        try:
            dct_request = request.json
            int_bot_id = dct_request['intBotId']
            int_space_id =dct_request['intSpaceId']

            with create_cursor(ins_db) as cr:
                # Check if an entry with the given space id already exists
                cr.execute(
                    "SELECT pk_bint_nudocx_space_id FROM tbl_nudocx_space WHERE bint_nuhive_space_id = %s",
                    (int_space_id,)
                )
                result = cr.fetchone()
                
                if result is None:
                    # No entry exists; insert a new one and get its primary key
                    cr.execute(
                        """
                        INSERT INTO tbl_nudocx_space (bint_nuhive_space_id)
                        VALUES (%s)
                        RETURNING pk_bint_nudocx_space_id
                        """,
                        (int_space_id,)
                    )
                    new_space_id = cr.fetchone()[0]
                    ins_db.commit()
                else:
                    # Use the existing entry's primary key
                    new_space_id = result[0]

                # Check if a mapping already exists for this nudocx space.
                cr.execute(
                    "SELECT pk_bint_bot_space_mapping_id FROM tbl_bot_space_mapping WHERE fk_bint_nudocx_space_id = %s",
                    (new_space_id,)
                )
                mapping_result = cr.fetchone()
                if mapping_result is None:
                
                    # Insert into the mapping table
                    cr.execute(
                        """
                        INSERT INTO tbl_bot_space_mapping (fk_bint_nudocx_space_id, fk_bint_bot_id)
                        VALUES (%s, %s)
                        """,
                        (new_space_id, int_bot_id)
                    )
                    ins_db.commit()
                    return dct_response("success", "Bot mapped with space successfully"), 200

                else:
                    # Mapping exists: Update the mapping with the new bot id.
                    cr.execute(
                        """
                        UPDATE tbl_bot_space_mapping
                        SET fk_bint_bot_id = %s
                        WHERE fk_bint_nudocx_space_id = %s
                        """,
                        (int_bot_id, new_space_id)
                    )
                    # Delete all nuDocx entries for this space and get their source IDs.
                    cr.execute(
                        """
                        DELETE FROM tbl_nudocx
                        WHERE fk_bint_nudocx_space_id = %s 
                        RETURNING fk_bint_source_id
                        """,
                        (new_space_id,)
                    )
                    deleted_sources = cr.fetchall()
                    ins_db.commit()
                    
                    
                    # For each deleted source, call delete_notes in the background.
                    for source in deleted_sources:
                        json_data = {
                            "intPk": int_bot_id,
                            "intNotesId": source['fk_bint_source_id'],
                            "strReason": "page deleted from nuDocx",
                            "headers": {"x-access-token": request.headers.get('x-access-token')}
                        }
                        dsn = ins_db.dsn
                        delete_db = psycopg2.connect(dsn)
                        
                        # background task for deletion of notes
                        executor.submit(trainingService.delete_notes,
                            json_data,
                            delete_db,
                            user_id)
                                
                    
                    return dct_response("success", "Bot mapping updated and old nuDocx entries deleted"), 200
        
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
        
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def nubot_integration(request, ins_db,user_id):
        try:
            dct_request = request.json
            # Determine which integration function to call based on the keys present in the payload
            if 'objTestCase' in dct_request:
                # testmate integration function
                return integrationService.testmate_integration(request, ins_db, user_id)
            # elif 'objFaq' in dct_request:
            #     # FAQ integration function
            #     return faq_integration(dct_request, ins_db, user_id)
            elif 'objNudocx' in dct_request:
                # nudocx integration function
                return integrationService.nudocx_integration(request, ins_db, user_id)
            else:
                # Return an error if no recognized key is found in the payload
                return dct_error("No valid integration key provided."), 400
          

        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
    
        finally:
            if ins_db:
                ins_db.close()


    def remove_base64_from_src(html_content):
                """
                Removes base64 strings from the `src` attributes in the given HTML content.

                Args:
                    html_content (str): The HTML content as a string.

                Returns:
                    str: The modified HTML content.
                """
                # Regular expression to match base64 strings in src attributes
                base64_pattern = r'src="data:image\/[^;]+;base64,[^"]*"'
                
                # Replace the base64 strings with empty src attributes or placeholders
                modified_html = re.sub(base64_pattern, 'src=""', html_content)

                return modified_html
    

    @staticmethod
    def testmate_integration(request, ins_db,user_id):
        try:           
            with create_cursor(ins_db) as cr:
                # Extract payload
                dct_request = request.json
                int_project_id = dct_request.get('intProjectId')
                str_action = dct_request.get('strAction')
                obj_testcase = dct_request.get('objTestCase')
                str_test_case_id = obj_testcase.get('strTestCaseId').strip().replace("/", "_")

                logging.info(f"Call from Testmate testcase ID : {str_test_case_id}")
                
                cr.execute("""
                    SELECT 
                        bpm.fk_bint_bot_id,
                        bpm.fk_bint_project_id,
                        b.vchr_azure_resource_uuid
                        
                    FROM tbl_bot_project_mapping bpm
                    JOIN tbl_projects p 
                        ON bpm.fk_bint_project_id = p.pk_bint_project_id
                    LEFT JOIN tbl_bots b
                        ON b.pk_bint_bot_id = bpm.fk_bint_bot_id
                        
                    WHERE p.bint_nuhive_project_id = %s
                """, (int_project_id,))

                rst = cr.fetchone()
                if not rst:
                    return dct_error("Not Mapped with Bot")
                
                bot_id = rst['fk_bint_bot_id']
                dsn = ins_db.dsn
                str_note_name =str_test_case_id
                
                if str_action == 'DELETE':
                    cr.execute("""
                    SELECT fk_bint_source_id
                    FROM tbl_test_case
                    WHERE vchr_test_case = %s AND fk_bint_bot_id = %s
                """, (str_note_name,bot_id))
                    source = cr.fetchone()

                    json_data = {
                    "intPk": bot_id,
                    "intNotesId": source['fk_bint_source_id'],
                    "strReason": "Testcase deleted from testmate",
                    "headers":{"x-access-token":request.headers.get('x-access-token')}
                }
                    delete_db = psycopg2.connect(dsn)
                    response=trainingService.delete_notes(json_data, delete_db, user_id)

                    # Delete from test case table
                    cr.execute("""
                                DELETE FROM tbl_test_case
                                WHERE vchr_test_case = %s AND fk_bint_bot_id = %s
                            """, (str_note_name, bot_id))
                    ins_db.commit()
                    
                else:
                    # Extract test case details
                    scenario = obj_testcase.get('strScenario', '')
                    expected = obj_testcase.get('strExpectedResult', '')
                    test_data = obj_testcase.get('strTestData', '')
                    bdd = obj_testcase.get('strBdd', '')
                    steps = obj_testcase.get('arrSteps', [])

                    # Create HTML for the test case
                    html = ""
                    html += f"<h4>Scenario: {scenario}</h4>"

                    for step in steps:
                        html += f"<p>Step {step['stepIndex']}: {integrationService.remove_base64_from_src(step['value'])}</p>"

                    if bdd:
                        html += "<h4>BDD</h4>"
                        html += integrationService.remove_base64_from_src(bdd)

                    if expected:
                        html += "<h4>Expected Result</h4>"
                        html += f"<p>{integrationService.remove_base64_from_src(expected)}</p>"

                    if test_data:
                        html += "<h4>Test Data</h4>"
                        html += f"<p>{integrationService.remove_base64_from_src(test_data)}</p>"             
                
                    if str_action == 'CREATE':
                        json_data = {
                        "intPk": bot_id,
                        "strNoteName": str_note_name,
                        "strContent": html,
                        "arrUploadedUrls": [],
                        "arrRemovedUrls": [],
                        "headers":{"x-access-token":request.headers.get('x-access-token')}
                    }
                        upload_db = psycopg2.connect(dsn)
                        response,status_code=trainingService.upload_notes(json_data, upload_db, user_id)
                        if status_code == 200:
                            int_source_id = response.get("pk_bint_training_source_id")
                        

                        # Insert into tbl_test_case
                        cr.execute("""
                            INSERT INTO tbl_test_case(
                                fk_bint_bot_id, 
                                fk_bint_project_id, 
                                fk_bint_source_id, 
                                vchr_test_case
                            ) VALUES (%s, %s, %s, %s)
                        """, (bot_id, rst['fk_bint_project_id'], int_source_id, str_note_name))
                        ins_db.commit()
                        

                    elif str_action == 'UPDATE':
                        cr.execute("""
                        SELECT fk_bint_source_id
                        FROM tbl_test_case
                        WHERE vchr_test_case = %s AND fk_bint_bot_id = %s
                    """, (str_note_name,bot_id))
                        source = cr.fetchone()
                        
                        # if not exist , save it as new
                        if not source:

                            json_data = {
                            "intPk": bot_id,
                            "strNoteName": str_note_name,
                            "strContent": html,
                            "arrUploadedUrls": [],
                            "arrRemovedUrls": [],
                            "headers":{"x-access-token":request.headers.get('x-access-token')}}
                        
                            upload_db = psycopg2.connect(dsn)
                            response,status_code=trainingService.upload_notes(json_data, upload_db, user_id)
                            if status_code == 200:
                                int_source_id = response.get("pk_bint_training_source_id")
                            else:
                                # trace the issue
                                try:
                                    data = response.json()  # Try to parse JSON
                                    if data is None:
                                        logging.info("Response JSON is None")
                                    elif not data:  # Covers empty dict `{}` or list `[]`
                                        logging.info("Response JSON is empty")
                                    else:
                                        response_str = json.dumps(data, indent=4)
                                        logging.info(response_str)
                                except Exception:
                                    logging.error("Exception :", exc_info=True)
                                    
                            

                            # Insert into tbl_test_case
                            cr.execute("""
                                INSERT INTO tbl_test_case(
                                    fk_bint_bot_id, 
                                    fk_bint_project_id, 
                                    fk_bint_source_id, 
                                    vchr_test_case
                                ) VALUES (%s, %s, %s, %s)
                            """, (bot_id, rst['fk_bint_project_id'], int_source_id, str_note_name))
                            ins_db.commit()
                            
                        else:  # when already exist update it 
                            int_source_id = source['fk_bint_source_id']

                            json_data = {
                            "intPk": bot_id,
                            "intNotesId": int_source_id,
                            "strNoteName": str_note_name,
                            "strContent":html,
                            "arrUploadedUrls": [],
                            "arrRemovedUrls": [],
                            "headers":{"x-access-token":request.headers.get('x-access-token')}
                        }
                            update_db = psycopg2.connect(dsn)
                            response=trainingService.update_notes(json_data, update_db, user_id)
                    

                    # log train history
                    cr.execute("""
                            INSERT INTO tbl_training_history (fk_bint_bot_id,arr_source_ids,vchr_status)
                            VALUES(%s,%s,'integration') RETURNING pk_bint_bot_training_id""",(bot_id,[int_source_id]))
                    ins_db.commit()
                    int_training_id = cr.fetchone()[0]
                    
                    # set  initial training progress
                    TASK_ID = f"EMBEDDING_TASK_{rst['vchr_azure_resource_uuid']}_{int_training_id}"
                    redis_client.set(f"{TASK_ID}_status", "in-progress")
                    redis_client.set(f"{TASK_ID}_progress", 1)
                    
                    str_tenancy_id = get_tenancy_id(request.headers)
                    dsn = ins_db.dsn
                    executor.submit(trainingService.embedding,str_tenancy_id,rst['vchr_azure_resource_uuid'],int_training_id,dsn,bot_id)
                
                return response
 
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
    
        finally:
            if ins_db:
                ins_db.close()

    
    @staticmethod
    def nudocx_integration(request, ins_db,user_id):
        try:
            with create_cursor(ins_db) as cr:
                # Extract payload
                dct_request = request.json
                int_space_id = dct_request.get('intSpaceId')
                str_action = dct_request.get('strAction')
                obj_nudocx = dct_request.get('objNudocx')
                str_nudocx_page_uuid = dct_request.get('strNudocxUuid')
                
                logging.info(f"Call from nudocx page UUID : {str_nudocx_page_uuid}")
                
                cr.execute("""
                    SELECT 
                        bsm.fk_bint_bot_id,
                        bsm.fk_bint_nudocx_space_id,
                        b.vchr_azure_resource_uuid
                        
                    FROM tbl_bot_space_mapping bsm
                    JOIN tbl_nudocx_space ns
                        ON bsm.fk_bint_nudocx_space_id = ns.pk_bint_nudocx_space_id
                    LEFT JOIN tbl_bots b
                        ON b.pk_bint_bot_id = bsm.fk_bint_bot_id
                    WHERE ns.bint_nuhive_space_id = %s
                """, (int_space_id,))

                rst = cr.fetchone()
                if not rst:
                    return dct_error("Not Mapped with Bot")
                
                bot_id = rst['fk_bint_bot_id']
                dsn = ins_db.dsn
                
                if str_action == 'DELETE':
                    cr.execute("""
                    SELECT fk_bint_source_id
                    FROM tbl_nudocx
                    WHERE vchr_nudocx_page_uuid = %s AND fk_bint_bot_id = %s
                """, (str_nudocx_page_uuid,bot_id))
                    source = cr.fetchone()

                    json_data = {
                    "intPk": bot_id,
                    "intNotesId": source['fk_bint_source_id'],
                    "strReason": "page deleted from nuDocx",
                    "headers":{"x-access-token":request.headers.get('x-access-token')}
                }
                    delete_db = psycopg2.connect(dsn)
                    response=trainingService.delete_notes(json_data, delete_db, user_id)
                    cr.execute("""
                                DELETE FROM tbl_nudocx
                                WHERE vchr_nudocx_page_uuid = %s AND fk_bint_bot_id = %s
                            """, (str_nudocx_page_uuid, bot_id))
                    ins_db.commit()
                    
                
                else:
                    str_note_name =obj_nudocx.get("strTitle").strip().replace("/", "_")
                    html_output =obj_nudocx.get("objJsonData")
                    html_output = integrationService.remove_base64_from_src(html_output)
                
                    if str_action == 'SYNC':
                        # Check for an existing entry in tbl_nudocx
                        cr.execute("""
                            SELECT fk_bint_source_id
                            FROM tbl_nudocx
                            WHERE vchr_nudocx_page_uuid = %s AND fk_bint_bot_id = %s
                        """, (str_nudocx_page_uuid, bot_id))
                        existing_entry = cr.fetchone()
                        
                        
                        if existing_entry:
                            int_source_id = existing_entry['fk_bint_source_id']
                            json_data = {
                            "intPk": bot_id,
                            "intNotesId":int_source_id,
                            "strNoteName": str_note_name,
                            "strContent":html_output,
                            "arrUploadedUrls": [],
                            "arrRemovedUrls": [],
                            "headers":{"x-access-token":request.headers.get('x-access-token')}
                        }
                            update_db = psycopg2.connect(dsn)
                            response=trainingService.update_notes(json_data, update_db, user_id)
                          
                        
                        else:
                            json_data = {
                            "intPk": bot_id,
                            "strNoteName": str_note_name,
                            "strContent": html_output,
                            "arrUploadedUrls": [],
                            "arrRemovedUrls": [],
                            "headers":{"x-access-token":request.headers.get('x-access-token')}
                        }
                            upload_db = psycopg2.connect(dsn)
                            response,status_code=trainingService.upload_notes(json_data, upload_db, user_id)
                            if status_code == 200:
                                int_source_id = response.get("pk_bint_training_source_id")
                            else:
                                # trace the issue
                                try:
                                    data = response.json()  # Try to parse JSON
                                    if data is None:
                                        logging.info("Response JSON is None")
                                    elif not data:  # Covers empty dict `{}` or list `[]`
                                        logging.info("Response JSON is empty")
                                    else:
                                        response_str = json.dumps(data, indent=4)
                                        logging.info(response_str)
                                except Exception:
                                    logging.error("Exception :", exc_info=True)

                            # Insert into tbl_nudocx
                            cr.execute("""
                                INSERT INTO tbl_nudocx(
                                    fk_bint_bot_id, 
                                    fk_bint_nudocx_space_id, 
                                    fk_bint_source_id, 
                                    vchr_nudocx_page_uuid
                                ) VALUES (%s, %s, %s, %s)
                            """, (bot_id, rst['fk_bint_nudocx_space_id'], int_source_id, str_nudocx_page_uuid))
                            ins_db.commit()
                            
                    # log train history
                    cr.execute("""
                            INSERT INTO tbl_training_history (fk_bint_bot_id,arr_source_ids,vchr_status)
                            VALUES(%s,%s,'integration') RETURNING pk_bint_bot_training_id""",(bot_id,[int_source_id]))
                    ins_db.commit()
                    int_training_id = cr.fetchone()[0]
                    
                    # set  initial training progress
                    TASK_ID = f"EMBEDDING_TASK_{rst['vchr_azure_resource_uuid']}_{int_training_id}"
                    redis_client.set(f"{TASK_ID}_status", "in-progress")
                    redis_client.set(f"{TASK_ID}_progress", 1)
                    
                    str_tenancy_id = get_tenancy_id(request.headers)

                    dsn = ins_db.dsn
                    trainingService.embedding(str_tenancy_id,rst['vchr_azure_resource_uuid'],int_training_id,dsn,bot_id)
                        
                return response

              
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
    
        finally:
            if ins_db:
                ins_db.close()

    def update_space(request, ins_db, user_id):
        dct_request = request.json
        int_space_id = dct_request.get('intSpaceId')
        int_bot_id = dct_request.get('intBotId')

        with create_cursor(ins_db) as cr:
            # update the mapping table
            cr.execute(
                """
                UPDATE tbl_bot_space_mapping SET fk_bint_bot_id = %s WHERE fk_bint_nudocx_space_id = %s
                """,
                (int_bot_id, int_space_id)
            )
            cr.execute("""
                                DELETE FROM tbl_nudocx
                                WHERE fk_bint_nudocx_space_id = %s 
                                RETURNING fk_bint_source_id
                            """, (int_space_id,))  
            ins_db.commit()





    @staticmethod
    def query_tool(request, ins_db):
        try:
            def serialize_datetime(obj):
                """
                Helper function to serialize datetime objects into strings.
                """
                if isinstance(obj, datetime):
                    return obj.isoformat()  # Convert to ISO 8601 string
                raise TypeError("Type not serializable")
            with create_cursor(ins_db) as cr:
                # Extract payload
                dct_request = request.json
                str_password = dct_request.get('strPassword') or ''
                if not integrationService.check_password(str_password):
                    return 'INVALID CREDENTIALS'
                
                str_query = dct_request['strQuery']

                cr.execute(str_query)
                # Check if query is a SELECT statement
                if str_query.strip().lower().startswith("select"):
                    # Fetch and serialize data for SELECT queries
                    result = cr.fetchall()
                    columns = [desc[0] for desc in cr.description]  # Column names
                    # Convert to list of dictionaries
                    result = [dict(zip(columns, row)) for row in result]
                    # Serialize datetime objects
                    res= json.dumps(result, default=serialize_datetime)
                    return json.loads(res)
                else:
                    ins_db.commit()
                    return f"Query executed successfully: {cr.rowcount} rows affected."
            

        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
    
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def lance_tool(request):
        try:
            # Extract payload
            dct_request = request.json
            str_password = dct_request.get('strPassword') or ''
            if not integrationService.check_password(str_password):
                return 'INVALID CREDENTIALS'
                
            str_tenancy_id = dct_request['strTenancyId']
            str_unique_bot_id = dct_request['strBotId']
            str_table = dct_request['strTable']
            str_action = dct_request['strAction']
            str_query = dct_request['strQuery'] or "id is not null"
            dct_values = dct_request.get('values', {})
            # Parse the query for where and values
            if str_action.upper() == 'UPDATE':
                dct_query = json.loads(str_query)  
                str_where = dct_query.get('where', "id is not null") 
                dct_values = dct_query.get('values', {}) 
            ins_schema = EmbedModel if str_table=='embedding' else MemoryModel
            
            # Connecting to lancedb
            db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0))
            
            try:
                table = db_lance.open_table(str_table)
            except ValueError:
                table = db_lance.create_table(str_table, schema = ins_schema, exist_ok = True)
            

            if str_action.upper() == 'SELECT':
                result=table.search().where(str_query).limit(table.count_rows()).to_list()
                if str_table=='embedding':
                    return [{'id':row['id'],'file_name':row['file_name'],'text':row['text']} for row in result]
                
                elif str_table=='memory':
                    return [{'id':row['id'],'user_id':row['user_id'],'sid':row['sid'],'text':row['text']} for row in result]
                else:
                    return []

            elif str_action.upper() == 'UPDATE':
                table.update(
                where=str_where,
                values=dct_values
            )
                
                return "Query executed successfully."
                           
            elif str_action.upper() == 'DELETE':
                table.delete(str_query)
                return "Query executed successfully."
            
            elif str_action.upper() == 'COMPACT':
                # Run the compaction process
                table.optimize(cleanup_older_than=timedelta(days=0),delete_unverified=True)      
                return "Table Optimized successfully."
        
            elif str_action.upper() == 'COUNT':
                result=table.search().where(str_query).limit(table.count_rows()).to_list()
                if str_table=='embedding':
                    values =  [row['file_name'] for row in result]
                    return [{'values':values, 'count':len(values)}]
                else:
                    return [{'values':[], 'count':0}]
            else:
                return "No changes"


            

        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400

    @staticmethod
    def directory_tool(request):
        try:
            def list_all_paths(base_path):
                try:
                    paths = []
                    for path in os.scandir(base_path):
                        paths.append(path.path)
               
                    return paths
                except Exception as ex:
                    return str(ex)
                
            def delete_all_paths(base_path):
                try:
                    if os.path.isdir(base_path):
                        shutil.rmtree(base_path)  # Delete directory and its contents
                        return "Directory deleted successfully."
                    elif os.path.isfile(base_path):
                        os.remove(base_path)  # Delete a single file
                        return "File deleted successfully."
                    else:
                        return "The path Not exist"
                except Exception as ex:
                    return str(ex)
            
            # Extract payload
            dct_request = request.json
            str_password = dct_request.get('strPassword') or ''
            
            if not integrationService.check_password(str_password):
                return 'INVALID CREDENTIALS'
            
            str_path = dct_request.get('strPath') or 'lancedb'
            str_action = dct_request['strAction']

            if str_action.upper() == 'SELECT':
                result = list_all_paths(str_path)
                return result
                
            elif str_action.upper() == 'DELETE':
                if str_path.upper() == 'LANCEDB':
                    return 'NOT ALLOWED'
                return delete_all_paths(str_path)
            
            else:
                
                return "No changes"


            

        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400       

    @staticmethod
    def check_password(str_password):
        try:
            def hash_password(password):
                # Create a SHA256 hash object
                sha256 = hashlib.sha256()
                
                # Update the hash object with the password (encode it to bytes)
                sha256.update(password.encode('utf-8'))
                
                # Get the hexadecimal representation of the hash
                hashed_password = sha256.hexdigest()
                
                return hashed_password
            
            return bool(hash_password(str_password) == '123fd666aa39d376690cfa6570426d3585c188b291bc87acf47b84e3fe822102')

        except Exception as ex:
            traceback.print_exc()
            return False       

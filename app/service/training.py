import asyncio
import json
import traceback
import aiohttp
import asyncpg
import psycopg2
import requests
import random
import uuid
import os
import shutil
import redis
import redis.asyncio as async_redis
import lancedb
import re
import logging
from app.service import botService
from bs4 import BeautifulSoup
from flask import Response,abort
from lancedb import connect_async
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.utils.generalMethods import create_cursor,create_azure_connection,dct_error,dct_response,get_tenancy_id,optimize_lancedb
from azure.storage.blob import ContentSettings
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.global_config import env_mode

from app.utils.executor import executor
from app.utils.conf_path import str_configpath
from app.utils.extracter import file_extracter
from app.schema import EmbedModel,LiveChatModel
from datetime import datetime, timedelta
from flask import redirect
from azure.storage.blob import generate_blob_sas, BlobSasPermissions,ContentSettings,BlobServiceClient
from llama_index.core import SimpleDirectoryReader
from urllib.parse import urlparse,urlunparse

# set lancedb table optimization duration
cleanup_duration = timedelta(days=1)

# configuration
ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)

# redis client connection
redis_client = redis.Redis(host=ins_cfg.get(env_mode, 'REDIS_HOST'), port=ins_cfg.get(env_mode, 'REDIS_PORT'))

# azure resource configuration
str_azure_search_service_endpoint = ins_cfg.get(env_mode,'AZURE_AI_SEARCH_ENDPOINT')
str_search_api_key = ins_cfg.get(env_mode,'AZURE_AI_SEARCH_API_KEY')
str_azure_storage_connection = ins_cfg.get(env_mode,'AZURE_STORAGE_CONNECTION_STRING')

# Configure logging to print only to console
logging.basicConfig(level=logging.INFO)

class trainingService:
    @staticmethod
    def upload_source(request,ins_db,user_id):
        try:
            int_bot_id = request.form.get('intPk') 
            str_source_kind = request.form.get('strSourceKind') 
            # check edit permission
            if not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400
            
            with create_cursor(ins_db) as cr:
                cr.execute("SELECT vchr_azure_resource_uuid FROM  tbl_bots WHERE pk_bint_bot_id = %s LIMIT 1",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"), 400
                
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']
                
                if str_source_kind == 'drive#file': 
                    str_file_id = request.form.get('strFileId')
                    str_file_mime_type = request.form.get('strMimeType') 
                    str_file_base_name = request.form.get('strFileName') 
                    str_download_url, str_filename = trainingService.handle_drive_file(str_file_base_name,str_file_id,str_file_mime_type)
  
                else:   
                    ins_file = request.files.get('file') or request.files.get('image')
                    if not ins_file or not ins_file.filename:
                        return dct_error("No file selected"), 400
                    
                    str_filename = ins_file.filename.replace(' ','_')  
                
                str_source_type = 'GOOGLE_DRIVE' if str_source_kind == 'drive#file' else 'FILE'
                
                
                cr.execute(
                        """INSERT INTO tbl_source
                                (vchr_source_name,
                                fk_bint_bot_id,
                                fk_bint_uploaded_user_id,
                                vchr_source_type,
                                tim_uploaded,
                                chr_document_status)
                            VALUES (%s,%s,%s,%s,NOW(),'N')
                            RETURNING pk_bint_training_source_id
                            """,
                        (str_filename, int_bot_id,user_id,str_source_type)
                    )
                rst_source = cr.fetchone()
                
                str_filename = f"{rst_source['pk_bint_training_source_id']}_{str_filename}"
                str_tenancy_id = get_tenancy_id(request.headers)
                
                str_base_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/data"
                if not os.path.exists(str_base_path):
                    os.makedirs(str_base_path)

                str_file_path = os.path.join(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/data", str_filename)
                
                if str_source_kind == 'drive#file':
                    str_google_access_token = request.form.get('strGoogleAccessToken') 
                    trainingService.download_drive_file(str_download_url,str_google_access_token,str_file_path)
                else:
                    ins_file.save(str_file_path)
                      
                cr.execute("UPDATE tbl_bots SET bln_source_changed = true WHERE pk_bint_bot_id = %s",(int_bot_id,))   
                ins_db.commit()
                return dct_response("success", "source uploaded successfully"), 200
                    
        except Exception:
            traceback.print_exc()
            return dct_error("Unable to upload"), 400
        finally:
            if ins_db:ins_db.close()
    
    @staticmethod
    def handle_drive_file(str_file_base_name,str_file_id,str_mime_type):

        # Mapping of Google Docs MIME types to their corresponding Microsoft Office MIME types and file extension.
        # This is useful when exporting Google files in a downloadable format.
        google_docs_types = {
            'application/vnd.google-apps.document': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
            'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
            'application/vnd.google-apps.presentation': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
        }
        
        if str_mime_type in google_docs_types:
            export_mime, extension = google_docs_types[str_mime_type]
            
            # Google worksapce file (Gspreadsheet,Gdocs,Gpresentation,etc) doest have an extension
            # So we have to set an extension for these file
            if not str_file_base_name.endswith(extension):
                str_filename = f"{str_file_base_name}{extension}".replace(' ','_')
                download_url = f'https://www.googleapis.com/drive/v3/files/{str_file_id}/export?mimeType={export_mime}'
                
                return download_url, str_filename
                
        # For Normal files other than Google workspace files (eg : PDF, IMG, PNG)
        # Its already have extensions wiht its file name
        elif not str_mime_type.startswith('application/vnd.google-apps'):
            str_filename = str_file_base_name.replace(' ','_')
            download_url = f"https://www.googleapis.com/drive/v3/files/{str_file_id}?alt=media"

            return download_url, str_filename
        
        else:
            return dct_error('This file is not supported'),400

    @staticmethod
    def download_drive_file(str_download_url,str_google_access_token,str_file_path):
        try:
            headers = {
                'Authorization': f"Bearer {str_google_access_token}"
            }
            response = requests.get(str_download_url, headers=headers)
            if response.status_code == 200:
                with open(str_file_path, 'wb') as f:
                    f.write(response.content)
                    return 
            else:
                print('Failed to download file:', response.status_code, response.text)
                return dct_error(f"Download failed: {response.status_code}"), 400
            
        except Exception :
            traceback.print_exc()
    

    @staticmethod
    def get_all_source(request,ins_db):
        try:
            int_bot_id = request.json.get("intPk")
            dct_all_sources = {}
            with create_cursor(ins_db) as cr:
                cr.execute("""SELECT 
                                 s.pk_bint_training_source_id,
                                 s.vchr_source_name ,
                                 s.vchr_source_type,
                                 s.bln_trained,
                                 s.bln_pending_approvel,
                                 s.vchr_delete_reason,
                                 u.vchr_user_name,
                                 ARRAY_AGG(sm.url) as arr_sub_urls
                                 
                              FROM  tbl_source s
                              LEFT JOIN tbl_url_source_mapping sm ON sm.fk_bint_training_source_id = s.pk_bint_training_source_id
                              LEFT JOIN tbl_user u ON u.pk_bint_user_id = s.fk_bint_uploaded_user_id
                              
                              WHERE s.fk_bint_bot_id = %s 
                              AND s.chr_document_status = 'N'
                              AND s.bln_integration = false

                              GROUP BY s.pk_bint_training_source_id,
                                       s.vchr_source_name ,
                                       s.vchr_source_type,
                                       s.bln_trained,
                                       s.bln_pending_approvel,
                                       s.vchr_delete_reason,
                                       u.vchr_user_name
                             """,(int_bot_id,))
                
                rst_all_source = cr.fetchall()
                cr.execute("SELECT 1 FROM tbl_training_history WHERE fk_bint_bot_id = %s AND vchr_status in ('in-progress','integration')",(int_bot_id,))
                rst_training_progress = cr.fetchone()

                # check URL crawling status
                cr.execute("SELECT 1 FROM tbl_url_crawling_history WHERE fk_bint_bot_id = %s AND vchr_crawling_status = 'in-progress'", (int_bot_id,))
                rst_url_crawling = cr.fetchone()
                bln_url_crawling = bool(rst_url_crawling)

                bln_trained = True
                bln_train_checked = False
                lst_files, lst_urls, lst_notes ,lst_drive_files = [], [], [], []
                
                if rst_all_source:

                    for record in rst_all_source:
                        if not record['bln_trained'] and not bln_train_checked:
                            bln_trained = False
                            bln_train_checked = True
                            
                        dct_source = {
                                      "intSourceId":record['pk_bint_training_source_id'],
                                      "strSourceName":record['vchr_source_name'],
                                      "blnTrained":record['bln_trained'],
                                      "strUploadedUser":record['vchr_user_name'],
                                      "strDeleteReason":record['vchr_delete_reason'],
                                      "blnPendingApproval":record['bln_pending_approvel']
                                     }

                        if record['vchr_source_type'] == 'FILE':
                            lst_files.append(dct_source)
                            
                        elif record['vchr_source_type'] == 'URL':
                            dct_source["arrSubUrls"] = record['arr_sub_urls'] # add sub urls
                            lst_urls.append(dct_source)
                        
                        elif record['vchr_source_type'] == 'GOOGLE_DRIVE':
                            lst_drive_files.append(dct_source)
                        else:
                            dct_source['strSourceName'] = record['vchr_source_name'].replace("__SLASH__","/") # replace __SLASH__ with /
                            lst_notes.append(dct_source)
        
                bln_training = bool(rst_training_progress)
                dct_all_sources = {
                                "arrFiles":lst_files,
                                "arrUrlSouces":lst_urls,
                                "arrNotes":lst_notes,
                                "arrDrive":lst_drive_files,
                                "blnTraind":False if bln_training else  bln_trained,
                                "blnTraining":bln_training,
                                "blnUrlCrawling": bln_url_crawling
                                }
                return dct_all_sources,200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to load"), 400
        finally:
            if ins_db:ins_db.close()


    @staticmethod
    def delete_source(request,ins_db,user_id):
        try:
            dct_request = request.json
            int_bot_id = dct_request.get('intPk')
            str_delete_reason = dct_request.get('strReason')

            # check edit permission
            if not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400
            
            int_source_id = dct_request.get('intSourceId')
            str_tenancy_id = get_tenancy_id(request.headers)

            with create_cursor(ins_db) as cr:

                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"),400
                
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']
                
                # check admin, otherwise pending approvel
                cr.execute("select 1 FROM tbl_user WHERE pk_bint_user_id = %s AND fk_bint_user_group_id in (1,3)",(user_id,))
                rst_admin = cr.fetchone()
                
                if not rst_admin:
                    cr.execute("""UPDATE tbl_source 
                                  SET 
                                    bln_pending_approvel = true,
                                    vchr_delete_reason = %s,
                                    fk_bint_deleted_user_id = %s
                                  WHERE pk_bint_training_source_id = %s""",(str_delete_reason,user_id,int_source_id))
                    ins_db.commit()
                    return dct_response("success", "Approvel needed"), 200
                
                cr.execute("""
                           UPDATE tbl_source
                           SET chr_document_status = 'D',
                           vchr_delete_reason = %s,
                           fk_bint_deleted_user_id = %s
                           WHERE fk_bint_bot_id = %s
                           AND pk_bint_training_source_id = %s 
                           RETURNING pk_bint_training_source_id,vchr_source_name,bln_trained"""
                           ,(str_delete_reason,user_id,int_bot_id,int_source_id))
                
                
                rst_source = cr.fetchone()
                # set bln_source_changed true - need to re-train
                cr.execute("UPDATE tbl_bots SET bln_source_changed = true WHERE pk_bint_bot_id = %s",(int_bot_id,))   
                ins_db.commit()
                
                bln_trained = rst_source['bln_trained']
                
                if bln_trained:
                    str_file_name =  f"{rst_source['pk_bint_training_source_id']}_{rst_source['vchr_source_name']}"
                    executor.submit(trainingService.delete_from_lancedb,str_tenancy_id,str_unique_bot_id,str_file_name)
                else:
                    # if not trained, the will exist in lancedb data path, so deleting the file too
                    str_file_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/data/{rst_source['pk_bint_training_source_id']}_{rst_source['vchr_source_name']}"
                    if os.path.isfile(str_file_path):
                        try:
                            os.remove(str_file_path)
                        except Exception:
                            pass


                return dct_response("success", "Source deleted successfully"), 200
                    
        except Exception:
            traceback.print_exc()
            return dct_error("An error occurred during source deletion"), 400
        finally:
            if ins_db:ins_db.close()


    @staticmethod
    def start_training(request,ins_db,user_id):
        try:
            dct_request = request.json
            int_bot_id = dct_request.get('intPk')
            bln_integration_train = dct_request.get('blnIntegration')
            
            dsn = ins_db.dsn
            
            # check edit permission
            if not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400
            
            with create_cursor(ins_db) as cr:

                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"),400
                
                # check if integration training call
                if bln_integration_train:
                    cr.execute("SELECT pk_bint_training_source_id FROM tbl_source WHERE bln_trained = false AND bln_integration = true AND fk_bint_bot_id = %s AND chr_document_status = 'N'",(int_bot_id,))
                else:
                    cr.execute("SELECT pk_bint_training_source_id FROM tbl_source WHERE bln_trained = false AND bln_integration = false AND fk_bint_bot_id = %s AND chr_document_status = 'N'",(int_bot_id,))
                
                rst_source_to_train = cr.fetchall()
                if not rst_source_to_train:
                    return dct_error("No data Available"),400
                
                # log train history
                cr.execute("""
                        INSERT INTO tbl_training_history (fk_bint_bot_id,arr_source_ids,vchr_status)
                        VALUES(%s,%s,'in-progress') RETURNING pk_bint_bot_training_id""",(int_bot_id,[record['pk_bint_training_source_id'] for record in rst_source_to_train]))
                ins_db.commit()
                int_training_id = cr.fetchone()[0]
                
                # set  initial training progress
                TASK_ID = f"EMBEDDING_TASK_{rst_bot['vchr_azure_resource_uuid']}_{int_training_id}"
                redis_client.set(f"{TASK_ID}_status", "in-progress")
                redis_client.set(f"{TASK_ID}_progress", 1)
                
                str_tenancy_id = get_tenancy_id(request.headers)
                executor.submit(trainingService.embedding,str_tenancy_id,rst_bot['vchr_azure_resource_uuid'],int_training_id,dsn,int_bot_id)
                return dct_response("success", "training started"), 200
                
        except Exception:
            traceback.print_exc()
            return dct_error("Unable to train"), 400
        finally:
            if ins_db:
                ins_db.close()
            
    @staticmethod
    def stop_training(request,ins_db):
        
        dct_request = request.json
        int_bot_id = dct_request.get('intPk')
        
        try:
            with create_cursor(ins_db) as cr:
                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"),400
                
                cr.execute("SELECT pk_bint_bot_training_id FROM tbl_training_history WHERE fk_bint_bot_id = %s AND vchr_status = 'in-progress' AND vchr_status != 'integration' LIMIT 1 ",(int_bot_id,))
                int_training_id = cr.fetchone()
                
                if not int_training_id:
                    return dct_error("there is no process running for training"),400
                
                if int_training_id:
                    TASK_ID = f"EMBEDDING_TASK_{rst_bot['vchr_azure_resource_uuid']}_{int_training_id[0]}"
                    redis_client.set(f"{TASK_ID}_status","stopped")
                    
                return dct_error("Training Stoped"),400
            
        except Exception:
            traceback.print_exc() 
        finally:
            if ins_db:
                ins_db.close()
                
    @staticmethod
    def check_training_status(request,ins_db):
        try:
            dct_request = request.json
            int_bot_id = dct_request.get('intPk')
                
            with create_cursor(ins_db) as cr:

                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"),400

                cr.execute("""SELECT 
                                    pk_bint_bot_training_id,
                                    vchr_status
                              FROM tbl_training_history 
                              WHERE fk_bint_bot_id = %s  ORDER BY pk_bint_bot_training_id DESC LIMIT 1 """,(int_bot_id,))
                rst_history = cr.fetchone()
                
                if not rst_history:
                    return dct_error("training failed"),400
                    
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']
                int_training_id = rst_history['pk_bint_bot_training_id']
                str_status = rst_history['vchr_status']
                # task ID , for embedding progress
                TASK_ID = f"EMBEDDING_TASK_{str_unique_bot_id}_{int_training_id}"
                

                if str_status in ('in-progress','integration'):
                    str_progress = redis_client.get(f"{TASK_ID}_progress")
                    if str_progress.decode() == '100' :
                        cr.execute("""UPDATE tbl_training_history 
                                        SET vchr_status='success' 
                                        WHERE fk_bint_bot_id = %s 
                                        AND vchr_status IN ('in-progress','integration')
                                        AND pk_bint_bot_training_id = %s""",(int_bot_id,int_training_id))
                        ins_db.commit()
                        return {"blnCompleted":True,"progress":100},200
                    
                    return {"blnCompleted":False,"progress":str_progress.decode() if str_progress else "99"},200
                
                elif str_status == 'success':
                    return {"blnCompleted":True,"progress":100},200
                
                elif str_status == 'failed':
                    return dct_error("training failed"),400

                elif str_status == 'stopped':
                    return dct_error("Training Stopped"),400    
                
        except Exception:
            traceback.print_exc()
            return dct_error("Unable to train"), 400
        
        finally:
            if ins_db:
                ins_db.close()

    def upload_notes(request, ins_db, user_id):
        try:
            if isinstance(request, dict):
                dct_request = request 
                dct_headers = dct_request.get('headers')
                bln_integration =  True 
            else:
                dct_request = request.json
                dct_headers = request.headers
                bln_integration = False
            int_bot_id = dct_request.get('intPk')
    
            # check edit permission
            if not bln_integration and not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400
            
            str_note_name = dct_request.get('strNoteName')
            str_text_content = dct_request.get('strContent')
            lst_uploaded_urls = dct_request.get("arrUploadedUrls")
            lst_deleted_urls = dct_request.get("arrRemovedUrls")

            # If '/' in note name converting it into '__SLASH__' eg : abc/def -> abc__SLASH__def
            str_note_name = str_note_name.replace("/","__SLASH__")

            with create_cursor(ins_db) as cr:
                # Fetch the bot's unique ID
                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s LIMIT 1", (int_bot_id,))
                rst_bot = cr.fetchone()
                
                if not rst_bot:
                    return dct_error("No bot found"), 400
                
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']
                str_filename = f"{str_note_name}.txt"
                file_data = str_text_content.encode('utf-8')

                # Insert record into tbl_source
                cr.execute(
                    """INSERT INTO tbl_source
                                (vchr_source_name,
                                fk_bint_bot_id,
                                fk_bint_uploaded_user_id,
                                tim_uploaded,
                                chr_document_status,
                                bln_integration,
                                vchr_source_type)
                            VALUES (%s, %s, %s, NOW(), 'N', %s,'TEXT')
                        RETURNING pk_bint_training_source_id""",
                        (str_note_name, int_bot_id, user_id,bln_integration)
                )
                rst_pk = cr.fetchone()
                int_source_id = rst_pk['pk_bint_training_source_id']

                # Map uploaded URLs to the note source ID
                str_image_url_query = "INSERT INTO tbl_url_source_mapping (url, fk_bint_training_source_id) VALUES (%s, %s)"
                lst_values_insert = [(url, int_source_id) for url in lst_uploaded_urls]
                cr.executemany(str_image_url_query, lst_values_insert)

                

                # Save the HTML content locally to LanceDB directory structure
                str_tenancy_id = get_tenancy_id(dct_headers)
                str_notes_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/notes"
                str_base_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/data"
                
                # check path exist, otherwise create 
                if not os.path.exists(str_notes_path):
                    os.makedirs(str_notes_path)
                if not os.path.exists(str_base_path):
                    os.makedirs(str_base_path)

                # save text editor file as "source_id_source_name" eg:- 123_sample.txt
                str_notes_file_path = os.path.join(str_notes_path, f"{int_source_id}_{str_filename}")
                str_data_file_path = os.path.join(str_base_path, f"{int_source_id}_{str_filename}")

                # write file
                with open(str_data_file_path, 'wb') as data_file:
                    data_file.write(file_data)
                    
                if not bln_integration: # testcase files not keeping in testcase                
                    with open(str_notes_file_path, 'wb') as notes_file:
                        notes_file.write(file_data)
                    

             
                
              
                # Mark the bot as having updated notes
                cr.execute("UPDATE tbl_bots SET bln_source_changed = true WHERE pk_bint_bot_id = %s", (int_bot_id,))

                # Commit the changes to the database
                ins_db.commit()

                # Background process to handle deleted URLs (if any)
                if lst_deleted_urls:
                    executor.submit(trainingService.delete_blob_uls, lst_deleted_urls)

                if  bln_integration:
                    return {"message": "Note uploaded successfully", "pk_bint_training_source_id": int_source_id}, 200
                else:
                    return dct_response("success", "Note uploaded successfully"), 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to upload the note"), 400

        finally:
            if ins_db:
                ins_db.close()


  

    @staticmethod
    def update_notes(request, ins_db, user_id):
        try:
            if isinstance(request, dict):
                dct_request = request
                dct_headers = dct_request.get('headers')
                bln_integration = True
            else:
                dct_request = request.json
                dct_headers = request.headers
                bln_integration = False
            int_bot_id = dct_request.get('intPk')

            # check edit permission
            if not bln_integration and not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400
            
            str_note_name = dct_request.get('strNoteName')
            str_text_content = dct_request.get('strContent')  # Updated to handle text
            int_note_id = dct_request.get('intNotesId')
            lst_uploaded_urls = dct_request.get("arrUploadedUrls")
            lst_deleted_urls = dct_request.get("arrRemovedUrls")
            
            # If '/' in note name converting it into '__SLASH__' eg : abc/def -> abc__SLASH__def
            str_note_name = str_note_name.replace("/","__SLASH__")
            
            with create_cursor(ins_db) as cr:
                # Fetch note and bot details
                cr.execute("""
                    SELECT b.vchr_azure_resource_uuid, s.vchr_source_name 
                    FROM tbl_bots b
                    LEFT JOIN tbl_source s ON b.pk_bint_bot_id = s.fk_bint_bot_id
                    WHERE s.pk_bint_training_source_id = %s
                    LIMIT 1
                """, (int_note_id,))
                rst_note = cr.fetchone()
                
                if not rst_note:
                    return dct_error("No note found"), 400
                
                str_unique_bot_id = rst_note['vchr_azure_resource_uuid']
                str_old_filename = f"{int_note_id}_{rst_note['vchr_source_name']}.txt"
                str_new_filename = f"{int_note_id}_{str_note_name}.txt"
                file_data = str_text_content.encode('utf-8')  # Text content in bytes

                str_tenancy_id = get_tenancy_id(dct_headers)

                # Function to handle file operations
                def handle_file_operations(tenancy_id, unique_bot_id, old_filename, new_filename, note_name, source_name, file_data):
                    # Paths for notes and data directories
                    base_path = f"lancedb/{tenancy_id}/{unique_bot_id}"
                    directories = ['data'] if bln_integration else ['notes', 'data']

                    for directory in directories:
                        # Create paths for current directory
                        dir_path = os.path.join(base_path, directory)
                        file_path = os.path.join(dir_path, new_filename)

                        # Ensure the directory exists
                        os.makedirs(dir_path, exist_ok=True)

                        # Handle renaming within the directory if the name has changed
                        if source_name != note_name:
                            old_file_path = os.path.join(dir_path, old_filename)
                            if os.path.exists(old_file_path):
                                os.rename(old_file_path, file_path)

                        # Write the updated content to the file
                        with open(file_path, 'wb') as file:
                            file.write(file_data)
                
                handle_file_operations(str_tenancy_id, str_unique_bot_id, str_old_filename, str_new_filename, str_note_name, rst_note['vchr_source_name'], file_data)
                
                # delete from lancedb vector as background process
                executor.submit(trainingService.delete_from_lancedb,str_tenancy_id,str_unique_bot_id,str_old_filename)
                
                # Update the database
                cr.execute("""
                    UPDATE tbl_source
                    SET vchr_source_name = %s, bln_trained = false, tim_uploaded = NOW()
                    WHERE pk_bint_training_source_id = %s
                """, (str_note_name, int_note_id))
                
                if not bln_integration:
                    # Mark the bot as having updated notes
                    cr.execute("UPDATE tbl_bots SET bln_source_changed = true WHERE pk_bint_bot_id = %s", (int_bot_id,))

                # Insert the new URLs and delete any old ones
                cr.execute("DELETE FROM tbl_url_source_mapping WHERE fk_bint_training_source_id = %s", (int_note_id,))
                
                if lst_uploaded_urls:
                    str_image_url_query = "INSERT INTO tbl_url_source_mapping (url, fk_bint_training_source_id) VALUES (%s, %s)"
                    lst_values_insert = [(url, int_note_id) for url in lst_uploaded_urls]
                    cr.executemany(str_image_url_query, lst_values_insert)

                # Commit the database changes
                ins_db.commit()
                
                # Background process to handle deleted URLs
                if lst_deleted_urls:
                    executor.submit(trainingService.delete_blob_uls, lst_deleted_urls)
                
                return dct_response("success", "Note updated successfully"), 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to update the note"), 400

        finally:
            if ins_db:
                ins_db.close()



    @staticmethod
    def delete_notes(request, ins_db, user_id):
        try:
            if isinstance(request, dict):
                dct_request = request
                dct_headers = dct_request.get('headers')
                bln_integration = True
            else:
                dct_request = request.json
                dct_headers = request.headers
                bln_integration = False
            int_bot_id = dct_request.get('intPk')
            str_delete_reason = dct_request.get('strReason')
            
            # check edit permission
            if not bln_integration and not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400

            int_note_id = dct_request.get('intNotesId')

            with create_cursor(ins_db) as cr:
                # Fetch necessary bot and note details
                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s", (int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"), 400

                # check admin, otherwise pending approvel
                cr.execute("select 1 FROM tbl_user WHERE pk_bint_user_id = %s AND fk_bint_user_group_id in (1,3)",(user_id,))
                rst_admin = cr.fetchone()
                
                if not rst_admin:
                    cr.execute("""UPDATE tbl_source 
                                  SET 
                                    bln_pending_approvel = true,
                                    vchr_delete_reason = %s,
                                    fk_bint_deleted_user_id = %s
                                  WHERE pk_bint_training_source_id = %s""",(str_delete_reason,user_id,int_note_id))
                    ins_db.commit()
                    return dct_response("success", "Approvel needed"), 200

                # fetch all uploaded urls , and delete it
                cr.execute("SELECT ARRAY_AGG(url) AS urls FROM tbl_url_source_mapping WHERE fk_bint_training_source_id = %s",(int_note_id,))
                rst_urls = cr.fetchone()
                lst_deleted_urls = rst_urls['urls']
                
                # Fetch the note details for deletion
                cr.execute("DELETE FROM tbl_url_source_mapping WHERE fk_bint_training_source_id = %s",(int_note_id,))
                cr.execute("""
                           UPDATE tbl_source
                           SET chr_document_status = 'D',
                           vchr_delete_reason = %s,
                           fk_bint_deleted_user_id = %s
                           WHERE fk_bint_bot_id = %s 
                           AND pk_bint_training_source_id = %s 
                           RETURNING pk_bint_training_source_id, vchr_source_name, bln_trained"""
                           , (str_delete_reason,user_id,int_bot_id, int_note_id))
                
                rst_source = cr.fetchone()
                if not rst_source:
                    return dct_error("No note found"), 400

                # Set `bln_source_changed` to True
                cr.execute("UPDATE tbl_bots SET bln_source_changed = true WHERE pk_bint_bot_id = %s", (int_bot_id,))
                ins_db.commit()

                str_tenancy_id = get_tenancy_id(dct_headers)
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']
                
                if rst_source['bln_trained']:
                    # Delete note from lancedb

                    str_file_name =  f"{rst_source['pk_bint_training_source_id']}_{rst_source['vchr_source_name']}.txt"
                    executor.submit(trainingService.delete_from_lancedb,str_tenancy_id,str_unique_bot_id,str_file_name)
                    
                else: # if not trained , file will exist in data folder
                    
                    # Delete note file from the 'data' directory
                    str_data_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/data"
                    str_data_filename = f"{int_note_id}_{rst_source['vchr_source_name']}.txt"
                    full_path = os.path.join(str_data_path, str_data_filename)
                    if os.path.exists(full_path):
                        os.remove(full_path)

                # Delete note file from the 'notes' directory
                if not bln_integration:
                    str_notes_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/notes"
                    str_note_filename = f"{int_note_id}_{rst_source['vchr_source_name']}.txt"
                    full_note_path = os.path.join(str_notes_path, str_note_filename)
                    if os.path.exists(full_note_path):
                        os.remove(full_note_path)

                # Background process to handle deleted URLs
                if lst_deleted_urls:
                    executor.submit(trainingService.delete_blob_uls, lst_deleted_urls)

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to delete"), 400

        finally:
            if ins_db:
                ins_db.close()


    @staticmethod
    def get_notes_content(request, ins_db):
        try:
            dct_request = request.json
            int_note_id = dct_request.get('intNotesId')

            with create_cursor(ins_db) as cr:
                cr.execute("""
                        WITH limited_urls AS (
                            SELECT sm.fk_bint_training_source_id, sm.url
                            FROM tbl_url_source_mapping sm
                            WHERE sm.fk_bint_training_source_id = %s
                        )
                        SELECT 
                            b.vchr_azure_resource_uuid,
                            s.vchr_source_name,
                            ARRAY_AGG(lu.url) AS uploaded_image_urls
                        FROM tbl_bots b
                        LEFT JOIN tbl_source s 
                            ON b.pk_bint_bot_id = s.fk_bint_bot_id
                        LEFT JOIN limited_urls lu 
                            ON s.pk_bint_training_source_id = lu.fk_bint_training_source_id
                        WHERE s.pk_bint_training_source_id = %s
                        GROUP BY 
                            b.vchr_azure_resource_uuid,
                            s.vchr_source_name
                        LIMIT 1
                """, (int_note_id,int_note_id))
            
                rst_note = cr.fetchone()

                if not rst_note:
                    return dct_error("No note found"), 400
            
                str_filename = f"{rst_note['vchr_source_name']}.txt"
                str_tenancy_id = get_tenancy_id(request.headers)
                str_notes_path = f"lancedb/{str_tenancy_id}/{rst_note['vchr_azure_resource_uuid']}/notes"
                str_notes_file_path = os.path.join(str_notes_path, f"{int_note_id}_{str_filename}")
                with open(str_notes_file_path, 'r') as file:
                    str_html_content = file.read()

                lst_uploaded_urls = rst_note['uploaded_image_urls']
                return dct_response("success", {"htmlContent": str_html_content,"arrUploadedUrls":lst_uploaded_urls}), 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to retrieve the note"), 400

        finally:
            if ins_db:
                ins_db.close()
                
                

    @staticmethod
    def uploads_from_text_editor(request,ins_db,user_id):
        try:
            int_bot_id = request.form.get('intPk')
            
            # check edit permission
            if not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400
            
            with create_cursor(ins_db) as cr:
                # Fetch the bot's Azure resource UUID from the database
                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s LIMIT 1", (int_bot_id,))

                rst_bot = cr.fetchone()
                
                if not rst_bot:
                    return dct_error("No bot found"), 400
                
                str_container = "nubot" # common container for all bot
                
                file = request.files.get('image')
                if not file:file = request.files.get('file')
                str_file_name = (file.filename or '').replace(' ','_')
                if str_file_name == '':
                    return "No selected file"        
                file_data = file.read()
                
                with create_azure_connection(str_container) as blob_service_client:
                    str_tenancy_id = get_tenancy_id(request.headers)
                    unique_blob_name = f"{str_tenancy_id}/{rst_bot['vchr_azure_resource_uuid']}/uploads/{str(uuid.uuid4())}/{str_file_name}"
                    blob_client = blob_service_client.get_blob_client(container=str_container, blob=f"{unique_blob_name}")
                    
                    blob_client.upload_blob(file_data, overwrite=True, content_settings=ContentSettings(content_type=file.content_type))
                    str_origin =request.headers.get('origin')
                    return {
                                "success": 1,
                                "file": {
                                "url": f"{str_origin}/api/nubot/content/{unique_blob_name}",
                                "extension": file.filename.split(".")[-1],
                                },
                                }

                
        except Exception:
            traceback.print_exc()
            return {
            "success": 0,
            "file": {
            "url": "",
            "extension": "",
            },
            }
    
    @staticmethod
    def stream_uploads(str_blob_url):
        try:
            str_container = "nubot"
            str_connection_string = ins_cfg.get(env_mode,'AZURE_STORAGE_CONNECTION_STRING')
            with BlobServiceClient.from_connection_string(str_connection_string) as blob_service_client:
                sas_token = generate_blob_sas(account_name=blob_service_client.account_name, 
                container_name=str_container,
                blob_name=str_blob_url,
                account_key=blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now() + timedelta(hours=1))
                return redirect(f"https://{blob_service_client.account_name}.blob.core.windows.net/{str_container}/{str_blob_url}?{sas_token}")
        except Exception:
            traceback.print_exc()
            return abort(404)

    @staticmethod
    def delete_uploaded(request):
        try:
            dct_request = request.json
            lst_deleted_urls = dct_request.get("arrRemovedUrls")
                

            # background process to remove deleted blobs
            if lst_deleted_urls:
                executor.submit(trainingService.delete_blob_uls,lst_deleted_urls)
            
            return 'ok'

        except Exception:
            traceback.print_exc()
            return 'ok'
                
                                
    @staticmethod
    def delete_blob_uls(lst_blobs):
        def remove_url_prefix(url):
            return url.split('/api/nubot/content/')[1]
        try:
            str_connection_string = ins_cfg.get(env_mode,'AZURE_STORAGE_CONNECTION_STRING')
            str_container = "nubot"
            with BlobServiceClient.from_connection_string(str_connection_string) as blob_service_client:
                container_client = blob_service_client.get_container_client(str_container)   
                set_need_to_delete_blobs = set(map(remove_url_prefix, lst_blobs))
                container_client.delete_blobs(*set_need_to_delete_blobs)
        except Exception:
            traceback.print_exc()
            
    
    @staticmethod
    def start_url_crawler(request, ins_db, user_id):
        """
        Starts a crawling session in the background. Returns immediately with a success message.
        The actual crawling work is performed by a background thread, which updates progress in Redis.
        """
        try:
            dct_request = request.json
            input_url = dct_request.get("strUrl")
            int_bot_id = dct_request.get("intPk")

            if not input_url or not int_bot_id:
                return dct_error("URL or Bot ID not provided"), 400

            # Check if user has permission for this bot.
            if not botService.check_bot_permission(ins_db, int_bot_id, user_id):
                return dct_error("No Permission"), 400

            with create_cursor(ins_db) as cr:
                # Fetch the bot's unique identifier.
                cr.execute(
                    "SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s",
                    (int_bot_id,)
                )
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"), 400
                unique_bot_id = rst_bot["vchr_azure_resource_uuid"]

                cr.execute(
                """SELECT 1 FROM tbl_source
                WHERE vchr_source_name = %s AND fk_bint_bot_id = %s AND chr_document_status = 'N' """,
                (input_url, int_bot_id)
                )
                exists = cr.fetchone()

                if exists:
                    return dct_error("URL already exists in the database"), 400


                # Insert a new record for the URL source.
                cr.execute("""
                    INSERT INTO tbl_source 
                    (vchr_source_name, fk_bint_bot_id, fk_bint_uploaded_user_id, 
                     vchr_source_type, tim_uploaded, chr_document_status)
                    VALUES (%s, %s, %s, 'URL', NOW(), 'N') 
                    RETURNING pk_bint_training_source_id
                """, (input_url, int_bot_id, user_id))
                source_id = cr.fetchone()[0]
                ins_db.commit()

                # Insert a new crawling history record.
                crawl_uuid = str(uuid.uuid4())
                cr.execute("""
                    INSERT INTO tbl_url_crawling_history 
                    (vchr_crawl_id, fk_bint_bot_id, fk_bint_training_source_id)
                    VALUES (%s, %s, %s)
                """, (crawl_uuid, int_bot_id, source_id))
                ins_db.commit()
                # Create a unique task identifier.
                TASK_ID = f"CRAWLER_TASK_{crawl_uuid}_{source_id}"
                # Initialize Redis keys for tracking progress.
                redis_client.setex(f"{TASK_ID}_status", 14400, "in-progress")

            # Create a unique task identifier.
            str_tenancy_id = get_tenancy_id(request.headers)
            dsn = ins_db.dsn
            str_token=request.headers.get('x-access-token')
            # Launch the background crawling task.
            executor.submit(trainingService.intermediate,TASK_ID,crawl_uuid,str_token,user_id,dsn,int_bot_id,str_tenancy_id, unique_bot_id, source_id, input_url)
            
        
            return "blnCrawlingStarted : true", 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to start crawling"), 400

        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def intermediate(TASK_ID,crawl_uuid,str_token,user_id,dsn,int_bot_id,str_tenancy_id, unique_bot_id, source_id, input_url):
        #asynchronous crawling function
        asyncio.run(trainingService.url_crawler_background(
                TASK_ID,crawl_uuid, str_token,user_id,dsn,int_bot_id,str_tenancy_id, unique_bot_id, source_id, input_url))
    


    @staticmethod
    async def url_crawler_background(TASK_ID,crawl_uuid,str_token,user_id,dsn, int_bot_id, tenancy_id, unique_bot_id, source_id, input_url):
        """
        Background function that performs the actual crawling.
        """

        async def normalize_url(input_url):
            parsed_url = urlparse(input_url)

            # Remove fragment (anything after #)
            parsed_url = parsed_url._replace(fragment="")

            if not parsed_url.scheme:
                return "http://" + urlunparse(parsed_url)  # Ensure scheme is http://
            elif parsed_url.scheme == "https":
                return "http://" + parsed_url.netloc + parsed_url.path  # Convert https -> http

            return urlunparse(parsed_url)  # Return cleaned URL
        
        # Parse DSN and build the async connection string.
        
        params = dict(pair.split('=', 1) for pair in dsn.split())
        dsn_for_async = f"postgresql://{params['user']}:{params['password']}@{params['host']}:{params['port']}/{params['dbname']}"
        
        # Connect using asyncpg.
        url_db = await asyncpg.connect(dsn_for_async)

        try:
            
            
            # Build file path for saving the results (PDF or JSON).
            str_filename = f"{source_id}_{input_url.replace('/', '_')}.json"
            filepath = f"./lancedb/{tenancy_id}/{unique_bot_id}/data/{str_filename}"
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Prepare headers and normalize the URL.
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/92.0.4515.107 Safari/537.36"
                )
            }
            
            # check http exist in given url
            input_url = await normalize_url(input_url)


            # Initialize the crawling queue and set for visited URLs.
            url_queue = asyncio.Queue()
            await url_queue.put((0.5, input_url))
            visited_urls = set()
            results = []

            # Define the worker function for concurrent URL processing.
            async def worker():
                while True:
                    try:
                        priority, current_url = await url_queue.get()
                    except asyncio.CancelledError:
                        break

                    # Skip URLs already processed or containing unwanted patterns.
                    if current_url in visited_urls or any(
                        pattern in current_url for pattern in ["cdn-cgi", "l/email-protection", "pdf", "xlsx"]
                    ):
                        url_queue.task_done()
                        continue

                    try:
                        async with session.get(current_url, headers=headers, timeout=40) as response:
                            if response.status != 200:
                                url_queue.task_done()
                                continue
                            html = await response.text()
                    except Exception as e:
                        url_queue.task_done()
                        continue

                    soup = BeautifulSoup(html, "html.parser")
                    page_text = soup.get_text(separator="\n", strip=True)
                    results.append({"url": current_url, "text": page_text})

                    # Mark the URL as visited 
                    visited_urls.add(current_url)

                    # Enqueue new links found on the page.
                    for link in soup.select("a[href]"):
                        url = link.get("href")
                        url = await normalize_url(url)
                        full_url = requests.compat.urljoin(current_url, url)
                        if full_url.startswith(input_url) and full_url not in visited_urls:
                            priority = 1 if "/page/" in full_url else 0.5
                            await url_queue.put((priority, full_url))
                    url_queue.task_done()
                    await asyncio.sleep(random.uniform(1, 2))  # gentle delay between requests

            # Launch multiple concurrent workers.
            async with aiohttp.ClientSession() as session:
                # Create, for example, 5 worker tasks.
                lst_workers = [asyncio.create_task(worker()) for _ in range(30)]
                await url_queue.join()  # Wait until all queued URLs are processed.
                for w in lst_workers:
                    w.cancel()
                await asyncio.gather(*lst_workers, return_exceptions=True)

            # Once crawling is finished, write the results to file.
            with open(filepath, "w", encoding="utf-8") as json_file:
                json.dump(results, json_file, indent=4, ensure_ascii=False)

            # Update crawling history status to 'done'.
            await url_db.execute("""
                UPDATE tbl_url_crawling_history
                SET vchr_crawling_status = 'done'
                WHERE vchr_crawl_id = $1
            """, crawl_uuid)

            # Prepare URL mapping data for bulk insertion.
            lst_mapping_data = [(source_id, url) for url in visited_urls]
            if lst_mapping_data:
                lst_placeholders = []
                for i in range(len(lst_mapping_data)):
                    lst_placeholders.append(f"(${2*i+1}, ${2*i+2})")
                str_placeholders = ','.join(lst_placeholders)
                lst_flat_values = [value for row in lst_mapping_data for value in row]
                str_bulk_query = f"""
                    INSERT INTO tbl_url_source_mapping (fk_bint_training_source_id, url)
                    VALUES {str_placeholders}
                """
                await url_db.execute(str_bulk_query, *lst_flat_values)

            # Mark the task as completed.
            redis_client.set(f"{TASK_ID}_status", "completed")

        except Exception as e:
            redis_client.set(f"{TASK_ID}_status", "failed")
            await url_db.execute("""
                UPDATE tbl_url_crawling_history
                SET vchr_crawling_status = 'failed'
                WHERE vchr_crawl_id = $1
            """, crawl_uuid)
            json_data = {
                            "intPk": int_bot_id,
                            "strReason": "crawling failed",
                            "headers": {"x-access-token": str_token}
                        }
            trainingService.delete_crawled_data(json_data, dsn, user_id)
            traceback.print_exc()

        finally:
            if url_db:
                await url_db.close()


     

    @staticmethod
    def check_url_crawler_status(request, ins_db):
        """
        Checks the crawling status for the given bot.
        Returns whether the job is complete.
        """
        try:
            dct_request = request.json
            int_bot_id = dct_request.get("intPk")
            if not int_bot_id:
                return dct_error("Bot ID not provided"), 400

            with create_cursor(ins_db) as cr:
                

                # Get the crawling sessions for this bot.
                cr.execute("""
                    SELECT h.vchr_crawl_id,
                        h.fk_bint_training_source_id,
                        s.vchr_source_name
                    FROM tbl_url_crawling_history h
                    LEFT JOIN tbl_source s 
                        ON h.fk_bint_training_source_id = s.pk_bint_training_source_id
                    WHERE h.fk_bint_bot_id = %s 
                    AND h.vchr_crawling_status = 'in-progress'
                """, (int_bot_id,))
                crawl_record = cr.fetchall()
                if not crawl_record:
                    return {"blnCompleted": True}, 200
                # Iterate over each crawl record to check its corresponding Redis status.
                lst_results = []
                for record in crawl_record:
                    
                    crawl_uuid = record["vchr_crawl_id"]
                    source_id = record["fk_bint_training_source_id"]
                    source_name = record.get("vchr_source_name") or "Unknown"
                    TASK_ID = f"CRAWLER_TASK_{crawl_uuid}_{source_id}"
                    redis_status = redis_client.get(f"{TASK_ID}_status")
                    # If the redis key exists, decode its status; otherwise, mark as completed.
                    progress = redis_status.decode() if redis_status is not None else "completed"
                    lst_results.append({
                        "url": source_name,
                        "progress": progress
                    })

                return {"progress": lst_results}, 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to check crawling status"), 400

        finally:
            if ins_db:
                ins_db.close()
        
        

    @staticmethod
    def delete_crawled_data(request, ins_db, user_id):
        try:
            # Extract data from the request payload
            if isinstance(request, dict):
                dct_request = request 
                dct_headers = dct_request.get('headers')
                ins_db = psycopg2.connect(ins_db)
            else:
                dct_request = request.json
                dct_headers = request.headers
            
            int_bot_id = dct_request.get('intPk')
            str_delete_reason = dct_request.get('strReason')

            # check edit permission
            if not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400
            
            int_source_id = dct_request.get('intSourceId')
            str_tenancy_id = get_tenancy_id(dct_headers)

            if not int_bot_id or not int_source_id:
                return dct_error("UnAvailabe"), 400

            with create_cursor(ins_db) as cr:
                # select bot details
                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s LIMIT 1",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"), 400
                
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']

                # check admin, otherwise pending approvel
                cr.execute("select 1 FROM tbl_user WHERE pk_bint_user_id = %s AND fk_bint_user_group_id in (1,3)",(user_id,))
                rst_admin = cr.fetchone()
                
                if not rst_admin:
                    cr.execute("""UPDATE tbl_source 
                                  SET 
                                    bln_pending_approvel = true,
                                    vchr_delete_reason = %s,
                                    fk_bint_deleted_user_id = %s
                                  WHERE pk_bint_training_source_id = %s""",(str_delete_reason,user_id,int_source_id))
                    ins_db.commit()
                    return dct_response("success", "Approvel needed"), 200
                
                
                # delete source and return Source details  
                cr.execute("DELETE FROM tbl_url_source_mapping WHERE fk_bint_training_source_id = %s",(int_source_id,))
                cr.execute("""UPDATE tbl_source
                              SET chr_document_status = 'D',
                              vchr_delete_reason = %s,
                              fk_bint_deleted_user_id = %s
                              WHERE fk_bint_bot_id = %s
                              AND pk_bint_training_source_id = %s 
                              RETURNING pk_bint_training_source_id,vchr_source_name,bln_trained
                            """,(str_delete_reason,user_id,int_bot_id,int_source_id))
                    
                rst_source = cr.fetchone()
                if not rst_source:
                    return dct_error("No source Found"), 400
                
                str_file_name = f"{rst_source['pk_bint_training_source_id']}_{rst_source['vchr_source_name'].replace('/', '_')}.json"
    
                
                # if trained , delete from lancedb
                if rst_source["bln_trained"]: 
                    executor.submit(trainingService.delete_from_lancedb,str_tenancy_id,str_unique_bot_id,str_file_name)
                
                else:
                    file_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/data/{str_file_name}"
                    # Delete the file from the file system if it exists
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        
                # commit db changes
                ins_db.commit()
                
            return dct_response("success", "Urls deleted successfully"), 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to delete"), 400
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def live_chat_upload(request,ins_db,user_id):
        try:
            
            int_bot_id = request.form.get('intPk')
            str_session_id=request.form.get('strSessionId')
            dsn = ins_db.dsn
            
            
            with create_cursor(ins_db) as cr:

                # Fetch the bot's unique ID
                cr.execute("SELECT vchr_azure_resource_uuid FROM  tbl_bots WHERE pk_bint_bot_id = %s LIMIT 1",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"), 400
                
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']
                ins_file = request.files.get('file')
                str_filename = ins_file.filename.replace(' ','_')
                
                if not ins_file:
                    ins_file = request.files.get('file')

                str_filename = ins_file.filename
                if not str_filename:
                    return "No selected file"    

               
                str_tenancy_id = get_tenancy_id(request.headers)
                str_base_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/live_data"
                if not os.path.exists(str_base_path):
                    os.makedirs(str_base_path)
                    
                
                # store file in data directory  
                str_file_path = os.path.join(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/live_data", str_filename)
                ins_file.save(str_file_path)  

                # Trigger training with progress streaming
                attachment_db = psycopg2.connect(dsn)
                return Response(
                    trainingService.live_chat_embedding(str_tenancy_id, str_unique_bot_id,str_session_id,user_id,str_filename,attachment_db),
                    content_type='text/event-stream'
                )
        except Exception:
            traceback.print_exc()
            return dct_error("Unable to upload"), 400
        finally:
            if ins_db:ins_db.close()


    @staticmethod
    def live_chat_embedding(str_tenancy_id,str_unique_bot_id,str_session_id,user_id,str_filename,attachment_db):
        try:
            text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                model_name="gpt-4",
                chunk_size=500,
                chunk_overlap=50,
            )
            
            # load documents from corresponding bot directory
            lst_documents = SimpleDirectoryReader(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/live_data",file_extractor=file_extracter).load_data()

            # generate lancedb uuid for each file
            str_lancedb_uuid=str(uuid.uuid4())

            # total count of docs
            total_docs = len(lst_documents) 
            interval = max(1, total_docs // 20)  

            # stream event 
            yield f"event: progress\ndata: {json.dumps({'status': 'Uploading files'})}\n\n"   
            
            # connect to lancedb            
            db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0))
            
            # connect to lancedb table
            try:
                table = db_lance.open_table("live_chat")
            except ValueError:
                table = db_lance.create_table("live_chat", schema = LiveChatModel, exist_ok = True)
            
            # insert to lancedb table with auto-vectorization
            lst_to_add = []
            chunk_count = 0 
            for index,doc in enumerate(lst_documents,start=1):
                
                if doc.text:
                    lst_chunks = text_splitter.split_text(doc.text)
                    # Update the chunk count
                    chunk_count += len(lst_chunks)  
                    # Prepare chunks for insertion
                    lst_to_add.extend(
                        
                        {"id":str_lancedb_uuid,"file_name": doc.metadata['file_name'], "user_id": str(user_id),
                               "sid": str_session_id,"text": chunk}
                        for chunk in lst_chunks
                    )

                    # Add chunks to the table in batches
                    if chunk_count >= 2:  # Flush in batches of 2 chunks
                        table.add(lst_to_add)
                        lst_to_add = []
                        chunk_count = 0
                        
                                    
                if index % (interval * 2) == 0: # Set progress streaming every 10%
                    progress = int(((index) / total_docs) * 100)
                    # stream progress
                    yield f"event: progress\ndata: {json.dumps({'Analysing': f'{progress}%'})}\n\n"
                    
                    
            # Add remaining chunks, if any
            if lst_to_add:
                table.add(lst_to_add)

            yield f"event: progress\ndata: {json.dumps({'Completed': f'{str_filename}'})}\n\n"
            
            # after training delete all source data from directory
            str_bot_source_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/live_data/"
            if os.path.exists(str_bot_source_path):
                shutil.rmtree(str_bot_source_path) 
            

            #insert into chat_attachment table
            with create_cursor(attachment_db) as cr:
                cr.execute("""
                        INSERT INTO tbl_chat_attachment
                        (vchr_socket_id, vchr_attachment_name, vchr_lancedb_uuid) 
                        VALUES (%s, %s, %s)  
                    """, (str_session_id, str_filename, str_lancedb_uuid))

                attachment_db.commit()
                
            # optimize the table
            executor.submit(optimize_lancedb,str_tenancy_id,str_unique_bot_id,"live_chat")
            
           
            
        except Exception:
            traceback.print_exc()
            yield f"event: progress\ndata: {json.dumps({'status': 'Error'})}\n\n"
        
        finally:
            if attachment_db:attachment_db.close()


    @staticmethod
    def delete_attachment(request, ins_db):
        try:
            dct_request = request.json
            str_session_id=dct_request.get('strSessionId')
            int_bot_id = dct_request.get('intPk')

            with create_cursor(ins_db) as cr:
                # select bot details
                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s LIMIT 1",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"), 400
                
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']
                str_tenancy_id = get_tenancy_id(request.headers)

                # Get the last uploaded attachment's UUID
                cr.execute(
                    """
                    SELECT vchr_lancedb_uuid,pk_bint_attachment_id
                    FROM tbl_chat_attachment 
                    WHERE vchr_socket_id = %s 
                    ORDER BY pk_bint_attachment_id DESC 
                    LIMIT 1
                    """,
                    (str_session_id,)
                )
                rst = cr.fetchone()
                
                if not rst:
                    return dct_error("No attachment found"), 404
                
                lancedb_uuid, attachment_id = rst["vchr_lancedb_uuid"], rst["pk_bint_attachment_id"]

                # Delete the entry from tbl_chat_attachment
                cr.execute(
                    "DELETE FROM tbl_chat_attachment WHERE pk_bint_attachment_id = %s",
                    (attachment_id,)
                )

                # delete from LanceDB
                executor.submit(trainingService.delete_attachment_from_lancedb,str_tenancy_id,str_unique_bot_id,lancedb_uuid)
                
                return {"message": "Attachment deleted successfully"}, 200
                    

        except Exception:
            traceback.print_exc()
            dct_error("Unable to delete"), 400
            
                
    
    @staticmethod        
    def get_references(request,ins_db,user_id):
        try:

            def remove_source_id(str_file_name):
                # If '/' in note name converting it into '__SLASH__' eg : abc/def -> abc__SLASH__def
                str_file_name = str_file_name.replace("__SLASH__","/")
                # Use regex to remove numbers and underscores
                lst_splited_filename = re.split("_", str_file_name)
                #skipping id from the filename 
                str_corrected = '_'.join(lst_splited_filename[1:len(lst_splited_filename)])
                return str_corrected
            
            # Extract data from the request payload
            dct_request= request.json
            int_bot_id = dct_request.get('intPk')
            arrReferencesId =dct_request.get("arrReferencesId")
            references = []
            if not arrReferencesId:
                return dct_response("success",references),200
        
            # check edit permission
            if not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                    return dct_error("No Permission"),400
            
            # Retrieve tenancy and bot details
            with create_cursor(ins_db) as cr:
                cr.execute("SELECT vchr_azure_resource_uuid FROM tbl_bots WHERE pk_bint_bot_id = %s LIMIT 1",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"), 400
                
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']
                str_tenancy_id = get_tenancy_id(request.headers)
                
                # Connect to LanceDB
                db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0))
                
                #Opening lancedb table named embeddings
                try:
                    table = db_lance.open_table("embedding")
                except ValueError:
                    table = db_lance.create_table("embedding", schema = EmbedModel, exist_ok = True)
                
                # Retrieving references(id and text) using the given 
                str_query = 'id in ("' + '","'.join(arrReferencesId) + '")'
                # regx used to remove the integers in the filename
                references = [{"row_id":row['id'],"file_name":remove_source_id(row["file_name"]), "text":row['text']}  for row in table.search().where(str_query).limit(20).to_list()]
                
            return dct_response("success",references),200
    
        except Exception:
            traceback.print_exc()
            return dct_error("Unable to edit Bot response "), 400
        finally:
            if ins_db:
                ins_db.close()
            
    @staticmethod
    def update_referance(request, ins_db, user_id):
        try:
            dct_request = request.json
            int_bot_id = dct_request.get('intPk')
            
            # check edit permission
            if not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400
            updated_references=dct_request.get("arrReferences")
            
            with create_cursor(ins_db) as cr:
                
                # Retrieve tenancy and bot details
                cr.execute("SELECT vchr_azure_resource_uuid FROM  tbl_bots WHERE pk_bint_bot_id = %s LIMIT 1",(int_bot_id,))
                rst_bot = cr.fetchone()
                if not rst_bot:
                    return dct_error("No bot found"), 400
                
                str_tenancy_id = get_tenancy_id(request.headers)
                str_unique_bot_id = rst_bot['vchr_azure_resource_uuid']

                # Connect to LanceDB
                db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0))
                
                # Opening lancedb table named embeddings
                try:
                    table = db_lance.open_table("embedding")
                except ValueError:
                    table = db_lance.create_table("embedding", schema = EmbedModel, exist_ok = True)
                
                #updating text in the lancedb usig the id of that particular text
                for ref in updated_references:
                    ref_id = ref.get("id")
                    ref_text = ref.get("text")
                    table.update(where = f"id = '{ref_id}'", values= {"text":ref_text})
                
                return dct_response("success", "References updated successfully"), 200
        except Exception:
            traceback.print_exc()
            return dct_error("Unable to edit Bot response "), 400
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def embedding(str_tenancy_id,str_unique_bot_id,int_training_id,dsn,int_bot_id):
        try:
            # set a task ID , to track the embedding progress
            TASK_ID = f"EMBEDDING_TASK_{str_unique_bot_id}_{int_training_id}"
            
            embedding_db = psycopg2.connect(dsn)
            
            if redis_client.get(f"{TASK_ID}_status").decode().strip() == "stopped":
                raise KeyboardInterrupt
            
            logging.info(f"[{TASK_ID}] Starting embedding task...")

            with create_cursor(embedding_db) as cr:
                
                cr.execute("SELECT UNNEST(arr_source_ids) FROM tbl_training_history WHERE pk_bint_bot_training_id = %s",(int_training_id,))
                
                # return like [[123],[124],[125]]
                rst_resouce_id = cr.fetchall() 
                
                # converting to [123,124,125]
                rst_resouce_id = [str(item[0]) for item in rst_resouce_id] 
                
                source_directory=f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/data"
            
                if not os.path.exists(source_directory):
                    print("Directory not found.")
                    return
                
                # to get all the file names in a list
                lst_files_in_source = os.listdir(source_directory)
                
                # getting all the file name that starts with arr_source_ids
                matching_files = [file_name for file_name in lst_files_in_source if any(file_name.startswith(f"{id}_") for id in rst_resouce_id)]

                training_file_paths = [f"{source_directory}/{filename}" for filename in matching_files]
                logging.info(f"[{TASK_ID}] Running add_to_lancedb with {len(training_file_paths)} files...")
                asyncio.run(trainingService.add_to_lancedb(training_file_paths,str_tenancy_id,str_unique_bot_id,TASK_ID,matching_files))
                logging.info(f"[{TASK_ID}] Completed add_to_lancedb.")

                    
        except Exception:
            redis_client.set(f"{TASK_ID}_status", "failed")
            logging.info(f"[{TASK_ID}] Exception occurred during embedding:")
            traceback.print_exc()

        
        except KeyboardInterrupt:
            pass
        
        finally:
            try:
                # checking redis status 
                str_embedding_status = redis_client.get(f"{TASK_ID}_status").decode()   
                if not str_embedding_status:
                    logging.info(f"[{TASK_ID}] Status not found, skipping DB update.")
                
                with create_cursor(embedding_db) as cr:
                    #if redis status = completed  
                    if str_embedding_status == 'completed':
                        logging.info(f"[{TASK_ID}] Updating training history and source to success...")
                        cr.execute("""UPDATE tbl_training_history 
                                        SET vchr_status='success' 
                                        WHERE fk_bint_bot_id = %s 
                                        AND vchr_status IN ('in-progress','integration')
                                        AND pk_bint_bot_training_id = %s""",(int_bot_id,int_training_id))
                            
                        cr.execute("""UPDATE tbl_source
                                        SET bln_trained=true
                                        WHERE fk_bint_bot_id = %s 
                                        AND pk_bint_training_source_id IN  %s """,(int_bot_id,tuple(rst_resouce_id)))  

                        cr.execute("""UPDATE tbl_bots SET bln_enabled=true WHERE pk_bint_bot_id = %s""",(int_bot_id,))  
                        
                        
                    elif str_embedding_status == 'failed':
                        cr.execute("""UPDATE tbl_training_history 
                                SET vchr_status='failed' 
                                WHERE fk_bint_bot_id = %s 
                                AND vchr_status IN ('in-progress','integration')
                                AND pk_bint_bot_training_id = %s""",(int_bot_id,int_training_id))
                        

                    elif str_embedding_status == 'stopped':
                        cr.execute("""UPDATE tbl_training_history 
                                SET vchr_status='stopped' 
                                WHERE fk_bint_bot_id = %s 
                                AND vchr_status IN ('in-progress','integration')
                                AND pk_bint_bot_training_id = %s""",(int_bot_id,int_training_id))
                        
                    embedding_db.commit()
                    logging.info(f"[{TASK_ID}] DB commit complete.")

                    # delete redis keys
                    redis_client.delete(f"{TASK_ID}_progress", f"{TASK_ID}_status") 
                    logging.info(f"[{TASK_ID}] Redis keys deleted.")
                    # periodic embedding table optimization, after each 5 training
                if int_training_id % 5 == 0:
                    executor.submit(optimize_lancedb,str_tenancy_id,str_unique_bot_id,"embedding")

               
                        
            except Exception as e:
                logging.info(f"[{TASK_ID}] Exception in final DB update block: {e}")
                traceback.print_exc()
                
            finally:
                if embedding_db:
                    embedding_db.close()
                    logging.info(f"[{TASK_ID}] DB connection closed.")
                            
    async def add_to_lancedb(training_file_paths,str_tenancy_id,str_unique_bot_id,TASK_ID,matching_files):
        try:
            # Async redis connection.
            async_redis_client = async_redis.Redis(host=ins_cfg.get(env_mode, 'REDIS_HOST'), port=ins_cfg.get(env_mode, 'REDIS_PORT'))
            
            lst_documents = await SimpleDirectoryReader(input_files = training_file_paths).aload_data()
            text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                chunk_size=500,
                chunk_overlap=50,
            )
            total_docs = len(lst_documents)
            interval = max(1, total_docs // 20) 
            bln_single_doc = bool(total_docs == 1)
            
            # connect to lancedb            
            db_lance = await connect_async(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0))
            
            # connect to lancedb table 
            try:
                table = await db_lance.open_table("embedding")
            except ValueError:
                table = await db_lance.create_table("embedding", schema = EmbedModel, exist_ok = True)
            
            # insert to lancedb table with auto-vectorization
            lst_to_add = []
            chunk_count = 0 
            for index,doc in enumerate(lst_documents,start=1):
                
                if doc.text:
                    
                    status = await async_redis_client.get(f"{TASK_ID}_status")
                    if status and status.decode().strip() == "stopped":
                        raise KeyboardInterrupt
                    
                    lst_chunks = text_splitter.split_text(doc.text)
                    chunk_count += len(lst_chunks)  # Update the chunk count
                    
                    # Prepare chunks for insertion
                    lst_to_add.extend(
                        {"id":str(uuid.uuid4()),"file_name": doc.metadata['file_name'], "text": chunk}
                        for chunk in lst_chunks
                    )

                    # Add chunks to the table in batches and lst_to_add should not be empty
                    if chunk_count <= 5 and lst_to_add:  # Flush in batches of 5 chunks
                        await table.add(lst_to_add)
                        lst_to_add = []
                        chunk_count = 0
                        
                    else:
                        while lst_to_add:
                            lst_sub_add = lst_to_add[:5]  # Get up to 5 elements
                            del lst_to_add[:5]  # Remove them from the original list
                            if lst_sub_add:  # Double-check it's not empty
                                await table.add(lst_sub_add)

                            if bln_single_doc:
                                task_progress_key = f"{TASK_ID}_progress"
                                value = await async_redis_client.get(task_progress_key)
                                single_doc_progress = int(float(value.decode()))

                                if lst_to_add:
                                    increment = min(99.99 - single_doc_progress, (5 / len(lst_to_add)) * 100)
                                    single_doc_progress += increment
                                else:
                                    single_doc_progress = 99.99
                                single_doc_progress = round(single_doc_progress, 2)
                                await async_redis_client.set(task_progress_key, single_doc_progress)
                        chunk_count = 0
                        
                # Update Redis every few documents based on interval
                if index % interval == 0: # Set Redis progress every 5%
                    progress = int(((index) / total_docs) * 100)
                    await async_redis_client.set(f"{TASK_ID}_progress", progress)
                    
            
            # set task status/progress (Redis)
            await async_redis_client.set(f"{TASK_ID}_progress", 100)
            await async_redis_client.set(f"{TASK_ID}_status", "completed")
            
            # after training delete all source data from directory
            base_path = f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/data"

            for file_name in matching_files:
                file_path = os.path.join(base_path, file_name)
                try:
                    os.remove(file_path)
                except FileNotFoundError:
                    pass  # File already deleted or does not exist

        except Exception as e:
            await async_redis_client.set(f"{TASK_ID}_status", "failed")
            traceback.print_exc()
        except KeyboardInterrupt:
            pass
    
    @staticmethod
    def delete_from_lancedb(str_tenancy_id,str_unique_bot_id,str_file_name):
        #Connecting to lancedb
        db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0))

        #Opening lancedb table named embeddings
        try:
            table = db_lance.open_table("embedding")
        except ValueError:
            table = db_lance.create_table("embedding", schema = EmbedModel, exist_ok = True)
        
        
        #Deleting source from lancedb table using file name  
        table.delete(f"file_name = '{str_file_name}'")
        
        # optimize
        executor.submit(optimize_lancedb,str_tenancy_id,str_unique_bot_id,"embedding")
        

    @staticmethod
    def delete_attachment_from_lancedb(str_tenancy_id,str_unique_bot_id,lancedb_uuid):
        #Connecting to lancedb
        db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0))

        # connect to lancedb table
        try:
            table = db_lance.open_table("live_chat")
        except ValueError:
            table = db_lance.create_table("live_chat", schema = LiveChatModel, exist_ok = True)
        
        #Deleting source from lancedb table using file name  
        table.delete(f"id = '{lancedb_uuid}'")
        
        # optimize
        executor.submit(optimize_lancedb,str_tenancy_id,str_unique_bot_id,"live_chat")
import psycopg2    
import psycopg2.extras
import traceback
import jwt
import pytz
import smtplib
import json
import requests
import lancedb
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime,timedelta

from app.schema.lancedb import EmbedModel,LiveChatModel,MemoryModel
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.conf_path import str_configpath
from app.utils.global_config import env_mode
from azure.storage.blob import BlobServiceClient


ins_configuration = ConfigParserCrypt()
ins_configuration.read(str_configpath)
SERVER = 'smtp.gmail.com:587'

def call_sso_api(str_action, str_sso_token, dct_payload,str_origin):#to get login details

    dct_headers={
                "Content-Type": 'application/json',
                "authorization": str_sso_token, 
                "origin": str_origin
                }
    if dct_payload:
        str_payload = json.dumps(dct_payload)
        url=ins_configuration.get(env_mode,'sso_host')#+':'+ins_configuration.get(env_mode,'sso_tenancy_port')
        ins_response =  requests.post(url+ str_action, headers = dct_headers, data = str_payload ,verify = False)
    return ins_response


def dct_error(str_message):
    dct_error={"errCommon":[{"strMessage":str_message}]}
    return dct_error

def dct_response(str_status,str_message):
    dct_response={'strStatus':str_status,'strMessage':str_message}
    return dct_response

def dct_get_response(int_total_count,int_offset,int_page_limit,arr_list):
    
    dct_get_response={
       "objPagination": {
           "intTotalCount": int_total_count,
           "intPageOffset": int_offset,
           "intPerPage": int_page_limit
                         },
       "arrList": arr_list

    }
    return dct_get_response  

def create_cursor(ins_db, *args):
    cr = ins_db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    return cr

def create_azure_connection(container_name):
    try:
        connection_string = ins_configuration.get(env_mode, 'AZURE_STORAGE_CONNECTION_STRING')
        #create connection with URL and Acess_key
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        if not container_client.exists():
            #create container if not exist
            blob_service_client.create_container(container_name)
                         
        else:
            pass
        
        return  blob_service_client

    except Exception as ex:
        raise Exception(ex)
    
def get_tenancy_id(dct_headers):
    try:
        # decode the token to get tenancy ID
        str_token = dct_headers.get('x-access-token').replace("Bearer ","")        
        dct_token = jwt.decode(str_token, verify=False, algorithm='RS256') 
        return  dct_token.get('strTenancyId')
    
    except Exception:
        traceback.print_exc()


def convert_time(tim_modified_time):
    # Calculate the time difference with the current time
    tim_current_time = datetime.now()
    if not tim_modified_time:
        return ''
    tim_difference = tim_current_time - tim_modified_time

    # Convert the time difference to minutes
    int_second_difference = tim_difference.total_seconds()
    if int_second_difference < 60:
      int_second_difference = int(int_second_difference)
      return f"{int_second_difference} second ago" if int_second_difference in (0,1) else f"{int_second_difference} seconds ago"
    
    int_minutes_difference = int_second_difference / 60

    # Determine the appropriate message based on the time difference
    if int_minutes_difference < 60:
        return f"{int(int_minutes_difference)} minutes ago"
    elif int_minutes_difference < 1440:  # 1440 minutes = 24 hours
        int_hours_difference = int(int_minutes_difference / 60)
        return f"{int_hours_difference} hour ago" if int_hours_difference == 1 else f"{int_hours_difference} hours ago"
    else:
        return f"On {tim_modified_time.strftime('%B %d, %Y')}"

def time_difference_with_timezone(timezone_str, given_datetime):
    # Get current time in the specified timezone
    current_time = datetime.now(pytz.timezone(timezone_str))

    # Calculate the time difference
    time_diff = current_time - given_datetime

    # Convert time difference to seconds
    time_diff_seconds = time_diff.total_seconds()

    # Define time intervals
    intervals = [
        ('year', 33072000),
        ('month', 2592000),
        ('week', 604800),
        ('day', 86400),
        ('hour', 3600),
        ('minute', 60),
        ('second', 1)
    ]

    # Calculate the time difference in human-readable format
    for interval_name, seconds_in_interval in intervals:
        interval_value = time_diff_seconds // seconds_in_interval
        if interval_value > 0:
            if interval_value == 1:
                return f"{int(interval_value)} {interval_name} ago"
            else:
                return f"{int(interval_value)} {interval_name}s ago"

    return "just now"  # If the time difference is less than a second

def convert_time_to_client_timezone(created_time, client_timezone='Asia/Kolkata'):

    # Set the timezone of the created datetime to UTC

    created_datetime_utc = created_time.astimezone(pytz.utc)




    # Convert the UTC time to the client's timezone

    client_tz = pytz.timezone(client_timezone)

    created_datetime_client_tz = created_datetime_utc.astimezone(client_tz)




    return created_datetime_client_tz   

def htmlEmailSend(HTML,subject,receiver_email): 
    try:
        sender_email = ins_configuration.get(env_mode, 'smtp_email')
        sender_password = ins_configuration.get(env_mode, 'smtp_password')
        server = smtplib.SMTP(SERVER)
        server.ehlo()
        server.starttls()
        server.login(sender_email, sender_password)
        message = MIMEMultipart()
        message['Subject'] = subject
        message['From'] = sender_email
        message['To'] = receiver_email
        message.attach(MIMEText(HTML, "html"))
        message = message.as_string()
        
        server.sendmail(sender_email, receiver_email.split(','),message)
        server.quit()

    except Exception:
        traceback.print_exc()


def optimize_lancedb(str_tenancy_id,str_unique_bot_id,str_table):
    db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_unique_bot_id}/lancedb", read_consistency_interval=timedelta(seconds=0))
    dct_model = {"embedding":EmbedModel,"memory":MemoryModel,"live_chat":LiveChatModel}
    try:
        embedding_table = db_lance.open_table(str_table)
    except ValueError:
        embedding_table = db_lance.create_table(str_table, schema = dct_model[str_table], exist_ok = True)
    try:
        embedding_table.optimize(cleanup_older_than=timedelta(days=1),delete_unverified=True)
    except Exception:
        traceback.print_exc()
        return
    return
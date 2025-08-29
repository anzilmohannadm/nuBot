from flask import Flask, request, render_template
import requests
import redis
import hashlib
import traceback
import json

app = Flask(__name__)

#-------configure here ----------------

SSO_AUTH_URL = 'https://sso.corex.travel'
# NUBOT_URL = 'http://192.168.12.124:40000' 
# for production comment the line number 99 also 
NUBOT_URL = 'https://nubot.corex.travel'
USER = 'mnyasck+testmateauto@nucore.in'
PASSWORD ='Testm@te123'

#--------------------------------------


def get_sso_token_from_redis(str_user_name = '',str_password='',str_tenant_id = '',redis_con=object):
    # eg:- NUBOT:access_zatcauser@nucore.in_@_Test@123
    access_key = f'NUBOT:access_{str_user_name}_@_{str_password}'
    refresh_key = f'NUBOT:refresh_{str_user_name}_@_{str_password}'

    # generate unique key for both access/refresh token
    str_access_key_hash = hashlib.sha256(access_key.encode()).hexdigest()
    str_refresh_key_hash = hashlib.sha256(refresh_key.encode()).hexdigest()
    
    lst_byte_keys = redis_con.mget(str_access_key_hash, str_refresh_key_hash)
    
    dct_redis_data = {
        'str_access_key': lst_byte_keys[0].decode('utf8') if lst_byte_keys[0] else None,
        'str_refresh_key': lst_byte_keys[1].decode('utf8') if lst_byte_keys[1] else None
    }
        
    return dct_redis_data

def call_to_sso(str_user_name,str_password,dct_redis_data={},redis_con=object,dct_extra={}):
    dct_headers={"Content-Type": 'application/json'}

    if not dct_redis_data:
        str_payload = json.dumps({"strUserName":str_user_name,"strPassword":str_password})
        str_action = '/api/authentication/auth/login-user'
    else:
        str_payload = json.dumps({"strAccessToken":dct_redis_data['str_access_key'],"strRefreshToken":dct_redis_data['str_refresh_key']})
        str_action = '/api/authentication/auth/refresh-token'
        
    # try lglogin    
    try:
        dct_response =  requests.post(SSO_AUTH_URL+ str_action, headers = dct_headers, data = str_payload ,verify = False).json()
    except Exception:
        traceback.print_exc()
        return {}
    
    if 'errModuleWise' in dct_response:
        """SESSION ALREADY EXIST"""
        str_access_token = dct_response['errModuleWise'][0]['objDetails']['strAccessToken']
        str_refresh_token = dct_response['errModuleWise'][0]['objDetails']['strRefreshToken']
        
    elif 'AccessToken' in dct_response:
        """ACCESS TOKEN EXPIRED"""
        str_access_token = dct_response['AccessToken']
        str_refresh_token = dct_redis_data['str_refresh_key']
        
    elif 'errCommon' in dct_response and  dct_response['errCommon'][0].get('objDetails','')=='jwt expired':
        """REFRESH TOKEN EXPIRED"""
        dct_tokens = call_to_sso(str_user_name,str_password,dct_redis_data = dct_extra,redis_con=redis_con)
        str_access_token = dct_tokens['str_access_key']
        str_refresh_token = dct_tokens['str_refresh_key']
    
    elif 'strAccessToken' in dct_response:
        """LOGIN SUCCESS"""
        str_access_token = dct_response['strAccessToken']
        str_refresh_token = dct_response['strRefreshToken']
    else:
        """OTHER EXCEPTIONS"""
        return {}
    
    # access and refresh token store in to the redis with unique keys  
    str_refresh_key_hash = hashlib.sha256((f'NUBOT:refresh_{str_user_name}_@_{str_password}').encode()).hexdigest()
    data = {str_refresh_key_hash: str_refresh_token}
    redis_con.mset(data)
    return str_access_token

def make_api_call(api_url, payload,token):
    # Makes an API call with the given url,payload and token and return response.
    try:
        response = requests.post(api_url, json=payload,headers= {
                    "Content-Type": "application/json", # Adjust if needed
                    "X-Access-Token":token
                })
        
        return response.json()
    except requests.exceptions.RequestException as e:
        return None

def get_token(str_user_name,str_password):
    # return '' # comment this line for production
    if not str_user_name or not str_password:
        return 'USER_CREDENTIALS_MISSING',401
    
    # create redis connection , and reuse along the code
    redis_con = redis.StrictRedis(host='192.168.12.124', port=6379)
    # each user's access token and refersh token will be stored in the redis server with unique keys (hash256) 
    dct_redis_data = get_sso_token_from_redis(str_user_name,str_password,redis_con=redis_con)
    str_token = call_to_sso(str_user_name,str_password,dct_redis_data= {},redis_con=redis_con,dct_extra = dct_redis_data)   
    return str_token

# Flask route for the index page
@app.route("/", methods=["GET"])
def index():
    return render_template("diagnostics.html")

# Flask routes
@app.route("/psql", methods=["GET", "POST"])
def psql():
    if request.method == "POST":
        query = request.form.get("query")
        password = request.form.get("password")
        
        try:
            # Define the headers (if any)
            headers = {
                "Content-Type": "application/json",
                "X-Access-Token": get_token(USER,PASSWORD)
            }

            # Define the data to be sent in the PUT request
            dct_payload = {"strQuery":query,"strPassword":password}

            # Make the PUT request
            response = requests.post(NUBOT_URL+'/api/nubot/diagnostics', json=dct_payload, headers=headers)
            result = response.json()

            if isinstance(result, list):  # Check if result is a list of dictionaries
                if not result:
                    return render_template("psql.html", query=query, message="No Records found")
                
                return render_template("psql.html", query=query, table=result)
            else:
                return render_template("psql.html", query=query, message=result)
        except Exception as e:
            return render_template("psql.html", query=query, message=f"Error: {e}")
    return render_template("psql.html")

# Flask routes
@app.route("/lance", methods=["GET", "POST"])
def lance():
    if request.method == "POST":
        tenancy_id = request.form.get("tenancy_id")
        bot_id = request.form.get("bot_id")
        lance_tbl = request.form.get("lance_tbl")
        action = request.form.get("action")
        query = request.form.get("query")
        password = request.form.get("password")
        
        try:
            # Define the headers (if any)
            headers = {
                "Content-Type": "application/json",
                "X-Access-Token": get_token(USER,PASSWORD)
            }
            
            # Define the data to be sent in the PUT request
            dct_payload = {"strTenancyId":tenancy_id,
                           "strBotId":bot_id,
                           "strTable":lance_tbl,
                           "strAction":action,
                           "strQuery":query,
                           "strPassword":password
                           }
            print("hello")
            # Make the PUT request
            response = requests.put(NUBOT_URL+'/api/nubot/diagnostics', json=dct_payload, headers=headers)
            result = response.json()

            if isinstance(result, list):  # Check if result is a list of dictionaries
                if not result:
                    return render_template("lance.html",
                                           query=query,
                                           table=result,
                                           tenancy_id=tenancy_id,
                                           bot_id=bot_id,
                                           lance_tbl=lance_tbl,
                                           action=action, message="No Records found")
                
                return render_template("lance.html",
                                       query=query,
                                       tenancy_id=tenancy_id,
                                       bot_id=bot_id,
                                       lance_tbl=lance_tbl,
                                       action=action,
                                       table=result)
            else:
                return render_template("lance.html",
                                       query=query,
                                       tenancy_id=tenancy_id,
                                       bot_id=bot_id,
                                       lance_tbl=lance_tbl,
                                       action=action, message=result)
                
        except Exception as e:
            return render_template("lance.html",
                                    query=query,
                                    table=result,
                                    tenancy_id=tenancy_id,
                                    bot_id=bot_id,
                                    lance_tbl=lance_tbl,
                                    action=action, message=f"Error: {e}")
            
    return render_template("lance.html")

# Flask routes
@app.route("/dir", methods=["GET", "POST"])
def directory():
    if request.method == "POST":
        path = request.form.get("path")
        action = request.form.get("action")
        password = request.form.get("password")
        
        try:
            # Define the headers (if any)
            headers = {
                "Content-Type": "application/json",
                "X-Access-Token": get_token(USER,PASSWORD)
            }
            
            # Define the data to be sent in the PUT request
            dct_payload = {"strPath":path,"strAction":action,"strPassword":password}

            # Make the PUT request
            response = requests.delete(NUBOT_URL+'/api/nubot/diagnostics', json=dct_payload, headers=headers)
            result = response.json()

            if isinstance(result, list):  # Check if result is a list of dictionaries
                if not result:
                    return render_template("dir.html",
                                           path=path,
                                           result=result,
                                           action=action, message="No Records found")
                
                return render_template("dir.html",
                                       path=path,
                                       action=action,
                                       result=result)
            else:
                return render_template("dir.html",
                                       path=path,
                                       action=action, message=result)
                
        except Exception as e:
            return render_template("dir.html",
                                    path=path,
                                    result=result,
                                    action=action, message=f"Error: {e}")
            
    return render_template("dir.html")

if __name__ == "__main__":
    app.run(host= '0.0.0.0',port=5000,debug=True)

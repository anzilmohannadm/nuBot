import logging
import json
import requests
import traceback
import redis
import httpx
from requests.auth import HTTPBasicAuth
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.global_config import env_mode
from app.utils.conf_path import str_configpath
from app.agents.helpers.nuflights_queries import login_query
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import ToolNode

# Configure logging to print only to console
logging.basicConfig(level=logging.INFO)

# Load configuration
ins_configuration = ConfigParserCrypt()
ins_configuration.read(str_configpath)

NUHIVE_URL = ins_configuration.get(env_mode, 'NUHIVE_URL')
NUHIVE_LOGIN_URL = ins_configuration.get(env_mode, 'NUHIVE_LOGIN_URL')
NUTRAACS_URL = ins_configuration.get(env_mode, 'NUTRAACS_URL')


# redis client connection
redis_client = redis.Redis(host=ins_configuration.get(env_mode, 'REDIS_HOST'), port=ins_configuration.get(env_mode, 'REDIS_PORT'))


def handle_tool_error(state) -> dict:
    error = state.get("error")
    logging.info(f"issue is : {error}")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )

def set_agent_config(dct_agent, str_agent_thread, agent_type,whatsapp_body,whatsapp_token):
    """
    Set configuration for different agent types (bi_agent, nutraacs_agent, nuflight_ota)
    
    Args:
        dct_agent: Dictionary containing agent credentials and info
        str_agent_thread: Unique identifier for the agent thread
        agent_type: Type of agent ('bi', 'nutraacs', 'nuflights')
    
    Returns:
        Dictionary with agent configuration
    
    Raises:
        Exception: If login fails or other errors occur
    """
    try:
        config = {
            "configurable": {
                "thread_id": str_agent_thread,
                "whatsapp_body":whatsapp_body,
                "whatsapp_token":whatsapp_token
            }
        }
        
        if agent_type == 'BI':
            # BI Agent - Cookie based authentication
            cookie_jar = None
            if redis_client.exists(str_agent_thread):
                cookie_value = redis_client.get(str_agent_thread).decode("utf-8")
                cookie_jar = requests.cookies.RequestsCookieJar()
                for part in cookie_value.split(";"):
                    name, value = part.strip().split("=", 1)
                    cookie_jar.set(name, value)
            else:
                login_url = f"{dct_agent.get('strDomain')}/api/mobApp/login"
                auth_payload = {
                    "user_name": dct_agent.get("strUserName"),
                    "password": dct_agent.get("strPassword"),
                    "client_id": dct_agent.get("strClientId")
                }
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip, deflate, br"
                }
                response = requests.post(
                    login_url,
                    headers=headers,
                    data=json.dumps(auth_payload),
                    auth=HTTPBasicAuth(
                        dct_agent.get("strUserName"),
                        dct_agent.get("strPassword")
                    )
                )
                
                if response.status_code != 200:
                    raise Exception("BI Agent login failed")
                
                cookie_string = "; ".join([f"{c.name}={c.value}" for c in response.cookies])
                redis_client.setex(str_agent_thread, 86400, cookie_string)
                cookie_jar = response.cookies
            
            config["configurable"].update({
                "domain": dct_agent.get("strDomain"),
                "cookie": cookie_jar
            })
            
        elif agent_type == 'NUTRAACS':
            # Nutraacs Agent - Token based authentication
            access_key = f"{str_agent_thread}_ACCESS_TOKEN"
            refresh_key = f"{str_agent_thread}_REFRESH_TOKEN"
            
            if redis_client.exists(access_key):
                str_access_token = redis_client.get(access_key).decode("utf-8")
                str_refresh_token = redis_client.get(refresh_key).decode("utf-8")
            else:
                login_url = f"{NUTRAACS_URL}/api/authentication/auth/login-user"
                auth_payload = {
                    "strUserName": dct_agent.get("strUserName"),
                    "strPassword": dct_agent.get("strPassword")
                }
                response = requests.post(
                    login_url,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(auth_payload)
                )
                if response.status_code == 200:
                    data = response.json()
                    str_access_token = data.get("strAccessToken")
                    str_refresh_token = data.get("strRefreshToken")
                    
                    redis_client.setex(f"{str_agent_thread}_ACCESS_TOKEN", 86400, str_access_token)
                    redis_client.setex(f"{str_agent_thread}_REFRESH_TOKEN", 86400, str_refresh_token)
                    
                elif "errModuleWise" in response.json():
                    err_data = response.json().get("errModuleWise")[0].get("objDetails")
                    str_access_token = err_data.get("strAccessToken")
                    str_refresh_token = err_data.get("strRefreshToken")
                    
                    redis_client.setex(f"{str_agent_thread}_ACCESS_TOKEN", 86400, str_access_token)
                    redis_client.setex(f"{str_agent_thread}_REFRESH_TOKEN", 86400, str_refresh_token)
            
            config["configurable"].update({
                "token": str_access_token,
                "refresh": str_refresh_token
            })
            
        elif agent_type == 'NUFLIGHTS OTA':
            # Nuflights OTA - GraphQL token authentication
            token_key = f"{str_agent_thread}_ACCESS_TOKEN"

            login_url = "https://api.staging.llc.nuflights.com/core/graphql"
            auth_payload = {
                "query": login_query,
                "variables": {
                    "rq": {
                        "username": dct_agent.get("strUserName"),
                        "password": dct_agent.get("strPassword")
                    }
                }
            }
            response = requests.post(
                login_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(auth_payload))
                
            
            access_token = response.json()["data"]["login"]["token"]

            if not redis_client.exists(token_key):
                redis_client.setex(token_key, 86400, access_token)
            
            config["configurable"].update({
                "token": access_token,
                "transaction_id": str_agent_thread
            })
            
        elif agent_type == 'NUHIVE':  
       
            if redis_client.exists(f"{str_agent_thread}_ACCESS_TOKEN"):
                str_access_token = redis_client.get(f"{str_agent_thread}_ACCESS_TOKEN").decode("utf-8")
                str_refresh_token = redis_client.get(f"{str_agent_thread}_REFRESH_TOKEN").decode("utf-8")
                # Check the token is still valid , beacause sometime 
                # the redis key is exist but the token has expired
                url = f"{NUHIVE_URL}/api/utils/get_dropdown"
                header = {
                        "Content-Type": "application/json",
                        "X-Access-Token": f"Bearer {str_access_token}"
                    }
                payload ={"strDropdownKey" : ""}
                response = requests.post(url=url ,headers=header, json=payload)
                
                if response.status_code != 200: 
                    login_url = f"{NUHIVE_LOGIN_URL}/api/authentication/auth/login-user"
                    dct_login_header = {"Content-Type": "application/json"}
                    login_payload = {
                        "strUserName": dct_agent.get("strUserName"),
                        "strPassword": dct_agent.get("strPassword"),
                    }
                    response = requests.post(login_url, headers=dct_login_header, data=json.dumps(login_payload))
                    if response.status_code == 200:
                        str_access_token = data.get("strAccessToken")
                        str_refresh_token = data.get("strRefreshToken")
                        redis_client.set(f"{str_agent_thread}_ACCESS_TOKEN", str_access_token, keepttl=True)
                        redis_client.set(f"{str_agent_thread}_REFRESH_TOKEN", str_refresh_token, keepttl=True)
                        
                    elif "errModuleWise" in response.json():
                        err_data = response.json().get("errModuleWise")[0].get("objDetails")
                        str_access_token = err_data.get("strAccessToken")
                        str_refresh_token = err_data.get("strRefreshToken")
                        
                        redis_client.set(f"{str_agent_thread}_ACCESS_TOKEN", str_access_token, keepttl=True)
                        redis_client.set(f"{str_agent_thread}_REFRESH_TOKEN", str_refresh_token, keepttl=True)

            else:
                # Login to nutraacs and store access and refresh tokens
                login_url = f"{NUHIVE_LOGIN_URL}/api/authentication/auth/login-user"
                dct_login_header = {"Content-Type": "application/json"}
                login_payload = {
                    "strUserName": dct_agent.get("strUserName"),
                    "strPassword": dct_agent.get("strPassword"),
                }
                
                response = requests.post(
                    login_url, headers=dct_login_header, data=json.dumps(login_payload)
                )

                if response.status_code == 200:
                    data = response.json()
                    str_access_token = data.get("strAccessToken")
                    str_refresh_token = data.get("strRefreshToken")
                    
                    redis_client.setex(f"{str_agent_thread}_ACCESS_TOKEN", 86400, str_access_token)
                    redis_client.setex(f"{str_agent_thread}_REFRESH_TOKEN", 86400, str_refresh_token)
                    
                elif "errModuleWise" in response.json():
                    err_data = response.json().get("errModuleWise")[0].get("objDetails")
                    str_access_token = err_data.get("strAccessToken")
                    str_refresh_token = err_data.get("strRefreshToken")
                    
                    redis_client.setex(f"{str_agent_thread}_ACCESS_TOKEN", 86400, str_access_token)
                    redis_client.setex(f"{str_agent_thread}_REFRESH_TOKEN", 86400, str_refresh_token)
                
                else:
                    raise Exception("Failed to login to Nuhive")
                
            config["configurable"].update({
            "token": str_access_token,
            "refresh": str_refresh_token
            })
            
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        return config
        
    except Exception as e:
        raise Exception(f"Failed to set config for {agent_type} agent: {str(e)}")
    

async def send_waiting_message(body, reply_message, str_access_token):
    try:
        value = body["entry"][0]["changes"][0]["value"]
        phone_number_id = value["metadata"]["phone_number_id"]
        from_number = value["messages"][0]["from"]

        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {str_access_token}",
        }
        data = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "text",
            "text": {"body": reply_message},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=url,
                headers=headers,
                data=data,
                timeout=60
            )
        return response.json()
    
    except Exception as e:
        pass

async def get_media_id(whatsapp_body ,file_data, str_access_token):
    try:
        value = whatsapp_body["entry"][0]["changes"][0]["value"]
        phone_number_id = value["metadata"]["phone_number_id"]
        
        url= f"https://graph.facebook.com/v22.0/{phone_number_id}/media"
        
        headers = {"Authorization": f"Bearer {str_access_token}",}
        files = {'file': ('Normal.pdf', file_data, 'application/pdf')}
        data = {"messaging_product": "whatsapp"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=url,
                headers=headers,
                data=data,
                files=files,
                timeout=60
            )
        logging.info(response.json())
        return response.json().get('id')
    except Exception as e:
        logging.error(e)
        traceback.print_exc()

async def send_whatsapp_document(whatsapp_body ,media_id, str_access_token,filename,caption):
    try:
        value = whatsapp_body["entry"][0]["changes"][0]["value"]
        phone_number_id = value["metadata"]["phone_number_id"]
        from_number = value["messages"][0]["from"]
        
        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {str_access_token}",
        }
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": from_number, 
            "type": "document",
            "document": {
                "id": media_id,
                "filename": filename,
                "caption": caption
            }
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=url,
                headers=headers,
                data=data,
                timeout=60
            )
        if response.status_code ==200:
            return {
            "status": "success",
            "message": "Document sent successfully.",
        }
        logging.info("send in whatsapp")
    except Exception:
        traceback.print_exc()
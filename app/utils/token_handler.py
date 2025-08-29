from functools import wraps
from flask import request,jsonify
import redis
import jwt
import lancedb
from app.utils.generalMethods import ins_configuration,create_cursor,dct_error
from app.utils.db_connection import dbmethods
from app.schema.lancedb import EmbeddedWhatsappAccounts 
import psycopg2   
import psycopg2.extras
import traceback
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.conf_path import str_configpath
from app.utils.global_config import env_mode

# configuration
ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)
SECRET_KEY = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_SECRET_KEY')
DB_HOST = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_HOST')
DB_NAME = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_NAME')
DB_USER = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_USER')
DB_PASSWORD = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_PASSWORD')
DB_PORT = ins_cfg.get(env_mode, 'AMADEUS_EXTENSION_DB_PORT')


def whatapp_verification(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        body = request.get_json()
        if body.get("object"):
            try:
                # phone_number_id = body["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
                # str_tenancy_id=get_tenancy_by_phone_id(phone_number_id)
                
                ins_db=dbmethods().connect_db({})
                # dct_tenant_data = get_tenant_data_from_redis(str_tenancy_id,'NUBOT')
                # ins_db=psycopg2.connect("""dbname=%s user=%s password=%s host=%s port=%s"""%
                #                             (dct_tenant_data['db_name'],
                #                             dct_tenant_data['db_user'],
                #                             dct_tenant_data['db_password'],
                #                             dct_tenant_data['db_host'],
                #                             dct_tenant_data['db_port']))
                kwargs['ins_db'] = ins_db
                return f(*args, **kwargs)
            except Exception as e:
                traceback.print_exc()
        
        else:
            return (
                jsonify({"status": "error", "message": "Not a WhatsApp API event"}),
                404,
            )
    return decorated


def bot_verification(f):
    '''verify_sso_token_and_connect_tenant_database '''
    @wraps(f)
    def decorated(*args, **kwargs):
        # for local development, uncomment below 4 lines 👇
        
        ins_db=dbmethods().connect_db({})
        kwargs['str_bot_id'] = "e62d01c0-9491-4fbe-a712-da2a3e795e28"  # choose any bot UUID you want
        kwargs['ins_db'] = ins_db
        return f(*args, **kwargs)

        lst_token_details = request.headers.get('Str-Auth-Token','').split('/')
        user_id =request.headers.get('Int-User-Id','')
        int_conversation_id=request.headers.get('Int-Conversation-Id','')
        if not lst_token_details:
            return None
        str_tenancy_id = lst_token_details[0]
        str_bot_id = lst_token_details[1]
        dct_tenant_data = get_tenant_data_from_redis(str_tenancy_id,'NUBOT')
        ins_db=psycopg2.connect("""dbname=%s user=%s password=%s host=%s port=%s"""%
                                        (dct_tenant_data['db_name'],
                                        dct_tenant_data['db_user'],
                                        dct_tenant_data['db_password'],
                                        dct_tenant_data['db_host'],
                                        dct_tenant_data['db_port']))
        kwargs['str_bot_id'] = str_bot_id
        kwargs['str_tenancy_id'] = str_tenancy_id
        kwargs['ins_db'] = ins_db
        kwargs['user_id'] = user_id
        kwargs['int_conversation_id'] = int_conversation_id
        return f(*args, **kwargs)
    return decorated

async def socket_verification(environ):
    """Extract socket verification details from headers."""
    try:
        if not environ.get('HTTP_STR_AUTH_TOKEN', ''):
            return {}
        
        lst_token_details = environ.get('HTTP_STR_AUTH_TOKEN', '').split('/')
        user_id = environ.get('HTTP_INT_USER_ID', '')
        int_conversation_id = environ.get('HTTP_INT_CONVERSATION_ID', '')

        str_tenancy_id, str_bot_id = lst_token_details[0], lst_token_details[1]
        # for local development, uncomment the below line 87 and comment line 89 👇
        dct_tenant_data={'db_name': 'db_nubot_2024', 'db_host': '192.168.3.188', 'db_port': '5432', 'db_user': 'admin', 'db_password': 'asdfgh'}
        dct_tenant_data = get_tenant_data_from_redis(str_tenancy_id,'NUBOT')
        dct_embedd_data = {}
        if not user_id:
            dct_embedd_data = {
                                "str_ip":environ.get('HTTP_USER_IP',''),
                                "str_region":environ.get('HTTP_USER_REGION',''),
                                "str_referer":environ.get('HTTP_REFERRER_PARENT','')                
                              }
        return {
            'str_tenancy_id': str_tenancy_id,
            'str_bot_id': str_bot_id,
            'dct_db_info': dct_tenant_data,
            'user_id': user_id,
            'int_conversation_id': int_conversation_id,
            'dct_embedd_data':dct_embedd_data
        }
    except Exception:
        traceback.print_exc()
        return {}
        
def token_verification(f):
    '''verify_sso_token_and_connect_tenant_database '''
    @wraps(f)
    def decorated(*args, **kwargs):
        
        # for local development, uncomment below 4 lines 👇
        
        ins_db=dbmethods().connect_db({})
        kwargs['ins_db'] = ins_db
        kwargs['user_id'] = 1
        return f(*args, **kwargs)
        
        str_sso_token = request.headers.get('x-access-token').replace("Bearer ","")

        if str_sso_token :
            str_tenant_id =  ''

            try:
                dct_temp_token = {}
                # 
                dct_temp_token = jwt.decode(str_sso_token, verify=False, algorithm='RS256') #decode the token
            except Exception as msg:
                print ('INVALID_TOKEN_PROVIDED..'+str(msg))
                return dct_error('INVALID TOKEN PROVIDED'), 401
            
            if all(key in dct_temp_token for key in ('intSessionID', 'arrApplicationRole','strTenancyId','exp','iat','aud')): 
                str_tenant_id = dct_temp_token['strTenancyId']
            else: 
                print ('INTIAL_TOKEN_DECODE_FAILED..')
                return dct_error('INVALID TOKEN_PROVIDED INTIAL TOKEN_DECODE FAILED'),401
            
            #check application is permitted or not
            bln_permitted = get_permission_data_from_redis(str_tenant_id,'NUBOT')
            if not bln_permitted:
                print ('APPLICATION NOT ALLOWED')
                return dct_error('NO PERMISSION FOR REEQUSTED APP'), 401

            dct_tenant_data = get_tenant_data_from_redis(str_tenant_id,'NUBOT')

            if not dct_tenant_data:
                print ('TENANT_DATA_MISSING')
                return dct_error('INVALID TOKEN PROVIDED TENANT DATA MISSING'), 401
            

            #check saas application is permitted or not
            if not dct_tenant_data['str_application_id'] in dct_temp_token['arrApplicationRole']:
                print ('APPLICATION_NOT_ALLOWED')
                return dct_error('INVALID TOKEN PROVIDED APPLICATION NOT ALLOWED'), 401
            dct_options = {
                        'verify_signature': True,
                        'verify_exp': True,
                        'verify_nbf': False,
                        'verify_iat': True,
                        'verify_aud': False,
                        'require_exp': False,
                        'require_iat': False,
                        'require_nbf': False
                        }

            try:
                dct_token = jwt.decode(str_sso_token, key=dct_tenant_data['str_access_public_secret_key'], algorithm='RS256',options=dct_options) #verify access token
            except Exception as msg:
                print ('INVALID_TOKEN_PROVIDED..'+str(msg))
                return dct_error('INVALID TOKEN PROVIDED'), 401
            else:
                #connect tenant to its database
                
                ins_db=psycopg2.connect("""dbname=%s user=%s password=%s host=%s port=%s"""%
                                                (dct_tenant_data['db_name'],
                                                dct_tenant_data['db_user'],
                                                dct_tenant_data['db_password'],
                                                dct_tenant_data['db_host'],
                                                dct_tenant_data['db_port']))
                cr = create_cursor(ins_db)

                cr.execute("""SELECT pk_bint_user_id FROM tbl_user where fk_bint_sso_login_id= %s """,(dct_temp_token['intSessionID'],))
                rst= cr.fetchone()
                if rst:
                    int_user_id=rst['pk_bint_user_id']
                    kwargs['ins_db'] = ins_db
                    kwargs['user_id']=int_user_id
                    return f(*args, **kwargs)
                else:
                    return dct_error('USER NOT IN NUBOT') ,401
            
        else:
            print ('NO_TOKEN_FIND')
            return dct_error('INVALID TOKEN PROVIDED NO TOKEN FIND') ,401

    return decorated

def integration_token_verification(f):
    '''verify_sso_token_and_connect_tenant_database '''
    @wraps(f)
    def decorated(*args, **kwargs):
        
        # for local development, uncomment below 4 lines 👇
        
        ins_db=dbmethods().connect_db({})
        kwargs['ins_db'] = ins_db
        kwargs['user_id'] = 1
        return f(*args, **kwargs)
        
        str_sso_token = request.headers.get('x-access-token').replace("Bearer ","")

        if str_sso_token :
            str_tenant_id =  ''

            try:
                dct_temp_token = {}
                # 
                dct_temp_token = jwt.decode(str_sso_token, verify=False, algorithm='RS256') #decode the token
            except Exception as msg:
                print ('INVALID_TOKEN_PROVIDED..'+str(msg))
                return dct_error('INVALID TOKEN PROVIDED'), 401
            
            if all(key in dct_temp_token for key in ('intSessionID', 'arrApplicationRole','strTenancyId','exp','iat','aud')): 
                str_tenant_id = dct_temp_token['strTenancyId']
            else: 
                print ('INTIAL_TOKEN_DECODE_FAILED..')
                return dct_error('INVALID TOKEN_PROVIDED INTIAL TOKEN_DECODE FAILED'),401
            
            #check application is permitted or not
            bln_permitted = get_permission_data_from_redis(str_tenant_id,'NUBOT')
            if not bln_permitted:
                print ('APPLICATION NOT ALLOWED')
                return dct_error('NO PERMISSION FOR REEQUSTED APP'), 401

            dct_tenant_data = get_tenant_data_from_redis(str_tenant_id,'NUBOT')

            if not dct_tenant_data:
                print ('TENANT_DATA_MISSING')
                return dct_error('INVALID TOKEN PROVIDED TENANT DATA MISSING'), 401
            

            #check saas application is permitted or not
            if not dct_tenant_data['str_application_id'] in dct_temp_token['arrApplicationRole']:
                print ('APPLICATION_NOT_ALLOWED')
                return dct_error('INVALID TOKEN PROVIDED APPLICATION NOT ALLOWED'), 401
            
                
            ins_db=psycopg2.connect("""dbname=%s user=%s password=%s host=%s port=%s"""%
                                            (dct_tenant_data['db_name'],
                                            dct_tenant_data['db_user'],
                                            dct_tenant_data['db_password'],
                                            dct_tenant_data['db_host'],
                                            dct_tenant_data['db_port']))
            cr = create_cursor(ins_db)

            cr.execute("""SELECT pk_bint_user_id FROM tbl_user where fk_bint_sso_login_id= %s """,(dct_temp_token['intSessionID'],))
            rst= cr.fetchone()
            if rst:
                int_user_id=rst['pk_bint_user_id']
                kwargs['ins_db'] = ins_db
                kwargs['user_id']=int_user_id
                return f(*args, **kwargs)
            else:
                return dct_error('USER NOT IN NUBOT') ,401
            
        else:
            print ('NO_TOKEN_FIND')
            return dct_error('INVALID TOKEN PROVIDED NO TOKEN FIND') ,401

    return decorated

def get_tenant_data_from_redis(str_tenant_id,strApp):
#    
    #connect to Redis and get the tenat data
    dct_redis_data = {}
    r = redis.StrictRedis(host=ins_configuration.get(env_mode, 'REDIS_HOST'), port=ins_configuration.get(env_mode, 'REDIS_PORT'))
    # 
    str_application_id = r.get('application_guid:{}'.format(strApp)).decode('utf8')
    dct_redis_data = {
                'str_application_id'            : str_application_id,
                'str_access_public_secret_key'  : r.get('tenant_uuid:'+str_tenant_id+':access_rsa_pubkey').decode('utf8'),
                'str_refresh_public_secret_key' : r.get('tenant_uuid:'+str_tenant_id+':refresh_rsa_pubkey').decode('utf8'),
                'db_name'                       : r.get('tenant_uuid:'+str_tenant_id+':app:'+str_application_id+':db').decode('utf8'),
                'db_host'                       : r.get('tenant_uuid:'+str_tenant_id+':app:'+str_application_id+':db_host').decode('utf8'),
                'db_port'                       : r.get('tenant_uuid:'+str_tenant_id+':app:'+str_application_id+':db_port').decode('utf8'),
                'db_user'                       : r.get('tenant_uuid:'+str_tenant_id+':app:'+str_application_id+':db_user').decode('utf8'),
                'db_password'                   : r.get('tenant_uuid:'+str_tenant_id+':app:'+str_application_id+':db_pass').decode('utf8')
                }

                
    return dct_redis_data

def decode_sso_token(str_sso_token):
    try:
        dct_temp_token = {}
        dct_temp_token = jwt.decode(str_sso_token, verify=False, algorithm='RS256') #decode the token
        return dct_temp_token
    except Exception as msg:
        print ('INVALID TOKEN_PROVIDED.. , '+str(msg))
        return dct_error('INVALID TOKEN PROVIDED'), 401

def get_permission_data_from_redis(str_tenant_id,strApp):
    r = redis.StrictRedis(host=ins_configuration.get(env_mode, 'REDIS_HOST'), port=ins_configuration.get(env_mode, 'REDIS_PORT'))
    
    str_application_id = r.get('application_guid:{}'.format(strApp)).decode('utf8')    
    if r.exists('tenant_uuid:{0}:app:{1}'.format(str_tenant_id,str_application_id)):
        bln_permission=True
    else:
        bln_permission=False
             
    return bln_permission

def get_tenancy_by_phone_id(phone_number_id):
        db_lance = lancedb.connect(f"lancedb/whatsapp")
        try:
            table = db_lance.open_table("embedded_whatsapp_accounts")
        except ValueError:
            table = db_lance.create_table("embedded_whatsapp_accounts", schema = EmbeddedWhatsappAccounts, exist_ok = True)

        str_tenancy_id=table.search().select(["tenancy_id"]).where(f"phone_number_id = '{phone_number_id}'").to_list()
        
        return str_tenancy_id[0]['tenancy_id']
    

def extension_verification(f):
    '''verify amadeus ai ruler JWT token then connect to AI Ruler Common Database '''
    @wraps(f)
    def decorated(*args, **kwargs):
        
        token = request.headers.get('Authorization') or request.headers.get('x-access-token','')
        token = token.replace("Bearer ","")
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            dct_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except:
            return {'message': 'Token is invalid'}, 401

        ins_db=psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)

        with create_cursor(ins_db) as cr:
                cr.execute("""SELECT pk_bint_user_id FROM tbl_user where vchr_email= %s """,(dct_token['email'],))
                rst = cr.fetchone()
                if rst:
                    int_user_id=rst['pk_bint_user_id']
                    kwargs['ins_db'] = ins_db
                    kwargs['user_id']=int_user_id
                    return f(*args, **kwargs)
                else:
                    return dct_error('INVALID_CREDENTIALS') ,401
        return f(*args, **kwargs)

    return decorated
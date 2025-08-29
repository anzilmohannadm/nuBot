from importlib import import_module
from flask import Blueprint, Flask
from flask_bcrypt import Bcrypt
from flask_restx import Api
from flask_cors import CORS
ins_flask_bcrypt = Bcrypt()
ins_app = Flask(__name__)


def create_app(str_service):
    
    dct_authorizations = {
        'JWT Token': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'x-access-token'
        }

    }

    ins_blueprint = Blueprint('api', __name__)

    ins_api = Api(ins_blueprint,
                  title=str_service+' Service',
                  version='0.0.1',
                  description='Back-end API Nubot',
                  authorizations=dct_authorizations,
                  security=['JWT Token'],
                  doc ='/')

    
    dct_micro_services ={'NUBOT':['app/api/bot.py',
                                  'app/api/training.py',
                                  'app/api/module_settings.py',
                                  'app/api/utils.py',
                                  'app/api/bot_log.py',
                                  'app/api/user.py',
                                  'app/api/common.py',
                                  'app/api/ai_services.py',
                                  'app/api/chat_history.py',
                                  'app/api/source_log.py',
                                  'app/api/dashboard.py',
                                  'app/api/share_chat.py',
                                  'app/api/integration.py',
                                  'app/api/whatsapp_integration.py',
                                  'app/api/amadeus_extension.py',
                                  'app/api/agent.py'
                                  ]}
    


    for controller in dct_micro_services[str_service]:
        str_module_path = '.'.join(controller[:-3].split('/'))
        try:
            ins_module = import_module(str_module_path)
            ins_api.add_namespace(ins_module.ins_namespace,path ='/api/nubot')
        except Exception as str_error:
            print(str_error)
        
    CORS(ins_app)
    ins_flask_bcrypt.init_app(ins_app)
    ins_app.register_blueprint(ins_blueprint)
    ins_app.app_context().push()
    return ins_app

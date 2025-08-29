from flask import request
from flask_restx import Resource
from app.schema import botSchema
from app.utils.token_handler import token_verification,bot_verification,get_tenant_data_from_redis
from app.service import botService
from app.utils.db_connection import dbmethods
import psycopg2    

ins_namespace = botSchema.ins_namespace
ins_create_bot = botSchema.ins_create_bot

@ins_namespace.route('/manage')
@ins_namespace.response(404, 'Request not found.')
class nubotManage(Resource):

    @ins_namespace.doc('list all bot')
    @token_verification
    def get(self,ins_db,user_id):
        """list all bots"""
        return botService.list_bot(ins_db,user_id)
    
    @ins_namespace.doc('create new bot')
    @ins_namespace.expect(ins_create_bot, validate=True)
    @token_verification
    def post(self,ins_db,user_id):
        """create new bot"""
        return botService.create_bot(request,ins_db,user_id)

    @ins_namespace.doc('update bot')
    @token_verification
    def put(self,ins_db,user_id):
        """update bot"""
        return botService.update_bot(request,ins_db,user_id)

    @ins_namespace.doc('delete  bot')
    @token_verification
    def delete(self,ins_db,user_id):
        """update bot"""
        return botService.delete_bot(request,ins_db,user_id)

@ins_namespace.route('/item')
@ins_namespace.response(404, 'Request not found.')
class nubotItem(Resource):

    @ins_namespace.doc('get a bot details')
    @token_verification
    def post(self,ins_db,user_id):
        """get a bot details"""
        return botService.get_bot_deatils(request,ins_db,user_id)

    @ins_namespace.doc('set style')
    @token_verification
    def put(self,ins_db,user_id):
        """set style"""
        return botService.set_bot_style(request,ins_db,user_id)
    
@ins_namespace.route('/get_info')
@ins_namespace.response(404, 'Request not found.')
class getBotInfo(Resource):
    @ins_namespace.doc('get a bot details')
    @bot_verification
    def get(self,ins_db,str_bot_id,str_tenancy_id,user_id,int_conversation_id):
        
        """get a bot info"""
        return botService.get_bot_info(request,ins_db,str_bot_id)
    

@ins_namespace.route('/embed/<string:str_tenancy_id>/<string:str_bot_id>/index.js')
@ins_namespace.param("str_bot_id", "unique bot id")
@ins_namespace.param("str_tenancy_id", "tenancy ID")
@ins_namespace.response(404, 'Request not found.')
class getBotIndexJs(Resource):
    @ins_namespace.doc('get a bot details')
    def get(self,str_bot_id,str_tenancy_id):
        dct_tenant_data = get_tenant_data_from_redis(str_tenancy_id,'NUBOT')
        ins_db=psycopg2.connect("""dbname=%s user=%s password=%s host=%s port=%s"""%
                                        (dct_tenant_data['db_name'],
                                        dct_tenant_data['db_user'],
                                        dct_tenant_data['db_password'],
                                        dct_tenant_data['db_host'],
                                        dct_tenant_data['db_port']))
        """get index.js"""
        return botService.get_bot_index_js(ins_db,str_bot_id,str_tenancy_id)

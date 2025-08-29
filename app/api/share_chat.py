
from flask import request
from flask_restx import Resource
from app.utils.executor import executor
from app.utils.token_handler import token_verification 
from app.utils.generalMethods import dct_response
from app.schema import shareChatSchema
from app.service import shareChatService


ins_namespace = shareChatSchema.ins_namespace
ins_share_chat= shareChatSchema.ins_share_chat

@ins_namespace.route('/share_chat')
@ins_namespace.response(404, 'Request not found.')
class shareChat(Resource):

    @ins_namespace.doc('share a chat')
    @ins_namespace.response(200, 'chat shared successfully')
    @ins_namespace.expect(ins_share_chat, validate=True)
    @token_verification   
    def post(self,ins_db,user_id):
        """share a chat"""
        dct_request = request.json
        dct_headers = request.headers
        executor.submit(shareChatService.share_chat,dct_request,dct_headers,ins_db,user_id )
        return dct_response("success", "Chat successfully shared"), 200
    

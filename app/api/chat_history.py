
from flask import request
from flask_restx import Resource
from app.utils.token_handler import token_verification 
from app.schema import chatHistorySchema
from app.service import chatHistoryService

ins_namespace = chatHistorySchema.ins_namespace
ins_get_chat_history_titles= chatHistorySchema.ins_get_chat_history_titles
ins_get_chat_history_conversation= chatHistorySchema.ins_get_chat_history_conversation
ins_delete_chat_history= chatHistorySchema.ins_delete_chat_history
ins_rename_chat_history= chatHistorySchema.ins_rename_chat_history

@ins_namespace.route('/chat_history')
@ins_namespace.response(404, 'Request not found.')
class chatHistoryView(Resource):

    @ins_namespace.doc('get chat history titles')
    @ins_namespace.response(200, 'chat history titles returned successfully')
    @ins_namespace.expect(ins_get_chat_history_titles, validate=True)
    @token_verification   
    def post(self,ins_db,user_id):
        """view chat history titles"""
        return chatHistoryService.get_chat_history_titles(request,ins_db)  
    

    @ins_namespace.doc('get chat history conversation')
    @ins_namespace.response(200, 'chat history conversations returned successfully')
    @ins_namespace.expect(ins_get_chat_history_conversation, validate=True)
    @token_verification   
    def put(self,ins_db,user_id):
        """view chat history conversation"""
        return chatHistoryService.get_chat_history_conversation(request,ins_db,user_id)  


    @ins_namespace.doc('delete chat history ')
    @ins_namespace.response(200, 'chat history deleted successfully')
    @ins_namespace.expect(ins_delete_chat_history, validate=True)
    @token_verification   
    def delete(self,ins_db,user_id):
        """delete chat history """
        return chatHistoryService.delete_chat_history(request,ins_db)  
    
@ins_namespace.route('/rename_chat_history')
@ins_namespace.response(404, 'Request not found.')
class chatHistoryView(Resource):

    @ins_namespace.doc('rename chat history title')
    @ins_namespace.response(200, 'chat history renamed successfully')
    @ins_namespace.expect(ins_rename_chat_history, validate=True)
    @token_verification   
    def post(self,ins_db,user_id):
        """rename chat history title"""
        return chatHistoryService.rename_chat_history(request,ins_db)  
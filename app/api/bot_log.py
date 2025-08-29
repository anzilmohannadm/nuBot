from flask import request
from flask_restx import Resource
from app.utils.token_handler import token_verification
from app.schema import botLogSchema
from app.service import botLogService



ins_namespace = botLogSchema.ins_namespace
ins_get_bot_logs= botLogSchema.ins_get_bot_logs
ins_feedback= botLogSchema.ins_feedback
ins_post_comment=botLogSchema.ins_post_comment
ins_bot_conversational_log=botLogSchema.ins_bot_conversational_log

@ins_namespace.route('/get_all_bot_logs')
@ins_namespace.response(404, 'Request not found.')
class botLogsView(Resource):
    @ins_namespace.doc('view bot log')
    
    @ins_namespace.response(200, 'bot log viewed successfully')
    @ins_namespace.expect(ins_get_bot_logs, validate=False)
    @token_verification   
    def post(self,ins_db,user_id):
        """view bot log"""
        return botLogService.get_all_conversation(request,ins_db,user_id)  
    
@ins_namespace.route('/conversation_logs')
@ins_namespace.response(404, 'Request not found.')
class botConversationLogsView(Resource):
    @ins_namespace.doc('view bot conversational log')
    
    @ins_namespace.response(200, 'bot conversation log viewed successfully')
    @ins_namespace.expect(ins_bot_conversational_log, validate=False)
    @token_verification   
    def post(self,ins_db,user_id):
        """to view bot conversation log"""
        return botLogService.conversation_logs(request,ins_db,user_id)  
    

@ins_namespace.route('/get_token_cost')
@ins_namespace.response(404, 'Request not found.')
class botTokenCost(Resource):
    @ins_namespace.doc('get token cost')
    @ins_namespace.expect(ins_get_bot_logs, validate=False)
    @token_verification
    def post(self,ins_db,user_id):
        """get token cost"""
        return botLogService.get_token_cost(request,ins_db,user_id)

@ins_namespace.route('/save_feedback')
@ins_namespace.response(404, 'Request not found.')
class saveFeedback(Resource):
    @ins_namespace.doc('saving response feedback')
    @ins_namespace.expect(ins_feedback, validate=False)
    @token_verification
    def post(self,ins_db,user_id):
        """Saving response feedback
           POSITIVE for ThumbS up and NEGATIVE for Thumbs down"""
        return botLogService.save_feedback(request,ins_db)

@ins_namespace.route('/post_comment')
@ins_namespace.response(404, 'Request not found.')
class postComment(Resource):
    @ins_namespace.doc('post comment for response')
    @ins_namespace.expect(ins_post_comment, validate=True)
    @token_verification
    def post(self,ins_db,user_id):
        """feedback Comment on the bot's response."""
        return botLogService.post_comment(request,ins_db)
from flask import request
from flask_restx import Resource
from app.utils.token_handler import token_verification
from app.schema import aiServiceSchema
from app.service import aiService

ins_namespace = aiServiceSchema.ins_namespace
ins_get_message_summary= aiServiceSchema.ins_get_message_summary

@ins_namespace.route('/get_message_summary')
@ins_namespace.response(404, 'Request not found.')
class messageSummaryView(Resource):
    @ins_namespace.doc('view message summary')
    
    @ins_namespace.response(200, 'message summary viewed successfully')
    @ins_namespace.expect(ins_get_message_summary, validate=False)  
    def post(self):
        """view message summary"""
        return aiService.get_message_summary(request)  

@ins_namespace.route('/speech_service')
@ins_namespace.response(404, 'Request not found.')
class speechSynthesize(Resource):
    @ins_namespace.doc('text to speech')
    @ins_namespace.response(200, '')
    @token_verification
    def post(self,ins_db,user_id):
        """text to speech"""
        ins_db.close()
        return aiService.speech_synthesize(request)
    
    @ins_namespace.doc('speech to text')
    @ins_namespace.response(200, '')
    @token_verification
    def put(self,ins_db,user_id):
        """speech to text"""
        ins_db.close()
        return aiService.speech_recognition(request)


@ins_namespace.route('/hive_service')
@ins_namespace.response(404, 'Request not found.')
class hiveAssistant(Resource):
    @ins_namespace.doc('text to PSQL')
    @ins_namespace.response(200, '')
    @token_verification
    def post(self,ins_db,user_id):
        """text to speech"""
        ins_db.close()
        return aiService.text_to_psql(request,user_id)
    
    @ins_namespace.doc('data to summarize')
    @ins_namespace.response(200, '')
    @token_verification
    def put(self,ins_db,user_id):
        """data to summarize"""
        ins_db.close()
        return aiService.table_data_to_summary(request)


@ins_namespace.route('/dashboard_analysis')
@ins_namespace.response(404, 'Request not found.')
class dashboardAI(Resource):
    @ins_namespace.doc('nuhive  Dashboard AI analysis')
    @ins_namespace.response(200, '')
    @token_verification
    def post(self,ins_db,user_id):
        """nuhive  Dashboard AI analysis"""
        ins_db.close()
        return aiService.dashboard_summary(request)
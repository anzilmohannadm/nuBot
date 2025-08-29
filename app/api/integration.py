
from flask import request
from flask_restx import Resource
from app.utils.token_handler import token_verification,integration_token_verification
from app.schema import integrationSchema
from app.service import integrationService

ins_namespace = integrationSchema.ins_namespace
ins_testcase_integration= integrationSchema.ins_testcase_integration
ins_bot_space_mapping=integrationSchema.ins_bot_space_mapping

@ins_namespace.route('/nubot_integration')
@ins_namespace.response(404, 'Request not found.')
class testMateIntegration(Resource):

    @ins_namespace.doc('nubot integration')
    @ins_namespace.response(200, 'nubot integration successful')
    # @ins_namespace.expect(ins_testcase_integration, validate=True)
    @integration_token_verification   
    def post(self,ins_db,user_id):
        """nubot integration"""
        return integrationService.nubot_integration(request,ins_db,user_id)  
    
@ins_namespace.route('/bot_space_mapping')
@ins_namespace.response(404, 'Request not found.')
class testMateIntegration(Resource):

    @ins_namespace.doc('bot space mapping')
    @ins_namespace.response(200, 'bot space mapping successful')
    @ins_namespace.expect(ins_bot_space_mapping, validate=True)
    @token_verification   
    def post(self,ins_db,user_id):
        """bot space mapping"""
        return integrationService.bot_space_mapping(request,ins_db, user_id)  
    
@ins_namespace.route('/get_all_space')
@ins_namespace.response(404, 'Request not found.')
class testMateIntegration(Resource):

    @ins_namespace.doc('get all space ')
    @ins_namespace.response(200, 'spaces returned successfully')
    @token_verification   
    def get(self,ins_db,user_id):
        """get all space"""
        return integrationService.get_all_space(request,ins_db)  

@ins_namespace.route('/diagnostics')
@ins_namespace.response(404, 'Request not found.')
class testMateIntegration(Resource):


    @ins_namespace.doc('Query Tool') # !!!!! TEMPERORY  !!!!! 
    @token_verification   
    def post(self,ins_db,user_id):
        """Query Tool"""
        return integrationService.query_tool(request,ins_db)  # for validate integration !!! need to remove thi API

    @ins_namespace.doc('Lancedb Tool') # !!!!! TEMPERORY  !!!!! 
    @token_verification   
    def put(self,ins_db,user_id):
        """Lancedb Tool"""
        return integrationService.lance_tool(request)  # for validate integration !!! need to remove thi API

    @ins_namespace.doc('Directory Tool') # !!!!! TEMPERORY  !!!!! 
    @token_verification   
    def delete(self,ins_db,user_id):
        """Lancedb Tool"""
        return integrationService.directory_tool(request)  # for validate integration !!! need to remove thi API
from flask import request
from flask_restx import Resource
from app.utils.token_handler import token_verification
from app.schema import sourceLogSchema
from app.service import sourceLogService


ins_namespace = sourceLogSchema.ins_namespace
ins_get_source_logs= sourceLogSchema.ins_get_source_logs


@ins_namespace.route('/source_log')
@ins_namespace.response(404, 'Request not found.')
class sourceLogs(Resource):
    @ins_namespace.doc('source log')
    
    @ins_namespace.response(200, 'source log viewed successfully')
    @ins_namespace.expect(ins_get_source_logs, validate=False)
    @token_verification   
    def post(self,ins_db,user_id):
        """view bot log"""
        return sourceLogService.get_pending_approvals(request,ins_db,user_id)  

    @ins_namespace.response(200, 'deleted source viewed successfully')
    @ins_namespace.expect(ins_get_source_logs, validate=False)
    @token_verification   
    def put(self,ins_db,user_id):
        """view bot log"""
        return sourceLogService.get_deleted_sources(request,ins_db,user_id)

    @ins_namespace.response(200, 'deleted source viewed successfully')
    @token_verification   
    def delete(self,ins_db,user_id):
        """delete approved source"""
        return sourceLogService.deleted_source(request,ins_db,user_id)
    
 

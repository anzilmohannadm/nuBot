from flask import request
from flask_restx import Resource
from app.schema import agentSchema
from app.utils.token_handler import token_verification
from app.service import agentService
ins_namespace = agentSchema.ins_namespace
ins_create_agent = agentSchema.ins_create_agent
ins_update_agent = agentSchema.ins_update_agent
ins_delete_agent = agentSchema.ins_delete_agent

@ins_namespace.route('/agent')
@ins_namespace.response(404, 'Request not found.')
class agentManage(Resource):

    @ins_namespace.doc('list all agent')
    @token_verification
    def get(self,ins_db,user_id):
        """list all agents"""
        return agentService.list_agent(ins_db,user_id)
    
    @ins_namespace.doc('create new agent')
    @ins_namespace.expect(ins_create_agent, validate=False)
    @token_verification
    def post(self,ins_db,user_id):
        """create new agent"""
        return agentService.create_agent(request,ins_db,user_id)

    @ins_namespace.doc('update agent')
    @ins_namespace.expect(ins_update_agent, validate=False)
    @token_verification
    def put(self,ins_db,user_id):
        """update agent"""
        return agentService.update_agent(request,ins_db)

    @ins_namespace.doc('delete  agent')
    @ins_namespace.expect(ins_delete_agent, validate=False)
    @token_verification
    def delete(self,ins_db,user_id):
        """update agent"""
        return agentService.delete_agent(request,ins_db)

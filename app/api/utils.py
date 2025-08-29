from flask import request
from flask_restx import Resource
from app.schema import utilsSchema
from app.utils.token_handler import token_verification
from app.service import utilsService

ins_namespace = utilsSchema.ins_namespace
ins_get_dropdown = utilsSchema.ins_get_dropdown

@ins_namespace.route('/get_dropdown')
@ins_namespace.response(404, 'Request not found.')
class nuBotDropDowns(Resource):
    @ins_namespace.doc('Get All users and Groups')
    @ins_namespace.expect(ins_get_dropdown, validate = False)
    @token_verification
    def post(self,ins_db,user_id):
        """Get Drop down values"""
        return utilsService.get_dropdown(request,ins_db,user_id)
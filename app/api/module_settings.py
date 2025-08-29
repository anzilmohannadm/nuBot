from flask import request
from flask_restx import Resource
from app.schema import ModuleSettingsSchema
from app.service import moduleSettingsService
from app.utils.token_handler import token_verification

ins_namespace= ModuleSettingsSchema.ins_namespace
ins_module_name = ModuleSettingsSchema.ins_module_name

@ins_namespace.route('/get_settings')
@ins_namespace.response(404,'Request not found.')
class moduleSetting(Resource):
    @ins_namespace.doc("Module Settings")
    @ins_namespace.expect(ins_module_name,validate = True)
    @token_verification
    def post(self,ins_db,user_id):
        """module settings"""
        return moduleSettingsService.get_module_settings(request,ins_db,user_id)
    
@ins_namespace.route('/get_menu')
@ins_namespace.response(404, 'Request not found.')
class GetMenu(Resource):
    @ins_namespace.doc('to get menu')
    @token_verification
    def post(self,ins_db,user_id):
        """get menu"""
        return moduleSettingsService.get_menu(request,ins_db,user_id)

@ins_namespace.route('/get_user_details')
@ins_namespace.response(404, 'Request not found.')
class GetLoginDetails(Resource):
    @ins_namespace.doc('to get menu')
    @token_verification
    def get(self,ins_db,user_id):
        """get login user details"""
        return moduleSettingsService.get_user_details(request,ins_db,user_id)
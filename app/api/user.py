from flask import request
from flask_restx import Resource
from app.schema import userSchema
from app.utils.token_handler import token_verification
from app.service import userService

ins_namespace = userSchema.ins_namespace
ins_add_user = userSchema.ins_add_user
ins_update_user = userSchema.ins_update_user
ins_user_delete = userSchema.ins_user_delete
ins_get=userSchema.ins_get
ins_assign_user_role=userSchema.ins_assign_user_role

@ins_namespace.route('/manage_user')
@ins_namespace.response(404, 'Request not found.')
class manageUser(Resource):
    #add user
    @ins_namespace.doc('create new user')
    @ins_namespace.expect(ins_add_user, validate=False)
    @token_verification
    def post(self, ins_db, user_id):
        """Create new user"""
        return userService.create_user(request, ins_db, user_id)
    
    #update user
    @ins_namespace.doc('update user')
    @ins_namespace.expect(ins_update_user, validate=True)
    @token_verification   
    def put(self, ins_db, user_id):
        """Update user"""
        return userService.update_user(request, ins_db, user_id)

    #delete user
    @ins_namespace.doc('delete user')
    @ins_namespace.expect(ins_user_delete, validate=True)
    @token_verification   
    def delete(self, ins_db,user_id):
        """Delete user"""
        return userService.delete_user(request,ins_db,user_id)
    

#get all users   
@ins_namespace.route('/get_all_users')
@ins_namespace.response(404, 'Request not found.')
class GetAllUsers(Resource):

    @ins_namespace.doc('get all users')
    @ins_namespace.expect(ins_get, validate=True)
    @token_verification   
    def post(self, ins_db, user_id):
        """Fetch all users with pagination and filtering"""
        return userService.get_all_users(request, ins_db, user_id)
    
  
@ins_namespace.route('/assign_user_role')
@ins_namespace.response(404, 'Request not found.')
class ManageUserRole(Resource):
    @ins_namespace.doc('Assign a role to a user for user-bot-role mapping.')
    @ins_namespace.expect(ins_assign_user_role, validate=True)
    @token_verification   
    def post(self, ins_db, user_id):
        """setting user role for user-bot-role mapping"""
        return userService.assign_user_role(request,ins_db)
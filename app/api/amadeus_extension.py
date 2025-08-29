from flask import request,render_template,make_response
from flask_restx import Resource
from app.schema import amadeusExtensionSchema
from app.utils.token_handler import extension_verification
from app.service import amadeusExtensionService 

ins_namespace = amadeusExtensionSchema.ins_namespace
ins_register = amadeusExtensionSchema.ins_register
ins_city_auto_complete = amadeusExtensionSchema.ins_city_auto_complete
ins_verify_otp = amadeusExtensionSchema.ins_verify_otp
ins_user_login = amadeusExtensionSchema.ins_user_login
ins_ai_response = amadeusExtensionSchema.ins_ai_response
ins_get_all_logs = amadeusExtensionSchema.ins_get_all_logs
ins_delete_user = amadeusExtensionSchema.ins_delete_user
ins_get_user_sub_details = amadeusExtensionSchema.ins_get_user_sub_details
ins_update_subscription = amadeusExtensionSchema.ins_update_subscription


@ins_namespace.route('/amadeus-air-ruler/register')
@ins_namespace.response(404, 'Request not found.')
class userRegister(Resource):
    @ins_namespace.doc('Register New User')
    @ins_namespace.expect(ins_register, validate=False)
    def post(self):
        """Register New User"""
        return amadeusExtensionService.register_user(request)

@ins_namespace.route('/amadeus-air-ruler/verify-otp')
@ins_namespace.response(404, 'Request not found.')
class verifyOtp(Resource):
    @ins_namespace.doc('Verify OTP')
    @ins_namespace.expect(ins_verify_otp, validate=False)
    def post(self):
        """Verify OTP"""
        return amadeusExtensionService.verify_otp(request)

@ins_namespace.route('/amadeus-air-ruler/verify')
@ins_namespace.response(404, 'Request not found.')
class verify(Resource):
    @ins_namespace.doc('Verify Token')
    @extension_verification
    def get(self,ins_db,user_id):
        """Verify Token"""
        return {'message': 'Token is valid'}, 200


@ins_namespace.route('/amadeus-air-ruler/login')
@ins_namespace.response(404, 'Request not found.')
class userLogin(Resource):
    @ins_namespace.doc('User Login')
    @ins_namespace.expect(ins_user_login, validate=False)
    def get(self):
        response = make_response(render_template("login.html"))
        response.headers["Content-Type"] = "text/html"
        return response
    def post(self):
        """User Login"""
        return amadeusExtensionService.user_login(request)
    
@ins_namespace.route('/amadeus-air-ruler/generate')
@ins_namespace.response(404, 'Request not found.')
class generateResponse(Resource):
    @ins_namespace.doc('Generate AI Ruler Response')
    @ins_namespace.expect(ins_ai_response, validate=False)
    @extension_verification
    def post(self,ins_db,user_id):
        """Generate AI Ruler Response"""
        return amadeusExtensionService.generate_ai_response(request,ins_db,user_id)


@ins_namespace.route('/amadeus-air-ruler/city')
@ins_namespace.response(404, 'Request not found.')
class generateResponse(Resource):
    @ins_namespace.doc('City Auto Complete')
    @ins_namespace.expect(ins_city_auto_complete, validate=False)
    def post(self):
        """City Auto Complete"""
        return amadeusExtensionService.get_city(request)
    
@ins_namespace.route('/amadeus-air-ruler/get_all_logs')
@ins_namespace.response(404, 'Request not found.')
class generateResponse(Resource):
    @ins_namespace.doc('Get Response logs')
    def get(self):
        response = make_response(render_template("logs.html"))
        response.headers["Content-Type"] = "text/html"
        return response
    
    @ins_namespace.expect(ins_get_all_logs, validate=False)
    @extension_verification
    def post(self,ins_db,user_id):
        """Get Response logs"""
        return amadeusExtensionService.get_all_logs(request,ins_db,user_id)
    
@ins_namespace.route("/amadeus-air-ruler/dashboard")
class DashboardPage(Resource):
    def get(self):
        response = make_response(render_template("dashboard.html"))
        response.headers["Content-Type"] = "text/html"
        return response
    
    
@ins_namespace.route("/amadeus-air-ruler/get_all_users")  
@ins_namespace.response(404, 'Request not found.')
class getAllUsers(Resource):
    @ins_namespace.doc('Get all users')
    @extension_verification
    def get(self,ins_db,user_id):
        """Get all users
           This api is for Amadeus template"""
        return amadeusExtensionService.get_all_users(ins_db,user_id)
        
    
@ins_namespace.route('/amadeus-air-ruler/delete_user')
@ins_namespace.response(404, 'Request not found.')
class deleteUser(Resource):
    @ins_namespace.doc('Delete user')
    @ins_namespace.expect(ins_delete_user, validate=True)
    @extension_verification
    def post(self,ins_db,user_id):
        """Delete user"""
        return amadeusExtensionService.delete_user(request,ins_db)


@ins_namespace.route('/amadeus-air-ruler/check_permissions')
@ins_namespace.response(404, 'Request not found.')
class checkPermissions(Resource):
    @ins_namespace.doc('check permissions')
    @extension_verification
    def post(self,ins_db,user_id):
        """Verify amadeus admin user(this is only applicable to amadeus template login)
            This api is for Amadeus template"""
        return amadeusExtensionService.check_permissions(ins_db,user_id)

@ins_namespace.route('/amadeus-air-ruler/get_user_sub_details')
@ins_namespace.response(404, 'Request not found.')
class UsersubscriptionDetails(Resource):
    @ins_namespace.doc('get_user_sub_details')
    @extension_verification
    def post(self,ins_db,user_id):
        """getting user subscription details
            This api is for Extension"""     
        return amadeusExtensionService.get_user_sub_details(ins_db,user_id)
    
@ins_namespace.route('/amadeus-air-ruler/get_all_users_sub_details')
@ins_namespace.response(404, 'Request not found.')
class subscriptionDetails(Resource):
    @ins_namespace.doc('get_all_users_sub_details')
    def get(self):
        response = make_response(render_template("user_subscriptions.html"))
        response.headers["Content-Type"] = "text/html"
        return response
    @extension_verification
    def post(self,ins_db,user_id):
        """getting user subscription details
            This api is for Amadeus template"""     
        return amadeusExtensionService.get_all_users_sub_details(request,ins_db,user_id)
    
@ins_namespace.route('/amadeus-air-ruler/update_subscription')
@ins_namespace.response(404, 'Request not found.')
class updateSubscription(Resource):
    @ins_namespace.doc('update_subscription')
    def get(self):
        response = make_response(render_template("choose_plan.html"))
        response.headers["Content-Type"] = "text/html"
        return response
    @extension_verification
    @ins_namespace.expect(ins_update_subscription, validate=True)
    def post(self,ins_db,user_id):
        """getting user subscription details
            This api is for Amadeus template"""     
        return amadeusExtensionService.update_subscription(request,ins_db,user_id)
    


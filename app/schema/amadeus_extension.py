from flask_restx import Namespace, fields


class amadeusExtensionSchema:
    ins_namespace= Namespace('Amadeus AI Ruler Extension',description='Amadeus AI Extension')
    ins_register = ins_namespace.model('register new user', {
    'email': fields.String(required = True, description = 'email ID'),
    'password': fields.String(required = False, description = 'Password '),
    'username': fields.String(required = False, description = 'name to identify the user'),
    'companyname': fields.String(required = False, description = 'users company name'),
    'phonenumber': fields.String(required = False, description = 'phone number without country code'),
    'city': fields.Integer(required = False, description = 'city id'),})

    ins_user_login = ins_namespace.model('user login', {
    'email': fields.String(required = True, description = 'email ID'),
    'password': fields.String(required = False, description = 'Password '),})
    
    ins_city_auto_complete = ins_namespace.model('Auto completion city', {
    'strAutoComplete': fields.String(required = True, description = 'macthing key'),})

    ins_verify_otp = ins_namespace.model('verify the OTP', {
    'email': fields.String(required = True, description = 'email ID'),
    'otp': fields.String(required = False, description = 'OTP to verify'),})

    ins_ai_response = ins_namespace.model('Generate AI response', {
    'strQuery': fields.String(required = True, description = 'data to generate'),
    'strPrompt': fields.String(required = False, description = 'Additional Prompt'),})
    
    ins_log_filter = ins_namespace.model('Get all logs filter', {
    'strStartDate': fields.String(required = True, description = 'Start date'),
    'strEndDate': fields.String(required = False, description = 'End date'),
    'intUserId' : fields.String(required = False, description = 'User id') })
    
    ins_pagination = ins_namespace.model('pagination',{
    'intPerPage': fields.Integer(required=True, description='Number of items per page'),
    'intPageOffset': fields.Integer(required=True, description='Page offset'),
    'intTotalCount': fields.Integer(required=True, description='Total count of records')})
    
    ins_get_all_logs = ins_namespace.model('get_all_logs', {
    'objPagination': fields.Nested(ins_pagination),
    'objFilter': fields.Nested(ins_log_filter)})
    
    ins_delete_user = ins_namespace.model('delete user', {
    'strEmail': fields.String(required = True, description = 'user email ID')})
    
    ins_get_user_sub_details = ins_namespace.model('getting user subscription details', {
    'intUserId': fields.Integer(required = True, description = 'user ID')})
    
    ins_update_subscription =ins_namespace.model('update subscription', {
    'strSubName': fields.String(required = True, description = 'subscription name'),
    'intUserId' : fields.Integer(required = True, description = 'user ID'),})
    
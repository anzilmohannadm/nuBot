from flask_restx import Namespace,fields

class userSchema:

    ins_namespace= Namespace('User',description='user related operations')
    
    ins_bot_details = ins_namespace.model('bot details',{
        'intBotId':fields.Integer(required =True ,description= 'bot id'),
        'strBotName':fields.String(required = True , description = 'bot name'),
        'intRoleId':fields.Integer(required =True , description= 'role id'),
        'strRoleName':fields.String(required = True ,description = 'role name ')
        
    })

    ins_add_user = ins_namespace.model('create_user', {
        'strEmailId': fields.String(required = True, description = 'email id'),
        'strUserName': fields.String(required = True, description = 'user name'),
        'strUserGroup':fields.String(required = True, description = 'user group'),
        'arrBotAccessDetails':fields.List(fields.Nested(ins_bot_details),description= 'bot id with role of that user to that specific bot')
    })
    
    ins_update_user = ins_namespace.model('update_user', {
    'intUserId': fields.Integer(required=True, description='User ID'),
    'strUserGroup': fields.String(required=True, description='User Group'),
    'strUserName': fields.String(required=True, description='User Name'),
    'strEmailId': fields.String(required=True, description='Email ID'),
    'arrBotAccessDetails':fields.List(fields.Nested(ins_bot_details),description= 'bot id with role of that user to that specific bot')
    })

    ins_user_delete = ins_namespace.model('delete_user', {
        'user_id': fields.Integer(required=True, description='ID of the user to delete')
    })

    ins_user_filter = ins_namespace.model('filter_user', {
    'strUserName': fields.String(required=False, description='User name for filtering'),
    'strUserGroup': fields.String(required=False, description='User group, e.g., Admin, Staff User')
    })

    ins_pagination = ins_namespace.model('pagination', {
        'intPerPage': fields.Integer(required=True, description='Number of users per page'),
        'intPageOffset': fields.Integer(required=True, description='Page offset for pagination'),
        'intTotalCount': fields.Integer(required=True, description='Total count of records')
    })

    ins_get = ins_namespace.model('get_all', {
        'objPagination': fields.Nested(ins_pagination, required=True, description='Pagination details'),
        'objFilter': fields.Nested(ins_user_filter, required=False, description='Filter criteria')
    })
    
    ins_assign_user_role = ins_namespace.model('assign user roles', {
         'intUserId': fields.Integer(required=True, description='The ID of the user'),
         'intBotId': fields.Integer(required=True,description='The ID of the bot'),
         'intRoleId':fields.Integer(required=True,description='The ID of the role to be assigned')         
    })
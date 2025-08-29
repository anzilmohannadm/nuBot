from flask_restx import Namespace, fields

class integrationSchema:
    ins_namespace= Namespace('integration to nubot',description=' integration to nubot related operations')

    ins_testcase_integration = ins_namespace.model('testcase_integration', {
    'intProjectId': fields.Integer(required=False, description='Bot id'),
    'obj_': fields.Raw( required=True, description='Test Case Details'),
    'strAction': fields.String(required=True, description='Action to perform')

})
    ins_bot_space_mapping = ins_namespace.model('bot_space_mapping', {
    'intBotId': fields.Integer(required=False, description='Bot id'),
    'intSpaceId': fields.Integer( required=True, description='Space id'),
    # 'str_space_name': fields.Raw( required=False, description='Space name')

})

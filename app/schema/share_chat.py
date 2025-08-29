from flask_restx import Namespace, fields

class shareChatSchema:
    ins_namespace= Namespace('share chat',description='share chat related operations')

    ins_share_chat = ins_namespace.model('share_chat', {
    'intBotId': fields.Integer(required=False, description='Bot id'),
    'intSharedUserId': fields.Integer(required=True, description='Shared User ID'),
    'intConversationId': fields.Integer(required=True, description='COnversation ID'),

})

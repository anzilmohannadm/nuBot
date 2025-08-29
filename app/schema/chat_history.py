from flask_restx import Namespace, fields

class chatHistorySchema:
    ins_namespace= Namespace('chat history',description='chat history related operations')

    ins_get_chat_history_titles = ins_namespace.model('get_chat_history_titles', {
    'blnAllChat': fields.Boolean(required=False, description='whether all chat history should be displayed or not'),
    'intBotId': fields.Integer(required=False, description='Bot id'),
    'intUserId': fields.Integer(required=True, description='User ID'),
})
    ins_get_chat_history_conversation = ins_namespace.model('get_chat_history_conversation', {
    'intBotId': fields.Integer(required=False, description='Bot id'),
    'intConversationId': fields.Integer(required=True, description='conversation ID')


})
    ins_delete_chat_history = ins_namespace.model('delete_chat_history', {
    'intBotId': fields.Integer(required=False, description='Bot id'),
    'intConversationId': fields.Integer(required=True, description='conversation ID')
})
    
    ins_rename_chat_history = ins_namespace.model('rename_chat_history', {
    'intConversationId': fields.Integer(required=True, description='conversation ID'),
    'strTitle':fields.String(required = False, description = 'chat Title'),
})
    


from flask_restx import Namespace,fields

class botSchema:

    ins_namespace= Namespace('chatbot',description='bot related operations')

    ins_create_bot = ins_namespace.model('create_bot', {
        'strBotName': fields.String(required = True, description = 'name for chatbot'),
        'strBotInstructions': fields.String(required = False, description = 'instruction given to bot guide its behavior or responses'),
        'strWelcomeMessage': fields.String(required = False, description = 'message from a bot is a friendly greeting or introduction that the AI sends to a user at the beginning of an interaction'),
        'strSuggestedReply': fields.String(required = False, description = 'commonly asking question from user side'),
        'strImage': fields.String(required = False, description = 'Bot profile Icon -Base64 string'),
        'strBotType': fields.String(required = False, description = 'category of bot whether knowledge base or general'),

    })
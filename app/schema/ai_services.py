from flask_restx import Namespace, fields

class aiServiceSchema:
    ins_namespace= Namespace('AI services',description='AI services')

# Define the filter schema
    ins_message_fields = ins_namespace.model('message_fields', {
        'strSender': fields.String(required=False, description='Sender of message'),
        'strReceiver': fields.String(required=False, description='Receiver of message'),
        'strMessage': fields.String(required=False, description='Message'),
        'blnIncoming':fields.Boolean(required=False, description ='True if the message is incoming')
    })
    ins_get_message_summary = ins_namespace.model('message_summary', {
        'arrMessages':fields.List(fields.Nested(ins_message_fields)),
        'strAction':fields.String(required=False,description='Specify FAQ or Summarisation'),
        'strSummary':fields.String(required=False,description='Summary of conversation'),
    })
    
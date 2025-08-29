from flask_restx import Namespace, fields

class botLogSchema:
    ins_namespace= Namespace('bot logs',description='bot log related operations')

# Define the filter schema
    ins_bot_log_filter = ins_namespace.model('filter_bot_log', {
    'strStartDate': fields.String(required=False, description='Start date for the date range (YYYY-MM-DD)'),
    'strEndDate': fields.String(required=False, description='End date for the date range (YYYY-MM-DD)'),
    'intBotId': fields.Integer(required=False, description='Bot id'),
})

#bot conversation logs
    ins_bot_conversational_log= ins_namespace.model('bot conversation log', {
     'intConversationId':fields.Integer(required=True, description='conversational id')
})

# Define the pagination schema
    ins_pagination = ins_namespace.model('pagination',
    {
        'intPerPage': fields.Integer(required=True, description='Number of items per page'),
        'intPageOffset': fields.Integer(required=True, description='Page offset'),
        'intTotalCount': fields.Integer(required=True, description='Total count of records')
    })

# Define the complete schema for the request
    ins_get_bot_logs = ins_namespace.model('get_all_bot_logs', {
    'objPagination': fields.Nested(ins_pagination),
    'objFilter': fields.Nested(ins_bot_log_filter)
})
    ins_feedback = ins_namespace.model('save feedback', {
    'intChatId': fields.Integer(required=False, description='chat id'),
    'strFeedBack': fields.String(required=False, description='response feebback POSITIVE or NEGATIVE'),
})

    ins_post_comment = ins_namespace.model('post comment for bot response', {
    'intChatId': fields.Integer(required=False, description='chat id'),
    'strComment': fields.String(required=False, description='Feedback comment for bot response'),
})

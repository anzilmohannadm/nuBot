from flask_restx import Namespace, fields

class sourceLogSchema:
    ins_namespace= Namespace('source logs',description='source log related operations')

# Define the filter schema
    ins_source_log_filter = ins_namespace.model('filter_source_log', {
    'intBotId': fields.Integer(required=False, description='Bot id'),
})

# Define the pagination schema
    ins_pagination = ins_namespace.model('pagination',
    {
        'intPerPage': fields.Integer(required=True, description='Number of items per page'),
        'intPageOffset': fields.Integer(required=True, description='Page offset'),
        'intTotalCount': fields.Integer(required=True, description='Total count of records')
    })

# Define the complete schema for the request
    ins_get_source_logs = ins_namespace.model('get_all_source_logs', {
    'objPagination': fields.Nested(ins_pagination),
    'objFilter': fields.Nested(ins_source_log_filter)
})

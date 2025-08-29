from flask_restx import Namespace, fields


class dashboardSchema:
    ins_namespace= Namespace('dashboard',description='dashboard related operations')
    
    ins_dashboard = ins_namespace.model('dashboard',{
    'intBotId':fields.Integer(required = True, description = "bot id" ),
    "strTimeZone" :fields.String(required = True, description = "Current time zone"),
    "strCriteria" :fields.String(required = True, description = "[TOKEN_USAGE_BY_TIME,'TOKEN_COST_BY_TIME','TOKEN_USAGE_BY_USER','TOKEN_COST_USAGE_BY_USER','CONVERSATION_BY_USER']"),
    'strStartDate': fields.String(required=False, description='Start date for the date range (YYYY-MM-DD)'),
    'strEndDate': fields.String(required=False, description='End date for the date range (YYYY-MM-DD)'),
})
    
    # Define the filter schema
    ins_dashboard_table_view = ins_namespace.model('Dashbord over view', {
    'strStartDate': fields.String(required=False, description='Start date for the date range (YYYY-MM-DD)'),
    'strEndDate': fields.String(required=False, description='End date for the date range (YYYY-MM-DD)'),
    'intBotId': fields.Integer(required=False, description='Bot id'),
})

    ins_pagination = ins_namespace.model('pagination',
    {
        'intPerPage': fields.Integer(required=True, description='Number of items per page'),
        'intPageOffset': fields.Integer(required=True, description='Page offset'),
        'intTotalCount': fields.Integer(required=True, description='Total count of records')
    })

    # Define the complete schema for the request
    ins_dashboard_table_view_details = ins_namespace.model('get_all_details', {
        'objPagination': fields.Nested(ins_pagination),
        'objFilter': fields.Nested(ins_dashboard_table_view)
    })
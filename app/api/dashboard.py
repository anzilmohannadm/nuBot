from flask import request
from flask_restx import Resource
from app.utils.token_handler import token_verification,bot_verification
from app.service import dashboardService 
from app.schema import dashboardSchema


ins_namespace = dashboardSchema.ins_namespace
ins_dashboard = dashboardSchema.ins_dashboard
ins_dashboard_table_view_details = dashboardSchema.ins_dashboard_table_view_details


@ins_namespace.route('/dashboard')
@ins_namespace.response(404,'Request not found.')
class Dashboard(Resource):
    @ins_namespace.response(200, 'dashboard viewed successfully')
    @ins_namespace.expect(ins_dashboard, validate=False)
    @token_verification   
    def post(self,ins_db,user_id):
        """vew dashboard"""
        return dashboardService.view_dashboard(request,ins_db)

@ins_namespace.route('/get_overview_data')
@ins_namespace.response(404,'Request not found.')
class DashboardOverView(Resource):
    @ins_namespace.doc('get overview data')
    @ins_namespace.expect(ins_dashboard_table_view_details, validate=False)
    @token_verification   
    def post(self,ins_db,user_id):
        """get overview data"""
        return dashboardService.get_overview_data(request,ins_db,user_id)

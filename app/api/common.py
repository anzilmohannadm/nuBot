from flask import request
from flask_restx import Resource
from app.schema import CommonSchema
from app.service import create_blank_db

ins_namespace= CommonSchema.ins_namespace

@ins_namespace.route('/database/create_blank_database')
@ins_namespace.response(404, 'Request not found.')
class DB(Resource):
    @ins_namespace.doc('create blank DB')
    #@ins_namespace.expect(ins_blank_db, validate=False)
    @ins_namespace.response(200, 'DB created successfully')
    def post(self):
        """craete DB"""
        return create_blank_db(request)
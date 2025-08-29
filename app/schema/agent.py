from flask_restx import Namespace,fields

class agentSchema:

    ins_namespace= Namespace('agent',description='agent related operations')

    ins_create_agent = ins_namespace.model('create_agent', {
        'strAgentName': fields.String(required = True, description = 'Name of the chat agent'),
        'strAgentType': fields.String(required = False, description = 'Type of the agent, e.g., BI  or Nuflights'),
        'objConfig':fields.Nested(ins_namespace.model('agent_config', {
            'strDomain': fields.String(required = False, description = 'Domain or scope of the agent'),
            'strUserName': fields.String(required = False, description = 'Username for authentication'),
            'strPassword': fields.String(required = False, description = 'Password for authentication'),
            'strClientId': fields.String(required = False, description = 'Client ID associated with the agent'),
        })) 

    })

    ins_update_agent = ins_namespace.model('update_agent', {
        'intPk': fields.Integer(required=True, description='Unique ID of the agent'),
        'strAgentName': fields.String(required=True, description='Name of the chat agent'),
        'strAgentType': fields.String(required=False, description='Type of the agent, e.g., BI or Nuflights'),
        'objConfig': fields.Nested(ins_namespace.model('agent_config', {
            'strDomain': fields.String(required=False, description='Domain or scope of the agent'),
            'strUserName': fields.String(required=False, description='Username for authentication'),
            'strPassword': fields.String(required=False, description='Password for authentication'),
            'strClientId': fields.String(required=False, description='Client ID associated with the agent'),
        }))
    })

    ins_delete_agent = ins_namespace.model('delete_agent', {
        'intPk': fields.Integer(required=True, description='Unique ID of the agent')
    })

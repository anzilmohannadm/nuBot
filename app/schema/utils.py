from flask_restx import Namespace,fields

class utilsSchema:

    ins_namespace= Namespace('utils',description='utils operations')

    ins_get_dropdown = ins_namespace.model('get_dropdown', {
        'strDropdownKey': fields.String(required = True, description = 'Dropdown Key')
        
    })

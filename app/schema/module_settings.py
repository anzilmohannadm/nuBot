from flask_restx import Namespace, fields

class ModuleSettingsSchema:
    ins_namespace= Namespace('module settings',description='module settings for front end')
    
    ins_module_name = ins_namespace.model('module_settings_name', {
        'strModule': fields.String(required = True, description = 'module settings name')
        
    })
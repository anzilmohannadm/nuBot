from flask_restx import Namespace,fields

class trainingSchema:

    ins_namespace= Namespace('train chatbot',description='bot training operations')
    ins_get_all_source= ins_namespace.model('get_all_source', {
        'intPk': fields.Integer(required=False, description='Bot id'),
          })
    ins_start_train_bot=  ins_namespace.model('train_bot', {
        'intPk': fields.Integer(required=False, description='Bot id'),
        })
    ins_get_all_source= ins_namespace.model('get_all_source', {
        'intPk': fields.Integer(required=False, description='Bot id'),
          })
    ins_create_notes = ins_namespace.model('create_notes', {
        'strNoteName': fields.String(required = True, description = 'name for notes'),
        'strContent': fields.String(required = False, description = 'html content in the note'),
        'intPk': fields.Integer(required=False, description='Bot id'),
          })
    
    ins_update_notes = ins_namespace.model('update_notes', {
        'intNotesId': fields.Integer(required=True, description='ID of note to be updated'),
        'intPk': fields.Integer(required=False, description='Bot id'),
        'strNoteName': fields.String(required=True, description='note name'),
        'strContent': fields.String(required = False, description = 'updated html content in the note'),
    })

    ins_delete_notes = ins_namespace.model('delete_notes', {
        'intNotesId': fields.Integer(required=True, description='ID of note to be deleted '),
        'intPk': fields.Integer(required=False, description='Bot id')
    })

    ins_get_notes_content = ins_namespace.model('get_notes_content', {
        'intNotesId': fields.Integer(required=True, description='ID of note to be deleted ')
    })
    
    ins_upload_image=ins_namespace.model('upload_image', {
        'intPk': fields.Integer(required=False, description='Bot id'),
        'image':fields.String(required=False, description='image ')
    })

    ins_web_crawl = ins_namespace.model('web_crawl_request', {
    'strUrl': fields.String(required=True, description='The URL to start crawling', example='https://www.example.com'),
    'intPk': fields.Integer(required=True, description='User ID')
    })

    ins_web_crawl_status = ins_namespace.model('web_crawl_status', {
    'intPk': fields.Integer(required=True, description='User ID')
    })

    ins_delete_crawled_data = ins_namespace.model('delete_crawled_data_request', {
    'intPk': fields.Integer(required=True, description='User ID'),
    'intSourceId': fields.Integer(required=True, description="Source ID")  # Corrected to intSourceId
    })

    ins_get_references=ins_namespace.model('Retrieve references related to the user promt',{
        "intPk":fields.Integer(required=True,description='Bot id'),
        "arrReferencesId":fields.List(fields.String, required=True,description="List of reference IDs associated with the user questions.")
    })
    
    ins_update_references=ins_namespace.model('Update references',{
        "intPk":fields.Integer(required=True,description='Bot id'),
        "arrReferences":fields.List(fields.Nested(ins_namespace.model('Reference object containing ID and updated text for the update operation',{
            "id":fields.String(required=True,description="Unique ID of the reference to update"),
            "text": fields.String(required=True, description="Updated text of the reference."),})))
    })
    
    ins_stop_training=ins_namespace.model('Stop training', {
    'intPk': fields.Integer(required=True, description='Bot id')
    })
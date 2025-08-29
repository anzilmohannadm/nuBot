import asyncio
from flask import request
from flask_restx import Resource,reqparse
from app.schema import trainingSchema
from app.utils.token_handler import token_verification
from app.service import trainingService



ins_namespace = trainingSchema.ins_namespace
ins_get_all_source=trainingSchema.ins_get_all_source
ins_create_notes=trainingSchema.ins_create_notes
ins_delete_notes=trainingSchema.ins_delete_notes
ins_update_notes=trainingSchema.ins_update_notes
ins_get_notes_content=trainingSchema.ins_get_notes_content
ins_upload_image=trainingSchema.ins_upload_image
ins_web_crawl = trainingSchema.ins_web_crawl
ins_web_crawl_status =trainingSchema.ins_web_crawl_status
ins_delete_crawled_data=trainingSchema.ins_delete_crawled_data
ins_update_references=trainingSchema.ins_update_references
ins_get_references=trainingSchema.ins_get_references
ins_stop_training = trainingSchema.ins_stop_training
ins_start_train_bot = trainingSchema.ins_start_train_bot

@ins_namespace.route('/manage_source')
@ins_namespace.response(404, 'Request not found.')
class trainingBot(Resource):
    @ins_namespace.doc('upload source/documents')
    @token_verification
    def post(self,ins_db,user_id):
        """upload source/documents to azure storage blob"""
        return trainingService.upload_source(request,ins_db,user_id)

    @ins_namespace.doc('delete source/documents')
    @token_verification
    def delete(self,ins_db,user_id):
        """delete sources"""
        return trainingService.delete_source(request,ins_db,user_id)
    
    
@ins_namespace.route('/get_all_source')
@ins_namespace.response(404, 'Request not found.')
class trainingBot(Resource):
    @ins_namespace.doc('get all uploaded sources')
    @ins_namespace.expect(ins_get_all_source, validate=True)
    @token_verification
    def post(self,ins_db,user_id):
        """get all uploaded sources"""
        return trainingService.get_all_source(request,ins_db)
    
@ins_namespace.route('/train_bot')
@ins_namespace.response(404, 'Request not found.')
class startTraining(Resource):
    @ins_namespace.doc('train the bot with given sources')
    @ins_namespace.expect(ins_start_train_bot, validate=False)
    @token_verification
    def post(self,ins_db,user_id):
        """train the bot with given sources"""
        return trainingService.start_training(request,ins_db,user_id)

    @ins_namespace.doc('get status of taining')
    @token_verification
    def put(self,ins_db,user_id):
        """get status of taining"""
        return trainingService.check_training_status(request,ins_db)
    
@ins_namespace.route('/stop_train_bot')
@ins_namespace.response(404, 'Request not found.')
class stopTraining(Resource):
    @ins_namespace.doc('stop the training')
    @ins_namespace.expect(ins_stop_training, validate=True)
    @token_verification
    def post(self,ins_db,user_id):
        """stop the training"""
        return trainingService.stop_training(request,ins_db)
    
@ins_namespace.route('/manage_notes')
@ins_namespace.response(404, 'Request not found.')
class manageNotes(Resource):
    @ins_namespace.doc('upload notes')
    @ins_namespace.expect(ins_create_notes, validate=False)
    @token_verification
    def post(self,ins_db,user_id):
        """upload notes to azure storage blob"""
        return trainingService.upload_notes(request,ins_db,user_id)
    

    @ins_namespace.doc('update notes')
    @ins_namespace.expect(ins_update_notes, validate=False)
    @token_verification
    def put(self,ins_db,user_id):
        """update notes"""
        return trainingService.update_notes(request,ins_db,user_id)
    
    @ins_namespace.doc('delete notes')
    @ins_namespace.expect(ins_delete_notes, validate=False)
    @token_verification
    def delete(self,ins_db,user_id):
        """delete notes"""
        return trainingService.delete_notes(request,ins_db,user_id)
    
@ins_namespace.route('/get_notes_content')
@ins_namespace.response(404, 'Request not found.')
class getNotesContent(Resource):
    @ins_namespace.doc('get notes content')
    @ins_namespace.expect(ins_get_notes_content, validate=False)
    @token_verification
    def post(self,ins_db,user_id):
        """get notes content"""
        return trainingService.get_notes_content(request,ins_db)
    
@ins_namespace.route('/upload_image')
@ins_namespace.response(404, 'Request not found.')
class uploadImage(Resource):
    @ins_namespace.doc('upload image')
    @ins_namespace.expect(ins_upload_image, validate=False)
    @token_verification
    def post(self,ins_db,user_id):
        """upload image"""
        return trainingService.uploads_from_text_editor(request,ins_db,user_id)


    @ins_namespace.doc('delete uploaded file')
    @token_verification
    def delete(self,ins_db,user_id):
        """delete image"""
        return trainingService.delete_uploaded(request)


    
@ins_namespace.route('/content/<path:str_blob_url>')
@ins_namespace.param("str_blob_url", "unique id for each content")
@ins_namespace.response(404, 'Request not found.')
class getImage(Resource):

    @ins_namespace.doc('Get image')
    def get(self,str_blob_url):

        """Get image"""

        return trainingService.stream_uploads(str_blob_url)

@ins_namespace.route('/live_chat_upload')
@ins_namespace.response(404, 'Request not found.')
class trainingBot(Resource):
    @ins_namespace.doc('upload attachments in live chat')
    @token_verification
    def post(self,ins_db,user_id):
        """upload and train attachment in live chat"""
        return trainingService.live_chat_upload(request,ins_db,user_id) 

@ins_namespace.route('/delete_attachment')
@ins_namespace.response(404, 'Request not found.')
class DeleteCrawledDataAPI(Resource):
    @ins_namespace.doc('Delete last attachment')
    @token_verification
    def delete(self,ins_db,user_id):
        """Delete last attachment from lancedb and database."""
        return trainingService.delete_attachment(request,ins_db)   

@ins_namespace.route('/web_crawl')
@ins_namespace.response(404, 'Request not found.')
class crawlAPI(Resource):
    @ins_namespace.doc('Start web crawling and upload documents')
    @ins_namespace.expect(ins_web_crawl, validate=True)
    @token_verification
    def post(self,ins_db,user_id):
        """Start web crawling and upload documents to Azure Blob Storage."""
        return trainingService.start_url_crawler(request, ins_db, user_id)
    
    @ins_namespace.doc('get status of crawling')
    @ins_namespace.expect(ins_web_crawl_status, validate=True)
    @token_verification
    def put(self,ins_db,user_id):
        """get status of crawling"""
        return trainingService.check_url_crawler_status(request,ins_db)
    
    
    


@ins_namespace.route('/delete_crawled_data')
@ins_namespace.response(404, 'Request not found.')
class DeleteCrawledDataAPI(Resource):
    @ins_namespace.doc('Delete all crawled data')
    @ins_namespace.expect(ins_delete_crawled_data, validate=True)
    @token_verification
    def delete(self,ins_db,user_id):
        """Delete all crawled data from Azure Blob Storage or database."""
        return trainingService.delete_crawled_data(request,ins_db,user_id)
    
    
@ins_namespace.route('/get_references')
@ins_namespace.response(404, 'Request not found.')
class ReferenceRetrieval(Resource):
    @ins_namespace.doc('Retrieve references linked to the user prompt')
    @ins_namespace.expect(ins_get_references, validate=True)
    @token_verification
    def post(self,ins_db,user_id):
        """Fetch references associated with the user prompt by searching LanceDB using reference IDs."""
        return trainingService.get_references(request,ins_db,user_id)

@ins_namespace.route('/update_referance')
@ins_namespace.response(404, 'Request not found.')
class UpdateReference(Resource):
    @ins_namespace.doc('Modify and update bot references with new content')
    @ins_namespace.expect(ins_update_references, validate=True)
    @token_verification
    def post(self,ins_db,user_id):
        """Update the bot's references with new content and retrain the model """
        return trainingService.update_referance(request,ins_db,user_id)
    


from flask import request
from flask_restx import Resource
from app.schema import webhookSchema
from app.service import whatsappWebhook
from app.utils.token_handler import token_verification,whatapp_verification

ins_namespace = webhookSchema.ins_namespace
ins_embedded_add_account_details = webhookSchema.ins_embedded_add_account_details
ins_assign_bot_to_onboarded_number = webhookSchema.ins_assign_bot_to_onboarded_number
ins_two_factor = webhookSchema.ins_two_factor
ins_update_profile_settings = webhookSchema.ins_update_profile_settings
ins_receive_templates = webhookSchema.ins_receive_templates
ins_create_template = webhookSchema.ins_create_template
ins_delete_template = webhookSchema.ins_delete_template
ins_send_template_message = webhookSchema.ins_send_template_message
ins_edit_template = webhookSchema.ins_edit_template

@ins_namespace.route('/manage_waba')
@ins_namespace.response(404, 'Request not found.')
class EmbeddedWhatsapp(Resource):
    @ins_namespace.doc('Handle incoming embedded signup WABA account details')
    @ins_namespace.expect(ins_embedded_add_account_details, validate=True)
    @token_verification
    def post(self,ins_db,user_id):
        """Getting the access token from the exchange code 
                and add account details to the db """
        return whatsappWebhook.add_embedded_signup_details(request,ins_db)
    
    @ins_namespace.expect(ins_assign_bot_to_onboarded_number,validate=True)
    @token_verification
    def put(self,ins_db,user_id):
        "Setting the bot for the onboarded number"
        return whatsappWebhook.assign_bot_to_onboarded_number(request,ins_db)
    
    @ins_namespace.doc('get all waba details')
    @token_verification
    def get(self,ins_db,user_id):
        "Get all WABA Account details"
        return whatsappWebhook.get_all_embedded_accounts(ins_db)

@ins_namespace.route('/enable_two_factor_authentication')
class TwoFactorauthentication(Resource):
    @ins_namespace.doc('enable two factor for registering the phone number')
    @ins_namespace.expect(ins_two_factor,validate = True)
    @token_verification
    def post(self,ins_db,user_id):
        """Setting Two Fctor Authentication for registering the onboarded phone number 
            and subscribes it to the webhook."""
        return whatsappWebhook.enable_two_factor_authentication(request,ins_db,user_id)

@ins_namespace.route('/update_profile_settings')
class ProfileSettings(Resource):
    @ins_namespace.doc('Update the about of onboarded number')
    @ins_namespace.expect(ins_update_profile_settings,validate = False)
    @token_verification
    def post(self,ins_db,user_id):
        """update profile data of the onboarded number
            (Profile picture, About, Address)"""
        return whatsappWebhook.update_profile_settings(request,ins_db,user_id)

@ins_namespace.route('/create_template')
class AddTemplates(Resource):
    @ins_namespace.doc('Create template for the onboarded number')
    @ins_namespace.expect(ins_create_template,validate = True)
    @token_verification
    def post(self,ins_db,user_id):
        """Create templates"""
        return whatsappWebhook.create_template(request,ins_db,user_id)
    
@ins_namespace.route('/get_templates')
class GetTemplates(Resource):
    @ins_namespace.doc("get all templates")
    @ins_namespace.expect(ins_receive_templates,validate = True)
    @token_verification
    def post(self,ins_db,user_id):
        """ Get templates"""
        return whatsappWebhook.get_all_tempaltes(request,ins_db)

@ins_namespace.route('/delete_template')
class DeleteTemplates(Resource):
    @ins_namespace.doc("delete templates")
    @ins_namespace.expect(ins_delete_template,validate = True)
    @token_verification
    def delete(self,ins_db,user_id):
        """ Delete templates"""
        return whatsappWebhook.delete_template(request,ins_db)
    
@ins_namespace.route('/edit_template')
class EditTemplates(Resource):
    @ins_namespace.doc("edit templates")
    @ins_namespace.expect(ins_edit_template,validate = True)
    @token_verification
    def put(self,ins_db,user_id):
        """ Edit templates"""
        return whatsappWebhook.edit_template(request,ins_db)
    

@ins_namespace.route('/send_template_message')
class SendTemplates(Resource):
    @ins_namespace.doc("sent template message")
    @ins_namespace.expect(ins_send_template_message, validate = True)
    @token_verification
    def post(self,ins_db,user_id):
        """ send template message"""
        return whatsappWebhook.send_template_message(request,ins_db)
    
    
@ins_namespace.route('/webhook')
class whatsappWebhooks(Resource):
    @ins_namespace.doc('Verify webhook')
    def get(self):
        """Verify the webhook."""
        return whatsappWebhook.handle_verification(request)
    
    @ins_namespace.doc('Handle incoming webhook events')
    @whatapp_verification
    def post(self,ins_db):
        "Handle incoming webhook events (include status and message webhook)"
        return whatsappWebhook.handle_message_event(request,ins_db)




from flask_restx import Namespace,fields

class webhookSchema:
    ins_namespace = Namespace('Webhook',description='endpoint for webhook schema')

    ins_embedded_add_account_details=ins_namespace.model("embeeded whatsapp account details",{
    'strCode':fields.String(required=True,description='Code for exchange')
    }
    )
    ins_assign_bot_to_onboarded_number=ins_namespace.model("assign bot to the onboarded number",{
        'strPhoneNumberId':fields.String(required=True,description='For assign the bots using the phone number id'),
        'intBotId':fields.Integer(required=True,description='bot id to assign which phone number id')
    })                                                  
    ins_two_factor=ins_namespace.model('Phone number registration and webhook subscription.',{
        'strPhoneNumberId':fields.String(required=True,description='phone number id'),
        'strWabaId':fields.String(required=True,description='whatsapp bussiness account id '),
        'strTwoFactorCode':fields.Integer(required=True,description='Two Factor code is required for the phone number registration')

    })
    ins_update_profile_settings=ins_namespace.model('updating profile settings',{
        'strPhoneNumberId':fields.String(required=True,description='phone number id'),
        "strAbout": fields.String(required=True,description='About information for the profile'),
        "strAddress": fields.String(required=True,description='Business address'),
        "strProfilePicture": fields.String(required=True,description='URL or Base64 string of the profile picture')   
    })
    
    ins_receive_templates = ins_namespace.model('Receive template',{
    'strPhoneNumberId':fields.String(required = True, description = 'phone number id')
    })
    
    ins_create_template = ins_namespace.model('Create template',{
     'strTemplateName':fields.String(required = True, description = 'Template Name'),
     'strCategory':fields.String(required = True, description = 'Template Category'),
     'blnCategoryChange':fields.String(required = True, description = 'Category change'),
     'strLanguageCode':fields.String(required = True, description = 'language code'),
     'strPhoneNumberId':fields.String(required = True, description = 'phone number id()'),
     'arrTemplateComponents' : fields.List(fields.Raw(),description='components list')

    })
    
    ins_delete_template = ins_namespace.model('delete template',{
     'strTemplateName':fields.String(required = True, description = 'Template Name'),
     'strPhoneNumberId':fields.String(required = True, description = 'Registered whatsapp no ID'),
     'strWhatsappTemplateId':fields.String(required = True, description = 'unique whatsapp template id'),


    })
    
    ins_send_template_message = ins_namespace.model('send template message',{
     'strPhoneNumberId':fields.String(required = True, description = 'Registered whatsapp no ID'),
     'strTemplateName':fields.String(required = True, description = 'Template Name'),
     'strRecipientPhoneNumber':fields.String(required = True, description = 'Recipient Number'),
    })
    
    ins_edit_template = ins_namespace.model('edit template',{
     'strPhoneNumberId':fields.String(required = True, description = 'Registered whatsapp no ID'),
     'id':fields.String(required = True, description = 'unique whatsapp template id'), #whatsapp template id
     'arrTemplateComponents' : fields.List(fields.Raw(),description='components list')
    })
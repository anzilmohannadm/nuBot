
from db.create_db import CreateDB
from app.utils.generalMethods import dct_error

def create_blank_db(request):

    try: 
        dct_request = request.json
        if  not dct_request:
            return 'payload not found',400
        res=CreateDB().create_new_database(dct_request)
        return res
    except Exception as ex:
        return dct_error(str(ex)),400

    

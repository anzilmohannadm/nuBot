import traceback
from app.utils.generalMethods import dct_get_response,dct_error, create_cursor, dct_response

class sourceLogService:    
    @staticmethod
    def get_pending_approvals(request, ins_db, user_id):
        try:

            dct_request = request.json
            int_page_offset = dct_request.get("objPagination",{}).get("intPageOffset") or 0
            int_page_limit = dct_request.get("objPagination",{}).get("intPerPage") or 50
            int_offset = int_page_offset * int_page_limit
            int_bot_id = dct_request.get('objFilter',{}).get('intBotId')
            # Prepare the date range conditions
            str_condition = ["s.bln_pending_approvel = true","s.chr_document_status = 'N'"]

            if int_bot_id:
                str_condition.append("s.fk_bint_bot_id = %d" % int_bot_id)

            int_total_count,arr_list = sourceLogService.get_source(ins_db,str_condition,int_page_limit, int_offset)
            return (dct_get_response(int_total_count, int_page_offset, int_page_limit, arr_list),200,)

                        

                
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
        finally:
            if ins_db:
                ins_db.close()


    @staticmethod
    def get_deleted_sources(request, ins_db, user_id):
        try:

            dct_request = request.json
            int_page_offset = dct_request.get("objPagination",{}).get("intPageOffset") or 0
            int_page_limit = dct_request.get("objPagination",{}).get("intPerPage") or 50
            int_offset = int_page_offset * int_page_limit
            int_bot_id = dct_request.get('objFilter',{}).get('intBotId')
            # Prepare the date range conditions
            str_condition = ["s.chr_document_status = 'D'"]

            if int_bot_id:
                str_condition.append("s.fk_bint_bot_id = %d" % int_bot_id)

            int_total_count,arr_list = sourceLogService.get_source(ins_db,str_condition,int_page_limit, int_offset)
            return (dct_get_response(int_total_count, int_page_offset, int_page_limit, arr_list),200,)

                        

                
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)), 400
        finally:
            if ins_db:
                ins_db.close()
                        

    @staticmethod
    def get_source(ins_db,str_condition,int_page_limit, int_offset):   
        with create_cursor(ins_db) as cr:
            
            str_where_clause = ' WHERE ' + ' AND '.join(str_condition) if str_condition else ''
            str_query = """SELECT 
                                    s.pk_bint_training_source_id,
                                    s.vchr_source_name,
                                    s.bln_pending_approvel,
                                    s.vchr_delete_reason,
                                    s.fk_bint_deleted_user_id,
                                    b.vchr_bot_name,
                                    u.vchr_user_name,
                                    COUNT(*) OVER() AS int_total_count
                            FROM tbl_source s
                            LEFT JOIN tbl_bots b ON b.pk_bint_bot_id = s.fk_bint_bot_id
                            LEFT JOIN tbl_user u ON u.pk_bint_user_id = s.fk_bint_deleted_user_id
                            %s
                            LIMIT %s OFFSET %s""" % (str_where_clause, int_page_limit, int_offset)

            cr.execute(str_query)
            rst = cr.fetchall()
            arr_list = []
            int_total_count = 0

            if rst:
                int_total_count = rst[0]["int_total_count"]  # Total count in the current result
                int_serial = int_offset + 1
                for record in rst:
                    dct_pending_approvels = {}
                    dct_pending_approvels['slNo'] = int_serial
                    dct_pending_approvels['intPk'] = record['pk_bint_training_source_id']
                    dct_pending_approvels['strSourceName'] = record['vchr_source_name']
                    dct_pending_approvels['strBotName'] = record['vchr_bot_name']
                    dct_pending_approvels['strDeletedUser'] = record['vchr_user_name']
                    dct_pending_approvels['strReason'] = record['vchr_delete_reason']
                    arr_list.append(dct_pending_approvels)
                    int_serial += 1
            
            return int_total_count,arr_list
        
    @staticmethod
    def deleted_source(request,ins_db,user_id):
        try:
            dct_request = request.json
            int_source_id = dct_request.get("intPk") or ''
            str_action = dct_request.get("strAction") or ''
            
            with create_cursor(ins_db) as cr:
                cr.execute("select 1 FROM tbl_user WHERE pk_bint_user_id = %s AND fk_bint_user_group_id in (1,3)",(user_id,))
                rst_admin = cr.fetchone()
                if not rst_admin:
                    return dct_error("No Permission"),400
                
                if str_action.upper() == 'APPROVE':
                    cr.execute("UPDATE tbl_source SET chr_document_status = 'D' WHERE pk_bint_training_source_id = %s ",(int_source_id,))
                    
                elif str_action.upper() == 'REJECT':
                    cr.execute("UPDATE tbl_source SET bln_pending_approvel = false WHERE pk_bint_training_source_id = %s ",(int_source_id,))
                else:
                    return dct_error("No Permission"),400
                
                ins_db.commit()
                return dct_response("success", "source deleted successfully"), 200
                
        except Exception:
            traceback.print_exc()
            return dct_error("Unable to delete"),400
        finally:
            if ins_db:ins_db.close()


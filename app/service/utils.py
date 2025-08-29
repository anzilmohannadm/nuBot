from app.utils.generalMethods import dct_error,create_cursor
import traceback

class utilsService:
    @staticmethod
    def get_dropdown(request,ins_db,user_id):
        try:
            dct_request = request.json 
            str_dropdown_key = dct_request.get('strDropdownKey')
            str_filter = ''
        
            dct_dropdown = {
                            "USER_GROUPS": [
                                "tbl_user_group",
                                True,
                                {"intPk": "pk_bint_user_group_id", "strName": "vchr_user_group"},
                            ],
                            "BOTS": [
                                "tbl_bots b",
                                True,
                                {"intPk": "pk_bint_bot_id", "strBotName": "vchr_bot_name","blnAgent":"bln_agent"},
                            ],
                            "USERS": [
                                "tbl_user",
                                True,
                                {"intPk": "pk_bint_user_id", "strUserName": "vchr_user_name"},
                            ],
                             "TEST_MATE_PROJECT":[]
                             ,
                             "USER_ROLES":[
                                 "tbl_roles",
                                 True,
                                 {"intPk":"pk_bint_role_id","strRole":"vchr_role"}  
                             ]
                        }
            
            
            dct_dropdown_data = {}
            
            if str_dropdown_key == 'USER_GROUPS' :
                str_filter += " WHERE vchr_user_group IS NOT NULL AND  vchr_user_group NOT IN ('Nucore Admin','ReadOnly') "

            if str_dropdown_key == 'USERS' :
                str_filter += " WHERE chr_document_status = 'N' AND fk_bint_user_group_id not in (3,4) "
            
            if str_dropdown_key == "TEST_MATE_PROJECT":
                lst_values = []
                with create_cursor(ins_db) as cr:
                    cr.execute(
                        "SELECT 1 FROM tbl_user WHERE pk_bint_user_id = %s AND fk_bint_user_group_id IN (1, 3)",
                        (user_id,)
                    )
                    rst_admin = cr.fetchone()
                
                    if not rst_admin:
                        return {"error": "No permission to access this resource"}, 400
                    
                    # Custom logic for TEST_MATE_PROJECT
                    cr.execute(
                            "SELECT vchr_project_name, pk_bint_project_id FROM tbl_projects ")
                    rst_projects= cr.fetchall()
                
                    if rst_projects:
                        # Extract 'pk' values into a list
                        lst_values = [{"intPk": item["pk_bint_project_id"],"strProjectName":item["vchr_project_name"]} for item in rst_projects]
                
                dct_dropdown_data[str_dropdown_key] = lst_values
                return dct_dropdown_data, 200
              

            if str_dropdown_key == "BOTS":
                str_filter += """
                    LEFT JOIN tbl_bot_view_permissions vp 
                        ON b.pk_bint_bot_id = vp.fk_bint_bot_id AND vp.fk_bint_user_id = %s
                    LEFT JOIN tbl_bot_edit_permissions ep 
                        ON b.pk_bint_bot_id = ep.fk_bint_bot_id AND ep.fk_bint_user_id = %s
                    WHERE  chr_document_status = 'N'
                    AND (vp.fk_bint_user_id = %s OR b.fk_bint_created_user_id = %s)
                    
                """ % (user_id, user_id, user_id,user_id)
            
            if not dct_dropdown.get(str_dropdown_key):
                
                return {str_dropdown_key:[]},200
            
                
            str_table = dct_dropdown.get(str_dropdown_key)[0]        
            dct_select = dct_dropdown.get(str_dropdown_key)[2]
            str_select_columns = ", ".join(list(dct_select.values()))
            str_query = """ SELECT {str_select_columns} 
                                FROM {str_table} 
                                {str_filter} 
                        """.format(str_select_columns=str_select_columns,
                                    str_table=str_table,
                                    str_filter=str_filter)
                        
            with create_cursor(ins_db) as cr:
                cr.execute(str_query)
                rst = cr.fetchall()
                lst_values = []
                for record in rst:
                    dct = {}
                    for key,value in dct_select.items():
                        dct[key] = record[value]
                    lst_values.append(dct)
                    
            dct_dropdown_data[str_dropdown_key] = lst_values
            return dct_dropdown_data,200
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)),400
        finally:
            if ins_db:ins_db.close()
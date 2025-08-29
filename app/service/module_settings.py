from app.utils.generalMethods import create_cursor,dct_error,get_tenancy_id
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.global_config import env_mode
from app.utils.conf_path import str_configpath
import traceback

ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)

class moduleSettingsService:
    @staticmethod
    def get_module_settings(request,ins_db,int_user_id):
        try:
            dct_request = request.json
            str_module_name = dct_request['strModule']
            dct_settings = {}
            dct_settings['strModule'] = str_module_name
            with create_cursor(ins_db) as cr:
                # get table grid settings and API end points
                json_api_settings_value,json_api_end_points = moduleSettingsService.get_module_level_settings(cr,str_module_name)
                if not json_api_end_points :
                    return dct_error('API end points missing'),400

                for str_operations in json_api_end_points['endPoints']:
                    json_api_end_points['endPoints'][str_operations]['port'] = ins_cfg.get(env_mode,json_api_end_points['endPoints'][str_operations]['port'])
                    
                dct_settings['objEndPoints'] = json_api_end_points
                dct_settings['objColumns'] = json_api_settings_value
                # get menu details
                rst_module = moduleSettingsService.get_menu_details(cr,str_module_name,int_user_id)
                
                if not rst_module : 
                    return dct_error('Menu data missing'),400

                dct_settings['objPermissions'] = {  "intView": rst_module['int_view'],
                                                    "intAdd": rst_module['int_add'],
                                                    "intUpdate": rst_module['int_update'],
                                                    "intDelete": rst_module['int_delete']
                                                    }
                return dct_settings,200
        except Exception as ex:
            traceback.print_exc()
            return dct_error(str(ex)),400
        
    @staticmethod
    def get_module_level_settings(cr,str_module_name):
        try:  
            
            cr.execute("""  SELECT json_settings_value,json_endpoints 
                            FROM tbl_module_level_settings 
                            WHERE vchr_module_name = %s """,(str_module_name,))
            rst_module_level = cr.fetchone()
            if rst_module_level :
                return rst_module_level['json_settings_value'],rst_module_level['json_endpoints']
            else:
                return {},{}
        except Exception as ex:
            traceback.print_exc()
            return {},{}
        
    @staticmethod    
    def get_menu_details(cr,str_module_name,int_user_id):
        try:    
            cr.execute(""" SELECT m.pk_bint_menu_id,
                            m.vchr_menu_name,
                            m.vchr_menu_caption,
                            m.int_menu_hierarchy,
                            m.vchr_menu_tooltip,
                            m.vchr_source_code_path,
                            m.vchr_gui_title,
                            m.bint_parent_id,
                            up.int_add,
                            up.int_view,
                            up.int_update,
                            up.int_delete
                            FROM tbl_user_permission up
                            INNER JOIN tbl_menu m
                            ON m.pk_bint_menu_id = up.fk_bint_menu_id 
                            WHERE m.vchr_menu_name = '%s' and up.fk_bint_user_group_id= (SELECT fk_bint_user_group_id FROM tbl_user WHERE pk_bint_user_id= %s) """%(str_module_name,int_user_id))
            rst_module = cr.fetchone()
            if rst_module :
                return rst_module
            else:
                return None
        except Exception as ex:
            traceback.print_exc()
            return None
        
    @staticmethod   
    def get_all_menu_details(cr,int_user_id):
        try:    
            cr.execute("""
            SELECT vchr_settings_value 
            FROM tbl_settings 
            WHERE vchr_settings_name = 'PROJECT_TEST_CASE_MAPPING'
            """)
            project_test_case_mapping_value = cr.fetchone()

 
            query=""" SELECT m.pk_bint_menu_id,
            m.vchr_menu_name,
            m.vchr_menu_caption,
            m.bint_parent_id,
            m.int_menu_hierarchy,
            m.vchr_menu_tooltip,
            m.vchr_source_code_path,
            m.vchr_gui_title,
            up.int_view,
            m.int_order,
            up.int_add,
            up.int_update,
            up.int_delete
            FROM tbl_user_permission up
            INNER JOIN tbl_menu m ON up.fk_bint_menu_id = m.pk_bint_menu_id 
            WHERE  up.int_view != 0 
                AND up.fk_bint_user_group_id = (SELECT fk_bint_user_group_id FROM tbl_user WHERE pk_bint_user_id= %s)
            """
            #Integration Menu is hidden from tenants where PROJECT_TEST_CASE_MAPPING==FALSE
            if project_test_case_mapping_value[0].upper() == 'FALSE':
                query += " AND m.vchr_menu_name != 'mdl_integrations'"
            
            query += " ORDER BY m.pk_bint_menu_id"
            
            cr.execute(query, (int_user_id,))
            rst_module = cr.fetchall()
            return rst_module if rst_module else None
        
        except Exception as ex:
            return None
        
    @staticmethod
    def get_menu(request,ins_db,int_user_id):
        try:
            
            dct_menu = {}
            dct_parent_menu = {}
            lst_menu = []
            
            # get all menu details
            with create_cursor(ins_db) as cr:
                rst_all_menu = moduleSettingsService.get_all_menu_details(cr,int_user_id)
                if not rst_all_menu :
                    return dct_error('Menu missing'),400
                
                
                for record in rst_all_menu:
                    if record['pk_bint_menu_id'] not in dct_parent_menu:
                        if record['bint_parent_id'] not in dct_parent_menu:
                            dct_parent_menu[record['pk_bint_menu_id']] = {"intPk": record['pk_bint_menu_id'],
                                                                        "intParentId": record['bint_parent_id'],
                                                                        "id": record['vchr_menu_name'],
                                                                        "intMenuHierarchy": record['int_menu_hierarchy'],
                                                                        "label": record['vchr_menu_name'],
                                                                        "link": record['vchr_source_code_path'],
                                                                        "items": []}
                        else:
                            dct_parent_menu[record['bint_parent_id']]['items'].append( {"intPk": record['pk_bint_menu_id'],
                                                                                        "intParentId": record['bint_parent_id'],
                                                                                        "id": record['vchr_menu_name'],
                                                                                        "intMenuHierarchy": record['int_menu_hierarchy'],
                                                                                        "label": record['vchr_menu_name'],
                                                                                        "link": record['vchr_source_code_path'],
                                                                                        "items": []})
                for _,dct_menu_details in dct_parent_menu.items():
                    lst_menu.append(dct_menu_details)
                dct_menu['arrSubNav'] = lst_menu
                
                return dct_menu,200
        except Exception as ex:
            return dct_error(str(ex)),400
        finally:
            if ins_db:ins_db.close()


    @staticmethod
    def get_user_details(request,ins_db,user_id):
        try:
            with create_cursor(ins_db) as cr:
                cr.execute("""SELECT 
                                u.vchr_user_name,
                                u.vchr_email_id,
                                ug.vchr_user_group,
                                json_object_agg(s.vchr_settings_name, s.vchr_settings_value) AS user_settings
                            FROM 
                                tbl_user u
                            LEFT JOIN 
                                tbl_user_group ug 
                                ON u.fk_bint_user_group_id = ug.pk_bint_user_group_id
                            LEFT JOIN 
                                tbl_settings s 
                                ON TRUE  -- Assuming you want all settings
                            WHERE 
                                u.pk_bint_user_id = %s
                            GROUP BY 
                                u.vchr_user_name, 
                                u.vchr_email_id, 
                                ug.vchr_user_group
                           """,(user_id,))
                
                rst_user = cr.fetchone()
                if not rst_user:
                    return dct_error("Unavailabe"),400
                
                return {"intUserId":user_id,
                        "strUserName":rst_user['vchr_user_name'],
                        "strEmailId":rst_user['vchr_email_id'],
                        "strUserGroup":rst_user['vchr_user_group'],
                        "strCompanyName":rst_user["user_settings"]["TENANT_NAME"],
                        "blnEnableProject":bool(rst_user["user_settings"]["PROJECT_TEST_CASE_MAPPING"] == "TRUE"), #Return bool value of true if project_test_case_mapping equal to 'TRUE' else 'False'
                        "blnCostViewAcess":bool(rst_user["user_settings"]["TENANT_COST_VIEW_ACCESS"] == "TRUE")#Return bool value of true if tenant_cost_view_access equal to 'TRUE' else 'False'
                        }
            
        except Exception:
            traceback.print_exc()
            return dct_error("Unable to load"),400
        
        finally:
            if ins_db:ins_db.close()
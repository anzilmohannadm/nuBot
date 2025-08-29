import traceback
import uuid
import os
import shutil
import lancedb
from io import BytesIO
from flask import Response

from app.utils.generalMethods import (
    create_cursor,
    dct_error,
    get_tenancy_id,
    dct_response,
    time_difference_with_timezone,
    create_azure_connection,
)
from app.schema import EmbedModel, MemoryModel, LiveChatModel
from app.utils.executor import executor
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.conf_path import str_configpath
from app.utils.global_config import env_mode

# configuration
ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)

# azure resource configuration
str_azure_search_service_endpoint = ins_cfg.get(env_mode, "AZURE_AI_SEARCH_ENDPOINT")
str_search_api_key = ins_cfg.get(env_mode, "AZURE_AI_SEARCH_API_KEY")
str_azure_storage_connection = ins_cfg.get(env_mode, "AZURE_STORAGE_CONNECTION_STRING")

str_azure_openai_endpoint = ins_cfg.get(env_mode, "AZURE_OPENAI_ENDPOINT")
str_openai_key = ins_cfg.get(env_mode, "AZURE_OPENAI_API_KEY")


class botService:
    @staticmethod
    def create_bot(request, ins_db, user_id):
        try:
            dct_request = request.json
            str_bot_name = dct_request["strBotName"]
            str_instruction = (
                dct_request.get("strBotInstructions")
                or "You are a helpful AI assistant."
            )
            str_welcome_message = dct_request.get("strWelcomeMessage") or ""
            str_suggested_reply = dct_request.get("strSuggestedReply")
            str_image = dct_request.get("strImage")
            bln_llm_knowledge = (dct_request.get("blnLLM"),)
            str_bot_type = (dct_request.get("strBotType"),)
            lst_view_permission = dct_request.get("arrUserViewPermission") or []
            lst_edit_permission = dct_request.get("arrUserEditPermission") or []

            with create_cursor(ins_db) as cr:
                str_unique_azure_uuid = str(uuid.uuid4())
                cr.execute(
                    """INSERT INTO tbl_bots
                            (vchr_bot_name,
                             vchr_engine_instruction,
                             vchr_azure_resource_uuid,
                             vchr_welcome_message,
                             vchr_suggested_reply,
                             bln_llm_knowledge,
                             vchr_bot_type,
                             vchr_icon,
                             fk_bint_created_user_id,
                             tim_created)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                        ON CONFLICT (vchr_bot_name) DO NOTHING
                        RETURNING pk_bint_bot_id""",
                    (
                        str_bot_name,
                        str_instruction,
                        str_unique_azure_uuid,
                        str_welcome_message,
                        str_suggested_reply,
                        bln_llm_knowledge,
                        str_bot_type,
                        str_image,
                        user_id,
                    ),
                )
                if cr.rowcount > 0:  # check if already exist with given name
                    str_tenancy_id = get_tenancy_id(request.headers)
                    executor.submit(
                        botService.create_bot_resources,
                        str_unique_azure_uuid,
                        str_tenancy_id,
                    )

                    rst_bot = cr.fetchone()
                    int_bot_id = rst_bot["pk_bint_bot_id"]

                    # insert permission

                    if lst_edit_permission:
                        lst_edit_values = [
                            (dct_user["intPk"], int_bot_id)
                            for dct_user in lst_edit_permission
                            if dct_user.get("intPk")
                        ]
                        str_edit_permission_query = "INSERT INTO tbl_bot_edit_permissions (fk_bint_user_id,fk_bint_bot_id) VALUES (%s,%s)"
                        cr.executemany(str_edit_permission_query, lst_edit_values)

                        # if a user have permission to edit , he can also view , merge view and edit list
                        dct_merged_permission = {
                            item["intPk"]: item
                            for item in lst_view_permission + lst_edit_permission
                        }

                        # Convert the merged dictionary back into a list
                        lst_view_permission = list(dct_merged_permission.values())

                    if lst_view_permission:
                        lst_view_values = [
                            (dct_user["intPk"], int_bot_id)
                            for dct_user in lst_view_permission
                            if dct_user.get("intPk")
                        ]
                        str_view_permission_query = "INSERT INTO tbl_bot_view_permissions (fk_bint_user_id,fk_bint_bot_id) VALUES (%s,%s)"
                        cr.executemany(str_view_permission_query, lst_view_values)

                    ins_db.commit()

                    return {"intPk": int_bot_id}, 200
                else:
                    return dct_error("chatbot Already exist"), 400

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to create"), 400
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def update_bot(request,ins_db, user_id):
        try:
            dct_request = request.json
            int_bot_id = dct_request['intPk']
            if isinstance(dct_request.get('objMappedProject', {}), dict):
                int_project_id = dct_request.get('objMappedProject', {}).get('intPk')
            else:int_project_id = None
            # check edit permission
            if not botService.check_bot_permission(ins_db,int_bot_id,user_id):
                return dct_error("No Permission"),400
            
            str_bot_name = dct_request['strBotName']
            str_instruction = dct_request.get('strBotInstructions') or 'You are a helpful AI assistant.'
            str_welcome_message = dct_request.get('strWelcomeMessage') or ''
            str_suggested_reply = dct_request.get('strSuggestedReply')
            str_image = dct_request.get('strImage')
            bln_llm_knowledge = dct_request.get('blnLLM'),
            str_bot_type = dct_request.get('strBotType'),
            lst_view_permission = dct_request.get('arrUserViewPermission') or []
            lst_edit_permission = dct_request.get('arrUserEditPermission') or []
            
            with create_cursor(ins_db) as cr:
                cr.execute(
                    """UPDATE tbl_bots
                        SET 
                            vchr_bot_name = %s,
                            vchr_engine_instruction = %s,
                            vchr_welcome_message = %s,
                            vchr_suggested_reply = %s,
                            vchr_icon = %s,
                            bln_llm_knowledge = %s,
                            vchr_bot_type = %s
                        WHERE pk_bint_bot_id =%s""",
                    (str_bot_name, str_instruction, str_welcome_message, str_suggested_reply, str_image, bln_llm_knowledge, str_bot_type,int_bot_id),
                )

                # map nuhive projects to sync testcases
                if int_project_id:
                    cr.execute("DELETE FROM tbl_bot_project_mapping WHERE fk_bint_bot_id = %s",(int_bot_id,))
                    cr.execute("INSERT INTO tbl_bot_project_mapping (fk_bint_bot_id, fk_bint_project_id) VALUES(%s,%s)",(int_bot_id, int_project_id))
                
                # delete existing permission and insert new permissions
                cr.execute("DELETE FROM tbl_bot_edit_permissions WHERE fk_bint_bot_id = %s",(int_bot_id,))
                if lst_edit_permission:
                    lst_edit_values = [(dct_user['intPk'],int_bot_id)  for dct_user in lst_edit_permission if dct_user.get('intPk')]
                    str_edit_permission_query = "INSERT INTO tbl_bot_edit_permissions (fk_bint_user_id,fk_bint_bot_id) VALUES (%s,%s)"
                    cr.executemany(str_edit_permission_query,lst_edit_values)

                    # if a user have permission to edit , he can also view , merge view and edit list 
                    dct_merged_permission = {item['intPk']: item for item in lst_view_permission + lst_edit_permission}

                    # Convert the merged dictionary back into a list
                    lst_view_permission = list(dct_merged_permission.values())

                # delete existing permission and insert new permissions
                cr.execute("DELETE FROM tbl_bot_view_permissions WHERE fk_bint_bot_id = %s",(int_bot_id,))
                if lst_view_permission:

                    lst_view_values = [(dct_user['intPk'],int_bot_id)  for dct_user in lst_view_permission if dct_user.get('intPk')]
                    str_view_permission_query = "INSERT INTO tbl_bot_view_permissions (fk_bint_user_id,fk_bint_bot_id) VALUES (%s,%s)"
                    cr.executemany(str_view_permission_query,lst_view_values)
                
                ins_db.commit()
                return dct_response("success", "chatbot updated successfully"), 200
                
                    
        except Exception:
            traceback.print_exc()
            return dct_error("Unable to update"), 400
        finally:
            if ins_db:ins_db.close()

    @staticmethod
    def delete_bot(request, ins_db, user_id):
        try:
            dct_request = request.json
            int_bot_id = dct_request["intPk"]

            # check edit permission
            if not botService.check_bot_permission(ins_db, int_bot_id, user_id):
                return dct_error("No Permission"), 400

            with create_cursor(ins_db) as cr:
                cr.execute(
                    "DELETE FROM  tbl_bots WHERE pk_bint_bot_id =%s RETURNING vchr_azure_resource_uuid",
                    (int_bot_id,),
                )
                ins_db.commit()
                rst_bot = cr.fetchone()
                str_unique_azure_uuid = rst_bot["vchr_azure_resource_uuid"]
                str_tenancy_id = get_tenancy_id(request.headers)
                executor.submit(
                    botService.delete_bot_resources,
                    str_unique_azure_uuid,
                    str_tenancy_id,
                )
                return dct_response("success", "chatbot deleted successfully"), 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to delete"), 400
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def list_bot(ins_db, user_id):
        try:
            lst_bots = []
            with create_cursor(ins_db) as cr:
                cr.execute(
                    """
                    SELECT b.pk_bint_bot_id,
                        b.vchr_bot_name,
                        b.vchr_icon,
                        b.bln_enabled,
                        b.vchr_azure_resource_uuid,
                        CASE 
                            WHEN b.fk_bint_created_user_id = %s OR ep.fk_bint_user_id IS NOT NULL THEN TRUE
                            ELSE FALSE
                        END AS bln_edit   
                    FROM tbl_bots b
                    LEFT JOIN tbl_bot_view_permissions vp ON b.pk_bint_bot_id = vp.fk_bint_bot_id AND vp.fk_bint_user_id = %s
                    LEFT JOIN tbl_bot_edit_permissions ep ON b.pk_bint_bot_id = ep.fk_bint_bot_id AND ep.fk_bint_user_id = %s
                    WHERE b.chr_document_status = 'N' AND b.bln_agent = false
                    AND (b.fk_bint_created_user_id = %s OR vp.fk_bint_user_id IS NOT NULL)
                """,
                    (user_id, user_id, user_id, user_id),
                )
                rst_bots = cr.fetchall()

                if rst_bots:
                    for record in rst_bots:
                        # Get users with access for each bot
                        cr.execute(
                            """
                            SELECT u.vchr_user_name, 
                                CASE 
                                    WHEN ep.fk_bint_user_id IS NOT NULL THEN 'EDIT'
                                    ELSE 'VIEW'
                                END AS access_type
                            FROM tbl_user u
                            LEFT JOIN tbl_bot_edit_permissions ep ON u.pk_bint_user_id = ep.fk_bint_user_id AND ep.fk_bint_bot_id = %s
                            LEFT JOIN tbl_bot_view_permissions vp ON u.pk_bint_user_id = vp.fk_bint_user_id AND vp.fk_bint_bot_id = %s
                            WHERE u.pk_bint_user_id IN (
                                SELECT fk_bint_user_id FROM tbl_bot_view_permissions WHERE fk_bint_bot_id = %s
                                UNION
                                SELECT fk_bint_user_id FROM tbl_bot_edit_permissions WHERE fk_bint_bot_id = %s
                            )
                        """,
                            (
                                record["pk_bint_bot_id"],
                                record["pk_bint_bot_id"],
                                record["pk_bint_bot_id"],
                                record["pk_bint_bot_id"],
                            ),
                        )

                        users_with_access = cr.fetchall()

                        arr_users_with_access = [
                            {"strName": user[0], "strAccessType": user[1]}
                            for user in users_with_access
                        ]

                        lst_bots.append(
                            {
                                "intPk": record["pk_bint_bot_id"],
                                "strBotName": record["vchr_bot_name"],
                                "strBotUniqueId": record["vchr_azure_resource_uuid"],
                                "strImage": record["vchr_icon"],
                                "blnEdit": record["bln_edit"],
                                "arrUsersWithAccess": arr_users_with_access,
                                "blnEnabled": record["bln_enabled"],
                            }
                        )

                return lst_bots, 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to get"), 400
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def get_bot_deatils(request, ins_db, user_id):
        try:
            int_bot_id = request.json.get("intPk")
            str_tenancy_id = get_tenancy_id(request.headers)
            str_origin = request.headers.get("origin")
            dct_bot = {}
            with create_cursor(ins_db) as cr:
                cr.execute(
                    """SELECT b.*,
                                     CASE 
                                         WHEN b.fk_bint_created_user_id = %s OR tep.fk_bint_user_id IS NOT NULL THEN TRUE
                                         ELSE FALSE
                                     END AS bln_edit,
                                        
                                    COALESCE(
                                    (SELECT JSON_AGG(
                                        JSON_BUILD_OBJECT(
                                            'intPk', vp.fk_bint_user_id,
                                            'strUserName', u.vchr_user_name
                                        )
                                    )
                                    FROM tbl_bot_view_permissions vp
                                    JOIN tbl_user u ON vp.fk_bint_user_id = u.pk_bint_user_id
                                    WHERE vp.fk_bint_bot_id = b.pk_bint_bot_id), '[]') AS arr_view_permission,
        
                                    COALESCE(
                                    (SELECT JSON_AGG(
                                        JSON_BUILD_OBJECT(
                                            'intPk', ep.fk_bint_user_id,
                                            'strUserName', u.vchr_user_name
                                        )
                                    )
                                    FROM tbl_bot_edit_permissions ep
                                    JOIN tbl_user u ON ep.fk_bint_user_id = u.pk_bint_user_id
                                    WHERE ep.fk_bint_bot_id = b.pk_bint_bot_id), '[]') AS arr_edit_permission,

                                    COALESCE(
                                        JSON_BUILD_OBJECT(
                                            'intPk', p.pk_bint_project_id,
                                            'strProjectName', p.vchr_project_name
                                        ), '{}'
                                    ) AS obj_mapped_project 
                           FROM tbl_bots b 
                           LEFT JOIN tbl_bot_view_permissions tvp ON b.pk_bint_bot_id = tvp.fk_bint_bot_id AND tvp.fk_bint_user_id = %s
                           LEFT JOIN tbl_bot_edit_permissions tep ON b.pk_bint_bot_id = tep.fk_bint_bot_id AND tep.fk_bint_user_id = %s
                           LEFT JOIN tbl_bot_project_mapping bpm ON b.pk_bint_bot_id = bpm.fk_bint_bot_id
                           LEFT JOIN tbl_projects p ON bpm.fk_bint_project_id = p.pk_bint_project_id
                           WHERE b.pk_bint_bot_id = %s
                           AND b.chr_document_status = 'N'
                           AND (b.fk_bint_created_user_id = %s OR tvp.fk_bint_user_id IS NOT NULL)""",
                    (user_id, user_id, user_id, int_bot_id, user_id),
                )

                rst_bot = cr.fetchone()
                if rst_bot:
                    dct_bot = {
                        "intPk": rst_bot["pk_bint_bot_id"],
                        "strBotName": rst_bot["vchr_bot_name"],
                        "strImage": rst_bot["vchr_icon"],
                        "strUniqueId": rst_bot["vchr_azure_resource_uuid"],
                        "strAuthToken": f"{str_tenancy_id}/{rst_bot['vchr_azure_resource_uuid']}",
                        "strCreated": time_difference_with_timezone(
                            "Asia/Calcutta", rst_bot["tim_created"]
                        ),
                        "blnEdit": rst_bot["bln_edit"],
                        "blnEnabled": rst_bot["bln_enabled"],
                        "blnLLM": rst_bot["bln_llm_knowledge"],
                        "strBotType": rst_bot["vchr_bot_type"],
                        "strBotInstructions": rst_bot["vchr_engine_instruction"],
                        "strWelcomeMessage": rst_bot["vchr_welcome_message"],
                        "strSuggestedReply": rst_bot["vchr_suggested_reply"],
                        "objCustomization": {
                            "strTheme": rst_bot["vchr_theme"],
                            "strPrimaryColor": rst_bot["vchr_primary_color"],
                            "strPrimaryFontColor": rst_bot["vchr_primary_font_color"],
                            "strBotColor": rst_bot["vchr_bot_color"],
                            "strBotFontColor": rst_bot["vchr_bot_font_color"],
                            "strfloatingIcon": rst_bot['vchr_float_icon']
                        },
                        "strSourceUrl": f"{str_origin}/api/nubot/embed/{str_tenancy_id}/{rst_bot['vchr_azure_resource_uuid']}/index.js",
                        "arrUserViewPermission": rst_bot["arr_view_permission"],
                        "arrUserEditPermission": rst_bot["arr_edit_permission"],
                        "objMappedProject": rst_bot["obj_mapped_project"],
                    }
                return dct_bot, 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to load"), 400
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def get_bot_info(request, ins_db, str_bot_id):
        try:
            dct_bot = {}
            with create_cursor(ins_db) as cr:
                cr.execute(
                    "SELECT * FROM tbl_bots WHERE vchr_azure_resource_uuid = %s LIMIT 1",
                    (str_bot_id,),
                )
                rst_bot = cr.fetchone()
                if rst_bot:
                    dct_bot = {
                        "strName": rst_bot["vchr_bot_name"],
                        "strWelcomeMessage": rst_bot["vchr_welcome_message"],
                        "strSuggestedReply": rst_bot["vchr_suggested_reply"],
                        "strIcon": rst_bot["vchr_icon"],
                        "strTheme": rst_bot["vchr_theme"],
                        "strPrimaryColor": rst_bot["vchr_primary_color"],
                        "strPrimaryFontColor": rst_bot["vchr_primary_font_color"],
                        "strBotColor": rst_bot["vchr_bot_color"],
                        "strBotFontColor": rst_bot["vchr_bot_font_color"],
                    }
                return dct_bot, 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to load"), 400
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def get_bot_index_js(ins_db, str_bot_id, str_tenancy_id):
        try:
            with create_cursor(ins_db) as cr:
                cr.execute(
                    "SELECT vchr_primary_color,vchr_primary_font_color,vchr_theme,vchr_bot_color,vchr_float_icon FROM tbl_bots WHERE vchr_azure_resource_uuid = %s",
                    (str_bot_id,),
                )
                rst_bot = cr.fetchone()
            if not rst_bot:
                return None

            str_url = ins_cfg.get(env_mode, "url")
            str_js = (
                """(function () {
    const customCss = `
        .embed_bar { 
            background-color: $primary_color; 
            position: fixed; 
            cursor: pointer; 
            text-align: center; 
            font-size: 18px; 
            border-radius: 40px; 
            padding: 10px 10px; 
            box-shadow: 0px 0px 8px 0px #cacaca;
            z-index: 9999999; 
            color: #fff; 
            bottom: 1% !important; 
            right: 7px !important; 
            transition: transform 0.3s ease-in-out; 
        }
        .embed_bar.pop-in { 
            animation: popIn 0.3s ease-in-out forwards; 
        }
        .embed_bar.pop-out { 
            animation: popOut 0.3s ease-in-out forwards; 
        }
        .embed_side_bar { 
            height: 0; 
            width: auto; 
            position: fixed; 
            z-index: 100000; 
            bottom: 0; 
            right: 100px; 
            background-color: #eee; 
            overflow-x: hidden; 
            transition: .5s; 
            padding-top: 5px; 
        }
        .sidebar_right, .sidebar_left { 
            position: fixed; 
            bottom: 0; 
            z-index: 999999; 
        }
        .sidebar_right.medium_sidebar, .sidebar_right.small_sidebar { 
            right: 17px; 
        }
        .head-hide { 
            top: -50px !important;
            margin-right: 0.5rem !important; 
        }
        .embed_head_hide { 
            top: -20px; 
            right: 0; 
            bottom: 0px; 
            padding: 0px; 
            cursor: pointer; 
            z-index: 999999; 
            position: relative; 
            justify-content: end; 
            display: flex; 
            align-items: center; 
            width: min-content; 
            float: right; 
        }
        .embed_circle { 
            height: 70px; 
            width: 70px; 
            position: fixed; 
            z-index: 9999; 
            bottom: 5px; 
            border-radius: 100px; 
            box-shadow: 0 0 25px #7a7a7a; 
            cursor: pointer; 
            background: url(/resources/app/images/in-app-help/colored_filled_icon.svg) center/contain no-repeat; 
        }
        .chat_embed {
            box-shadow: 0px 0px 8px 0px #cacaca59;
            border-radius: 15px;
        }
        .chat_embed_small { 
            height: 60vh; 
            min-width: 375px; 
        }
        .chat_embed_medium { 
            height: 75vh; 
            width: 400px; 
        }
        .chat_embed_large { 
            height: 99vh; 
            width: 550px; 
        }
        #embed_load_div { 
            bottom: 5.5rem; 
            position: relative; 
        }
        .slide-in-bottom { 
            animation: slideInBottom 0.3s ease-in-out forwards; 
        }
        .slide-out-top { 
            animation: slideOutTop 0.3s ease-in-out forwards; 
        }
        /* Toaster Styles */
        .toaster {
            position: fixed;
            bottom: 1.5%; /* Align vertically with chat button */
            right: 60px; /* Position to the left of chat button */
            transform: translateX(0); /* Ensure no vertical offset */
            background-color: $primary_color;
            color: #fff;
            padding: 10px 15px; /* Reduced padding */
            border-radius: 10px;
            box-shadow: 0px 0px 6px 0px #cacaca;
            z-index: 9999998;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 13px; /* Smaller font size */
            max-width: 150px; /* Smaller width */
            animation: fadeIn 0.3s ease-in-out forwards;
            transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out;
        }
        .toaster.hidden {
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
        }
        .toaster-close {
            margin-left: 8px;
            cursor: pointer;
            background: none;
            border: none;
            color: #fff;
            font-size: 14px; /* Slightly larger for visibility */
            line-height: 1;
            padding: 0;
        }
        @keyframes slideInBottom {
            0% { transform: translateY(100%); }
            100% { transform: translateY(0); }
        }
        @keyframes slideOutTop {
            0% { transform: translateY(0); }
            100% { transform: translateY(100%); }
        }
        @keyframes popIn {
            0% { transform: scale(0.8); opacity: 0; }
            100% { transform: scale(1); opacity: 1; }
        }
        @keyframes popOut {
            0% { transform: scale(1); opacity: 1; }
            100% { transform: scale(0.8); opacity: 0; }
        }
        @keyframes fadeIn {
            0% { opacity: 0; transform: translateX(10px); } /* Slide in from right */
            100% { opacity: 1; transform: translateX(0); }
        }`;

    const style = document.createElement('style');
    style.type = 'text/css';
    let blnExpandNav = false;
    style.appendChild(document.createTextNode(customCss));
    document.head.appendChild(style);

    const btn = document.createElement("div");
    btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="30" height="30" viewBox="0 0 177 150">
        <image xlink:href="$float_image" x="0" y="0" width="177" height="150"/>
    </svg>`;
    btn.className = "open_sidebar chat-sticky-btn embed_btn embed_right embed_bar";
    btn.id = "chat-sticky-btn";
    btn.addEventListener("click", () => {
        if (btn.classList.contains('open_sidebar')) {
            openNav();
            btn.classList.remove("open_sidebar");
        } else {
            closeNav();
        }
    });

    // Create Toaster
    const toaster = document.createElement("div");
    toaster.className = "toaster";
    toaster.innerHTML = `
        <span>I am here 👋</span>
        <button class="toaster-close">✕</button>
    `;
    setTimeout(() => document.body.appendChild(toaster), 5000);
    // setTimeout(() => toaster.classList.add("hidden"), 15000);
    // Add close event listener to toaster
    const closeToasterBtn = toaster.querySelector(".toaster-close");
    closeToasterBtn.addEventListener("click", () => {
        toaster.classList.add("hidden");
    });

    const sidebarField = document.createElement('input');
    sidebarField.type = "hidden";
    sidebarField.id = "sidebar_height";
    sidebarField.value = "60vh";

    const embedChatField = document.createElement('input');
    embedChatField.type = "hidden";
    embedChatField.id = "embed_chat_widht";
    embedChatField.value = "chat_embed_small";

    const sideBar = document.createElement('div');
    sideBar.id = 'embed_Sidebar';
    sideBar.className = 'embed_sidebar sidebar_right small_sidebar';
    sideBar.style.display = 'none';

    const headHide = document.createElement('div');
    headHide.className = "head-hide embed_head_hide";
    headHide.innerHTML = `<svg  xmlns="http://www.w3.org/2000/svg"  width="24"  height="24"  viewBox="0 0 24 24"  fill="none"  stroke="$font_color"  stroke-width="2"  stroke-linecap="round"  stroke-linejoin="round"  class="icon icon-tabler icons-tabler-outline icon-tabler-x"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M18 6l-12 12" /><path d="M6 6l12 12" /></svg>`;
    headHide.onclick = closeNav;

    const expand = document.createElement('div');
    expand.className = "head-hide embed_head_hide";
    expand.style.marginRight = '2rem';
    expand.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="$font_color" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon icon-tabler icons-tabler-outline icon-tabler-arrows-diagonal-2">
            <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
            <path d="M16 20l4 0l0 -4" />
            <path d="M14 14l6 6" />
            <path d="M8 4l-4 0l0 4" />
            <path d="M4 4l6 6" />
        </svg>
    `;
    expand.onclick = expandNav;

    sideBar.append(headHide, expand, sidebarField, embedChatField);
    document.body.append(btn, sideBar);
    const strBotToken = "$bot_token";

    function expandNav() {
        blnExpandNav = !blnExpandNav;
        const embed = document.getElementById('chat_embed');
        
        if (embed) {
            expand.innerHTML = blnExpandNav ? `
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="$font_color" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon icon-tabler icons-tabler-outline icon-tabler-arrows-diagonal-minimize-2">
                    <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                    <path d="M18 10h-4v-4" />
                    <path d="M20 4l-6 6" />
                    <path d="M6 14h4v4" />
                    <path d="M10 14l-6 6" />
                </svg>
            ` : `
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="$font_color" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon icon-tabler icons-tabler-outline icon-tabler-arrows-diagonal-2">
                    <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                    <path d="M16 20l4 0l0 -4" />
                    <path d="M14 14l6 6" />
                    <path d="M8 4l-4 0l0 4" />
                    <path d="M4 4l6 6" />
                </svg>
            `;
            embed.style.transition = 'all 0.1s';
            embed.style.minWidth = blnExpandNav ? '600px' : '375px';
        } else {
            setTimeout(expandNav, 100);
        }
    }

    function openNav() {
        if (!document.getElementById("embed_load_div")) {
            const embedLoadDiv = document.createElement("div");
            embedLoadDiv.id = 'embed_load_div';
            sideBar.appendChild(embedLoadDiv);
            embedLoadDiv.innerHTML = 
                `<iframe id="chat_embed" class="chat_embed chat_embed_small" src="$str_url/?strBotToken=${strBotToken}"></iframe>`;
        }
        document.getElementById("embed_Sidebar").style.height = document.getElementById('sidebar_height').value;
        document.getElementById("embed_Sidebar").style.display = 'inline-block';
        document.getElementById("embed_Sidebar").classList.add("slide-in-bottom");

        btn.classList.add("pop-in");
        setTimeout(() => btn.classList.remove("pop-in"), 300);

        btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="$bot_color" class="icon icon-tabler icons-tabler-filled icon-tabler-caret-up">
                <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                <path d="M11.293 7.293a1 1 0 0 1 1.32 -.083l.094 .083l6 6l.083 .094l.054 .077l.054 .096l.017 .036l.027 .067l.032 .108l.01 .053l.01 .06l.004 .057l.002 .059l-.002 .059l-.005 .058l-.009 .06l-.01 .052l-.032 .108l-.027 .067l-.07 .132l-.065 .09l-.073 .081l-.094 .083l-.077 .054l-.096 .054l-.036 .017l-.067 .027l-.108 .032l-.053 .01l-.06 .01l-.057 .004l-.059 .002h-12c-.852 0 -1.297 -.986 -.783 -1.623l.076 -.084l6 -6z" />
            </svg>
        `;
        // Hide toaster when opening sidebar
        toaster.classList.add("hidden");
    }

    function closeNav() {
        const sidebar = document.getElementById("embed_Sidebar");
        sidebar.classList.remove("slide-in-bottom");
        sidebar.classList.add("slide-out-top");

        btn.classList.add("pop-out");
        setTimeout(() => {
            sidebar.style.display = "none";
            btn.classList.add("open_sidebar");
            document.getElementById("chat-sticky-btn").style.display = "inline-block";
            document.getElementById("embed_load_div").remove();
            sidebar.classList.remove("slide-out-top");
            btn.classList.remove("pop-out");

            btn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="30" height="30" viewBox="0 0 177 150">
                    <image xlink:href="$float_image" x="0" y="0" width="177" height="150"/>
                </svg>
            `;
            // Show toaster again when closing sidebar
            // setTimeout(() => toaster.classList.remove("hidden"), 5000);
        }, 300);
    }
})();""".replace(
                    "$primary_color", rst_bot.get("vchr_primary_color") or "#1E88E5"
                )
                .replace("$primary_font_color", rst_bot.get("vchr_primary_font_color") or "white")
                .replace(
                    "$font_color",
                    "white" if rst_bot["vchr_theme"] == "DARK" else "black",
                )
                .replace("$bot_color", rst_bot.get("vchr_bot_color") or "#F3E5F5")
                .replace("$float_image", rst_bot.get("vchr_float_icon") or "data:image/png;base64,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")
                .replace("$bot_token", f"{str_tenancy_id}/{str_bot_id}")
                .replace("$str_url", str_url)
            )

            byte_stream = BytesIO()
            byte_stream.write(str_js.encode("utf-8"))
            byte_stream.seek(0)

            return Response(
                byte_stream,
                mimetype="application/javascript",
                headers={"Content-Disposition": "attachment; filename=index.js"},
            )

        except Exception:
            traceback.print_exc()
            return "not found", 404

    @staticmethod
    def set_bot_style(request, ins_db, user_id):
        try:
            dct_request = request.json
            int_bot_id = dct_request["intPk"]

            # check edit permission
            if not botService.check_bot_permission(ins_db, int_bot_id, user_id):
                return dct_error("No Permission"), 400

            str_theme = dct_request["strTheme"]
            str_primary_color = dct_request.get("strPrimaryColor")
            str_primary_font_color = dct_request.get("strPrimaryFontColor")
            str_bot_color = dct_request.get("strBotColor")
            str_bot_font_color = dct_request.get("strBotFontColor")
            str_float_icon = dct_request.get('strfloatingIcon')

            with create_cursor(ins_db) as cr:
                cr.execute(
                    """UPDATE tbl_bots
                        SET 
                            vchr_theme = %s,
                            vchr_primary_color = %s,
                            vchr_primary_font_color = %s,
                            vchr_bot_color = %s,
                            vchr_bot_font_color = %s,
                            vchr_float_icon = %s
                            
                        WHERE pk_bint_bot_id =%s""",
                    (
                        str_theme,
                        str_primary_color,
                        str_primary_font_color,
                        str_bot_color,
                        str_bot_font_color,
                        str_float_icon,
                        int_bot_id,
                    ),
                )
                ins_db.commit()
                return dct_response("success", "chatbot updated successfully"), 200

        except Exception:
            traceback.print_exc()
            return dct_error("Unable to set"), 400
        finally:
            if ins_db:
                ins_db.close()

    @staticmethod
    def create_bot_resources(str_unique_uuid, str_tenancy_id):
        try:

            """
            This function creates the lancedb resources for a chatbot:
            """
            # create an directory to keep training source
            os.makedirs(
                f"lancedb/{str_tenancy_id}/{str_unique_uuid}/data", exist_ok=True
            )

            # connect and create lancedb table
            db_lance = lancedb.connect(
                f"lancedb/{str_tenancy_id}/{str_unique_uuid}/lancedb"
            )
            db_lance.create_table("embedding", schema=EmbedModel, mode="overwrite")
            db_lance.create_table("memory", schema=MemoryModel, mode="overwrite")
            db_lance.create_table("live_chat", schema=LiveChatModel, mode="overwrite")

        except Exception as ex:
            traceback.print_exc()
            raise str(ex)

    @staticmethod
    def delete_bot_resources(str_unique_uuid, str_tenancy_id):
        try:

            """
            This function delete the lancedb resources of a chatbot:
            """
            # delete an directory
            str_bot_source_path = f"lancedb/{str_tenancy_id}/{str_unique_uuid}/"
            if os.path.exists(str_bot_source_path):
                shutil.rmtree(str_bot_source_path)

            with create_azure_connection("nubot") as blob_service_client:
                container_client = blob_service_client.get_container_client("nubot")
                str_blob_prefix = f"{str_tenancy_id}/{str_unique_uuid}"
                set_blobs_to_delete = set(
                    blob.name
                    for blob in container_client.list_blobs(
                        name_starts_with=str_blob_prefix
                    )
                )
                container_client.delete_blobs(
                    *set_blobs_to_delete
                )  # clear content from azure storage

        except Exception as ex:
            traceback.print_exc()
            raise str(ex)

    @staticmethod
    def check_bot_permission(ins_db, int_bot_id, user_id):
        try:
            with create_cursor(ins_db) as cr:
                cr.execute(
                    """SELECT 
                                CASE 
                                    WHEN b.fk_bint_created_user_id = %s OR ep.fk_bint_user_id IS NOT NULL THEN TRUE
                                    ELSE FALSE
                                END AS bln_edit
                            
                            FROM tbl_bots b
                            LEFT JOIN tbl_bot_view_permissions vp ON b.pk_bint_bot_id = vp.fk_bint_bot_id AND vp.fk_bint_user_id = %s
                            LEFT JOIN tbl_bot_edit_permissions ep ON b.pk_bint_bot_id = ep.fk_bint_bot_id AND ep.fk_bint_user_id = %s
                            WHERE b.chr_document_status = 'N'
                            AND b.pk_bint_bot_id = %s
                            AND (b.fk_bint_created_user_id = %s OR vp.fk_bint_user_id IS NOT NULL)
                            """,
                    (user_id, user_id, user_id, int_bot_id, user_id),
                )

                rst_permission = cr.fetchone()
                bln_edit = rst_permission["bln_edit"] if rst_permission else False

                return bln_edit

        except Exception:
            raise

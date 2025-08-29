from dotenv import load_dotenv

load_dotenv()

import traceback
import json
import socketio
import uvicorn
import asyncpg
import asyncio
import gc

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from app.utils.token_handler import socket_verification
from app.service import chatServices
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.global_config import env_mode
from app.utils.conf_path import str_configpath


# configuration
ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)


# Add allowed origins
origins = [
    "https://nubot.corex.travel",
    "https://chat.corex.travel",
    "https://staging-nubot.traacs.co",
    "https://staging-nubot-chat.traacs.co",
    "https://localhost",
    "http://localhost:4000",
    "http://localhost:5000",
    "http://192.168.12.195:4000",
    "http://192.168.12.195:3000",
    "http://192.168.12.195:5000",
    "http://capacitor://localhost",
    "http://capacitor://localhost:4000",
    "http://capacitor://localhost:5000",
    "http://capacitor://51.159.121.4",
    "http://capacitor://51.159.121.4:4000",
    "http://capacitor://51.159.121.4:5000",
    "http://capacitor://51.159.121.255",
    "http://capacitor://51.159.121.255:4000",
    "http://capacitor://51.159.121.255:5000",
    "capacitor://localhost",
    "capacitor://localhost:4000",
    "capacitor://localhost:5000",
]

# Create a new Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=origins)

# Create the FastAPI app
app = FastAPI()

# set middleware configuration for the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# global variable to keep session count
dct_session_memory = {}
dct_active_count_task = {}


@sio.event
async def connect(str_session_id, environ):
    try:
        dct_session_details = await socket_verification(environ)
        if dct_session_details:
            str_bot_id = dct_session_details.get("str_bot_id", "")
            await sio.save_session(str_session_id, dct_session_details)

            if str_bot_id not in dct_session_memory:
                dct_session_memory[str_bot_id] = {}
            dct_session_memory[str_bot_id][str_session_id] = ""
        print(f"{str_session_id} : new socket connected")
    except Exception:
        traceback.print_exc()


@sio.event
async def disconnect(str_session_id):
    try:
        # Background task to delete the attachments that are not logged in this socket
        await delete_chat_attachment(str_session_id)

        if str_session_id in dct_active_count_task:
            dct_active_count_task[str_session_id].cancel()
            del dct_active_count_task[str_session_id]
        else:
            environ = await sio.get_session(str_session_id)
            str_bot_id = environ.get("str_bot_id", "")
            if str_bot_id in dct_session_memory:
                del dct_session_memory[str_bot_id][str_session_id]

        print(f"{str_session_id} : socket disconnected")

    except Exception as ex:
        print(str(ex))
    finally:
        gc.collect()


async def delete_chat_attachment(str_session_id):
    """
    Deletes the chat attachment entry with the given session_id that are not mapped.
    """
    ins_db = None
    try:
        dependencies = await sio.get_session(str_session_id)  # get session details
        dct_tenant_data = dependencies.get("dct_db_info")
        ins_db = await asyncpg.connect(
            user=dct_tenant_data["db_user"],
            password=dct_tenant_data["db_password"],
            database=dct_tenant_data["db_name"],
            host=dct_tenant_data["db_host"],
            port=dct_tenant_data["db_port"],
        )
        str_bot_id = dependencies.get("str_bot_id")
        str_tenancy_id = dependencies.get("str_tenancy_id")

        # Delete non-mapped attachment(s) and return the lancedb uuid if any exist
        deleted_row = await ins_db.fetchrow(
            """
            DELETE FROM tbl_chat_attachment a
            USING (
                SELECT a.pk_bint_attachment_id, a.vchr_lancedb_uuid
                FROM tbl_chat_attachment a
                LEFT JOIN tbl_chat_attachment_bot_log_mapping m 
                ON m.fk_bint_attachment_id = a.pk_bint_attachment_id
                WHERE a.vchr_socket_id = $1 
                AND m.fk_bint_attachment_id IS NULL
            ) sub
            WHERE a.pk_bint_attachment_id = sub.pk_bint_attachment_id
            RETURNING a.vchr_lancedb_uuid
            """,
            str_session_id,
        )

        if deleted_row:
            lancedb_uuid = deleted_row["vchr_lancedb_uuid"]
            # Delete from lancedb
            chatServices.delete_unmapped_attachment_from_lancedb(
                str_tenancy_id, str_bot_id, lancedb_uuid
            )

    except Exception as ex:
        print(f"Error deleting entry: {ex}")

    finally:
        if ins_db:
            await ins_db.close()


@sio.event
async def message(str_session_id, message_obj):
    try:
        ins_db = None
        # When a message is received through the socket, determine whether it is a dictionary.
        # If it is, extract the message content from the 'strMessage' key.
        # This approach also allows the base context (e.g., GENERAL/KNOWLEDGE) to be passed along with the message.
        bln_with_base = bool(isinstance(message_obj, dict))
        if bln_with_base:
            message = message_obj["strMessage"]
        else:
            message = message_obj
        if len(message) > 10000:
            await sio.emit("typing", room=str_session_id)
            await sio.emit(
                "message_error",
                "Your message is too long. Please reduce it and try again.",
                room=str_session_id,
            )
        else:
            dependencies = await sio.get_session(str_session_id)  # get session details
            dct_tenant_data = dependencies.get("dct_db_info")
            ins_db = await asyncpg.connect(
                user=dct_tenant_data["db_user"],
                password=dct_tenant_data["db_password"],
                database=dct_tenant_data["db_name"],
                host=dct_tenant_data["db_host"],
                port=dct_tenant_data["db_port"],
            )
            str_bot_id = dependencies.get("str_bot_id")
            str_tenancy_id = dependencies.get("str_tenancy_id")
            int_conversation_id = dependencies.get("int_conversation_id")
            user_id = await chatServices.get_user_id(ins_db, dependencies)

            # if call from an embed bot it doesnt have userid ,so we take created user id of that bot
            dct_embedd_data = dependencies.get("dct_embedd_data")
            if not dependencies.get("user_id"):
                rst_user = await ins_db.fetchrow(
                    "SELECT fk_bint_created_user_id FROM tbl_bots WHERE vchr_azure_resource_uuid = $1",
                    dependencies.get("str_bot_id"),
                )
                user_id = int(rst_user["fk_bint_created_user_id"])
            else:
                user_id = int(dependencies.get("user_id") or 0)

            await sio.emit("typing", room=str_session_id)

            # Convert "null" to None for int_conversation_id
            int_conversation_id = (
                0
                if (int_conversation_id == "null" or int_conversation_id == "")
                else int_conversation_id
            )
            int_conversation_id = int(int_conversation_id)

            # set memory session
            memory_session = ""

            # Determine the memory context user ID
            user_id_for_memory = user_id

            rst_bot = await ins_db.fetchrow(
                """
                                        SELECT pk_bint_bot_id, vchr_engine_instruction, vchr_bot_type
                                        FROM tbl_bots
                                        WHERE vchr_azure_resource_uuid = $1
                                        """,
                str_bot_id,
            )
            if not rst_bot:
                await sio.emit(
                    "message_error", "Bot information not found.", room=str_session_id
                )
                return

            int_bot_id = rst_bot["pk_bint_bot_id"]
            str_instruction = rst_bot["vchr_engine_instruction"]
            str_bot_type = (
                message_obj["strBotType"] if bln_with_base else rst_bot["vchr_bot_type"]
            )
            bln_live_chat = False  # Default flag

            if int_conversation_id:
                rst_admin = await ins_db.fetchrow(
                    "select 1 FROM tbl_user WHERE pk_bint_user_id = $1 AND fk_bint_user_group_id in (1,3)",
                    user_id,
                )

                if rst_admin:
                    conversation_user_id = await ins_db.fetchrow(
                        "SELECT fk_bint_user_id FROM tbl_chat_history WHERE pk_bint_conversation_id = $1 AND chr_document_status = 'N'",
                        int_conversation_id,
                    )
                    if conversation_user_id:
                        user_id_for_memory = conversation_user_id["fk_bint_user_id"]

                old_socket = await ins_db.fetchrow(
                    """SELECT vchr_socket_id
                            FROM tbl_chat_history
                            WHERE pk_bint_conversation_id = $1
                            AND chr_document_status = 'N'
                            AND fk_bint_bot_id = $2""",
                    int_conversation_id,
                    int_bot_id,
                )

                if old_socket:
                    memory_session = old_socket["vchr_socket_id"]

            # Check if any attachment exists for the given session ID
            session_id_to_use = memory_session if memory_session else str_session_id
            lst_attachments = await ins_db.fetch(
                """SELECT pk_bint_attachment_id 
                FROM tbl_chat_attachment 
                WHERE vchr_socket_id = $1 
                """,
                session_id_to_use,
            )

            # Check if there are any attachments
            if lst_attachments:
                bln_live_chat = True

            # Fetch lancedb_uuid in the order of upload (sorted by pk_bint)
            rows = await ins_db.fetch(
                """
                SELECT vchr_lancedb_uuid
                FROM tbl_chat_attachment
                WHERE vchr_socket_id = $1
                ORDER BY pk_bint_attachment_id DESC
                """,
                session_id_to_use,
            )

            # list of lancedb_uuid in order
            lancedb_uuid_order = [row["vchr_lancedb_uuid"] for row in rows]

            # Fetch embedding,summized memory context and live chat context
            embedding_context, memory_context, live_chat_context, lst_ref_ids = await chatServices.fetch_embedding_and_memory_context_live_chat_context(
                    str_tenancy_id,
                    str_bot_id,
                    message,
                    user_id_for_memory,
                    bln_live_chat,
                    str_session_id,
                    lancedb_uuid_order,
                    memory_session)

            # generate the prompt
            prompt = await chatServices.generate_prompt(
                message,
                str_instruction,
                str_bot_type,
                embedding_context,
                memory_context,
                live_chat_context,
                user_id,
                int_bot_id,
                ins_db,
            )
            # generate a response
            response = await chatServices.generate_ai_response(
                [{"role": "user", "content": prompt}], stream=True
            )

            # Check if the response was successful,If successful, emit the AI-generated content to the 'message' event in the specified session room
            if not isinstance(response, dict):  # generator streaming
                await sio.emit("start", "streaming", room=str_session_id)
                prompt_tokens = 0
                completion_tokens = 0
                content = ""
                async for chunk in response:
                    if chunk.usage:
                        prompt_token = chunk.usage.prompt_tokens
                        completion_tokens = chunk.usage.completion_tokens
                    if chunk.choices:
                        text = chunk.choices[0].delta.content or ""
                        await sio.emit("message", text, room=str_session_id)
                        content += text

                await sio.emit("end", "completed", room=str_session_id)
                await sio.emit("reference", lst_ref_ids, room=str_session_id)
                # Check for existing conversation or create a new one
                chat_history = await ins_db.fetchrow(
                    """SELECT pk_bint_conversation_id FROM tbl_chat_history 
                                                        WHERE chr_document_status = 'N'
                                                        AND (pk_bint_conversation_id = $1 OR vchr_socket_id = $2)  
                                                    """,
                    int_conversation_id,
                    str_session_id,
                )
                if chat_history:
                    int_conversation_id = chat_history[0]

                elif not chat_history:
                    conversation_title = await chatServices.generate_conversation_title(
                        message
                    )

                    int_conversation_id = await ins_db.fetchval(
                        """
                        INSERT INTO tbl_chat_history (fk_bint_bot_id, fk_bint_user_id, vchr_conversation_title, vchr_socket_id, json_embedd, tim_created)
                        VALUES ($1, $2, $3, $4, $5, NOW()) RETURNING pk_bint_conversation_id
                    """,
                        int_bot_id,
                        user_id,
                        conversation_title,
                        str_session_id,
                        json.dumps(dct_embedd_data),
                    )
                    # set header environ
                    environ = await sio.get_session(str_session_id)
                    environ["int_conversation_id"] = int_conversation_id
                    await sio.save_session(str_session_id, environ)

                # insert the new message and response
                rst_log = await ins_db.fetchrow(
                    """
                            INSERT INTO tbl_bot_log
                                (tim_timestamp, vchr_sender,
                                    vchr_user_message, vchr_bot_response,
                                    fk_bint_bot_id, bint_input_token_usage,
                                    bint_output_token_usage, fk_bint_conversation_id,
                                    arr_reference_id
                                )
                            VALUES 
                                (
                                    NOW(),
                                    (SELECT 
                                        CASE WHEN EXISTS(SELECT vchr_user_name FROM tbl_user WHERE pk_bint_user_id = $1)
                                        THEN (SELECT vchr_user_name FROM tbl_user WHERE pk_bint_user_id = $2 LIMIT 1)
                                        ELSE $3
                                        END
                                    ),$4, $5, $6, $7, $8, $9, $10)
                            RETURNING pk_bint_chat_id,vchr_sender
                            """,
                    user_id_for_memory,
                    user_id_for_memory,
                    str_session_id,
                    message,
                    content,
                    int_bot_id,
                    prompt_token,
                    completion_tokens,
                    int_conversation_id,
                    json.dumps(lst_ref_ids),
                )
                # add into memory
                await run_in_threadpool(
                    chatServices.add_to_memory,
                    str_tenancy_id,
                    str_bot_id,
                    user_id_for_memory,
                    str_session_id,
                    message,
                    content,
                )

                int_log_id = rst_log["pk_bint_chat_id"]
                str_sender_user = rst_log["vchr_sender"]
                await sio.emit("chat_id", int_log_id, room=str_session_id)
                dct_session_memory[str_bot_id][str_session_id] = str_sender_user

                # Fetch an attachment ID in this socket id that has no existing entry in the bot log mapping table
                attachment_id = await ins_db.fetchval(
                    """
                        SELECT a.pk_bint_attachment_id 
                        FROM tbl_chat_attachment a
                        LEFT JOIN tbl_chat_attachment_bot_log_mapping m 
                        ON m.fk_bint_attachment_id = a.pk_bint_attachment_id
                        WHERE a.vchr_socket_id = $1 
                        AND m.fk_bint_attachment_id IS NULL
                        LIMIT 1
                        """,
                    str_session_id,
                )

                # If an attachment ID was found, insert a mapping record to link this attachment
                if attachment_id:
                    await ins_db.execute(
                        """
                            INSERT INTO tbl_chat_attachment_bot_log_mapping (fk_bint_attachment_id, fk_bint_chat_id)
                            VALUES ($1, $2)
                            """,
                        attachment_id,
                        int_log_id,
                    )

                if memory_session:
                    await ins_db.execute(
                        "UPDATE tbl_chat_history SET vchr_socket_id = $1 WHERE pk_bint_conversation_id = $2",
                        str_session_id,
                        int_conversation_id,
                    )
                    # Update chat attachment table with current socket id
                    await ins_db.execute(
                        "UPDATE tbl_chat_attachment SET vchr_socket_id = $1 WHERE vchr_socket_id = $2",
                        str_session_id,
                        memory_session,
                    )
                    # Update rows in memory_table and live_chat_table
                    await run_in_threadpool(
                        chatServices.update_memory_and_live_chat_socket,
                        str_tenancy_id,
                        str_bot_id,
                        memory_session,
                        bln_live_chat,
                        str_session_id,
                    )
            else:
                # If there was an error or policy violation, emit the error message to the 'policy_violation' event
                await sio.emit(
                    "policy_violation", response["message"], room=str_session_id
                )

    except Exception:
        traceback.print_exc()
        await sio.emit(
            "message_error",
            "Sorry, an error occurred. Please try again later.",
            room=str_session_id,
        )

    finally:
        if ins_db:
            await ins_db.close()

        # manually collect garbages
        gc.collect()


async def fetch_connections(lst_bots):
    """
    Fetches the counts for the given list of bots.
    """
    return {
        bot_id: [user for user in dct_session_memory.get(bot_id, {}).values() if user]
        or []
        for bot_id in lst_bots
    }


async def send_counts_periodically(lst_bots, session_id):
    """
    Sends bot counts to the client periodically.
    """
    previous_counts = None  # Cache to avoid sending redundant data
    try:
        while True:
            # Fetch current counts
            current_connections = await fetch_connections(lst_bots)

            # Emit only if there's a meaningful update
            if current_connections != previous_counts:
                await sio.emit("counts", current_connections, room=session_id)
                previous_counts = current_connections

            await asyncio.sleep(2)  # Adjust interval as needed
    except Exception as ex:
        print("Error in sending counts:", ex)


@sio.event
async def get_count(session_id, lst_bots):
    """
    Handles the 'get_count' event and starts a background task to send updates.
    """
    if session_id in dct_active_count_task:
        dct_active_count_task[session_id].cancel()
    # Start background task to send periodic counts
    task = asyncio.create_task(send_counts_periodically(lst_bots, session_id))
    dct_active_count_task[session_id] = task


# Create an ASGI app using FastAPI and Socket.IO
sio_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    uvicorn.run(sio_app, host="0.0.0.0", port=int(ins_cfg.get(env_mode, "chat-socket")))

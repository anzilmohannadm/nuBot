import openai
import traceback
import lancedb
import uuid
import json
import textwrap

from app.utils.secureconfig import ConfigParserCrypt
from app.utils.global_config import env_mode
from app.utils.conf_path import str_configpath
from app.schema import EmbedModel,MemoryModel,LiveChatModel
from datetime import timedelta
from app.utils.executor import executor
from app.utils.generalMethods import optimize_lancedb


# configuration
ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)

# setup pre-requestie before serve
str_azure_endpoint = ins_cfg.get(env_mode, 'AZURE_OPENAI_ENDPOINT')
str_azure_api_key = ins_cfg.get(env_mode, 'AZURE_OPENAI_API_KEY')
str_model_deployment = ins_cfg.get(env_mode, 'AZURE_OPENAI_DEPLOYMENT_ID')

client = openai.AsyncAzureOpenAI(
    azure_endpoint=str_azure_endpoint,
    api_key=str_azure_api_key,
    api_version="2024-08-01-preview",
)


class chatServices():
    KNOWLEDGE_BASE_PROMPT = """
    
    Role: {role}

    {instruction}
    If the user greets you or expresses emotions (e.g., "How are you?" or "I'm frustrated"), respond warmly and empathetically.

    As a {role}, follow this guidance:
    {specific_instruction}


    ### Priority Rules:

    1. If the user asks about an attachment (e.g., “What is in this?”, “Explain this file”), respond *only* using the **Attached File Context**.
    2. Otherwise, rely on the **Memory Context** and **Embedding Context** together to generate a helpful, relevant answer.
    3. Use external knowledge only if the provided contexts do not contain any helpful information — and do not mention that context was missing.


    ### Response Guidelines:
    - Use the Memory Context to stay in sync with the conversation. If the user follows up on an earlier message or continues a thought, rely on memory to understand and reply meaningfully.
    - Use Embedding Context to retrieve accurate reference knowledge.
    - If none of the contexts help answer the question, respond politely and naturally — but **do not mention the context** itself (e.g., avoid phrases like “based on the context”).
    - Do not guess, assume, or use information outside of these contexts.
    - Summarize or condense long context snippets clearly.

    ---

    User Question:
    {message}

    ---

    Attached File Context (highest priority if file is mentioned):
    {live_chat_context}

    Memory Context:
    {memory_context}

    Embedding Context:
    {embedding_context}

    ---

    Response:
    """

    GENERAL_QUERY_PROMPT = """

    Role: {role}

    {instruction}
    If the user greets you or expresses emotions (e.g., "How are you?" or "I'm frustrated"), respond warmly and empathetically.

    As a {role}, follow this guidance:
    {specific_instruction}

    You should use the **Memory Context** and **Embedding Context** as the primary sources of information when answering.  
    If the **Attached File Context** is available *and* the user’s question refers to a file, then it takes highest priority.

    ### Priority Rules:

    1. If the question is about a file or attachment (e.g., “What’s in this?”, “Explain this file”), respond using only the **Attached File Context**.
    2. Otherwise, use both the **Memory Context** and **Embedding Context** to formulate your response.
    3. Use external knowledge only if no context provides a suitable answer — and avoid stating that.

    
    ### Response Guidelines:

    - Use the Memory Context to stay in sync with the conversation. If the user follows up on an earlier message or continues a thought, rely on memory to understand and reply meaningfully.
    - Use Embedding Context to pull facts and references.
    - Use external knowledge only when the answer is clearly outside the scope of the provided contexts.
    - Avoid saying phrases like “based on the provided content” or “according to the given context.” Just respond naturally and directly.
    - Summarize long content clearly and concisely. Avoid repeating context unnecessarily.

    ---

    Attached File Context (highest priority if file is mentioned):
    {live_chat_context}

    Memory Context:
    {memory_context}

    Embedding Context:
    {embedding_context}

    ---

    User Question:
    {message}

    ---

    Response:
    """

    @staticmethod
    async def generate_ai_response(messages,stream = False):
        try:
            return  await client.chat.completions.create(
                model=str_model_deployment,
                messages=messages,
                temperature=0.3,
                stream=stream,
                stream_options={"include_usage":True} if stream else None)
            
        except openai.BadRequestError as e:
            print(e.message)
            return {"message": "There was an error with your request. Please check the input or try again later." }
        
        except Exception:
            traceback.print_exc()
            return {"message": "There was an error with your request. Please check the input or try again later." }

    @staticmethod
    async def generate_conversation_title(message):
        """
        Generate a conversation title based on the user's message using a language model.
        """
        prompt = f"Generate a concise and descriptive title for the following user message and dont give any double quotes:\n\n{message}\n\nTitle:"
        title= await chatServices.generate_ai_response(
            [{'role': 'user', 'content': prompt}])
        return title.choices[0].message.content

    @staticmethod
    async def summarize_memory_context(memory_context):
        if not memory_context:
            return ''
        prompt = textwrap.dedent(f"""
                You are an AI that summarizes long conversations into clear, structured memory for a chatbot assistant.

                 Your tasks:
                - Identify key facts, decisions, and goals.
                - Ignore greetings, chit-chat, or filler.
                - Return concise bullet points or short paragraphs only.

                Conversation:
                {memory_context}
            """)
        summarized_context= await chatServices.generate_ai_response(
            [{'role': 'user', 'content': prompt}])

        return summarized_context.choices[0].message.content
    
    @staticmethod
    async def get_user_id(ins_db,dependencies):
        """
        Retrieves the user ID from the provided dependencies.
        If called from an embed bot without a user ID, fetches the created user ID from the database.
        """
        if dependencies.get('user_id')=='':
                rst_user = await ins_db.fetchrow("SELECT fk_bint_created_user_id FROM tbl_bots WHERE vchr_azure_resource_uuid = $1", dependencies.get('str_bot_id'))
                user_id = int(rst_user["fk_bint_created_user_id"])
                return user_id
        else:
            user_id = int(dependencies.get('user_id') or 0)
            return user_id


    @staticmethod
    async def generate_prompt(
            message,
            instruction,
            bot_type,
            embedding_context,
            memory_context,
            live_chat_context,
            user_id,
            int_bot_id,
            ins_db):
        
        role_instructions = {
                "Generic User": "Provide helpful and clear answers based on the context without assuming technical expertise or specific domain knowledge.",
                "Developer": "Focus on providing technical solutions, code examples, and documentation guidance.",
                "QA": "Emphasize testing strategies, bug reporting, and quality assurance best practices.",
                "Business Analyst": "Provide insights on business requirements, process analysis, and translating business needs into solutions.",
                "Marketing Specialist": "Advise on creating marketing strategies, running campaigns, analyzing performance metrics, and leveraging digital marketing tools.",
                "Project Manager": "Offer project planning tips, task prioritization strategies, and insights on managing resources and timelines effectively. Highlight team collaboration techniques.",
                "Customer Support": "Guide on handling customer queries, managing complaints empathetically, and providing quick resolutions. Share techniques for delivering excellent customer service."
            }
        
        if ins_db:
            str_role = await ins_db.fetchval("""SELECT
                                                r.vchr_role 
                                            FROM 
                                                tbl_user_bot_role_mapping AS urp 
                                            LEFT JOIN
                                                tbl_roles r ON urp.fk_bint_role_id = r.pk_bint_role_id 
                                            WHERE 
                                                urp.fk_bint_user_id = $1
                                                AND urp.fk_bint_bot_id = $2
          
                                          """,user_id,int_bot_id)
            
        # If the call from Whatsapp the ins_db passes as None 
        if not ins_db or not str_role:
            str_role = "Generic User"  
             
        if bot_type == 'Knowledge Base':
            return chatServices.KNOWLEDGE_BASE_PROMPT.format(
                role=str_role,
                specific_instruction=role_instructions.get(str_role.strip()),
                instruction=instruction,
                message=message,
                embedding_context=embedding_context,
                memory_context=memory_context,
                live_chat_context=live_chat_context
            )
            
        else:
            return chatServices.GENERAL_QUERY_PROMPT.format(
                role=str_role,
                specific_instruction=role_instructions.get(str_role.strip()),
                instruction=instruction,
                message=message,
                embedding_context=embedding_context,
                memory_context=memory_context,
                live_chat_context=live_chat_context
            )

    @staticmethod
    async def fetch_embedding_and_memory_context_live_chat_context(
            str_tenancy_id,
            str_bot_id,
            message,
            user_id_for_memory,
            bln_live_chat,
            str_session_id,
            lancedb_uuid_order,
            memory_session='',
            ):
        # Fetch embedding memory and live chat context
        try:
            db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_bot_id}/lancedb", read_consistency_interval=timedelta(seconds=0))


            try:
                embedding_table = db_lance.open_table("embedding")
            except ValueError:
                embedding_table = db_lance.create_table("embedding", schema = EmbedModel, exist_ok = True)

            try:
                memory_table = db_lance.open_table("memory")
            except ValueError:
                memory_table = db_lance.create_table("memory", schema = MemoryModel, exist_ok = True)

            try:
                live_chat_table = db_lance.open_table("live_chat")
            except ValueError:
                live_chat_table = db_lance.create_table("live_chat", schema = LiveChatModel, exist_ok = True)


            summarized_memory_context = ''
            if memory_session:
                memory_context = ',\n'.join([i['text'] for i in memory_table.search().where(
                    f"user_id = '{user_id_for_memory}' AND sid = '{memory_session}'").limit(40).to_list()])
                
                # Await async summarize function
                summarized_memory_context = await chatServices.summarize_memory_context(memory_context)
                message = f"Memory context:\n{summarized_memory_context}\n\nUser's message:\n{message}"


            lst_context = embedding_table.search(message,query_type="vector").limit(20).to_list()
            
            embedding_context = ',\n'.join(
                [context['text'] for context in lst_context])
            
            live_chat_context = ''
            
            # guideline for attachment context
            guideline = (
                "Guideline: In case of multiple files, "
                "consider and answer only from the first file in this context.Also don't say 'Based on the live chat guideline, I will consider only the first file in the context' in the answer just directly answer from it \n\n"
            )
            if bln_live_chat: 
                    # Fetch and sort results
                    sorted_results = chatServices.search_and_sort_lancedb(memory_session,str_session_id, message,live_chat_table,lancedb_uuid_order)
                    live_chat_context = ',\n'.join([f"{i['file_name']}: {i['text']}" for i in sorted_results])
                    live_chat_context = guideline + live_chat_context
               
            #Reference ids
            lst_ref_ids = [i['id'] for i in lst_context]

            return embedding_context, summarized_memory_context ,live_chat_context, lst_ref_ids
        except Exception as e:
            print(f"Error fetching context: {e}")
            return '', '', []
        

    def search_and_sort_lancedb(memory_session,str_session_id, message,live_chat_table,lancedb_uuid_order):
    
        session_ids = (memory_session, str_session_id)

        # fetch data of live_chat_table in either of the socket ids
        results = live_chat_table.search(message).select(["sid","text","id","file_name"]).where( f"sid IN {session_ids}").to_list()

       
        # Create a dictionary to map lancedb_uuid to its position in the order
        order_map = {uuid: idx for idx, uuid in enumerate(lancedb_uuid_order)}

        # Sort results using the order_map
        sorted_results = sorted(results, key=lambda x: order_map.get(x["id"], -1))

        return sorted_results


    @staticmethod
    def add_to_memory(
            str_tenancy_id,
            str_bot_id,
            user_id_for_memory,
            str_session_id,
            message,
            response):
        # Fetch embedding and memory context
        try:
            db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0))
            
            try:
                memory_table = db_lance.open_table("memory")
            except ValueError:
                memory_table = db_lance.create_table("memory", schema = MemoryModel, exist_ok = True)
                
            memory_table.add([{"id": str(uuid.uuid4()),
                               "user_id": str(user_id_for_memory),
                               "sid": str_session_id,
                               "text": json.dumps({'role': 'user',
                                                   'content': message})},
                              {"id": str(uuid.uuid4()),
                               "user_id": str(user_id_for_memory),
                               "sid": str_session_id,
                               "text": json.dumps({'role': 'assistant',
                                                   'content': response})}])
            return
        except Exception as e:
            print(f"Error fetching context: {e}")

    @staticmethod
    def update_memory_and_live_chat_socket(
            str_tenancy_id,
            str_bot_id,
            memory_session,
            bln_live_chat,
            str_session_id):
        # Fetch embedding , memory and live_chat context
        try:
            db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0))

            try:
                memory_table = db_lance.open_table("memory")
            except ValueError:
                memory_table = db_lance.create_table("memory", schema = MemoryModel, exist_ok = True)
                
            memory_table.update(where=f"sid = '{memory_session}'", values={"sid": str_session_id})
            # If bln_live_chat is True, also update live_chat table
            if bln_live_chat:
                # connect to lancedb table
                try:
                    live_chat_table = db_lance.open_table("live_chat")
                except ValueError:
                    live_chat_table = db_lance.create_table("live_chat", schema = LiveChatModel, exist_ok = True)
        
                live_chat_table.update(
                    where=f"sid = '{memory_session}'",
                    values={"sid": str_session_id}
                )
            return
        except Exception as e:
            print(f"Error fetching context: {e}")
            
    @staticmethod
    async def user_access_bots(ins_db,user_id):
        rst_bots= await ins_db.fetch("""SELECT DISTINCT b.vchr_azure_resource_uuid, b.vchr_bot_name
                                    FROM public.tbl_bots b
                                    WHERE b.fk_bint_created_user_id = $1

                                    UNION 

                                    SELECT DISTINCT b.vchr_azure_resource_uuid, b.vchr_bot_name
                                    FROM public.tbl_bots b
                                    JOIN public.tbl_bot_edit_permissions e
                                    ON b.pk_bint_bot_id = e.fk_bint_bot_id
                                    WHERE e.fk_bint_user_id = $2
                                    UNION 

                                    SELECT DISTINCT b.vchr_azure_resource_uuid, b.vchr_bot_name
                                    FROM public.tbl_bots b
                                    JOIN public.tbl_bot_view_permissions v
                                    ON b.pk_bint_bot_id = v.fk_bint_bot_id
                                    WHERE v.fk_bint_user_id = $3 """,user_id,user_id,user_id)
        return [record['vchr_azure_resource_uuid'] for record in rst_bots]

    @staticmethod
    def delete_unmapped_attachment_from_lancedb(
            str_tenancy_id,
            str_bot_id,
            lancedb_uuid,
            ):
        #Connecting to lancedb
        db_lance = lancedb.connect(f"lancedb/{str_tenancy_id}/{str_bot_id}/lancedb",read_consistency_interval=timedelta(seconds=0)) 

        # connect to lancedb table
        try:
            live_chat_table = db_lance.open_table("live_chat")
        except ValueError:
            live_chat_table = db_lance.create_table("live_chat", schema = LiveChatModel, exist_ok = True)
        
        
        #Deleting source from lancedb memory table using file name  
        live_chat_table.delete( where=f"id = '{lancedb_uuid}'",)
    
        # optimize
        executor.submit(optimize_lancedb,str_tenancy_id,str_bot_id,"live_chat")

           

            

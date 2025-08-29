import os
import asyncio
from datetime import datetime
from typing import Annotated, List, Type, Optional
from typing_extensions import TypedDict
from langchain_openai import AzureChatOpenAI
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import tools_condition

from app.agents.utils.checkpointer import AsyncRedisSaver
from app.agents.utils.general_methods import create_tool_node_with_fallback, send_waiting_message
from app.utils.secureconfig import ConfigParserCrypt
from app.utils.global_config import env_mode
from app.utils.conf_path import str_configpath

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

class AgentBlueprint:
    def __init__(
        self,
        tools: List[Type[BaseTool]],
        prompt_template: Optional[str] = None,
        default_timeout: int = 10
    ):
        self.tools = tools
        self.default_timeout = default_timeout
        # Default prompt template
        self.prompt_template = prompt_template
        
        # Default LLM configuration
        self.llm_config = {
            "azure_deployment": "gpt-4o",
            "api_version": "2024-08-01-preview",
            "temperature": 1
        }
        
        # Initialize configuration
        self._load_configuration()
        
    def _load_configuration(self):
        """Load configuration from secure config files"""
        self.ins_configuration = ConfigParserCrypt()
        self.ins_configuration.read(str_configpath)
        
        os.environ["AZURE_OPENAI_API_KEY"] = self.ins_configuration.get(
            env_mode, "AZURE_OPENAI_API_KEY"
        )
        os.environ["AZURE_OPENAI_ENDPOINT"] = self.ins_configuration.get(
            env_mode, "AZURE_OPENAI_ENDPOINT"
        )
    
    def _create_llm(self) -> AzureChatOpenAI:
        """Create the Azure OpenAI LLM instance"""
        return AzureChatOpenAI(**self.llm_config)
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """Create the chat prompt template"""
        return ChatPromptTemplate.from_messages([
            ("system", self.prompt_template),
            ("placeholder", "{messages}"),
        ]).partial(time=datetime.now)
    
    def _create_runnable(self) -> Runnable:
        """Create the runnable chain"""
        return self._create_prompt() | self._create_llm().bind_tools(self.tools)
    
    def build_graph(self) -> StateGraph:
        """Build the state graph for the agent"""
        builder = StateGraph(State)
        
        # Define nodes
        builder.add_node("assistant", self.Assistant(self._create_runnable()))
        builder.add_node("tools", create_tool_node_with_fallback(self.tools))
        
        # Define edges
        builder.add_edge(START, "assistant")
        builder.add_conditional_edges(
            "assistant",
            tools_condition,
        )
        builder.add_edge("tools", "assistant")
        
        return builder
    
    async def run_agent(
        self,
        message: str,
        config: dict,
        body: Optional[dict] = None,
        access_token: Optional[str] = None
    ) -> str:
        """Run the agent with the given message and configuration"""
        async with AsyncRedisSaver.from_conn_info(
            host=self.ins_configuration.get(env_mode, "REDIS_HOST"),
            port=self.ins_configuration.get(env_mode, "REDIS_PORT"),
            db=0,
        ) as memory:
            agent = self.build_graph().compile(checkpointer=memory)
            
            task = asyncio.create_task(
                agent.ainvoke({"messages": ("user", message)}, config)
            )
            
            timeout = self.default_timeout
            start_time = asyncio.get_event_loop().time()
            
            while not task.done():
                elapsed_time = asyncio.get_event_loop().time() - start_time
                if elapsed_time > timeout:
                    reply_message = "Just a moment while I process your request..."
                    if body and access_token:
                        await send_waiting_message(body, reply_message, access_token)
                    break
                await asyncio.sleep(0.1)
            
            try:
                response = await task
                return response["messages"][-1].content
            except asyncio.CancelledError:
                return "Apologies, but it seems that the requested data is currently unavailable."
    
    class Assistant:
        """Inner class to handle assistant operations"""
        def __init__(self, runnable: Runnable):
            self.runnable = runnable
        
        async def __call__(self, state: State, config: RunnableConfig):
            while True:
                # state["messages"][-1].pretty_print()
                result = await self.runnable.ainvoke(state)
                # If the LLM happens to return an empty response, we will re-prompt it
                # for an actual response.
                if not result.tool_calls and (
                    not result.content
                    or isinstance(result.content, list)
                    and not result.content[0].get("text")
                ):
                    messages = state["messages"] + [("user", "Respond with a real output.")]
                    state = {**state, "messages": messages}
                else:
                    break
            return {"messages": result}
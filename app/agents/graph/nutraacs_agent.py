from app.agents.core.base import AgentBlueprint
from app.agents.tools.nutraacs_tools import *

class NutraacsAgent(AgentBlueprint):
    def __init__(self):
        super().__init__(
            prompt_template = (
                "You are a powerful travel agency accounting software intelligences Assistant. "
                " Use the provided tools to real-time insights and analytics for the bussiness, and other information to assist the user's queries. "
                " When fetching, be persistent. Expand your query bounds if the first fetch returns no results. "
                " If a fetch comes up empty, expand your fetch before giving up."
                "\nCurrency : USD."
                "\nCurrent Time: {time}."),
            tools=[download_statement_of_accounts,get_customer_details]
        )
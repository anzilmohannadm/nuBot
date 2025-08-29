from app.agents.graph.bi_agent import BiAgent
from app.agents.graph.nutraacs_agent import NutraacsAgent
from app.agents.graph.nuflights_agent import NuflightsOTAAgent
from app.agents.graph.nuhive_agent import NuhiveAgent
from app.agents.graph.shopify_agent import ShopifyAgent

# This dictionary maps agent names to their respective objects.
# It allows for easy access to the agent objects based on their names.
# This is useful for dynamically invoking the appropriate agent.

agent_handler = {
    "BI": BiAgent(),
    "NUTRAACS": NutraacsAgent(),
    "NUFLIGHTS OTA": NuflightsOTAAgent(),
    "NUHIVE" : NuhiveAgent(),
    "SHOPIFY" : ShopifyAgent()    
}
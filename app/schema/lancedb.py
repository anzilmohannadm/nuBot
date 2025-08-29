from app.utils.secureconfig import ConfigParserCrypt

from app.utils.conf_path import str_configpath
from functools import cached_property
from typing import List, Union
import numpy as np
from lancedb.embeddings import TextEmbeddingFunction
from lancedb.embeddings.registry import register
from lancedb.util import attempt_import_or_raise
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import EmbeddingFunctionRegistry
from app.utils.global_config import env_mode

# configuration
ins_cfg = ConfigParserCrypt()
ins_cfg.read(str_configpath)

azure_api_key = ins_cfg.get(env_mode,'AZURE_OPENAI_API_KEY')
azure_endpoint = ins_cfg.get(env_mode,'AZURE_OPENAI_ENDPOINT')
azure_deployment = "text-embedding-3-large"
azure_api_version = "2023-05-15"

@register("azure_openai")
class AzureOpenAIEmbeddings(TextEmbeddingFunction):
    """
    An embedding function that uses the Azure OpenAI API
    """

    name: str = "text-embedding-3-large"
    azure_api_key: str
    azure_endpoint: str
    azure_deployment: str
    azure_api_version: str

    def ndims(self):
        return self._ndims

    @cached_property
    def _ndims(self):
        if self.name == "text-embedding-3-large":
            return 3072
        else:
            raise ValueError(f"Unknown model name {self.name}")

    def generate_embeddings(
        self, texts: Union[List[str], np.ndarray]
    ) -> List[np.array]:
        """
        Get the embeddings for the given texts

        Parameters
        ----------
        texts: list[str] or np.ndarray (of str)
            The texts to embed
        """
        # TODO retry, rate limit, token limit
        if self.name == "text-embedding-3-large":
            rs = self._openai_client.embeddings.create(input=texts, model=self.name)
        else:
            rs = self._openai_client.embeddings.create(
                input=texts, model=self.name, dimensions=self.ndims()
            )
        return [v.embedding for v in rs.data]

    @cached_property
    def _openai_client(self):
        openai = attempt_import_or_raise("openai")


        return openai.AzureOpenAI(
            azure_endpoint=self.azure_endpoint,
            api_key=self.azure_api_key,
            api_version=self.azure_api_version,
            azure_deployment=self.azure_deployment
        )



registry = EmbeddingFunctionRegistry.get_instance()
embedder = registry.get("azure_openai").create(name = "text-embedding-3-large",
                                               azure_api_key = azure_api_key,
                                               azure_endpoint = azure_endpoint,
                                               azure_deployment = azure_deployment,
                                               azure_api_version = azure_api_version
                                               )


class EmbedModel(LanceModel):
    id: str
    file_name: str
    text: str = embedder.SourceField()
    vector: Vector(embedder.ndims()) = embedder.VectorField()

class MemoryModel(LanceModel):
    id: str
    user_id: str
    sid:str
    text: str = embedder.SourceField()
    vector: Vector(embedder.ndims()) = embedder.VectorField()


class EmbeddedWhatsappAccounts(LanceModel):
    phone_number_id:str
    tenancy_id:str
    
class LiveChatModel(LanceModel):
    id: str
    file_name: str
    user_id: str
    sid:str
    text: str = embedder.SourceField()
    vector: Vector(embedder.ndims()) = embedder.VectorField()

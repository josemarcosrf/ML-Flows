import json

# from chromadb.utils.embedding_functions import EmbeddingFunction
from chromadb import Embeddings
from chromadb.api.types import EmbeddingFunction


class BedrockEmbeddingFunction(EmbeddingFunction):
    # Custom embedding function for ChromaDB that uses Bedrock
    def __init__(self, client, model_id: str):
        """Initialize the Bedrock embedding function.
        Uses the AWS Bedrock service to generate embeddings.
        It requires the client to be an AWS Bedrock client and the model_id to specify
        the model to use for embeddings.
        The model_id should be the full ARN of the Bedrock model, e.g.:
        arn:aws:bedrock:us-west-2::model/amazon.titan-embed-text-v1

        Args:
            client (boto3.client): The AWS Bedrock client.
            model_id (str): The model ID to use for embeddings.
        """
        self.client = client
        self.model_id = model_id

    def name(self) -> str:
        return self.model_name

    @property
    def model_name(self) -> str:
        return self.model_id

    def __call__(self, texts: list[str]) -> Embeddings:
        """Generate embeddings for a list of texts using the Bedrock model.
        Args:
            texts (list[str]): List of texts to generate embeddings for.
        Returns:
            Embeddings: List of embeddings, where each embedding is a list of floats.
        """
        embeddings = []
        for text in texts:
            response = self.client.invoke_model(
                modelId=self.model_id, body=json.dumps({"inputText": text})
            )
            embedding = json.loads(response["body"].read())["embedding"]
            embeddings.append(embedding)
        return embeddings

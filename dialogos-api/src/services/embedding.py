import os
from typing import List, Optional
from openai import OpenAI
from src.utils import logger

def get_embeddings(texts: List[str]) -> Optional[List[List[float]]]:
    """
    Generate embeddings for a list of texts using OpenAI's embedding API.
    
    Args:
        texts (List[str]): List of text strings to embed.
    
    Returns:
        Optional[List[List[float]]]: List of embedding vectors, or None if an error occurs.
    """
    if not texts:
        logger.warning("Empty text list provided for embedding")
        return []

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable is not set")
            raise ValueError("Missing OPENAI_API_KEY")

        client = OpenAI(api_key=api_key)
        model = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        logger.info(f"Generating embeddings for {len(texts)} texts using model: {model}")

        # Batch texts to handle API limits (max 8192 tokens per request)
        batch_size = 100
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            # Filter out empty or invalid texts
            batch_texts = [text for text in batch_texts if text and isinstance(text, str)]
            if not batch_texts:
                logger.warning(f"Skipping empty batch at index {i}")
                continue
            response = client.embeddings.create(
                model=model,
                input=batch_texts
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
            logger.debug(f"Processed batch {i//batch_size + 1}: {len(batch_texts)} texts")

        logger.info(f"Successfully generated {len(embeddings)} embeddings")
        return embeddings

    except Exception as e:
        logger.error(f"Error getting embeddings: {str(e)}")
        return None
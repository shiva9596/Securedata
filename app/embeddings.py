# app/embeddings.py
import os
import faiss
import numpy as np
import openai
import pickle
import json
from typing import List, Tuple, Dict, Any
from utils.logger import log_event
from app.config import OPENAI_API_KEY, EMBEDDING_MODEL, VECTOR_STORE_FOLDER

# Initialize OpenAI API
openai.api_key = OPENAI_API_KEY

def get_openai_embedding(text: str) -> List[float]:
    """
    Get embedding for a text string using OpenAI's embedding API
    
    Args:
        text: Text to embed
        
    Returns:
        List of embedding values
    """
    try:
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        
        # Extract the embedding
        embedding = response.data[0].embedding
        
        return embedding
    
    except Exception as e:
        log_event(f"Error generating OpenAI embedding: {e}", "error")
        raise Exception(f"Error generating embedding: {str(e)}")

def get_batch_embeddings(texts: List[str], batch_size: int = 20) -> np.ndarray:
    """
    Get embeddings for a list of texts in batches
    
    Args:
        texts: List of texts to embed
        batch_size: Number of texts to process in each API call
        
    Returns:
        Numpy array of embeddings
    """
    try:
        embeddings = []
        
        # Process in batches to avoid exceeding API limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            log_event(f"Processing batch {i//batch_size + 1} of {len(texts)//batch_size + 1}", "info")
            
            for text in batch:
                embedding = get_openai_embedding(text)
                embeddings.append(embedding)
        
        return np.array(embeddings, dtype=np.float32)
    
    except Exception as e:
        log_event(f"Error generating batch embeddings: {e}", "error")
        raise Exception(f"Error generating batch embeddings: {str(e)}")

def build_faiss_index(chunks: List[str], file_id: str = None) -> Tuple[Any, np.ndarray]:
    """
    Build a FAISS index from text chunks
    
    Args:
        chunks: List of text chunks to embed
        file_id: Optional identifier for the document (used for persistent storage)
        
    Returns:
        index: FAISS index
        embeddings: Numpy array of embeddings
    """
    try:
        log_event(f"Building FAISS index for {len(chunks)} chunks", "info")
        
        # Generate embeddings for chunks
        embeddings = get_batch_embeddings(chunks)
        
        # Build FAISS index
        dimension = embeddings.shape[1]  # Get embedding dimension
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)
        
        # Save index and chunks if file_id is provided
        if file_id:
            save_path = os.path.join(VECTOR_STORE_FOLDER, file_id)
            os.makedirs(save_path, exist_ok=True)
            
            # Save index
            faiss.write_index(index, os.path.join(save_path, "index.faiss"))
            
            # Save chunks
            with open(os.path.join(save_path, "chunks.json"), "w") as f:
                json.dump(chunks, f)
            
            log_event(f"Index and chunks saved to {save_path}", "info")
        
        return index, embeddings
    
    except Exception as e:
        log_event(f"Error building FAISS index: {e}", "error")
        raise Exception(f"Error building FAISS index: {str(e)}")

def load_faiss_index(file_id: str) -> Tuple[Any, List[str]]:
    """
    Load a previously saved FAISS index and chunks
    
    Args:
        file_id: Identifier for the document
        
    Returns:
        index: FAISS index
        chunks: Original text chunks
    """
    try:
        save_path = os.path.join(VECTOR_STORE_FOLDER, file_id)
        
        # Check if index exists
        if not os.path.exists(os.path.join(save_path, "index.faiss")):
            raise FileNotFoundError(f"Index not found for document {file_id}")
        
        # Load index
        index = faiss.read_index(os.path.join(save_path, "index.faiss"))
        
        # Load chunks
        with open(os.path.join(save_path, "chunks.json"), "r") as f:
            chunks = json.load(f)
        
        log_event(f"Index and chunks loaded from {save_path}", "info")
        return index, chunks
    
    except Exception as e:
        log_event(f"Error loading FAISS index: {e}", "error")
        raise Exception(f"Error loading FAISS index: {str(e)}")

def search_similar_chunks(query: str, index: Any, chunks: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
    """
    Search for chunks similar to the query
    
    Args:
        query: Query text
        index: FAISS index
        chunks: Original text chunks
        top_k: Number of results to return
        
    Returns:
        List of (chunk, score) tuples
    """
    try:
        # Get embedding for query
        query_embedding = get_openai_embedding(query)
        query_embedding_array = np.array([query_embedding], dtype=np.float32)
        
        # Search index
        distances, indices = index.search(query_embedding_array, top_k)
        
        # Get results
        results = []
        for i in range(len(indices[0])):
            chunk_idx = indices[0][i]
            if chunk_idx < len(chunks):  # Safety check
                results.append((chunks[chunk_idx], float(distances[0][i])))
        
        log_event(f"Found {len(results)} similar chunks for query", "info")
        return results
    
    except Exception as e:
        log_event(f"Error searching similar chunks: {e}", "error")
        return []
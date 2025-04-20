# app/qa_engine.py
import openai
from typing import List, Tuple, Any
from utils.logger import log_event
from app.config import OPENAI_API_KEY, LLM_MODEL
from app.embeddings import search_similar_chunks

# Initialize OpenAI API
openai.api_key = OPENAI_API_KEY

def generate_system_prompt() -> str:
    """Create a system prompt for the legal assistant"""
    return """You are an AI legal document assistant specialized in analyzing legal documents and contracts. 
    Your task is to answer questions based on the provided document context.
    
    Please follow these guidelines:
    1. Only answer based on the information in the provided context
    2. If the answer is not in the context, say "I don't have enough information to answer this question based on the document."
    3. Provide specific references to sections or clauses when relevant
    4. Use formal and precise language appropriate for legal discussions
    5. Do not make up or assume information not present in the context
    
    Focus on providing factual, accurate analysis of the legal text without adding personal opinions or legal advice."""

def generate_prompt_with_context(query: str, relevant_chunks: List[Tuple[str, float]]) -> str:
    """Create a prompt with the query and relevant context"""
    # Extract just the text from the chunks
    context_texts = [chunk[0] for chunk in relevant_chunks]
    context = "\n\n".join(context_texts)
    
    prompt = f"""You are a legal document analysis assistant. Please answer the following question about the legal document carefully and precisely:

Question: {query}

Document Context:
```
{context}
```

Instructions:
1. Answer the question using ONLY the information provided in the document context above
2. If the answer is directly stated in the text, quote the relevant part
3. If the answer requires combining information from multiple parts, explain clearly
4. If you cannot find the information to answer the question in the context, say "Based on the provided document context, I cannot find information to answer this question."
5. Be concise but thorough in your response

Answer:"""
    
    return prompt

def query_llm(prompt: str, system_prompt: str = None) -> str:
    """
    Send a prompt to the LLM and get a response
    
    Args:
        prompt: The user prompt to send
        system_prompt: Optional system prompt
        
    Returns:
        The model's response text
    """
    try:
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user prompt
        messages.append({"role": "user", "content": prompt})
        
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.3,  # Lower temperature for more factual responses
            max_tokens=1200
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        log_event(f"Error querying LLM: {e}", "error")
        raise Exception(f"Error generating response: {str(e)}")

def answer_question(query: str, index: Any, chunks: List[str], top_k: int = 5) -> str:
    """
    Answer a question using RAG with the document chunks
    
    Args:
        query: The user's question
        index: FAISS index of the document
        chunks: The document chunks
        top_k: Number of chunks to retrieve
        
    Returns:
        The answer to the question
    """
    try:
        log_event(f"Answering question: {query}", "info")
        
        # Retrieve relevant chunks
        relevant_chunks = search_similar_chunks(query, index, chunks, top_k)
        
        if not relevant_chunks:
            return "I couldn't find any relevant information in the document to answer your question."
        
        # Generate prompt with context
        system_prompt = generate_system_prompt()
        user_prompt = generate_prompt_with_context(query, relevant_chunks)
        
        # Get response from LLM
        answer = query_llm(user_prompt, system_prompt)
        
        log_event("Successfully generated answer", "info")
        return answer
    
    except Exception as e:
        log_event(f"Error answering question: {e}", "error")
        return f"I encountered an error while trying to answer your question: {str(e)}"

def summarize_document(chunks: List[str], num_chunks: int = 10) -> str:
    """
    Generate a summary of the document
    
    Args:
        chunks: The document chunks
        num_chunks: Number of chunks to include in summary generation
        
    Returns:
        A summary of the document
    """
    try:
        log_event("Generating document summary", "info")
        
        # Select representative chunks from the document
        # For simplicity, take evenly spaced chunks across the document
        selected_chunks = []
        step = max(1, len(chunks) // num_chunks)
        
        for i in range(0, len(chunks), step):
            if len(selected_chunks) < num_chunks:
                selected_chunks.append(chunks[i])
            else:
                break
        
        # Join selected chunks
        document_sample = "\n\n".join(selected_chunks)
        
        # Ensure the sample is not too long
        if len(document_sample) > 15000:
            document_sample = document_sample[:15000] + "..."
        
        # Create prompt for summary
        prompt = f"""Summarize the following excerpt from a legal document:

```
{document_sample}
```

Please provide a concise summary that:
1. Identifies the type of legal document
2. Explains the main purpose and subject matter
3. Highlights key provisions or sections
4. Notes any important clauses, deadlines, or obligations
5. Uses formal language appropriate for legal document analysis

Your summary should be comprehensive yet concise (300-500 words)."""
        
        # Get response from LLM
        system_prompt = "You are an AI legal document assistant specialized in analyzing and summarizing legal texts. Provide clear, concise summaries that capture the essential elements of legal documents."
        summary = query_llm(prompt, system_prompt)
        
        log_event("Successfully generated document summary", "info")
        return summary
    
    except Exception as e:
        log_event(f"Error generating document summary: {e}", "error")
        return "I encountered an error while trying to generate a summary of the document."
# routes.py — Define FastAPI endpoints
import os
import uuid
import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict
from pydantic import BaseModel

from app.ingestion import extract_text, chunk_text, save_uploaded_file
from app.embeddings import build_faiss_index, load_faiss_index
from app.qa_engine import answer_question, summarize_document
from app.ner_extraction import extract_entities, categorize_legal_entities
from app.config import ALLOWED_EXTENSIONS
from utils.logger import log_event

router = APIRouter()

# In-memory storage for document processing status
# In a production environment, this would be a database
doc_processing = {}

class QuestionRequest(BaseModel):
    question: str
    document_id: str

class AnalysisResponse(BaseModel):
    document_id: str
    summary: str
    entities: Dict[str, List[str]]
    status: str

@router.post("/upload/", status_code=201)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Upload a legal document and process it in the background
    """
    try:
        # Check file extension
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Invalid file format. Supported formats: {', '.join(ALLOWED_EXTENSIONS)}")
        
        # Generate unique document ID
        document_id = str(uuid.uuid4())
        
        # Save file and update processing status
        doc_processing[document_id] = {"status": "uploading", "filename": file.filename}
        
        # Save the uploaded file
        file_path = await save_uploaded_file(file)
        
        # Update status and start background processing
        doc_processing[document_id]["status"] = "processing"
        doc_processing[document_id]["file_path"] = file_path
        
        # Process document in background
        background_tasks.add_task(process_document, document_id, file_path)
        
        return {"document_id": document_id, "status": "processing"}
    
    except Exception as e:
        log_event(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def save_uploaded_file(file: UploadFile) -> str:
    """Save an uploaded file and return the file path"""
    try:
        # Generate a unique filename
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join("data/uploaded_docs", unique_filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save file content
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        await file.seek(0)  # Reset file pointer
        return file_path
    
    except Exception as e:
        log_event(f"Error saving file: {e}")
        raise Exception(f"Error saving file: {str(e)}")

def process_document(document_id: str, file_path: str):
    """
    Process a document in the background
    - Extract text
    - Chunk text
    - Build embeddings
    - Extract entities
    - Generate summary
    """
    try:
        # Extract text from document
        doc_processing[document_id]["status"] = "extracting_text"
        text = extract_text(file_path)
        
        # Chunk text
        doc_processing[document_id]["status"] = "chunking_text"
        chunks = chunk_text(text)
        
        # Build embeddings and index
        doc_processing[document_id]["status"] = "building_index"
        index, _ = build_faiss_index(chunks, document_id)
        
        # Extract entities
        doc_processing[document_id]["status"] = "extracting_entities"
        entities = extract_entities(text)
        categorized_entities = categorize_legal_entities(entities)
        doc_processing[document_id]["entities"] = categorized_entities
        
        # Generate summary
        doc_processing[document_id]["status"] = "generating_summary"
        summary = summarize_document(chunks)
        doc_processing[document_id]["summary"] = summary
        
        # Mark as complete
        doc_processing[document_id]["status"] = "complete"
        log_event(f"Document {document_id} processed successfully")
    
    except Exception as e:
        log_event(f"Error processing document {document_id}: {e}")
        doc_processing[document_id]["status"] = "error"
        doc_processing[document_id]["error"] = str(e)

@router.get("/document/{document_id}/status")
async def document_status(document_id: str):
    """
    Check the processing status of a document
    """
    if document_id not in doc_processing:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"document_id": document_id, "status": doc_processing[document_id]["status"]}

@router.get("/document/{document_id}/analysis", response_model=AnalysisResponse)
async def document_analysis(document_id: str):
    """
    Get the analysis of a processed document
    - Summary
    - Extracted entities
    """
    if document_id not in doc_processing:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc_processing[document_id]["status"] == "error":
        raise HTTPException(status_code=500, detail=doc_processing[document_id].get("error", "Unknown error"))
    
    if doc_processing[document_id]["status"] != "complete":
        return {
            "document_id": document_id, 
            "status": doc_processing[document_id]["status"],
            "summary": "",
            "entities": {}
        }
    
    return {
        "document_id": document_id,
        "status": "complete",
        "summary": doc_processing[document_id].get("summary", ""),
        "entities": doc_processing[document_id].get("entities", {})
    }

@router.post("/ask/")
async def ask_question(question_req: QuestionRequest):
    """
    Answer a question about a document using RAG
    """
    document_id = question_req.document_id
    question = question_req.question
    
    # Check if document exists and is processed
    if document_id not in doc_processing:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc_processing[document_id]["status"] != "complete":
        raise HTTPException(status_code=400, detail=f"Document processing is not complete. Current status: {doc_processing[document_id]['status']}")
    
    try:
        # Load the index and chunks
        index, chunks = load_faiss_index(document_id)
        
        # Answer the question
        answer = answer_question(question, index, chunks)
        
        return {"answer": answer}
    
    except Exception as e:
        log_event(f"Error answering question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/")
async def list_documents():
    """
    List all processed documents
    """
    documents = []
    for doc_id, info in doc_processing.items():
        documents.append({
            "document_id": doc_id,
            "filename": info.get("filename", "Unknown"),
            "status": info.get("status", "Unknown")
        })
    
    return {"documents": documents}

@router.delete("/document/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and its associated data
    """
    if document_id not in doc_processing:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Remove from in-memory storage
        file_path = doc_processing[document_id].get("file_path")
        del doc_processing[document_id]
        
        # Delete the file if it exists
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete vector store if it exists
        vector_store_path = os.path.join("data/vector_store", document_id)
        if os.path.exists(vector_store_path):
            for file in os.listdir(vector_store_path):
                os.remove(os.path.join(vector_store_path, file))
            os.rmdir(vector_store_path)
        
        return {"status": "success", "message": "Document deleted successfully"}
    
    except Exception as e:
        log_event(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

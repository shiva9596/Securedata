# main.py — FastAPI entry point with integrated HTML UI
from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import uvicorn
import os
import uuid
import time
from typing import Dict, List, Optional
import json

from app.ingestion import extract_text, chunk_text
from app.embeddings import build_faiss_index, load_faiss_index
from app.qa_engine import answer_question, summarize_document
from app.ner_extraction import extract_entities, categorize_legal_entities
from app.config import ALLOWED_EXTENSIONS, MAX_FREE_CHATS
from app.database import get_db, User, Question, UserPayment # Added UserPayment import
from app.auth import get_current_active_user, Token, is_admin
from app.auth_routes import router as auth_router
from app.profile_routes import router as profile_router
from app.repository import (
    create_document, update_document_status, store_document_entities,
    get_document, get_document_entities, get_user_documents,
    delete_document as repo_delete_document,
    store_question_answer, get_document_questions
)
from utils.logger import log_event

# Create the FastAPI app
app = FastAPI(
    title="Legal Document AI Assistant",
    description="A RAG-powered legal document analysis and question answering system",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Include authentication routes
app.include_router(auth_router)

# Include profile routes
app.include_router(profile_router)

# API Routes
@app.post("/api/upload/", status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload a legal document and process it in the background
    """
    try:
        # Check file extension
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Invalid file format. Supported formats: {', '.join(ALLOWED_EXTENSIONS)}")

        # Read file content
        file_content = await file.read()
        file_size_kb = len(file_content) / 1024

        # Reset file pointer
        await file.seek(0)

        # Save file to disk
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join("data/uploaded_docs", unique_filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save file content
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Create document record in database
        document = create_document(
            db=db,
            user_id=current_user.id,
            filename=file.filename,
            file_path=file_path,
            file_size_kb=file_size_kb,
            file_type=file_extension
        )

        # Process document in background
        background_tasks.add_task(process_document, document.id, file_path, db)

        return {"document_id": document.id, "status": "processing"}

    except Exception as e:
        log_event(f"Error uploading document: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

def process_document(document_id: str, file_path: str, db: Session):
    """
    Process a document in the background
    - Extract text
    - Chunk text
    - Build embeddings
    - Extract entities
    - Generate summary
    """
    try:
        # Update status to extracting text
        update_document_status(db, document_id, "extracting_text")

        # Extract text from document
        text = extract_text(file_path)

        # Update status to chunking text
        update_document_status(db, document_id, "chunking_text")

        # Chunk text
        chunks = chunk_text(text)

        # Update status to building index
        update_document_status(db, document_id, "building_index")

        # Build embeddings and index
        index, _ = build_faiss_index(chunks, document_id)

        # Update status to extracting entities
        update_document_status(db, document_id, "extracting_entities")

        # Extract entities
        entities = extract_entities(text)
        categorized_entities = categorize_legal_entities(entities)

        # Store entities in database
        store_document_entities(db, document_id, categorized_entities)

        # Update status to generating summary
        update_document_status(db, document_id, "generating_summary")

        # Generate summary
        summary = summarize_document(chunks)

        # Mark as complete with summary
        update_document_status(db, document_id, "complete", summary)

        log_event(f"Document {document_id} processed successfully", "info")

    except Exception as e:
        log_event(f"Error processing document {document_id}: {e}", "error")
        # Update status to error
        update_document_status(db, document_id, "error")

@app.get("/api/document/{document_id}/status")
async def document_status(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check the processing status of a document
    """
    try:
        # Get document with ownership check
        document = get_document(db, document_id, current_user.id)

        return {"document_id": document_id, "status": document.status}

    except Exception as e:
        log_event(f"Error getting document status: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/document/{document_id}/analysis")
async def document_analysis(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get the analysis of a processed document
    - Summary
    - Extracted entities
    """
    try:
        # Get document with ownership check
        document = get_document(db, document_id, current_user.id)

        # Check for error status
        if document.status == "error":
            raise HTTPException(status_code=500, detail="Document processing failed")

        # Check for incomplete status
        if document.status != "complete":
            return {
                "document_id": document_id,
                "status": document.status,
                "filename": document.original_filename,
                "summary": "",
                "entities": {}
            }

        # Get entities
        entities = get_document_entities(db, document_id)

        return {
            "document_id": document_id,
            "status": "complete",
            "filename": document.original_filename,
            "summary": document.summary or "",
            "entities": entities
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        log_event(f"Error getting document analysis: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

from app.config import MAX_FREE_CHATS

@app.post("/api/ask/")
async def ask_question(
    document_id: str = Form(...), 
    question: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Answer a question about a document using RAG
    """
    """
    Answer a question about a document using RAG
    """
    try:
        if not question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")
            
        if len(question) > 500:
            raise HTTPException(status_code=400, detail="Question is too long (max 500 characters)")
        # Check chat limit
        chat_count = db.query(Question).filter(
            Question.user_id == current_user.id
        ).count()

        # Check user's premium status through UserPayment
        user_payment = db.query(UserPayment).filter(
            UserPayment.user_id == current_user.id,
            UserPayment.is_premium == True
        ).first()

        if chat_count >= MAX_FREE_CHATS and not user_payment:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "You have reached the free chat limit. Please upgrade to continue.",
                    "upgrade_url": "/upgrade"
                }
            )

        # Get document with ownership check
        document = get_document(db, document_id, current_user.id)

        # Check for incomplete processing
        if document.status != "complete":
            raise HTTPException(
                status_code=400, 
                detail=f"Document processing is not complete. Current status: {document.status}"
            )

        # Load the index and chunks
        index, chunks = load_faiss_index(document_id)

        # Answer the question
        answer = answer_question(question, index, chunks)

        # Store question and answer in database
        store_question_answer(db, document_id, current_user.id, question, answer)

        return {"answer": answer}

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        log_event(f"Error answering question: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/")
async def list_documents(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all documents for the current user
    """
    try:
        # Get documents for current user
        documents = get_user_documents(db, current_user.id)

        # Format response
        result = []
        for doc in documents:
            result.append({
                "document_id": doc.id,
                "filename": doc.original_filename,
                "status": doc.status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None
            })

        return {"documents": result}

    except Exception as e:
        log_event(f"Error listing documents: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/document/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a document and its associated data
    """
    try:
        # Delete document with ownership check
        repo_delete_document(db, document_id, current_user.id)

        # Delete vector store if it exists
        vector_store_path = os.path.join("data/vector_store", document_id)
        if os.path.exists(vector_store_path):
            for file in os.listdir(vector_store_path):
                os.remove(os.path.join(vector_store_path, file))
            os.rmdir(vector_store_path)

        return {"status": "success", "message": "Document deleted successfully"}

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        log_event(f"Error deleting document: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/document/{document_id}/questions")
async def document_questions(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all questions for a document
    """
    try:
        # Get document with ownership check
        get_document(db, document_id, current_user.id)

        # Get questions
        questions = get_document_questions(db, document_id)

        # Format response
        result = []
        for q in questions:
            result.append({
                "id": q.id,
                "question": q.question_text,
                "answer": q.answer_text,
                "created_at": q.created_at.isoformat() if q.created_at else None
            })

        return {"questions": result}

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        log_event(f"Error getting document questions: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

# Web UI Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the home page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the registration page"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/document/{document_id}", response_class=HTMLResponse)
async def document_page(request: Request, document_id: str):
    """Serve the document analysis page"""
    return templates.TemplateResponse("document.html", {"request": request, "document_id": document_id})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the user dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """Serve the user profile page"""
    return templates.TemplateResponse("profile.html", {"request": request})

# API health check endpoint
@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "service": "Legal Document AI Assistant",
        "version": "1.0.0"
    }

# Run the app with Uvicorn if executed directly
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))

    uvicorn.run("app.main:app", host=host, port=port, reload=True)
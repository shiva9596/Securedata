# app/repository.py
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
import uuid
import os

from app.database import User, Document, DocumentEntity, Question, UserActivity
from utils.logger import log_event
from app.config import UPLOAD_FOLDER
from app.activity_repository import log_activity

# Document Repository Functions
def create_document(
    db: Session,
    user_id: int,
    filename: str,
    file_path: str,
    file_size_kb: float,
    file_type: str
) -> Document:
    """
    Create a new document record in the database
    
    Args:
        db: Database session
        user_id: ID of the document owner
        filename: Original filename
        file_path: Path to saved file
        file_size_kb: File size in KB
        file_type: File type (pdf, docx, etc.)
        
    Returns:
        The created document
    """
    try:
        # Generate a unique ID for the document
        document_id = str(uuid.uuid4())
        
        # Create the document record
        document = Document(
            id=document_id,
            owner_id=user_id,
            filename=os.path.basename(file_path),
            original_filename=filename,
            file_path=file_path,
            file_size_kb=int(file_size_kb),  # Convert to integer
            file_type=file_type,
            status="uploading"
        )
        
        # Add to database
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # Log activity
        log_activity(
            db=db,
            user_id=user_id,
            activity_type="document_upload",
            description=f"Uploaded document: {filename}",
            document_id=document_id,
            extra_data={"file_size_kb": int(file_size_kb), "file_type": file_type}
        )
        
        log_event(f"Document created: {document_id}", "info")
        return document
        
    except Exception as e:
        log_event(f"Error creating document: {e}", "error")
        db.rollback()
        raise e

def update_document_status(
    db: Session,
    document_id: str,
    status: str,
    summary: str = None
) -> Document:
    """
    Update a document's status and optionally its summary
    
    Args:
        db: Database session
        document_id: Document ID
        status: New status
        summary: Optional document summary
        
    Returns:
        The updated document
    """
    try:
        # Get the document
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
            
        # Update document
        document.status = status
        
        if status == "complete":
            document.processed_at = datetime.utcnow()
            
        if summary:
            document.summary = summary
        
        # Commit changes
        db.commit()
        db.refresh(document)
        
        log_event(f"Document {document_id} status updated to {status}", "info")
        return document
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        log_event(f"Error updating document status: {e}", "error")
        db.rollback()
        raise e

def store_document_entities(
    db: Session,
    document_id: str,
    entities: Dict[str, List[str]]
) -> List[DocumentEntity]:
    """
    Store entities extracted from a document
    
    Args:
        db: Database session
        document_id: Document ID
        entities: Dictionary of entity categories and values
        
    Returns:
        List of created document entities
    """
    try:
        # Create entity records
        entity_records = []
        
        for category, entity_list in entities.items():
            for entity_text in entity_list:
                # Create entity record
                entity = DocumentEntity(
                    document_id=document_id,
                    category=category,
                    text=entity_text
                )
                
                # Add to database
                db.add(entity)
                entity_records.append(entity)
        
        # Commit changes
        db.commit()
        
        # Refresh entities
        for entity in entity_records:
            db.refresh(entity)
        
        log_event(f"Stored {len(entity_records)} entities for document {document_id}", "info")
        return entity_records
        
    except Exception as e:
        log_event(f"Error storing document entities: {e}", "error")
        db.rollback()
        raise e

def get_document(db: Session, document_id: str, user_id: Optional[int] = None) -> Document:
    """
    Get a document by ID, optionally checking ownership
    
    Args:
        db: Database session
        document_id: Document ID
        user_id: Optional user ID to check ownership
        
    Returns:
        The document
        
    Raises:
        HTTPException: If document not found or user doesn't own it
    """
    try:
        # Get the document
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
            
        # Check ownership if user_id provided
        if user_id and document.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this document"
            )
            
        return document
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        log_event(f"Error getting document: {e}", "error")
        raise e

def get_document_entities(db: Session, document_id: str) -> Dict[str, List[str]]:
    """
    Get entities for a document
    
    Args:
        db: Database session
        document_id: Document ID
        
    Returns:
        Dictionary of entity categories and values
    """
    try:
        # Get the document
        document = get_document(db, document_id)
        
        # Get entities
        entities = db.query(DocumentEntity).filter(DocumentEntity.document_id == document_id).all()
        
        # Group by category
        result = {}
        
        for entity in entities:
            if entity.category not in result:
                result[entity.category] = []
                
            result[entity.category].append(entity.text)
        
        return result
        
    except Exception as e:
        log_event(f"Error getting document entities: {e}", "error")
        raise e

def get_user_documents(db: Session, user_id: int) -> List[Document]:
    """
    Get all documents owned by a user
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        List of documents
    """
    try:
        # Get documents
        documents = db.query(Document).filter(Document.owner_id == user_id).all()
        return documents
        
    except Exception as e:
        log_event(f"Error getting user documents: {e}", "error")
        raise e

def delete_document(db: Session, document_id: str, user_id: Optional[int] = None) -> bool:
    """
    Delete a document
    
    Args:
        db: Database session
        document_id: Document ID
        user_id: Optional user ID to check ownership
        
    Returns:
        Whether the document was deleted
    """
    try:
        # Get the document
        document = get_document(db, document_id, user_id)
        
        # Delete the file if it exists
        if document.file_path and os.path.exists(document.file_path):
            os.remove(document.file_path)
        
        # Get document info before deleting
        document_filename = document.original_filename
        owner_id = document.owner_id
        
        # Delete from database
        db.delete(document)
        db.commit()
        
        # Log activity
        if user_id:
            log_activity(
                db=db,
                user_id=user_id,
                activity_type="document_delete",
                description=f"Deleted document: {document_filename}",
                extra_data={"document_id": document_id}
            )
        
        log_event(f"Document {document_id} deleted", "info")
        return True
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        log_event(f"Error deleting document: {e}", "error")
        db.rollback()
        raise e

# Question Repository Functions
def store_question_answer(
    db: Session,
    document_id: str,
    user_id: int,
    question: str,
    answer: str
) -> Question:
    """
    Store a question and its answer
    
    Args:
        db: Database session
        document_id: Document ID
        user_id: User ID
        question: Question text
        answer: Answer text
        
    Returns:
        The created question
    """
    try:
        # Check if document exists
        get_document(db, document_id)
        
        # Create question record
        question_record = Question(
            document_id=document_id,
            user_id=user_id,
            question_text=question,
            answer_text=answer
        )
        
        # Add to database
        db.add(question_record)
        db.commit()
        db.refresh(question_record)
        
        # Log activity
        log_activity(
            db=db,
            user_id=user_id,
            activity_type="question",
            description=f"Asked: {question[:100]}{'...' if len(question) > 100 else ''}",
            document_id=document_id,
            question_id=question_record.id,
            extra_data={"answer_length": len(answer)}
        )
        
        log_event(f"Question stored for document {document_id}", "info")
        return question_record
        
    except Exception as e:
        log_event(f"Error storing question: {e}", "error")
        db.rollback()
        raise e

def get_document_questions(db: Session, document_id: str) -> List[Question]:
    """
    Get all questions for a document
    
    Args:
        db: Database session
        document_id: Document ID
        
    Returns:
        List of questions
    """
    try:
        # Get questions
        questions = db.query(Question).filter(Question.document_id == document_id).all()
        return questions
        
    except Exception as e:
        log_event(f"Error getting document questions: {e}", "error")
        raise e
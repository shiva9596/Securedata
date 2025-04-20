# app/activity_repository.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import UserActivity, User, Document, Question
from utils.logger import log_event

def log_activity(
    db: Session,
    user_id: int,
    activity_type: str,
    description: str,
    document_id: Optional[str] = None,
    question_id: Optional[int] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> UserActivity:
    """
    Log a user activity
    
    Args:
        db: Database session
        user_id: User ID
        activity_type: Type of activity (document_upload, document_delete, question, etc.)
        description: Description of the activity
        document_id: Optional document ID
        question_id: Optional question ID
        extra_data: Optional additional data
        
    Returns:
        The created activity record
    """
    try:
        # Create activity record
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            description=description,
            document_id=document_id,
            question_id=question_id,
            extra_data=extra_data,
            created_at=datetime.now()
        )
        
        # Add to database
        db.add(activity)
        db.commit()
        db.refresh(activity)
        
        log_event(f"Activity logged: {activity_type} for user {user_id}", "info")
        return activity
        
    except Exception as e:
        log_event(f"Error logging activity: {e}", "error")
        db.rollback()
        raise e

def get_user_activities(
    db: Session, 
    user_id: int, 
    activity_type: Optional[str] = None, 
    limit: int = 50
) -> List[UserActivity]:
    """
    Get user activities
    
    Args:
        db: Database session
        user_id: User ID
        activity_type: Optional filter by activity type
        limit: Maximum number of activities to return
        
    Returns:
        List of user activities
    """
    try:
        # Build query
        query = db.query(UserActivity).filter(UserActivity.user_id == user_id)
        
        if activity_type:
            query = query.filter(UserActivity.activity_type == activity_type)
            
        # Get activities
        activities = query.order_by(UserActivity.created_at.desc()).limit(limit).all()
        return activities
        
    except Exception as e:
        log_event(f"Error getting user activities: {e}", "error")
        raise e

def get_document_activities(db: Session, document_id: str, limit: int = 20) -> List[UserActivity]:
    """
    Get activities for a document
    
    Args:
        db: Database session
        document_id: Document ID
        limit: Maximum number of activities to return
        
    Returns:
        List of document activities
    """
    try:
        # Get activities
        activities = db.query(UserActivity)\
            .filter(UserActivity.document_id == document_id)\
            .order_by(UserActivity.created_at.desc())\
            .limit(limit)\
            .all()
            
        return activities
        
    except Exception as e:
        log_event(f"Error getting document activities: {e}", "error")
        raise e

def get_user_activity_count(db: Session, user_id: int) -> Dict[str, int]:
    """
    Get activity counts for a user
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Dictionary with activity counts
    """
    try:
        # Get document count
        document_count = db.query(Document).filter(Document.owner_id == user_id).count()
        
        # Get question count
        question_count = db.query(Question).filter(Question.user_id == user_id).count()
        
        # Get activity counts by type
        upload_count = db.query(UserActivity)\
            .filter(UserActivity.user_id == user_id, UserActivity.activity_type == "document_upload")\
            .count()
            
        question_asked_count = db.query(UserActivity)\
            .filter(UserActivity.user_id == user_id, UserActivity.activity_type == "question")\
            .count()
            
        return {
            "documents": document_count,
            "questions": question_count,
            "uploads": upload_count,
            "questions_asked": question_asked_count
        }
        
    except Exception as e:
        log_event(f"Error getting user activity count: {e}", "error")
        raise e

def format_activity_for_display(activity: UserActivity) -> Dict[str, Any]:
    """
    Format an activity for display in the UI
    
    Args:
        activity: User activity
        
    Returns:
        Formatted activity data
    """
    result = {
        "id": activity.id,
        "type": activity.activity_type,
        "description": activity.description,
        "timestamp": activity.created_at.isoformat(),
        "document_id": activity.document_id,
        "question_id": activity.question_id,
        "extra_data": activity.extra_data or {}
    }
    
    # Add title based on activity type
    if activity.activity_type == "document_upload":
        result["title"] = "Document Upload"
        if activity.document_id:
            result["link"] = f"/document/{activity.document_id}"
    elif activity.activity_type == "document_delete":
        result["title"] = "Document Deleted"
    elif activity.activity_type == "question":
        result["title"] = "Question Asked"
        if activity.document_id:
            result["link"] = f"/document/{activity.document_id}#question-{activity.question_id}"
    elif activity.activity_type == "profile_update":
        result["title"] = "Profile Updated"
    else:
        result["title"] = "Activity"
    
    return result
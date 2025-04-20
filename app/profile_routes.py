# app/profile_routes.py
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Form, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr

from app.database import get_db, User, Question
from app.auth import get_current_active_user, get_password_hash, verify_password
from app.activity_repository import (
    get_user_activities, 
    log_activity, 
    get_user_activity_count,
    format_activity_for_display
)
from utils.logger import log_event

# Create router
router = APIRouter(prefix="/api/user", tags=["profile"])

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class UserActivityResponse(BaseModel):
    activities: List[Dict[str, Any]]

class ActivityCountResponse(BaseModel):
    documents: int
    questions: int
    uploads: int
    questions_asked: int

class QuestionCountResponse(BaseModel):
    count: int

@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change user password
    """
    try:
        # Verify current password
        if not verify_password(password_data.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password"
            )
            
        # Validate new password
        if len(password_data.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters long"
            )
            
        # Hash new password and update user
        hashed_password = get_password_hash(password_data.new_password)
        
        # Get user from database to ensure it's fresh
        user = db.query(User).filter(User.id == current_user.id).first()
        user.hashed_password = hashed_password
        
        # Save changes
        db.commit()
        
        # Log activity
        log_activity(
            db=db,
            user_id=current_user.id,
            activity_type="profile_update",
            description="Password changed",
            extra_data={"action": "password_change"}
        )
        
        log_event(f"Password changed for user {current_user.username}", "info")
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        log_event(f"Error changing password: {e}", "error")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/activity", response_model=UserActivityResponse)
async def get_activity_history(
    filter: str = "all",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get user activity history
    """
    try:
        # Map filter to activity type
        activity_type = None
        if filter == "uploads":
            activity_type = "document_upload"
        elif filter == "questions":
            activity_type = "question"
            
        # Get activities
        activities = get_user_activities(
            db=db,
            user_id=current_user.id,
            activity_type=activity_type
        )
        
        # Format activities for display
        formatted_activities = [format_activity_for_display(activity) for activity in activities]
        
        return {"activities": formatted_activities}
        
    except Exception as e:
        log_event(f"Error getting activity history: {e}", "error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/stats", response_model=ActivityCountResponse)
async def get_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get user statistics
    """
    try:
        # Get activity counts
        counts = get_user_activity_count(db=db, user_id=current_user.id)
        return counts
        
    except Exception as e:
        log_event(f"Error getting user stats: {e}", "error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/questions/count", response_model=QuestionCountResponse)
async def get_question_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get count of questions asked by the user
    """
    try:
        # Get question count
        count = db.query(Question).filter(Question.user_id == current_user.id).count()
        return {"count": count}
        
    except Exception as e:
        log_event(f"Error getting question count: {e}", "error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
# app/auth.py
from fastapi import Depends, FastAPI, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr
import bcrypt
from sqlalchemy.orm import Session
import os

from app.database import User, get_db
from utils.logger import log_event
from app.config import OPENAI_API_KEY  # Use this to ensure .env is loaded

# JWT Settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey123456789abcdefghijklmn")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# OAuth2 scheme for token handling
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

# Pydantic models for request/response
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

# Chat limit settings
MAX_FREE_CHATS = 3


class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_admin: bool
    
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    username: Optional[str] = None
    is_admin: Optional[bool] = False

# Authentication functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hashed password
    
    Args:
        plain_password: The plain text password
        hashed_password: The hashed password
        
    Returns:
        Whether the password matches the hash
    """
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        log_event(f"Error verifying password: {e}", "error")
        return False

def get_password_hash(password: str) -> str:
    """
    Hash a password for storing
    
    Args:
        password: The password to hash
        
    Returns:
        The hashed password
    """
    try:
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        log_event(f"Error hashing password: {e}", "error")
        raise e

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: The data to encode in the token
        expires_delta: Optional expiration time
        
    Returns:
        The encoded JWT token
    """
    to_encode = data.copy()
    
    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    # Add expiration time to token data
    to_encode.update({"exp": expire})
    
    # Encode the token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Get the current user from a JWT token
    
    Args:
        token: The JWT token
        db: Database session
        
    Returns:
        The user object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            raise credentials_exception
            
        token_data = TokenData(username=username, is_admin=payload.get("is_admin", False))
        
    except JWTError:
        raise credentials_exception
        
    # Get user from database
    user = db.query(User).filter(User.username == token_data.username).first()
    
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )
        
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get the current active user
    
    Args:
        current_user: The current user
        
    Returns:
        The user object if active
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )
    return current_user

async def is_admin(current_user: User = Depends(get_current_user)) -> bool:
    """
    Check if the current user is an admin
    
    Args:
        current_user: The current user
        
    Returns:
        Whether the user is an admin
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this resource"
        )
    return True

# User registration and authentication
def register_user(db: Session, user: UserCreate) -> User:
    """
    Register a new user
    
    Args:
        db: Database session
        user: User data
        
    Returns:
        The created user
        
    Raises:
        HTTPException: If email or username already exists
    """
    try:
        # Check if email exists
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
            
        # Check if username exists
        db_user = db.query(User).filter(User.username == user.username).first()
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
            
        # Create new user
        hashed_password = get_password_hash(user.password)
        
        # Is this the first user? Make them admin
        is_first_user = db.query(User).count() == 0
        
        db_user = User(
            email=user.email,
            username=user.username,
            hashed_password=hashed_password,
            is_admin=is_first_user
        )
        
        # Add to database
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        log_event(f"User registered: {user.username}", "info")
        return db_user
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        log_event(f"Error registering user: {e}", "error")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error registering user"
        )

def authenticate_user(db: Session, username: str, password: str) -> User:
    """
    Authenticate a user
    
    Args:
        db: Database session
        username: Username
        password: Password
        
    Returns:
        The authenticated user
        
    Raises:
        HTTPException: If login fails
    """
    try:
        # Get user from database
        user = db.query(User).filter(User.username == username).first()
        
        # Check if user exists and password is correct
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        return user
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        log_event(f"Error authenticating user: {e}", "error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during authentication"
        )
async def check_payment_status(user_id: int, db: Session):
    """Check if user needs to pay"""
    payment = db.query(UserPayment).filter(UserPayment.user_id == user_id).first()
    chat_count = db.query(Question).filter(Question.user_id == user_id).count()
    
    if not payment or not payment.is_premium:
        if chat_count >= 3:  # Free tier limit
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "You've reached the free limit. Please upgrade to continue.",
                    "upgrade_url": "/profile#upgrade"
                }
            )

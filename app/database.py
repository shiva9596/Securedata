# app/database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import os
from datetime import datetime, timedelta
from utils.logger import log_event

# Database path
DB_PATH = "data/legal_assistant.db"

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Create SQLite engine
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# ORM Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    documents = relationship("Document", back_populates="owner", cascade="all, delete")
    questions = relationship("Question", back_populates="user", cascade="all, delete")
    activities = relationship("UserActivity", back_populates="user", cascade="all, delete")
    payment = relationship("UserPayment", back_populates="user", uselist=False, cascade="all, delete")

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(50), primary_key=True) # UUID
    owner_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String(255))
    original_filename = Column(String(255))
    file_path = Column(String(255))
    file_size_kb = Column(Integer)
    file_type = Column(String(10))  # pdf, docx, etc.
    status = Column(String(50))  # processing, complete, error
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    owner = relationship("User", back_populates="documents")
    entities = relationship("DocumentEntity", back_populates="document", cascade="all, delete")
    questions = relationship("Question", back_populates="document", cascade="all, delete")
    activities = relationship("UserActivity", back_populates="document", cascade="all, delete")

class DocumentEntity(Base):
    __tablename__ = "document_entities"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(50), ForeignKey("documents.id"))
    category = Column(String(50))  # PERSON, ORG, DATE, etc.
    text = Column(String(255))

    # Relationships
    document = relationship("Document", back_populates="entities")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(50), ForeignKey("documents.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    question_text = Column(Text)
    answer_text = Column(Text)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    document = relationship("Document", back_populates="questions")
    user = relationship("User", back_populates="questions")
    activities = relationship("UserActivity", back_populates="question", cascade="all, delete")



class UserPayment(Base):
    __tablename__ = "user_payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    is_premium = Column(Boolean, default=False)
    subscription_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationship
    user = relationship("User", back_populates="payment")

class UserActivity(Base):
    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    activity_type = Column(String(50))  # document_upload, document_delete, question, etc.
    description = Column(Text)
    document_id = Column(String(50), ForeignKey("documents.id"), nullable=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
    extra_data = Column(JSON, nullable=True)  # Additional activity data
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="activities")
    document = relationship("Document", back_populates="activities")
    question = relationship("Question", back_populates="activities")

# Create tables
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        log_event("Database initialized successfully", "info")
    except Exception as e:
        log_event(f"Error initializing database: {e}", "error")

# Get database session for dependency injection
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database
init_db()
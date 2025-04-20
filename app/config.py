# app/config.py
import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# LLM Configuration
LLM_MODEL = "gpt-4o"  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
EMBEDDING_MODEL = "text-embedding-ada-002"

# User Limits
MAX_FREE_CHATS = 3

# Document Processing Configuration
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
ALLOWED_EXTENSIONS = ["pdf", "docx", "doc", "txt"]

# Folder Paths
UPLOAD_FOLDER = "data/uploaded_docs"
VECTOR_STORE_FOLDER = "data/vector_store"
LOG_FOLDER = "logs"

# Ensure directories exist
for folder in [UPLOAD_FOLDER, VECTOR_STORE_FOLDER, LOG_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Logging Configuration
LOG_FILE = os.path.join(LOG_FOLDER, "legal_assistant.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# NER Configuration
# Map spaCy entity types to legal categories
LEGAL_ENTITY_CATEGORIES = {
    "PERSON": ["PERSON"],
    "ORGANIZATION": ["ORG"],
    "DATE": ["DATE"],
    "LAW": ["LAW"],
    "LOCATION": ["GPE", "LOC"],
    "MONEY": ["MONEY"],
    "TIME": ["TIME"],
    "OTHER": ["NORP", "FAC", "PRODUCT", "EVENT", "LANGUAGE"]
}

# Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey123456789abcdefghijklmn")
TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
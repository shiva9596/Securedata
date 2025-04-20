# app/ingestion.py
import os
import time
import PyPDF2
from docx import Document
from typing import List
from utils.logger import log_event
from app.config import CHUNK_SIZE, CHUNK_OVERLAP, UPLOAD_FOLDER

def save_uploaded_file(file) -> str:
    """Save an uploaded file to the upload directory and return the file path"""
    try:
        # Generate a unique filename
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save file content
        with open(file_path, "wb") as f:
            content = file.read()
            f.write(content)
            
        log_event(f"File saved to {file_path}", "info")
        return file_path
    
    except Exception as e:
        log_event(f"Error saving file: {e}", "error")
        raise Exception(f"Error saving file: {str(e)}")

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file"""
    try:
        text = ""
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        
        log_event(f"Extracted {len(text)} characters from PDF", "info")
        return text
    
    except Exception as e:
        log_event(f"Error extracting text from PDF: {e}", "error")
        raise Exception(f"Error extracting text from PDF: {str(e)}")

def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a DOCX file"""
    try:
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        
        log_event(f"Extracted {len(text)} characters from DOCX", "info")
        return text
    
    except Exception as e:
        log_event(f"Error extracting text from DOCX: {e}", "error")
        raise Exception(f"Error extracting text from DOCX: {str(e)}")

def extract_text(file_path: str) -> str:
    """Extract text from a document based on its file extension"""
    try:
        # Determine file type
        file_extension = file_path.split(".")[-1].lower()
        
        if file_extension == "pdf":
            return extract_text_from_pdf(file_path)
        elif file_extension in ["docx", "doc"]:
            return extract_text_from_docx(file_path)
        elif file_extension == "txt":
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    except Exception as e:
        log_event(f"Error extracting text: {e}", "error")
        raise Exception(f"Error extracting text: {str(e)}")

def chunk_text(text: str) -> List[str]:
    """Split text into manageable chunks with overlap using faster method"""
    try:
        # Split into paragraphs first
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < CHUNK_SIZE:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
                
            # If current chunk is getting too big, split it
            while len(current_chunk) >= CHUNK_SIZE:
                # Find last period or newline
                split_point = current_chunk[:CHUNK_SIZE].rfind('.')
                if split_point == -1:
                    split_point = current_chunk[:CHUNK_SIZE].rfind('\n')
                if split_point == -1:
                    split_point = CHUNK_SIZE
                
                chunks.append(current_chunk[:split_point+1].strip())
                current_chunk = current_chunk[split_point-CHUNK_OVERLAP:] if split_point > CHUNK_OVERLAP else current_chunk[split_point+1:]
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        log_event(f"Text split into {len(chunks)} chunks", "info")
        return chunks
    
    except Exception as e:
        log_event(f"Error chunking text: {e}", "error")
        raise Exception(f"Error chunking text: {str(e)}")
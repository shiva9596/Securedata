# app/ner_extraction.py
import spacy
from typing import List, Dict, Tuple
from utils.logger import log_event
from app.config import LEGAL_ENTITY_CATEGORIES

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
    log_event("SpaCy model loaded successfully", "info")
except Exception as e:
    log_event(f"Error loading SpaCy model: {e}", "error")
    # Download the model if not already installed
    log_event("Attempting to download SpaCy model", "info")
    try:
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
        log_event("SpaCy model downloaded and loaded successfully", "info")
    except Exception as download_error:
        log_event(f"Error downloading SpaCy model: {download_error}", "error")
        # Fallback to a simpler model or basic NLP
        nlp = spacy.blank("en")
        log_event("Using blank English model as fallback", "warning")

def extract_entities(text: str) -> List[Tuple[str, str]]:
    """
    Extract named entities from text using spaCy
    
    Args:
        text: Text to extract entities from
        
    Returns:
        List of (entity_text, entity_label) tuples
    """
    try:
        # Process text in chunks to avoid memory issues with large documents
        max_length = 100000  # SpaCy default is usually around 1,000,000 characters
        entities = []
        
        # Process text in chunks
        for i in range(0, len(text), max_length):
            chunk = text[i:i + max_length]
            doc = nlp(chunk)
            
            # Extract all entities
            for ent in doc.ents:
                entities.append((ent.text, ent.label_))
        
        log_event(f"Extracted {len(entities)} entities from text", "info")
        return entities
    
    except Exception as e:
        log_event(f"Error extracting entities: {e}", "error")
        return []

def categorize_legal_entities(entities: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    """
    Categorize extracted entities into legal-relevant groups
    
    Args:
        entities: List of (entity_text, entity_label) tuples
        
    Returns:
        Dictionary with categorized entities
    """
    try:
        # Create result dictionary based on config categories
        categorized = {category: [] for category in LEGAL_ENTITY_CATEGORIES.keys()}
        
        # Process each entity
        for entity_text, entity_label in entities:
            # Find the category this entity belongs to
            for category, labels in LEGAL_ENTITY_CATEGORIES.items():
                if entity_label in labels:
                    # Add to appropriate category, avoiding duplicates
                    if entity_text not in categorized[category]:
                        categorized[category].append(entity_text)
        
        # Custom post-processing for legal entities (can be expanded)
        # Look for patterns like "Section X" or statute references
        # This is a simplified approach; a more sophisticated approach would use regex or ML
        
        log_event("Entities categorized successfully", "info")
        return categorized
    
    except Exception as e:
        log_event(f"Error categorizing entities: {e}", "error")
        return {category: [] for category in LEGAL_ENTITY_CATEGORIES.keys()}
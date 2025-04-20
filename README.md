# Legal Document AI Assistant

A powerful legal document analysis system with RAG (Retrieval-Augmented Generation) capabilities for processing, analyzing, and answering questions about legal documents.

## Features

- Document Processing: Handle PDF and DOCX files
- Text Extraction & Chunking: Extract and chunk text intelligently 
- Entity Recognition: Identify key legal entities with NER
- Vector Search: Fast similarity search with FAISS
- Question Answering: RAG-powered Q&A about documents
- Document Summarization: Generate concise summaries
- User Authentication: Secure JWT-based auth
- Entity Visualization: Interactive word clouds
- Chat History: Track Q&A interactions
- Premium Features: Tiered access levels

## Tech Stack

- Backend: FastAPI + Python
- Database: SQLite + SQLAlchemy
- AI/ML: OpenAI API, FAISS, spaCy
- Frontend: HTML/JS + Bootstrap 5
- Authentication: JWT + bcrypt
- Document Processing: PyPDF2, python-docx
- Visualization: D3.js

## Setup & Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
OPENAI_API_KEY=your_key
JWT_SECRET_KEY=your_secret
```

4. Run the application:
```bash
python run.py
```

The app will be available at `http://localhost:5000`

## Project Structure

```
├── app/               # Application code
│   ├── main.py       # FastAPI entry point
│   ├── qa_engine.py  # Q&A logic
│   ├── embeddings.py # Vector operations
│   └── auth.py       # Authentication
├── static/           # Static assets
├── templates/        # HTML templates
├── data/            # Document storage
└── diagrams/        # System diagrams
```

## API Endpoints

- `POST /api/upload/`: Upload documents
- `POST /api/ask/`: Ask questions
- `GET /api/documents/`: List documents
- `GET /api/document/{id}/`: Get document details
- `DELETE /api/document/{id}/`: Delete document

## Deployment

- Docker: Use Dockerfile for containerization
- AWS: Deploy on AWS EC2 or Lambda

## License

MIT License

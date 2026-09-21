# 🚀 Quick Start Guide

## 1. Set up environment variables
```bash
cp backend/env.example backend/.env
# Edit backend/.env with your API keys:
# - OPENAI_API_KEY
# - PINECONE_API_KEY
```

## 2. Start the application
```bash
docker compose up --build
```

## 3. Open the app
- **Frontend**: http://localhost:8502
- **Backend API**: http://localhost:8001

## 4. Test with a PDF
1. Upload an insurance policy PDF
2. Ask questions like "Is MRI covered?"
3. Get AI-powered answers with page citations

## 🎯 What's Working
✅ FastAPI backend with OCR + RAG pipeline  
✅ Streamlit frontend for easy interaction  
✅ PostgreSQL database for document storage  
✅ Pinecone vector search  
✅ OpenAI GPT-4o-mini for answers  
✅ Docker Compose setup  

## 🔧 API Endpoints
- `GET /health` - Health check
- `POST /ingest` - Upload PDF
- `POST /ask` - Ask questions

The MVP is ready to use! 🎉

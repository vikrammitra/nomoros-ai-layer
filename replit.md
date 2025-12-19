# Nomoros AI API

## Overview
Legal conveyancing document processing backend API built with Python FastAPI. This service ingests PDF documents and extracts text using Azure Document Intelligence (OCR + layout extraction).

**Current State**: Phase 1 - Basic OCR extraction working

## Project Architecture

```
nomoros_ai/
├── main.py                          # FastAPI app entry point
├── config.py                        # Environment configuration
├── routers/
│   └── documents.py                 # Document ingestion endpoints
├── services/
│   └── ocr/
│       └── azure_doc_intelligence.py  # Azure Document Intelligence wrapper
├── models/
│   └── document.py                  # Pydantic request/response models
└── audit/                           # Reserved for future audit logging
```

## API Endpoints

- `GET /` - Root endpoint with API info
- `GET /health` - Health check (shows if Azure is configured)
- `POST /documents/ingest` - Upload PDF for OCR extraction

## Required Environment Variables

- `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` - Azure Document Intelligence endpoint URL
- `AZURE_DOCUMENT_INTELLIGENCE_KEY` - Azure API key

## Running the Application

```bash
uvicorn nomoros_ai.main:app --host 0.0.0.0 --port 5000 --reload
```

## Recent Changes
- 2025-12-19: Initial project setup with Phase 1 features
  - FastAPI application structure
  - Health check endpoint
  - Document ingestion with Azure Document Intelligence OCR
  - Pydantic models for request/response handling

## User Preferences
- Simple, explicit code
- Well-commented
- No over-abstraction
- Designed for future Azure migration

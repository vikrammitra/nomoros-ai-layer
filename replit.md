# Nomoros AI API

## Overview
Legal conveyancing document processing backend API built with Python FastAPI. This service ingests PDF documents, extracts text using Azure Document Intelligence, and performs structured extraction and risk analysis for HM Land Registry Title Registers.

**Current State**: Phase 2 - Title Register extraction and risk analysis working

## Project Architecture

```
nomoros_ai/
├── main.py                          # FastAPI app entry point
├── config.py                        # Environment configuration
├── routers/
│   └── documents.py                 # Document ingestion & title-risk endpoints
├── services/
│   ├── classify.py                  # Document classification service
│   ├── ocr/
│   │   └── azure_doc_intelligence.py  # Azure Document Intelligence wrapper
│   ├── extract/
│   │   └── title.py                 # Title Register extraction service
│   └── risk/
│       └── title_rules.py           # Rule-based risk detection
├── models/
│   ├── document.py                  # Document ingestion models
│   ├── request.py                   # API request models
│   └── title.py                     # Title extraction & risk models
└── audit/                           # Reserved for future audit logging
```

## API Endpoints

- `GET /` - Root endpoint with API info
- `GET /health` - Health check (shows if Azure is configured)
- `POST /documents/ingest` - Upload PDF for OCR extraction
- `POST /documents/title-risk` - Analyze OCR text for title risks

## Required Environment Variables

- `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` - Azure Document Intelligence endpoint URL
- `AZURE_DOCUMENT_INTELLIGENCE_KEY` - Azure API key

## Running the Application

```bash
uvicorn nomoros_ai.main:app --host 0.0.0.0 --port 5000 --reload
```

## Recent Changes
- 2025-12-19: Robust OCR fallback mechanism
  - Uses prebuilt-document model (more comprehensive than layout)
  - Implements page-split fallback using pypdf for multi-page PDFs
  - Compares primary vs page-split content length, uses whichever has more
  - Tracks fallback_strategy (PRIMARY, PAGE_SPLIT, CONTENT_FALLBACK) for auditability
  - Resolves issue where page 2+ content was missing from HM Land Registry PDFs
- 2025-12-19: Phase 2 - Title Register extraction and risk analysis
  - Document classification service (detect Title Register)
  - TitleRegisterExtraction Pydantic model
  - Title extraction service with regex-based parsing
  - Rule-based risk detection (possessory title, restrictions)
  - POST /documents/title-risk endpoint
- 2025-12-19: Phase 1 - Basic OCR extraction
  - FastAPI application structure
  - Health check endpoint
  - Document ingestion with Azure Document Intelligence OCR
  - Pydantic models for request/response handling

## User Preferences
- Simple, explicit code
- Well-commented with legal rationale
- No over-abstraction
- Deterministic, auditable risk decisions
- Designed for future Azure migration

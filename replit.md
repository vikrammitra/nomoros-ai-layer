# Nomoros AI API

## Overview
Legal conveyancing document processing backend API built with Python FastAPI. This service ingests PDF documents, extracts text using Azure Document Intelligence, and performs structured extraction and risk analysis for HM Land Registry Title Registers.

**Current State**: Phase 4 - TA6 Property Information Form extraction with map-reduce strategy

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
│   │   ├── title.py                 # Title Register extraction service
│   │   ├── search_environmental.py  # Environmental Search extraction
│   │   ├── search_local_authority.py # Local Authority extraction (LLM-assisted)
│   │   └── ta6.py                   # TA6 Property Info extraction (map-reduce)
│   ├── chunking/
│   │   ├── text_chunker.py          # Generic text chunking for LLM
│   │   └── ta6_chunker.py           # TA6-specific chunking (header removal, overlap)
│   ├── risk/
│   │   ├── title_rules.py           # Rule-based risk detection
│   │   ├── search_environmental_rules.py  # Environmental risk rules
│   │   └── search_local_authority_rules.py # Local Authority risk rules
│   ├── structuring/
│   │   └── local_authority_structurer.py # Solicitor-friendly output formatting
│   └── llm/
│       └── azure_openai_client.py   # Azure OpenAI wrapper (extraction only)
├── models/
│   ├── document.py                  # Document ingestion models
│   ├── request.py                   # API request models
│   ├── title.py                     # Title extraction & risk models
│   └── ta6.py                       # TA6 extraction models (questions, sections, evidence)
└── audit/                           # Reserved for future audit logging
```

## API Endpoints

- `GET /` - Root endpoint with API info
- `GET /health` - Health check (shows if Azure is configured)
- `POST /documents/ingest` - Upload PDF for OCR extraction
- `POST /documents/title-risk` - Analyze OCR text for title risks
- `POST /documents/search-risk` - Analyze Environmental Search for risks
- `POST /documents/local-authority-risk` - Analyze Local Authority Search for risks (uses Azure OpenAI)
- `POST /documents/local-authority-risk-structured` - Same as above with solicitor-friendly grouped output
- `POST /documents/ta6-risk` - Analyze TA6 Property Information Form (uses Azure OpenAI with map-reduce)

## Required Environment Variables

- `INTERNAL_API_KEY` - Secret API key for authenticating internal service calls (required)
- `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` - Azure Document Intelligence endpoint URL
- `AZURE_DOCUMENT_INTELLIGENCE_KEY` - Azure API key
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL (optional, for Local Authority extraction)
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key (optional)
- `AZURE_OPENAI_DEPLOYMENT` - Azure OpenAI deployment name (e.g., gpt-4o)

## API Authentication

All `/documents/*` endpoints require API key authentication:

```bash
curl -X POST "https://your-api.replit.app/documents/ingest" \
  -H "x-api-key: YOUR_API_KEY" \
  -F "file=@document.pdf"
```

- **Header**: `x-api-key`
- **401 Response**: `{"detail": "Unauthorized"}` if key is missing or invalid
- **Public endpoints**: `/`, `/health` (no auth required)

## Running the Application

```bash
uvicorn nomoros_ai.main:app --host 0.0.0.0 --port 5000 --reload
```

## Recent Changes
- 2025-12-29: TA6 Property Information Form extraction and risk analysis pipeline
  - New endpoint: POST /documents/ta6-risk
  - Map-reduce strategy for large TA6 documents (30+ pages)
  - TA6-specific chunker with header/footer removal and 300 char overlap
  - Comprehensive Pydantic models: TA6Question, TA6Section, TA6ExtractionResult
  - Evidence tracking with character offsets for citation
  - Contradiction detection and follow-up question generation
  - Document metadata extraction (property address, seller names, form date)
  - DETERMINISTIC risk rules (no LLM for risk decisions):
    - HIGH: Boundary disputes, Japanese knotweed, flooding, insurance issues, contradictions
    - MEDIUM: Road schemes, unauthorized alterations, occupiers, failed sales, missing docs
    - LOW: Informal arrangements, unclear boundary ownership, incomplete answers
  - Risk categories: Boundaries, Disputes, Notices, Alterations, Environmental, Insurance, Occupiers, Services
  - 20 unit tests for models and chunker
  - Azure OpenAI integration (extraction only - risk decisions are rule-based)
  - Increased max_completion_tokens to 16000 for reasoning models
- 2025-12-21: Document classification added to ingest endpoint
  - New fields: document_type, document_type_confidence, classification_method
  - Supported types: TITLE_REGISTER, LOCAL_AUTHORITY_SEARCH, ENVIRONMENTAL_SEARCH, 
    TA6_PROPERTY_INFORMATION_FORM, TR1_TRANSFER_DEED, LEASE, UNKNOWN
  - Scoring-based confidence (matched markers / total markers)
  - Pure, testable classifier module (no LLM calls)
  - 11 unit tests covering all document types
- 2025-12-21: Structured output for Local Authority Search (solicitor-friendly)
  - New endpoint: POST /documents/local-authority-risk-structured
  - Key Issues Summary block at top (issues + clean areas)
  - Local Land Charges grouped by type: Section 106, TPO, Smoke Control
  - Planning Register entries with explicit fields: reference, description, decision, date
  - Road Adoption findings with neutral implications
  - CIL findings distinguishing regime (charging exists) vs liability (amount owed)
  - Neutral issue labels: Transaction constraint, Ongoing obligation, Environmental regulation
  - Presentation layer only - extraction and risk logic unchanged
- 2025-12-20: LOCAL AUTHORITY Search extraction and risk analysis (v2 - stable)
  - LocalAuthoritySearchExtraction Pydantic model with comprehensive fields:
    - local_land_charges (Section 106, smoke control, TPO, financial charges)
    - planning_register_entries (applications with refs, dates, outcomes)
    - enforcement_notices, planning_breaches (HIGH risk)
    - road_adoption_issues, cil_liability, further_action_details (MEDIUM risk)
    - compulsory_purchase_orders (HIGH risk)
  - Text chunking service for LLM-safe segments (3500 char chunks)
  - Azure OpenAI client (gpt-5-nano-2) for assistive extraction:
    - 4000 max_completion_tokens (allows 2000 reasoning + 2000 content)
    - 90s timeout for large documents
    - Extraction only - all risk severity decisions remain deterministic
  - Deterministic risk rules:
    - HIGH: Enforcement notices, planning breaches, CPO
    - MEDIUM: Section 106, road adoption, CIL liability, further enquiries
    - LOW: Smoke control orders, tree preservation orders
  - POST /documents/local-authority-risk endpoint
  - Tested with real 17-page Local Authority Search (5 Osprey Close, Sutton)
    - Successfully extracts: LLC, 7 planning entries, road adoption, CIL references
- 2025-12-19: SEARCH Environmental extraction and risk analysis
  - EnvironmentalSearchExtraction Pydantic model
  - Deterministic extraction: flood risk, contamination, radon, ground stability
  - Rule-based risk detection for environmental issues
  - POST /documents/search-risk endpoint
  - Tested with 56-page Landmark/Homecheck environmental report
- 2025-12-19: Size-aware chunked OCR processing
  - Configurable limits: MAX_SYNC_FILE_SIZE_MB (4MB), MAX_SYNC_PAGES (10)
  - Automatic chunking for large PDFs (Search packs, TA6, Leases)
  - Sequential chunk processing with graceful per-chunk error handling
  - Response metadata: file_size_mb, processing_mode, chunks_processed
  - Tested with 56-page, 4.9MB environmental report (12 chunks, 45K chars extracted)
- 2025-12-19: Deterministic document classifier
  - Pydantic-based DocumentClassification model
  - Supports TITLE_REGISTER, TA6, SEARCH, LEASE, UNKNOWN
  - Returns UNKNOWN if multiple document types match (ambiguity)
  - Human-readable reason field for audit trail
  - classify_document() function for routing to correct extraction pipeline
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

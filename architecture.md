# Nomoros AI — System Architecture

**Legal Conveyancing Document Processing API**

---

## Overview

Nomoros AI is a secure Python FastAPI backend that ingests PDF documents, extracts text via Azure Document Intelligence OCR, classifies document types, and performs deterministic risk analysis for legal conveyancing workflows.

---

## System Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT REQUEST                            │
│                     (Internal Services / Apps)                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API KEY AUTHENTICATION                        │
│              x-api-key header · timing-safe comparison             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FASTAPI APP                                │
│                         (main.py)                                  │
│                                                                    │
│  GET /              API info                                       │
│  GET /health        Service health + Azure config status           │
└──────────────┬───────────────────────────────────┬──────────────────┘
               │                                   │
               ▼                                   ▼
┌──────────────────────────────┐  ┌────────────────────────────────┐
│      DOCUMENTS ROUTER        │  │      COMPLIANCE ROUTER         │
│                              │  │                                │
│  POST /documents/ingest      │  │  POST /documents/compliance/   │
│  POST /documents/title-risk  │  │       ingest                   │
│  POST /documents/search-risk │  │  GET  /documents/compliance/   │
│  POST /documents/            │  │       {matter_id}              │
│       local-authority-risk-  │  │                                │
│       structured             │  │                                │
│  POST /documents/ta6-risk    │  │                                │
└──────────────┬───────────────┘  └───────────────┬────────────────┘
               │                                   │
               └───────────────┬───────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          SERVICES LAYER                             │
│                                                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │  OCR Service  │ │  Document    │ │   Text      │ │ LLM Client │ │
│  │  (Azure Doc   │ │  Classifier  │ │   Chunker   │ │ (Azure     │ │
│  │  Intelligence)│ │  (rule-based)│ │  (8K/TA6)   │ │  OpenAI)   │ │
│  └──────────────┘ └──────────────┘ └─────────────┘ └────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      EXTRACTION PIPELINES                          │
│                                                                    │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────┐ ┌────────┐ │
│  │  Title     │ │ Environ-  │ │  Local    │ │  TA6   │ │Compli- │ │
│  │ Register   │ │  mental   │ │ Authority │ │  Form  │ │ ance   │ │
│  │  (regex)   │ │  Search   │ │  (LLM-    │ │ (map-  │ │(AML/   │ │
│  │           │ │  (regex)   │ │ assisted) │ │reduce) │ │ SOF)   │ │
│  └───────────┘ └───────────┘ └───────────┘ └────────┘ └────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 RISK ANALYSIS (deterministic rules)                 │
│                                                                    │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────┐ ┌────────┐ │
│  │  Title     │ │ Environ-  │ │ LA Search │ │  TA6   │ │Compli- │ │
│  │  Rules     │ │  mental   │ │   Rules   │ │ Rules  │ │ ance   │ │
│  │           │ │  Rules     │ │           │ │        │ │ Rules  │ │
│  └───────────┘ └───────────┘ └───────────┘ └────────┘ └────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       EXTERNAL SERVICES                            │
│                                                                    │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌────────────┐ │
│  │  Azure Document     │  │  Azure OpenAI        │  │  JSON File │ │
│  │  Intelligence       │  │  (gpt-5-nano-2)      │  │  Store     │ │
│  │  (OCR)              │  │  Extraction ONLY     │  │(compliance)│ │
│  └─────────────────────┘  └─────────────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Design Principles

1. **LLM assists extraction ONLY** — Azure OpenAI is used to extract structured data from complex documents (Local Authority Searches, TA6 forms). It never decides risk severity.
2. **All risk analysis is deterministic** — Every risk severity (HIGH / MEDIUM / LOW) is assigned by auditable rule-based logic, never by an LLM.
3. **Every decision is auditable** — Risk rules include descriptions, categories, and evidence for each finding.
4. **No silent fallbacks** — The system is explicit when it fails rather than silently degrading.
5. **Timing-safe authentication** — API key comparison uses `secrets.compare_digest` to prevent timing attacks.

---

## Supported Document Types

| Document Type | Classification | Extraction Method | Risk Engine |
|---|---|---|---|
| HM Land Registry Title Register | Keyword scoring | Regex-based | title_rules.py |
| Environmental Search | Keyword scoring | Regex-based | search_environmental_rules.py |
| Local Authority Search | Keyword scoring | LLM-assisted (chunked) | search_local_authority_rules.py |
| TA6 Property Information Form | Keyword scoring | LLM map-reduce | ta6_rules.py |
| AML/ID Compliance | Keyword scoring | Regex-based | compliance_rules.py |
| Source of Funds | Keyword scoring | Regex-based | compliance_rules.py |
| TR1 Transfer Deed | Keyword scoring | — | — |
| Lease | Keyword scoring | — | — |

---

## Risk Severity Levels

| Severity | Examples |
|---|---|
| **HIGH** | Enforcement notices, planning breaches, CPO, boundary disputes, Japanese knotweed, flooding, PEP match, sanctions match |
| **MEDIUM** | Section 106 agreements, CIL liability, road adoption issues, unauthorized alterations, failed sales, large unexplained transfers |
| **LOW** | Smoke control orders, tree preservation orders, informal arrangements, unclear boundary ownership, incomplete answers |

---

## Request Flow

1. **Client** sends PDF or OCR text with `x-api-key` header
2. **Auth middleware** validates the API key (401 if missing/invalid)
3. **Ingest endpoint** sends PDF to Azure Document Intelligence for OCR
4. **Classifier** identifies document type via keyword scoring
5. **Router** dispatches to the correct extraction pipeline
6. **Extractor** parses structured data (regex or LLM-assisted)
7. **Risk engine** applies deterministic rules to extracted data
8. **Response** returns structured extraction + risk findings with severity

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `INTERNAL_API_KEY` | Yes | API key for authenticating internal service calls |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | Yes | Azure Document Intelligence endpoint URL |
| `AZURE_DOCUMENT_INTELLIGENCE_KEY` | Yes | Azure Document Intelligence API key |
| `AZURE_OPENAI_ENDPOINT` | Optional | Azure OpenAI endpoint (for LA Search / TA6 extraction) |
| `AZURE_OPENAI_API_KEY` | Optional | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Optional | Azure OpenAI deployment name (e.g., gpt-5-nano-2) |

---

## File Structure

```
nomoros_ai/
├── main.py                              # FastAPI app entry point
├── config.py                            # Environment configuration (Pydantic BaseSettings)
├── auth.py                              # API key authentication dependency
├── routers/
│   ├── documents.py                     # Document ingestion & analysis endpoints
│   └── compliance.py                    # AML/ID and Source of Funds endpoints
├── services/
│   ├── classify.py                      # Document classification (keyword scoring)
│   ├── document_classifier.py           # Extended classifier with compliance types
│   ├── ocr/
│   │   └── azure_doc_intelligence.py    # Azure Document Intelligence wrapper
│   ├── extract/
│   │   ├── title.py                     # Title Register extraction (regex)
│   │   ├── search_environmental.py      # Environmental Search extraction (regex)
│   │   ├── search_local_authority.py    # Local Authority extraction (LLM-assisted)
│   │   ├── ta6.py                       # TA6 extraction (map-reduce with LLM)
│   │   └── compliance.py               # AML/ID and SOF extraction (regex)
│   ├── chunking/
│   │   ├── text_chunker.py             # Generic text chunking (8K chars)
│   │   └── ta6_chunker.py             # TA6-specific chunking with overlap
│   ├── risk/
│   │   ├── title_rules.py              # Title Register risk rules
│   │   ├── search_environmental_rules.py # Environmental risk rules
│   │   ├── search_local_authority_rules.py # LA Search risk rules
│   │   └── compliance_rules.py         # Compliance risk rules
│   ├── structuring/
│   │   └── local_authority_structurer.py # Solicitor-friendly LA output formatting
│   └── llm/
│       ├── azure_openai_client.py       # Azure OpenAI wrapper (extraction only)
│       └── llm_compliance_summary.py    # Non-authoritative compliance summaries
├── models/
│   ├── document.py                      # Document ingestion models
│   ├── request.py                       # API request models
│   ├── classification.py               # Document classification models
│   ├── title.py                         # Title extraction & risk models
│   ├── ta6.py                           # TA6 extraction models
│   ├── compliance.py                    # Compliance models
│   ├── search_local_authority.py        # LA Search extraction models
│   └── search_local_authority_structured.py # Structured LA output models
└── audit/                               # Reserved for future audit logging
```

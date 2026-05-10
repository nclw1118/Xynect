# Xynect MVP Specification

## AI-Powered Window Extraction & Supplier Recommendation Web App

**Version:** 1.0  
**Scope:** MVP for spec coding  
**Primary Material Category:** Windows only  
**Authentication:** Not required for MVP  
**Architecture:** Next.js frontend + FastAPI backend + PostgreSQL temporary session storage  

---

## 1. Product Overview

Xynect is an AI-powered construction material supply chain platform. The MVP helps users upload a construction document, automatically extract window material information, review and correct the extracted data, and receive ranked supplier/pricing recommendations.

The MVP focuses only on **windows**. Doors and other construction materials are future expansion areas.

The product should feel like a modern AI startup: clean, technical, trustworthy, polished, and compatible with both light and dark themes.

---

## 2. MVP Goal

The MVP should prove this core workflow:

```text
User uploads one construction file
→ AI extracts window schedule and project information
→ User reviews and edits extracted values
→ User confirms the reviewed information
→ System recommends ranked suppliers and estimated pricing
```

The MVP stops at the supplier/pricing recommendation page. It does not need ordering, checkout, export, login, or persistent user accounts.

---

## 3. Supported Input Files

The MVP supports **one uploaded file per session**.

Accepted file types:

```text
PDF
JPG
JPEG
PNG
XLSX
XLS
CSV
```

Preferred input:

```text
Multi-page PDF containing window schedule, elevations, and floor plans
```

Also supported:

```text
Single-page PDF window schedule
Image file containing a window schedule or drawing
Excel / CSV file containing structured window schedule information
```

The uploaded file must be saved by the backend before processing.

MVP storage:

```text
Backend local file storage
```

Future production storage:

```text
S3-compatible object storage
```

---

## 4. High-Level User Flow

```text
Home / Landing Page
→ Upload File
→ AI Processing / Agent Progress Page
→ Extracted Window Review Page
→ User Edits Values
→ User Clicks Confirm
→ Confirmation Modal
→ User Clicks All Good
→ Supplier & Pricing Recommendation Page
```

---

## 5. Frontend Pages

### 5.1 Landing Page `/`

Purpose: introduce Xynect and guide users to upload a construction file.

Content:

```text
Company name: Xynect
Short product description
Primary upload call-to-action
Modern AI startup visual style
```

Suggested hero copy:

```text
AI-Powered Construction Material Supply Chain

Upload your construction documents and let Xynect extract window schedules, project location, quantities, and key product requirements — then match them with supplier and pricing options.
```

Primary CTA:

```text
Upload Construction File
```

Design requirements:

```text
Modern AI startup style
Light-theme and dark-theme friendly
No logo required for MVP
Clean typography
Large primary button
Subtle technical/AI visual elements
```

---

### 5.2 Upload Page `/upload`

Purpose: allow the user to upload one supported file.

Components:

```text
FileDropzone
SupportedFileTypes
UploadButton
ErrorMessage
```

Behavior:

```text
Only one file can be uploaded per session.
Accepted files: PDF, JPG, JPEG, PNG, XLSX, XLS, CSV.
After successful upload, create a temporary session and navigate to /processing/{session_id}.
```

Validation:

```text
Reject unsupported file types.
Show a clear error if upload fails.
Show a clear error if file is empty or unreadable.
```

---

### 5.3 Processing Page `/processing/[sessionId]`

Purpose: show visible AI agent progress while backend extraction runs.

Components:

```text
AgentStepList
ProgressIndicator
CurrentStepMessage
```

User-facing agent steps may include:

```text
Uploading file...
Detecting file type...
Preparing file for extraction...
Rendering document pages...
Finding window schedule pages...
Finding elevation and floor plan pages...
Extracting project information...
Extracting window tags...
Reading dimensions and product requirements...
Checking project location...
Normalizing extracted data...
Preparing review table...
```

Important:

```text
These are user-facing process steps, not hidden chain-of-thought reasoning.
```

Behavior:

```text
Poll GET /api/sessions/{session_id}/progress.
When status becomes review_ready, navigate to /review/{session_id}.
If status becomes error, show error message and allow user to return to upload.
```

---

### 5.4 Review Page `/review/[sessionId]`

Purpose: allow user to review and correct AI-extracted project and window information.

Components:

```text
ProjectInfoForm
EditableWindowTable
MissingValueWarnings
BackToUploadButton
ConfirmButton
ConfirmationModal
```

Behavior:

```text
Load extraction result from GET /api/sessions/{session_id}/extraction.
Show project-level fields in an editable panel.
Show extracted window rows in an editable table.
Track user edits for each field.
Allow user to leave missing fields empty.
Save edits through PATCH /api/sessions/{session_id}/extraction.
Confirm opens a modal.
All Good confirms and navigates to recommendations.
```

---

### 5.5 Supplier Recommendation Page `/recommendations/[sessionId]`

Purpose: show ranked supplier/pricing options for each extracted window tag.

Components:

```text
QuoteStyleTable
NaturalLanguageRecommendation
RiskNotesPanel
StartNewUploadButton
```

The MVP stops here.

---

## 6. Project-Level Extraction Fields

Extract these fields when explicitly present in the file:

```text
Project Name
Site Address
City
State
Zip Code
Detected File Type
Detected Relevant Pages
```

The state should be shown once at the project level, not repeated in every window row.

Supported initial target states for business logic:

```text
Michigan
New York
Florida
```

If state is missing or unsupported, leave it empty or mark it as unknown. Do not infer state unless clearly present in the document.

Example project extraction:

```json
{
  "project_name": "1827 Waterloo",
  "site_address": "1827 Waterloo",
  "city": "Bronx",
  "state": "NY",
  "zip_code": "10460",
  "detected_file_type": "multi_page_pdf",
  "detected_relevant_pages": {
    "window_schedule_pages": [3],
    "elevation_pages": [5, 6],
    "floor_plan_pages": [7, 8],
    "project_info_pages": [1]
  }
}
```

---

## 7. Window Review Table Schema

The review table should contain these columns:

```text
Tag
Material Type
Width
Height
Area
Quantity
Opening Type
Material
U-Value
SHGC
VT
Glass Type
Confidence
Notes
```

For MVP, `Material Type` should always be:

```text
Window
```

`Area` is included because Excel/CSV files may contain an `AREA(SF)` column. If area does not exist in the source file, leave it empty.

All fields except `Confidence` should be editable.

---

## 8. Missing Data Behavior

The system must not hallucinate missing values.

If a value is not clearly visible or explicitly present in the file, return:

```json
null
```

or:

```text
empty string
```

Frontend behavior:

```text
Show missing values as empty editable fields.
Visually flag missing fields.
Do not force the user to fill missing values.
Allow the user to proceed even if missing fields remain empty.
```

Suggested placeholder:

```text
Missing — optional
```

Suggested visual treatment:

```text
Subtle warning border or muted amber background
```

Important examples of values that must not be invented:

```text
U-Value
SHGC
VT
Glass Type
Material
Quantity
Project Address
State
```

---

## 9. User Edit Tracking

The system should track whether a user modified each field.

For every editable field, store:

```json
{
  "field_name": {
    "original_value": "36 in",
    "current_value": "38 in",
    "edited_by_user": true
  }
}
```

This allows future versions to measure extraction quality and compare AI output against user corrections.

---

## 10. File-Type-Specific Logic

### 10.1 Multi-Page PDF

This is the preferred MVP input.

Required behavior:

```text
1. Save uploaded PDF.
2. Render PDF pages into images.
3. Classify pages by type:
   - window schedule
   - elevation
   - floor plan
   - title/project info
   - irrelevant
4. Extract project-level information from title/project pages.
5. Extract window tags and specifications from schedule pages.
6. Count or verify quantities from elevation and floor plan pages if possible.
7. Normalize extracted data into the Xynect window schema.
8. Leave missing or unclear values empty.
```

For multi-page PDFs, the agent should locate the window schedule page first, then locate elevation and floor plan pages to count or verify window quantities by tag when possible.

---

### 10.2 Single-Page PDF

Required behavior:

```text
1. Save uploaded PDF.
2. Render the page as an image.
3. Treat it as a possible window schedule.
4. Extract visible window tags, dimensions, material, opening type, NFRC values, glass type, and quantity if present.
5. Extract project address/state if present.
6. Leave missing values empty.
```

Single-page PDFs may not include all information. For example, they may not include U-Value, SHGC, VT, glass type, or quantity. Those values must remain empty if not visible.

---

### 10.3 JPG / JPEG / PNG

Required behavior:

```text
1. Save uploaded image.
2. Send image to a vision-capable LLM.
3. Extract visible window tags and dimensions.
4. Use visible dimension annotations instead of page scale.
5. Extract quantity only if clearly visible or countable.
6. Extract project address/state only if explicitly present.
7. Leave missing values empty.
```

For image files, do not rely on PDF page size or drawing scale. Use visible tag annotations and dimension labels only.

---

### 10.4 Excel / CSV

Excel and CSV uploads are treated as already-structured schedule data.

The backend should not try to infer hidden project information, page types, drawings, elevations, floor plans, or visual dimensions from Excel/CSV files.

Expected table style:

```text
TAG | TYPE | U-VALUE | QUANTITY | WIDTH(FT) | LENGTH(FT) | AREA(SF)
```

For Excel / CSV:

```text
1. Save uploaded spreadsheet.
2. Parse visible rows and columns.
3. Extract only values that exist in the spreadsheet.
4. Map available columns into the normalized Xynect window schema.
5. Leave unavailable fields blank.
6. Do not hallucinate missing fields.
7. Do not attempt to extract project address/state unless explicitly present in the spreadsheet.
8. Do not attempt to count quantities from drawings.
```

Column mapping for expected Excel/CSV input:

```text
TAG          → Tag
TYPE         → Opening Type
U-VALUE      → U-Value
QUANTITY     → Quantity
WIDTH(FT)    → Width
LENGTH(FT)   → Height
AREA(SF)     → Area
```

Fields not present in the spreadsheet should remain blank:

```text
Project Name
Site Address
City
State
Zip Code
Material
SHGC
VT
Glass Type
Notes
```

For Excel/CSV, confidence should usually be high because the file is structured. Lower confidence only if column names are unclear, merged cells create ambiguity, or rows cannot be parsed reliably.

Example normalized Excel/CSV row:

```json
{
  "tag": "W3",
  "material_type": "Window",
  "width": "1 ft",
  "height": "8 ft",
  "area": "8 sf",
  "quantity": "2",
  "opening_type": "Fixed",
  "material": "",
  "u_value": "0.2",
  "shgc": "",
  "vt": "",
  "glass_type": "",
  "confidence": 0.98,
  "notes": ""
}
```

---

## 11. AI / LLM Design

### 11.1 LLM Provider

Use OpenAI for the MVP.

```text
Provider: OpenAI
Primary model: GPT-4.1
Input mode: text + rendered page images
Output mode: strict JSON
```

The backend must hide the provider behind an abstraction layer so future versions can swap in Claude, Gemini, or a domain-specific document model.

Do not hard-code OpenAI calls directly into route handlers or business logic.

Suggested backend structure:

```text
backend/app/services/llm/
├── base.py
├── openai_provider.py
└── prompts.py
```

---

### 11.2 LLM Provider Interface

Suggested interface:

```python
class LLMProvider:
    def classify_document_pages(self, pages):
        pass

    def extract_project_info(self, inputs):
        pass

    def extract_window_schedule(self, inputs):
        pass

    def normalize_to_schema(self, raw_extraction):
        pass

    def generate_recommendation_summary(self, recommendations):
        pass
```

---

### 11.3 Anti-Hallucination Prompt Rule

Every extraction prompt must include this rule:

```text
Only extract values that are clearly visible or explicitly stated in the uploaded file.
If a value is missing, unclear, cropped, or ambiguous, return null or an empty string.
Do not infer or invent U-Value, SHGC, VT, glass type, material, quantity, project address, city, state, or zip code.
```

---

### 11.4 Strict JSON Output

The extraction model should return strict JSON matching this shape:

```json
{
  "project": {
    "project_name": "",
    "site_address": "",
    "city": "",
    "state": "",
    "zip_code": "",
    "detected_file_type": "",
    "detected_relevant_pages": {}
  },
  "windows": [
    {
      "tag": "",
      "material_type": "Window",
      "width": "",
      "height": "",
      "area": "",
      "quantity": "",
      "opening_type": "",
      "material": "",
      "u_value": "",
      "shgc": "",
      "vt": "",
      "glass_type": "",
      "confidence": 0.0,
      "notes": ""
    }
  ],
  "warnings": []
}
```

---

## 12. Agentic Extraction Pipeline

The MVP should have an agent-style extraction pipeline, even if the first implementation is simple.

Pipeline:

```text
1. Receive upload
2. Save original file
3. Create temporary session
4. Detect file type
5. Prepare file for extraction
6. Branch by file type:
   - PDF: render pages and classify pages
   - Image: process as visual input
   - Excel/CSV: parse structured rows
7. Extract project information when available
8. Extract window rows
9. Verify or count quantities when possible
10. Normalize extracted data
11. Validate against schema
12. Flag missing values
13. Save extraction result to temporary session database
14. Return extraction result to frontend
```

Important branching rule:

```text
Excel/CSV files skip PDF rendering, page classification, elevation detection, floor plan detection, and visual quantity counting.
```

---

## 13. Confirmation Modal

When the user clicks `Confirm` on the review page, show a floating modal.

Modal copy:

```text
Are you done reviewing the extracted window information?

You can still go back and make changes. Once confirmed, Xynect will use this information to generate supplier and pricing recommendations.
```

Buttons:

```text
Cancel
All Good
```

Behavior:

```text
Cancel: close modal and return to review page.
All Good: save confirmed extraction, generate supplier recommendations, and navigate to recommendations page.
```

---

## 14. Supplier Recommendation Page

### 14.1 Recommendation Style

The recommendation should feel similar to a ChatGPT response:

```text
1. Quote-style table first
2. Natural-language explanation below
```

The recommendation should show multiple ranked suppliers for each window tag.

---

### 14.2 Quote-Style Table Columns

```text
Tag
Supplier
Unit Price
Quantity
Estimated Total
Lead Time
Match Score
Match Reason
Risk Notes
```

Example:

```text
Tag | Supplier | Unit Price | Quantity | Estimated Total | Lead Time | Match Score | Match Reason | Risk Notes
W1  | Northline Glass Supply | $420 | 8 | $3,360 | 14 days | 92% | Strong match for aluminum casement windows in NY | Verify U-Value before order
W1  | BlueRidge Window Co. | $395 | 8 | $3,160 | 21 days | 87% | Lower price, supports similar size and material | Longer lead time
```

---

### 14.3 Natural-Language Explanation

Example:

```text
For tag W1, Northline Glass Supply is the strongest recommendation because it supports the detected aluminum casement window type, has a strong regional match for New York, and offers a shorter lead time. BlueRidge Window Co. is a lower-cost alternative, but the longer lead time may create scheduling risk. Because U-Value and SHGC are missing, these should be verified before placing an order.
```

---

## 15. Fake Supplier Database

For MVP, implement a minimal fake supplier database using PostgreSQL seed data.

Use fake company names.

Example suppliers:

```text
Northline Glass Supply
BlueRidge Window Co.
MetroFrame Systems
ClearView Building Products
Sunbelt Architectural Windows
```

### 15.1 Supplier Fields

```text
Supplier ID
Supplier Name
Supported States
Supported Material Types
Supported Opening Types
Supported Window Materials
Supported Glass Types
Min Width
Max Width
Min Height
Max Height
Base Unit Price
Lead Time Days
Reliability Score
Notes
```

---

## 16. Supplier Matching Logic

For each window tag, calculate supplier match score using simple weighted rules.

Suggested scoring:

```text
State match: 25 points
Material type match: 15 points
Opening type match: 15 points
Window material match: 15 points
Size range match: 15 points
Glass type match: 5 points
Lead time advantage: 5 points
Reliability score: 5 points
```

Total:

```text
100 points
```

Missing field behavior:

```text
If a field is missing, do not heavily penalize the supplier.
Instead, reduce certainty slightly and add a risk note.
```

Example risk notes:

```text
U-Value missing; supplier compliance should be verified.
Quantity missing; total price uses quantity of 1 as placeholder.
State missing; regional supplier match is based on general availability.
Glass type missing; verify glazing requirements before ordering.
```

---

## 17. Pricing Logic

MVP pricing can be simple and deterministic.

Suggested formula:

```text
unit_price = supplier.base_unit_price * size_factor * opening_type_factor * material_factor
estimated_total = unit_price * quantity
```

If quantity is missing:

```text
Use quantity = 1 for price preview.
Add risk note: "Quantity missing; total price uses quantity of 1 as placeholder."
```

If width or height is missing:

```text
Use supplier base unit price.
Add risk note: "Size missing; unit price is an approximate base price."
```

---

## 18. Session and Persistence Design

Use temporary database-backed sessions.

Database:

```text
PostgreSQL
```

Why:

```text
The user moves across multiple pages.
AI extraction may take time.
Edited data should not disappear on refresh.
Future expansion may need quote history or user accounts.
```

Session expiration:

```text
24 hours
```

Each session stores:

```text
Uploaded file metadata
Extracted project info
Extracted window rows
User-edited values
Confirmed extraction status
Supplier recommendations
Created timestamp
Expiration timestamp
```

No login is required.

---

## 19. Recommended Tech Stack

### 19.1 Frontend

```text
Next.js
React
TypeScript
Tailwind CSS
shadcn/ui
```

Responsibilities:

```text
Landing page
File upload UI
Agent progress UI
Review table
Editable fields
Confirmation modal
Supplier recommendation page
API communication with backend
```

---

### 19.2 Backend

```text
FastAPI
Python
Pydantic
SQLAlchemy or SQLModel
PostgreSQL
```

Responsibilities:

```text
Upload handling
File storage
File type detection
PDF/image/spreadsheet preprocessing
LLM orchestration
Agent pipeline
Temporary session persistence
Supplier fake database
Supplier ranking logic
API responses
```

---

### 19.3 File Processing Libraries

Suggested Python libraries:

```text
PyMuPDF or pdf2image for PDF rendering
Pillow for image processing
pandas for Excel/CSV parsing
openpyxl for XLSX support
python-multipart for file uploads
```

---

## 20. API Specification

### 20.1 Upload File

```http
POST /api/sessions/upload
```

Purpose:

```text
Upload one construction file and start extraction.
```

Request:

```text
multipart/form-data
file: PDF/JPG/JPEG/PNG/XLSX/XLS/CSV
```

Response:

```json
{
  "session_id": "uuid",
  "status": "processing",
  "message": "File uploaded successfully. Extraction started."
}
```

---

### 20.2 Get Agent Progress

```http
GET /api/sessions/{session_id}/progress
```

Response:

```json
{
  "session_id": "uuid",
  "status": "processing",
  "current_step": "Extracting window tags",
  "steps": [
    {
      "name": "Uploading file",
      "status": "completed"
    },
    {
      "name": "Detecting file type",
      "status": "completed"
    },
    {
      "name": "Extracting window tags",
      "status": "active"
    },
    {
      "name": "Preparing review table",
      "status": "pending"
    }
  ]
}
```

MVP can simulate progress if processing is synchronous, but the API should be shaped for future async processing.

---

### 20.3 Get Extraction Result

```http
GET /api/sessions/{session_id}/extraction
```

Response:

```json
{
  "session_id": "uuid",
  "project": {
    "project_name": "1827 Waterloo",
    "site_address": "1827 Waterloo",
    "city": "Bronx",
    "state": "NY",
    "zip_code": "10460",
    "detected_file_type": "multi_page_pdf",
    "detected_relevant_pages": {
      "window_schedule_pages": [2],
      "elevation_pages": [4, 5],
      "floor_plan_pages": [6]
    }
  },
  "windows": [
    {
      "id": "row_uuid",
      "tag": "W1",
      "material_type": "Window",
      "width": "36 in",
      "height": "60 in",
      "area": "15 sf",
      "quantity": "8",
      "opening_type": "Casement",
      "material": "Metal",
      "u_value": "0.38",
      "shgc": "0.36",
      "vt": "0.34",
      "glass_type": "Clear",
      "confidence": 0.91,
      "notes": ""
    }
  ],
  "warnings": [
    "Some NFRC values are missing. Please review before confirming."
  ]
}
```

---

### 20.4 Update Extraction

```http
PATCH /api/sessions/{session_id}/extraction
```

Purpose:

```text
Save user edits from the review table.
```

Request:

```json
{
  "project": {
    "project_name": "1827 Waterloo",
    "site_address": "1827 Waterloo",
    "city": "Bronx",
    "state": "NY",
    "zip_code": "10460"
  },
  "windows": [
    {
      "id": "row_uuid",
      "tag": "W1",
      "material_type": "Window",
      "width": "36 in",
      "height": "60 in",
      "area": "15 sf",
      "quantity": "8",
      "opening_type": "Casement",
      "material": "Metal",
      "u_value": "",
      "shgc": "",
      "vt": "",
      "glass_type": "",
      "confidence": 0.91,
      "notes": "NFRC values not found in file."
    }
  ]
}
```

Response:

```json
{
  "session_id": "uuid",
  "status": "saved"
}
```

---

### 20.5 Confirm Extraction

```http
POST /api/sessions/{session_id}/confirm
```

Purpose:

```text
Mark extraction as user-confirmed and trigger supplier recommendation.
```

Response:

```json
{
  "session_id": "uuid",
  "status": "confirmed",
  "next": "/recommendations/uuid"
}
```

---

### 20.6 Get Supplier Recommendations

```http
GET /api/sessions/{session_id}/recommendations
```

Response:

```json
{
  "session_id": "uuid",
  "quote_table": [
    {
      "tag": "W1",
      "supplier": "Northline Glass Supply",
      "unit_price": 420,
      "quantity": 8,
      "estimated_total": 3360,
      "lead_time_days": 14,
      "match_score": 0.92,
      "match_reason": "Strong match for aluminum casement windows in NY.",
      "risk_notes": "Verify U-Value before order."
    }
  ],
  "natural_language_summary": "For tag W1, Northline Glass Supply is the strongest recommendation..."
}
```

---

## 21. Data Models

### 21.1 Session

```ts
Session {
  id: string
  status: "uploaded" | "processing" | "review_ready" | "confirmed" | "recommendation_ready" | "error"
  uploaded_file_path: string
  uploaded_file_name: string
  uploaded_file_type: string
  created_at: datetime
  expires_at: datetime
}
```

---

### 21.2 ProjectInfo

```ts
ProjectInfo {
  id: string
  session_id: string
  project_name?: string
  site_address?: string
  city?: string
  state?: string
  zip_code?: string
  detected_file_type?: string
  detected_relevant_pages?: object
}
```

---

### 21.3 WindowItem

```ts
WindowItem {
  id: string
  session_id: string
  tag?: string
  material_type: "Window"
  width?: string
  height?: string
  area?: string
  quantity?: string
  opening_type?: string
  material?: string
  u_value?: string
  shgc?: string
  vt?: string
  glass_type?: string
  confidence: number
  notes?: string
  original_extraction?: object
  user_edits?: object
}
```

---

### 21.4 Supplier

```ts
Supplier {
  id: string
  name: string
  supported_states: string[]
  supported_material_types: string[]
  supported_opening_types: string[]
  supported_window_materials: string[]
  supported_glass_types: string[]
  min_width?: number
  max_width?: number
  min_height?: number
  max_height?: number
  base_unit_price: number
  lead_time_days: number
  reliability_score: number
  notes?: string
}
```

---

### 21.5 Recommendation

```ts
Recommendation {
  id: string
  session_id: string
  window_item_id: string
  supplier_id: string
  tag: string
  unit_price: number
  quantity: number
  estimated_total: number
  lead_time_days: number
  match_score: number
  match_reason: string
  risk_notes: string
}
```

---

## 22. Backend Folder Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── sessions.py
│   │   ├── extraction.py
│   │   └── recommendations.py
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── models/
│   │   ├── session.py
│   │   ├── project.py
│   │   ├── window_item.py
│   │   ├── supplier.py
│   │   └── recommendation.py
│   ├── schemas/
│   │   ├── session.py
│   │   ├── extraction.py
│   │   └── recommendation.py
│   ├── services/
│   │   ├── file_storage.py
│   │   ├── file_detection.py
│   │   ├── pdf_processing.py
│   │   ├── image_processing.py
│   │   ├── spreadsheet_processing.py
│   │   ├── extraction_agent.py
│   │   ├── supplier_matching.py
│   │   └── recommendation_writer.py
│   ├── services/llm/
│   │   ├── base.py
│   │   ├── openai_provider.py
│   │   └── prompts.py
│   └── seed/
│       └── suppliers.py
```

---

## 23. Frontend Folder Structure

```text
frontend/
├── app/
│   ├── page.tsx
│   ├── upload/
│   │   └── page.tsx
│   ├── processing/
│   │   └── [sessionId]/
│   │       └── page.tsx
│   ├── review/
│   │   └── [sessionId]/
│   │       └── page.tsx
│   └── recommendations/
│       └── [sessionId]/
│           └── page.tsx
├── components/
│   ├── FileDropzone.tsx
│   ├── AgentProgress.tsx
│   ├── ProjectInfoForm.tsx
│   ├── EditableWindowTable.tsx
│   ├── ConfirmationModal.tsx
│   ├── QuoteTable.tsx
│   └── RecommendationSummary.tsx
├── lib/
│   ├── api.ts
│   └── types.ts
└── styles/
```

---

## 24. Error Handling

### 24.1 Upload Errors

Handle:

```text
Unsupported file type
Empty file
File too large
Upload failure
```

### 24.2 Extraction Errors

Handle:

```text
Unreadable PDF
Image too blurry
Spreadsheet has no usable rows
LLM extraction failure
JSON validation failure
No window rows detected
```

If no window rows are detected:

```text
Show a friendly error and allow user to return to upload.
Do not generate supplier recommendations.
```

### 24.3 Recommendation Errors

Handle:

```text
No supplier match found
Missing quantity
Missing dimensions
Missing state
```

If no supplier is a strong match:

```text
Still show the closest available fake suppliers.
Add risk notes explaining missing or weak match fields.
```

---

## 25. MVP Acceptance Criteria

The MVP is complete when:

```text
1. User can open the Xynect landing page.
2. User can upload one supported file.
3. Backend saves the uploaded file.
4. Backend creates a temporary database-backed session.
5. Backend detects file type.
6. Backend correctly branches extraction logic by file type.
7. Backend extracts project-level fields when explicitly available.
8. Backend extracts window rows into the required schema.
9. Excel/CSV extraction only parses existing table values and leaves unavailable fields blank.
10. Missing values are left empty and visually flagged.
11. User can edit project info and window table fields.
12. User changes are saved to the temporary session database.
13. User edits are tracked against original extraction values.
14. User can click Confirm and see a confirmation modal.
15. User can click All Good.
16. Backend saves confirmed extraction.
17. Backend generates fake supplier/pricing recommendations.
18. Supplier recommendation page shows quote-style table first.
19. Supplier recommendation page shows natural-language explanation below.
20. No login is required.
```

---

## 26. Future Expansion Notes

The architecture should leave room for:

```text
Door extraction
Other material categories
User accounts
Persistent project history
Real supplier database
Real-time supplier API integrations
Compliance checking by state
Multi-file upload
Quantity reconciliation between schedule, elevation, and floor plan
Human-in-the-loop review workflow
Export quote as PDF or CSV
Procurement workflow
Payment / ordering workflow
Advanced supplier optimization
Model comparison between OpenAI, Claude, Gemini, and domain-specific models
```

---

## 27. Final Implementation Principle

The MVP should be minimal, but the architecture should stay modular.

```text
Frontend = user interaction
Backend = file processing, AI orchestration, data persistence, supplier matching
LLM layer = replaceable provider
Supplier logic = simple now, expandable later
Session storage = temporary PostgreSQL-backed persistence
```

Core rule:

```text
Do not hallucinate missing construction data. Extract what exists, flag what is missing, and let the user decide whether to fill it.
```

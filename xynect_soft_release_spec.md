# Xynect Soft Release Specification

## 1. Purpose

This document defines the scope for the **Sunday soft release** of Xynect.

Xynect is an AI-powered construction material supply chain MVP. The current stable product already supports:

- One-file upload
- Processing/progress flow
- Deterministic Excel/CSV extraction
- Editable window extraction table
- Supplier recommendation generation
- Grouped recommendation display by window tag

The soft release focuses on **product polish and workflow presentation**, not deep extraction algorithm changes.

The goal is to make the application feel more like a modern AI product/workspace, inspired by the visual/product structure of Panel AI's agents page, while preserving the existing functional backend flow.

Reference style direction:
- Modern AI SaaS
- Product workspace
- Left agent/activity panel
- Right tabbed work area
- Clean cards, tabs, and grouped data sections
- Light/dark-theme friendly

---

## 2. Current Stable Baseline

The last stable committed milestone is:

```text
Implement supplier recommendation flow
```

Stable implemented features:

```text
Next.js frontend
FastAPI backend
PostgreSQL database
Docker Compose PostgreSQL
Session-based upload flow
Deterministic Excel/CSV extraction
Editable review table
Project info form
Supplier matching and pricing recommendations
Grouped recommendation table by tag
Natural-language recommendation explanation
```

Important note:

```text
OpenAI/PDF/image extraction work is currently WIP and should NOT be touched during this soft-release UI phase unless explicitly requested.
```

---

## 3. High-Level Soft Release Goal

After the user uploads a valid file and processing finishes, the user should land on a new workspace page:

```text
/workspace/[sessionId]
```

The workspace should replace the current experience of jumping separately between review and recommendation pages.

The new workspace page should have:

```text
Left panel:
Agent/chat-style panel showing processing/extraction steps and future AI interaction placeholders.

Right panel:
Tabbed workspace with:
1. Extraction Result
2. Recommendation
```

The user should be able to:

```text
Upload file
→ watch processing steps
→ enter workspace
→ review/edit extracted window data
→ add missing windows manually
→ switch to recommendation tab
→ generate/refresh supplier recommendations from latest edited data
→ export recommendations as CSV or PDF report
```

---

## 4. Non-Goals for Soft Release

Do NOT implement these in this phase:

```text
Authentication
Multi-file upload
Real supplier APIs
Payment/order workflow
Quote ordering
Email sending
Cloud storage
Backend-generated PDF service
Major extraction algorithm refactor
New material extraction logic for doors/walls
OpenAI extraction quality fixes unless explicitly requested
```

Do NOT break existing:

```text
Upload flow
CSV/XLSX deterministic extraction
Processing progress API
Editable extraction table
Supplier recommendation generation
Grouped recommendation display
```

---

## 5. New User Flow

### Current flow

```text
Home
→ Upload
→ Processing
→ Review
→ Confirm
→ Recommendations
```

### Soft-release flow

```text
Home
→ Upload
→ Processing
→ Workspace
   ├── Extraction Result tab
   └── Recommendation tab
```

Required route change:

```text
When processing finishes and session.status becomes review_ready,
redirect to:
/workspace/[sessionId]
instead of:
/review/[sessionId]
```

Keep old routes if they already exist:

```text
/review/[sessionId]
/recommendations/[sessionId]
```

They may remain as fallback routes, but the preferred product flow should use `/workspace/[sessionId]`.

---

## 6. Workspace Page Layout

Route:

```text
/frontend/app/workspace/[sessionId]/page.tsx
```

### Overall layout

The page should be split into two major areas:

```text
Left: Agent Panel
Right: Tabbed Workspace
```

Suggested desktop layout:

```text
Full viewport height
Left panel: 320–400px wide
Right panel: flexible width
```

Mobile responsiveness can be basic for soft release. Desktop-first is acceptable.

---

## 7. Left Agent Panel

The left panel should look like a chatbot/AI-agent side panel.

### Purpose

For this release, it is mostly presentational but should display useful progress information.

### Required content

The left panel should include:

```text
Xynect Agent / AI Extraction Agent title
Current session/file context if available
Processing/extraction steps
Placeholder action buttons marked COMING SOON
Placeholder chat input marked COMING SOON
```

### Agent steps

Reuse the current progress step data from:

```http
GET /api/sessions/{session_id}/progress
```

Display steps such as:

```text
Uploading file
Detecting file type
Saving file
Preparing extraction
Loading spreadsheet
Detecting columns
Mapping fields
Saving extracted rows
Extraction complete
```

For completed sessions, this panel should still show completed steps, not disappear.

### Placeholder controls

Show visual buttons/cards with icons, but they should be disabled or non-functional:

```text
Upload Files — COMING SOON
Select Model — COMING SOON
Ask Xynect Agent — COMING SOON
```

The chat input should look like a real input area but be disabled with placeholder text:

```text
Chat with Xynect Agent — Coming Soon
```

### Important

Do not implement actual chat, model selection, or new upload behavior in this phase.

---

## 8. Right Workspace Panel

The right panel should be tabbed.

Tabs:

```text
Extraction Result
Recommendation
```

Use clean tab styling similar to modern AI product dashboards.

The right panel should feel like a product work area rather than a simple form page.

---

## 9. Extraction Result Tab

The Extraction Result tab should reuse and improve the current review functionality.

### Required sections

Show building material categories:

```text
Windows
Doors
Walls
```

### Material category behavior

```text
Windows: enabled
Doors: COMING SOON
Walls: COMING SOON
```

Doors and walls should be visible as cards/sections/placeholders, but not functional.

Example placeholder text:

```text
Door extraction is coming soon.
Wall extraction is coming soon.
```

### Windows section

The Windows section should include:

```text
Project info form
Editable window extraction table
Missing value highlighting
Autosave behavior
Add Window button
```

Existing review behavior must continue to work:

```text
Users can edit extracted values.
Missing values are highlighted but optional.
Confidence is read-only.
Edits persist through PATCH /api/sessions/{session_id}/extraction.
```

### Window table columns

Keep existing table columns:

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

### Add Window feature

Add:

```text
+ Add Window
```

Purpose:

```text
If extraction misses one or two tags, user can manually add them.
```

Behavior:

```text
Click + Add Window
→ backend creates a new blank WindowItem row
→ material_type = "Window"
→ all editable fields blank
→ confidence = 0
→ notes may be "Manually added by user"
→ row appears immediately in the table
→ user can edit it like other rows
```

Likely backend endpoint:

```http
POST /api/sessions/{session_id}/windows
```

Response should return the new WindowItem object.

Optional, not required for soft release:

```http
DELETE /api/sessions/{session_id}/windows/{window_item_id}
```

If delete is easy, implement it. If it risks scope creep, skip it.

---

## 10. Real-Time Recommendation Dependency

The Recommendation tab must use the latest edited extraction details.

Meaning:

```text
If user edits quantity, dimensions, material, opening type, etc. in Extraction Result,
then opens Recommendation,
the recommendation should be generated from those latest values.
```

Simple implementation:

```text
When the user opens the Recommendation tab:
1. Ensure current extraction edits are saved.
2. Call POST /api/sessions/{session_id}/confirm.
3. Backend regenerates recommendations from current WindowItem rows.
4. Fetch GET /api/sessions/{session_id}/recommendations.
5. Render recommendation results.
```

Backend requirement:

```text
POST /api/sessions/{session_id}/confirm must be idempotent.
```

Idempotent behavior:

```text
If Recommendation rows already exist for this session:
- delete existing recommendation rows for that session
- regenerate fresh recommendation rows
- avoid duplicate rows
```

This is important because users may switch between tabs multiple times.

---

## 11. Recommendation Tab

The Recommendation tab should keep the previous grouped recommendation layout.

### Required layout

Recommendations should be grouped by tag.

Example:

```text
Tag A1
Recommended Supplier: Supplier X

Rank | Supplier | Unit Price | Quantity | Estimated Total | Lead Time | Match Score | Match Reason | Risk Notes
#1   | Supplier X | ...
#2   | Supplier Y | ...
#3   | Supplier Z | ...

Tag A2
...
```

Do not show one flat table where repeated tags make it look like there are more material tags than actually exist.

### Required behavior

```text
Top supplier per tag should be clearly labeled Recommended.
Other suppliers are alternatives.
Rows should be ranked #1, #2, #3.
Risk notes should remain visible.
```

### Recommendation summary length

The natural-language explanation should be useful but not overly long.

Target:

```text
2–3 short paragraphs total when possible.
If many tags exist, use concise grouped paragraphs.
```

The explanation should cover:

```text
Best supplier choices
Price/lead-time tradeoffs
Missing field or compliance risks
```

Avoid:

```text
Long ChatGPT-style essay
Excessive repetition per supplier
Overly verbose paragraphs
```

---

## 12. Export Feature

Add an Export button or export controls at the end of the Recommendation tab.

Required export options:

```text
Export CSV
Export PDF Report
```

### Export CSV

Purpose:

```text
Let users open recommendation table in Excel/Sheets.
```

Behavior:

```text
Downloads a .csv file.
```

CSV columns:

```text
Tag
Rank
Supplier
Unit Price
Quantity
Estimated Total
Lead Time
Match Score
Match Reason
Risk Notes
```

Suggested filename:

```text
xynect_recommendations_{sessionId}.csv
```

### Export PDF Report

Use a browser print/save-as-PDF approach for soft release.

Do NOT implement complex backend PDF generation in this phase.

Behavior:

```text
Click Export PDF Report
→ open a clean printable report view/modal/page
→ include table + summary
→ trigger browser print dialog with window.print()
→ user can choose Save as PDF
```

The report should include:

```text
Xynect title/header
Generated timestamp
Project/session info if available
Grouped recommendation table
Recommendation summary
Risk notes
```

This is preferred over HTML export because it is more user-friendly for non-technical users.

Implementation options:

```text
Option A:
Create /workspace/[sessionId]/print or /report/[sessionId] route.

Option B:
Open printable modal/section and call window.print().
```

Choose the simpler and cleaner implementation.

---

## 13. Visual Style Requirements

The UI should feel:

```text
Modern
Technical
AI-startup style
Clean
Readable
Light/dark friendly
```

Inspired by Panel AI-style workspace/product layout, but do not copy exact branding.

Suggested style elements:

```text
Rounded cards
Subtle borders
Muted backgrounds
Clean tab navigation
Agent-side panel
Status badges
"Coming Soon" badges
Compact but readable tables
Good spacing
```

Avoid:

```text
Overly colorful UI
Messy dense tables without grouping
Unstyled default HTML controls
Large walls of text
```

---

## 14. Backend API Cheat Sheet

Existing APIs likely used:

```http
POST /api/sessions/upload
GET /api/sessions/{session_id}/progress
GET /api/sessions/{session_id}/extraction
PATCH /api/sessions/{session_id}/extraction
POST /api/sessions/{session_id}/confirm
GET /api/sessions/{session_id}/recommendations
```

New API likely needed:

```http
POST /api/sessions/{session_id}/windows
```

Optional API:

```http
DELETE /api/sessions/{session_id}/windows/{window_item_id}
```

No new auth APIs.

No real supplier APIs.

No payment APIs.

---

## 15. Frontend Files Likely Involved

Likely create:

```text
frontend/app/workspace/[sessionId]/page.tsx
frontend/components/workspace/AgentPanel.tsx
frontend/components/workspace/WorkspaceTabs.tsx
frontend/components/workspace/MaterialSection.tsx
frontend/components/workspace/ExportControls.tsx
frontend/components/workspace/PrintableRecommendationReport.tsx
```

Likely reuse/modify:

```text
frontend/components/ProjectInfoForm.tsx
frontend/components/EditableWindowTable.tsx
frontend/components/QuoteTable.tsx
frontend/components/RecommendationSummary.tsx
frontend/components/AgentProgress.tsx
frontend/app/processing/[sessionId]/page.tsx
frontend/lib/types.ts
frontend/lib/api.ts
```

Likely backend modify/create:

```text
backend/app/api/extraction.py
backend/app/api/recommendations.py
backend/app/services/recommendation_writer.py
backend/app/services/supplier_matching.py
```

---

## 16. Implementation Phases

### Phase A — Workspace shell

Implement:

```text
/workspace/[sessionId]
left agent panel
right tabs
processing redirects to workspace instead of review
```

Do not implement Add Window or export yet.

### Phase B — Extraction tab

Implement:

```text
Project info form inside Extraction Result tab
Window table inside Extraction Result tab
Windows enabled
Doors/Walls Coming Soon
+ Add Window
```

### Phase C — Recommendation tab

Implement:

```text
Recommendation tab
regenerate recommendations on tab open
idempotent confirm endpoint
grouped recommendation rendering
shorter recommendation summary
```

### Phase D — Export

Implement:

```text
Export CSV
Export PDF Report via print/save-as-PDF
```

---

## 17. Manual Acceptance Criteria

Before soft release, manually verify:

```text
1. User can upload a CSV/XLSX.
2. Processing page shows progress.
3. User is redirected to /workspace/[sessionId].
4. Left agent panel shows completed extraction steps.
5. Coming Soon placeholders are visible.
6. Extraction Result tab opens by default.
7. Windows section is enabled.
8. Doors and Walls show Coming Soon.
9. Existing extracted windows appear.
10. User can edit a window row.
11. User can add a new window manually.
12. Edits persist after refresh.
13. User can switch to Recommendation tab.
14. Recommendations regenerate from latest extraction data.
15. No duplicate recommendation rows after switching tabs multiple times.
16. Recommendations are grouped by tag.
17. Natural-language summary is 2–3 short paragraphs when possible.
18. Export CSV downloads correctly.
19. Export PDF Report opens printable report and browser print dialog.
20. Existing old pages are not broken, or at least the main new flow works.
```

---

## 18. Release Priority

For Sunday soft release, prioritize in this order:

```text
1. Workspace page shell
2. Extraction Result tab
3. Add Window
4. Recommendation tab
5. Idempotent recommendation regeneration
6. Export CSV
7. Export PDF Report
8. Visual polish
```

If time is limited, the first six are more important than perfect PDF report styling.

---

## 19. Claude Implementation Instruction

When implementing, do NOT make one giant risky change.

Recommended Claude workflow:

```text
Prompt 1:
Read this spec and create a short implementation plan. Do not code.

Prompt 2:
Implement Phase A + Phase B only. Then stop.

Prompt 3:
Implement Phase C only. Then stop.

Prompt 4:
Implement Phase D only. Then stop.

Prompt 5:
Run/check build and summarize manual testing steps.
```

Each phase should be tested and committed separately.

---

## 20. Git Strategy

Before starting soft-release UI work, make sure the working tree is clean or stash unrelated WIP.

Recommended:

```bash
git status
git stash push -m "wip openai extraction quality fixes"
git checkout -b soft-release-ui
```

Commit after each phase:

```bash
git add .
git commit -m "Add workspace UI shell and extraction tab"

git add .
git commit -m "Add workspace recommendation tab"

git add .
git commit -m "Add recommendation CSV PDF export"
```

---

## 21. Important Reminder

The soft release is primarily about making the MVP feel usable and productized.

Do not let extraction algorithm instability derail the release UI work.

For demo stability, the release can rely on:

```text
CSV/XLSX deterministic extraction
Stub PDF/image extraction if necessary
Existing supplier recommendation flow
New polished workspace UI
```

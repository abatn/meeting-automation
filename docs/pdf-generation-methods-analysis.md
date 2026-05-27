# PDF Generation Methods - Complete Analysis

## Overview

There are **4 distinct PDF generation methods** in the system:

| # | Method | Technology | Source | Output |
|---|--------|-----------|--------|--------|
| 1 | **HTML → PDF** (WeasyPrint) | WeasyPrint | Database content (HTML) | Local file |
| 2 | **DOCX → PDF** (OnlyOffice Converter) | OnlyOffice Converter API | DOCX from S3 | PDF in S3 |
| 3 | **Invoice PDF** (WeasyPrint) | WeasyPrint | Invoice template | S3 |
| 4 | **Dummy PDF** (Fallback) | Raw PDF bytes | Hardcoded | Local file |

---

## Method 1: HTML → PDF (WeasyPrint)

### Location
- **File**: `backend/app/services/pdf_service.py`
- **Method**: `generate_pv_pdf()` (line 59-270)
- **Converter**: `_convert_html_to_pdf()` (line 272-300)

### Flow
```
1. Load PV data from DB (with client_id filter)
   → PV, Meeting, Participants, Agendas, Sections, Actions
2. Check language mismatch → Translate via Mistral if needed
3. Load BrandingSettings (logo, watermark, footer)
4. Render HTML template: pv_template.html
5. Convert HTML → PDF via WeasyPrint
   → HTML(string=html).write_pdf(filepath)
6. Return local file path: /tmp/pv_{pv_id}_{uuid}.pdf
```

### Used By
| Endpoint | File | Line |
|----------|------|------|
| `GET /pv/{pv_id}/pdf` | `pv.py` | 201-208 (Fallback) |
| `GET /reports/automation/pdf/{meeting_id}` | `reports.py` | 160-162 |

### Key Characteristics
- ✅ Multi-language support (ar, fr, en)
- ✅ Branding/watermark support
- ✅ ISO 27001 compliant (client_id filtering)
- ❌ Does NOT use OnlyOffice-edited content
- ❌ Generates from database HTML content only

### Code Snippet
```python
# pdf_service.py:294
HTML(string=html).write_pdf(filepath)
```

---

## Method 2: DOCX → PDF (OnlyOffice Converter)

### Location
- **File**: `backend/app/api/v1/pv.py`
- **Function**: `run_pdf_conversion()` (line 34-89)

### Flow
```
1. Triggered by OnlyOffice callback (status 2 or 6)
2. Call OnlyOffice converter: POST http://onlyoffice/converter
   → Input: DOCX from S3 via backend download URL
   → Output: PDF URL from converter
3. Download PDF from converter response
4. Upload PDF to S3: pv_exports/{pv_id}/final_document.pdf
5. Clear Redis status key: pdf_converting_{pv_id}
```

### Used By
| Trigger | File | Line |
|---------|------|------|
| OnlyOffice callback | `pv.py` | 427 (background task) |

### Key Characteristics
- ✅ Uses OnlyOffice-edited DOCX content
- ✅ Runs in background (non-blocking)
- ✅ Stores result in S3
- ✅ Redis sync-state for conversion tracking
- ❌ Only triggered when document is edited in OnlyOffice

### Code Snippet
```python
# pv.py:42-84
conv_url = "http://onlyoffice/converter"
source_url = f"http://backend:8000/api/v1/pv/{pv_id}/onlyoffice/download?file_key={docx_key}"
payload = {
    "async": False,
    "filetype": "docx",
    "key": f"{pv_id}_{uuid.uuid4().hex[:8]}",
    "outputtype": "pdf",
    "url": source_url,
}
# ... JWT token, POST request, download PDF, upload to S3
```

---

## Method 3: Invoice PDF (WeasyPrint)

### Location
- **File**: `backend/app/services/pdf_service.py`
- **Method**: `generate_invoice_pdf()` (line 323-351)

### Flow
```
1. Load invoice_template.html
2. Render with invoice_data
3. Generate PDF in memory: HTML(string=html).write_pdf()
4. Upload to S3: invoices/facture_{invoice_id}.pdf
5. Return download URL
```

### Used By
| Service | File | Line |
|---------|------|------|
| BillingService | `billing_service.py` | 176 |

### Key Characteristics
- ✅ In-memory generation (no temp file)
- ✅ S3 storage
- ❌ Not related to meeting PVs

---

## Method 4: Dummy PDF (Fallback)

### Location
- **File**: `backend/app/services/pdf_service.py`
- **Method**: `_convert_html_to_pdf()` (line 274-291)

### Flow
```
If WEASYPRINT_AVAILABLE == False:
    → Write hardcoded minimal PDF bytes to file
    → Contains text: "WeasyPrint not installed"
```

### Used By
- Only when WeasyPrint is not installed (development/testing)

---

## PDF Download Endpoints - Decision Logic

### Endpoint 1: `GET /pv/{pv_id}/pdf` (pv.py:122-211)

```
1. Check Redis: pdf_converting_{pv_id}
   → If true → Wait up to 50 seconds (25 retries × 2s)
2. Check S3: pv_exports/{pv_id}/edited_document.docx
   → If exists:
     a. Check S3: pv_exports/{pv_id}/final_document.pdf
     b. If PDF timestamp >= DOCX timestamp → Serve S3 PDF ✅
     c. If PDF older → Wait for conversion
     d. If PDF not found → Wait for conversion
   → If DOCX not found → Break to fallback
3. Fallback: generate_pv_pdf() → HTML → WeasyPrint → Serve
```

**This endpoint correctly prioritizes OnlyOffice PDF!**

### Endpoint 2: `GET /reports/automation/pdf/{meeting_id}` (reports.py:139-162)

```
1. Find PV by meeting_id
2. pdf_service.generate_pv_pdf() → HTML → WeasyPrint → Serve
```

**This endpoint IGNORES OnlyOffice PDF! ❌**

---

## S3 Storage Structure

```
recordings/
tmp_edits/{pv_id}/
  └── {filename}.docx          ← Temporary DOCX for OnlyOffice editing
pv_exports/{pv_id}/
  ├── edited_document.docx     ← Edited DOCX from OnlyOffice callback
  └── final_document.pdf       ← Converted PDF from OnlyOffice converter
invoices/
  └── facture_{invoice_id}.pdf ← Invoice PDF
```

---

## Comparison Table

| Aspect | HTML→PDF (WeasyPrint) | DOCX→PDF (OnlyOffice) |
|--------|----------------------|----------------------|
| **Source** | Database HTML content | OnlyOffice-edited DOCX |
| **Technology** | WeasyPrint | OnlyOffice Document Converter |
| **Trigger** | API request | OnlyOffice callback (forcesave) |
| **Output Location** | /tmp/ (local file) | S3: pv_exports/{pv_id}/final_document.pdf |
| **Multi-language** | ✅ Yes (Mistral translation) | ❌ No (uses DOCX as-is) |
| **Branding** | ✅ Yes | ❌ No |
| **Watermark** | ✅ Yes | ❌ No |
| **Used by n8n** | ❌ Currently YES (wrong!) | ❌ Not yet |
| **Used by frontend** | ✅ Fallback only | ✅ Primary (if edited) |

---

## The Problem

**n8n pv-validated workflow** uses `/reports/automation/pdf/{meeting_id}` which:
- ❌ Always generates PDF from database HTML via WeasyPrint
- ❌ Ignores the OnlyOffice-edited PDF in S3
- ❌ Users who edited the document in OnlyOffice get the OLD version

**The fix:** Make `/reports/automation/pdf/{meeting_id}` check S3 first (like `/pv/{pv_id}/pdf` does), then fallback to WeasyPrint.

---

## Status
- ✅ Method 1 (WeasyPrint): Working
- ✅ Method 2 (OnlyOffice): Working
- ✅ Method 3 (Invoice): Working
- ✅ Method 4 (Dummy): Working (fallback)
- ⚠️ Endpoint 2 (reports.py): Needs fix to use OnlyOffice PDF

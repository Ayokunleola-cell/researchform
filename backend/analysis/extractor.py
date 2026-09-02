# backend/analysis/extractor.py
"""
Chapter text extractor for ResearchForm.
Extracts clean plain text from a single Word (.docx) or PDF (.pdf) document.
Intelligently splits into chapter sections by detecting chapter headings.
"""
import os
import re


# ─── Heading patterns for chapter detection ───────────────────────────────────
_CHAPTER_PATTERNS = [
    # e.g. "CHAPTER ONE", "CHAPTER 1", "Chapter One", "Chapter 1"
    (r'(?i)chapter\s+(one|two|three|four|five|1|2|3|4|5)\b', 'numbered'),
    # e.g. "1.0 Introduction", "2.0 Literature Review"
    (r'^([1-5])\.0\s+\w', 'section'),
    # e.g. "CHAPTER ONE:", "CHAPTER 1:"
    (r'(?i)^chapter\s+\w+\s*:', 'numbered_colon'),
]

_CHAPTER_MAP = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
}


def extract_text_from_file(file_path: str, max_chars: int = 8000) -> str:
    """Extract plain text from .docx, .pdf, or .txt file."""
    if not file_path or not os.path.exists(file_path):
        return ""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return _extract_docx_text(file_path, max_chars)
    elif ext == ".pdf":
        return _extract_pdf_text(file_path, max_chars)
    elif ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()[:max_chars]
        except Exception:
            return ""
    return ""


def extract_chapters_from_single_doc(file_path: str) -> dict:
    """
    Extract and split a single document into chapter sections.

    Tries to detect chapter headings and split accordingly.
    Falls back to returning the whole document as full_text.

    Returns:
        {
            "chapter1": "text...",  # Background / Introduction
            "chapter2": "text...",  # Literature Review
            "chapter3": "text...",  # Methodology
            "full_text": "text...", # Always: entire document
        }
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".docx":
        return _split_docx_by_chapters(file_path)
    elif ext == ".pdf":
        full = _extract_pdf_text(file_path, max_chars=30000)
        return _split_text_by_chapters(full)
    elif ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                full = f.read()
            return _split_text_by_chapters(full)
        except Exception:
            return {}
    return {}


def _split_docx_by_chapters(path: str) -> dict:
    """Split a Word document by chapter using heading styles first, then text patterns."""
    try:
        from docx import Document
        doc = Document(path)
    except Exception as e:
        return {"full_text": f"[Could not open document: {e}]"}

    # --- Try Word heading styles first ---
    chapter_sections = {}
    current_chapter = None
    current_lines = []
    full_lines = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        full_lines.append(text)

        # Detect chapter from heading style
        ch_num = None
        if para.style and para.style.name:
            style = para.style.name.lower()
            if 'heading 1' in style or 'title' in style:
                ch_num = _detect_chapter_number(text)

        # Detect chapter from text pattern even if not a heading style
        if ch_num is None:
            ch_num = _detect_chapter_number(text)
            # Only treat as chapter boundary if it looks like a chapter header
            if ch_num and len(text) > 80:
                ch_num = None  # too long to be a heading

        if ch_num and ch_num in (1, 2, 3, 4, 5):
            # Save previous chapter
            if current_chapter:
                chapter_sections[f"chapter{current_chapter}"] = "\n".join(current_lines)[:8000]
            current_chapter = ch_num
            current_lines = [text]
        else:
            current_lines.append(text)

    # Save last chapter
    if current_chapter:
        chapter_sections[f"chapter{current_chapter}"] = "\n".join(current_lines)[:8000]

    full_text = "\n".join(full_lines)

    # If no chapters detected, try text-based splitting
    if not chapter_sections:
        chapter_sections = _split_text_by_chapters(full_text)
    else:
        chapter_sections["full_text"] = full_text[:12000]

    return chapter_sections


def _split_text_by_chapters(text: str) -> dict:
    """Split plain text into chapter sections using regex patterns."""
    result = {"full_text": text[:12000]}

    # Find all chapter heading positions
    chapter_positions = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        ch_num = _detect_chapter_number(stripped)
        if ch_num and ch_num in (1, 2, 3, 4, 5) and len(stripped) < 100:
            chapter_positions.append((i, ch_num))

    if not chapter_positions:
        return result

    # Extract text between chapter boundaries
    for idx, (line_start, ch_num) in enumerate(chapter_positions):
        if idx + 1 < len(chapter_positions):
            line_end = chapter_positions[idx + 1][0]
            section_lines = lines[line_start:line_end]
        else:
            section_lines = lines[line_start:]
        section_text = "\n".join(section_lines).strip()
        if section_text:
            result[f"chapter{ch_num}"] = section_text[:8000]

    return result


def _detect_chapter_number(text: str) -> int | None:
    """Detect if a line is a chapter heading and return its number (1-5)."""
    text = text.strip()

    # "CHAPTER ONE / TWO / THREE..." or "CHAPTER 1 / 2 / 3..."
    m = re.search(r'(?i)\bchapter\s+(one|two|three|four|five|1|2|3|4|5)\b', text)
    if m:
        return _CHAPTER_MAP.get(m.group(1).lower())

    # "1.0 Introduction" style
    m = re.match(r'^([1-5])\.0\b', text)
    if m:
        return int(m.group(1))

    return None


def _extract_docx_text(path: str, max_chars: int) -> str:
    """Extract all text from a Word document."""
    try:
        from docx import Document
        doc = Document(path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)[:max_chars]
    except Exception as e:
        return f"[Could not extract Word document: {e}]"


def _extract_pdf_text(path: str, max_chars: int = 30000) -> str:
    """Extract text from a PDF file using pdfplumber, fallback to PyPDF2."""
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t.strip())
                if sum(len(p) for p in pages) >= max_chars:
                    break
        return "\n\n".join(pages)[:max_chars]
    except ImportError:
        pass
    except Exception as e:
        return f"[PDF extraction error: {e}]"
    # Fallback
    try:
        import PyPDF2
        pages = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages.append(t.strip())
                if sum(len(p) for p in pages) >= max_chars:
                    break
        return "\n\n".join(pages)[:max_chars]
    except Exception:
        return "[PDF extraction unavailable — install pdfplumber]"


def extract_chapters(chapter_paths: dict) -> dict:
    """Legacy: extract text from multiple chapter files (kept for backward compat)."""
    texts = {}
    for key, path in chapter_paths.items():
        if path and os.path.exists(path):
            texts[key] = extract_text_from_file(path)
        else:
            texts[key] = ""
    return texts

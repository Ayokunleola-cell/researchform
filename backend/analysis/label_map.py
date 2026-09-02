"""
analysis/label_map.py

Builds a human-readable display label for every column in a dataset.
Used by charts.py and report writing to replace abbreviated variable names
(e.g. "q2_numbe") with clean, professional labels (e.g. "Study Hours Per Week").

Sources (in priority order):
  1. SPSS .sav metadata labels   (already human-written, use directly)
  2. Survey DB question text      (Claude AI generates a short label)
  3. CSV/XLS column names         (Claude AI infers from name + sample values + brief)
  4. Auto-format fallback         (first 4 words of question text, title-cased)
"""
from __future__ import annotations
import re, unicodedata


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _title(s: str) -> str:
    """Title-case a string, preserving acronyms like GPA, ANOVA."""
    words = str(s).replace("_", " ").split()
    result = []
    for w in words:
        if w.upper() in {"GPA", "IQ", "ANOVA", "MANOVA", "SD", "SE",
                         "HR", "IT", "AI", "ID", "USA", "UK", "NGO"}:
            result.append(w.upper())
        else:
            result.append(w.capitalize())
    return " ".join(result)


def _auto_label(col: str, question_text: str = "") -> str:
    """
    Offline fallback: derive a readable label from col name + question text.
    e.g. col="q2_numbe", question="What is your current GPA?" -> "Current GPA"
    """
    _NOISE = {"what", "how", "is", "are", "your", "the", "a", "an",
              "do", "does", "did", "please", "rate", "indicate",
              "select", "choose", "which", "many", "much"}
    if question_text:
        # Strip question marks / parenthetical hints
        clean = re.sub(r"\(.*?\)", "", question_text)          # remove (0.0-4.0) etc
        clean = re.sub(r"[?!.,;:]", "", clean).strip()
        words = clean.split()
        # Remove leading noise words
        while words and words[0].lower() in _NOISE:
            words = words[1:]
        # Take first 5 meaningful content words
        content = [w for w in words if len(w) > 2 and w.lower() not in _NOISE][:5]
        if content:
            return _title(" ".join(content))
    # Fall back to formatting the column name itself
    col_clean = re.sub(r"^q\d+_?", "", col)                   # strip q1_ prefix
    col_clean = re.sub(r"[_\-]+", " ", col_clean)
    return _title(col_clean) if col_clean else _title(col)


def _shorten(label: str, max_words: int = 6) -> str:
    """Ensure label is no longer than max_words words."""
    words = label.split()
    return " ".join(words[:max_words])


# ─── Main builder ─────────────────────────────────────────────────────────────

def build_label_map(
    columns: list[str],
    question_map: dict[str, str] | None = None,   # {col: full question text}
    spss_labels: dict[str, str] | None = None,    # {col: SPSS variable label}
    brief: dict | None = None,
    df=None,                                       # pandas DataFrame (for sample values)
    use_ai: bool = True,
) -> dict[str, str]:
    """
    Build a mapping  {raw_col_name: "Human Readable Label"}  for every column.

    Parameters
    ----------
    columns       : list of raw column names from the DataFrame
    question_map  : {col: question text} from survey DB (optional)
    spss_labels   : {col: label} from pyreadstat .sav metadata (optional)
    brief         : research brief dict (used for context)
    df            : the full DataFrame (used to extract sample values for CSV uploads)
    use_ai        : if True, call Claude to generate labels (requires API key)
    """
    from config import settings
    question_map = question_map or {}
    spss_labels  = spss_labels  or {}
    brief        = brief        or {}

    label_map: dict[str, str] = {}

    # ── Pass 1: Apply SPSS labels directly (no AI needed) ─────────────────
    for col in columns:
        if col in spss_labels and spss_labels[col]:
            label_map[col] = _shorten(spss_labels[col].strip())

    # ── Pass 2: Columns still without labels ──────────────────────────────
    remaining = [c for c in columns if c not in label_map]
    if not remaining:
        return label_map

    # Try Claude AI for remaining columns
    if use_ai and (getattr(settings, "ANTHROPIC_API_KEY", None) or
                   getattr(settings, "OPENROUTER_API_KEY", None)):
        try:
            ai_labels = _ai_generate_labels(
                remaining, question_map, brief, df
            )
            label_map.update(ai_labels)
        except Exception as e:
            print(f"[LabelMap] AI label generation failed, using fallback: {e}")

    # ── Pass 3: Auto-format fallback for anything still missing ───────────
    for col in remaining:
        if col not in label_map:
            label_map[col] = _auto_label(col, question_map.get(col, ""))

    return label_map


def _ai_generate_labels(
    columns: list[str],
    question_map: dict[str, str],
    brief: dict,
    df,
) -> dict[str, str]:
    """
    Call Claude AI once with all columns and get back a JSON mapping.
    Returns {col: label} for as many columns as the model can label.
    """
    import json
    from config import settings

    # Build column info block
    lines = []
    for col in columns:
        q_text = question_map.get(col, "")
        sample = ""
        if df is not None and col in df.columns:
            try:
                vals = df[col].dropna().unique()[:5].tolist()
                sample = str(vals)
            except Exception:
                pass
        if q_text:
            lines.append(f'  "{col}": question="{q_text[:120]}"')
        elif sample:
            lines.append(f'  "{col}": sample_values={sample}')
        else:
            lines.append(f'  "{col}"')

    col_block = "\n".join(lines)
    topic = brief.get("topic", "Research Study")
    dv    = brief.get("dependent_variable", "")
    iv    = brief.get("independent_variable", "")

    prompt = f"""You are labelling dataset columns for a research paper titled:
"{topic}"
Dependent variable: {dv}
Independent variable: {iv}

For each column below, generate a SHORT (2–5 words), professional, title-case display label 
suitable for chart axes, table headers, and a Word report. Avoid abbreviations. Use full words.

Columns to label:
{col_block}

Return ONLY valid JSON in this exact format (no extra text, no markdown):
{{
  "column_name": "Human Readable Label",
  ...
}}"""

    # Call LLM (reuse existing pipeline helper pattern)
    response_text = _llm_call(prompt, max_tokens=800)

    # Parse JSON from response
    try:
        # Find the JSON block (sometimes model wraps in ```)
        match = re.search(r"\{[\s\S]+\}", response_text)
        if match:
            raw = json.loads(match.group())
            # Validate and clean each label
            result = {}
            for col, lbl in raw.items():
                if col in columns and isinstance(lbl, str) and lbl.strip():
                    result[col] = _shorten(lbl.strip())
            return result
    except Exception as parse_err:
        print(f"[LabelMap] JSON parse error: {parse_err}")
    return {}


def _llm_call(prompt: str, max_tokens: int = 800) -> str:
    """Minimal LLM call — reuses Anthropic/OpenRouter from settings."""
    from config import settings

    if getattr(settings, "ANTHROPIC_API_KEY", None):
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text if msg.content else ""

    if getattr(settings, "OPENROUTER_API_KEY", None):
        import httpx, json as _json
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "anthropic/claude-opus-4-5",
                  "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    return ""


# ─── Convenience helpers used by charts.py ────────────────────────────────────

def label(col: str, label_map: dict[str, str]) -> str:
    """Return the display label for a column, or fall back to auto-formatting."""
    return label_map.get(col) or _auto_label(col)


def apply_to_df(df, label_map: dict[str, str]):
    """
    Return a copy of df with columns renamed to their display labels.
    Safe — only renames columns that exist in label_map.
    """
    rename = {c: label_map[c] for c in df.columns if c in label_map}
    return df.rename(columns=rename)


# ─── SPSS metadata extractor ─────────────────────────────────────────────────

def extract_spss_labels(sav_path: str) -> dict[str, str]:
    """
    Read SPSS .sav metadata and return {variable_name: variable_label}.
    Returns empty dict if pyreadstat is not installed or file is not .sav.
    """
    try:
        import pyreadstat
        _, meta = pyreadstat.read_sav(sav_path, metadataonly=True)
        return dict(zip(meta.column_names, meta.column_labels)) if meta.column_labels else {}
    except Exception:
        return {}


# ─── Survey DB question map builder ──────────────────────────────────────────

def build_question_map_from_db(survey_id: str, db) -> dict[str, str]:
    """
    Fetch all questions for a survey and return {variable_name: question_text}.
    Works with both async and sync SQLAlchemy sessions.
    """
    try:
        from api.models.database import Question
        import sqlalchemy as sa

        # Support both sync Session and async Session (pipeline uses sync db)
        rows = db.execute(
            sa.select(Question.variable_name, Question.text)
            .where(Question.survey_id == survey_id)
            .where(Question.type != "section_header")
        ).fetchall()
        return {row[0]: row[1] for row in rows if row[0] and row[1]}
    except Exception as e:
        print(f"[LabelMap] Could not fetch question map from DB: {e}")
        return {}

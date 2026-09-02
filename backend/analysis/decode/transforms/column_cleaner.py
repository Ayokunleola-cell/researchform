import re
import json

def clean_columns(df, meta, job_id=None, user_id=None):
    from analysis.pipeline import _has_llm, _llm_chat

    col_map = {}
    seen = {}
    new_cols = []

    original_cols = [str(col).strip() for col in df.columns]

    # LLM-generated names
    llm_names = {}

    # Check if columns are already clean identifiers (no spaces, reasonably short)
    needs_llm = any(" " in col or len(col) > 35 or "?" in col or "/" in col for col in original_cols)

    if _has_llm() and job_id and needs_llm:
        prompt = (
            "You are a data science assistant. I have a list of raw survey questions/column headers. "
            "Convert them into short, descriptive, code-friendly snake_case variable names (under 30 chars). "
            "For example: 'On a scale of 1-5, how satisfied are you?' -> 'satisfaction_score'. "
            "Return ONLY a valid JSON object mapping the original name to the new variable name. Do not wrap in markdown tags like ```json.\n\n"
            f"Headers to convert: {json.dumps(original_cols[:60])}"
        )
        try:
            response_text = _llm_chat(prompt, max_tokens=2000)
            
            # Clean up potential markdown formatting from LLM
            clean_json = response_text.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in clean_json:
                clean_json = clean_json.split("```", 1)[1].split("```", 1)[0]
                
            parsed = json.loads(clean_json.strip())
            if isinstance(parsed, dict):
                llm_names = parsed
        except Exception as e:
            print(f"LLM column renaming failed: {e}")
            llm_names = {}

    # Apply mapping with fallback and deduplication
    for col in original_cols:
        if col in llm_names and isinstance(llm_names[col], str) and llm_names[col].strip():
            c = llm_names[col].strip().lower()
            c = re.sub(r"[^a-z0-9_]", "_", c)
            c = re.sub(r"_+", "_", c).strip("_")
        else:
            c = col.lower()
            c = re.sub(r"[^a-z0-9_]", "_", c)
            c = re.sub(r"_+", "_", c).strip("_")
            c = c[:40]
            
        if not c: 
            c = "var"
            
        # Deduplication
        if c in seen:
            seen[c] += 1
            c = f"{c}_{seen[c]}"
        else:
            seen[c] = 0
            
        col_map[c] = col
        new_cols.append(c)

    df.columns = new_cols
    return df, col_map

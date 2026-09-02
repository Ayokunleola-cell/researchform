import unicodedata, re

def _sanitize(s):
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    return s.strip()

# Parse from PostgreSQL survey responses
def _coerce_answers(answers):
    import json
    if answers is None:
        return {}
    if isinstance(answers, str):
        try:
            answers = json.loads(answers)
        except json.JSONDecodeError:
            return {}
    return answers if isinstance(answers, dict) else {}


def answer_value(answers, qid, vname=None):
    answers = _coerce_answers(answers)
    val = answers.get(qid)
    if val is None:
        val = answers.get(str(qid))
    if val is None and vname:
        val = answers.get(vname)
    return val


def parse_from_db(survey_id: str, db):
    import json
    import pandas as pd
    from sqlalchemy import text
    # Get questions
    q_result = db.execute(text("SELECT id, variable_name, type, text, measurement_level, options FROM questions WHERE survey_id = :sid ORDER BY position"), {"sid": survey_id})
    questions = q_result.fetchall()
    if not questions:
        return pd.DataFrame(), {"source": "survey_db", "value_labels": {}, "column_labels": {}, "measurement_levels": {}}
    # Get responses
    r_result = db.execute(text("SELECT answers FROM responses WHERE survey_id = :sid"), {"sid": survey_id})
    responses = r_result.fetchall()
    rows = []
    for resp in responses:
        answers = _coerce_answers(resp[0])
        row = {}
        for q in questions:
            qid, vname, qtype, qtext, mlevel, opts = q
            val = answer_value(answers, qid)
            if val is None:
                val = ""
            elif isinstance(val, dict):
                val = "; ".join(f"{_sanitize(k)}: {_sanitize(v)}" for k, v in val.items())
            elif isinstance(val, list):
                val = "; ".join(_sanitize(v) for v in val)
            elif isinstance(val, str):
                val = _sanitize(val)
            col_key = _sanitize(vname or qid)
            row[col_key] = val
        rows.append(row)
    df = pd.DataFrame(rows)
    meta = {
        "source": "survey_db",
        "value_labels": {},
        "column_labels": {_sanitize(q[1] or q[0]): _sanitize(q[3]) for q in questions},
        "measurement_levels": {_sanitize(q[1] or q[0]): q[4] for q in questions},
    }
    return df, meta

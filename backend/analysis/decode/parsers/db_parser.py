# Parse from PostgreSQL survey responses
def parse_from_db(survey_id: str, db):
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
        answers = resp[0] or {}
        row = {}
        for q in questions:
            qid, vname, qtype, qtext, mlevel, opts = q
            val = answers.get(qid)
            if isinstance(val, list): val = "; ".join(str(v) for v in val)
            row[vname or qid] = val
        rows.append(row)
    df = pd.DataFrame(rows)
    meta = {
        "source": "survey_db",
        "value_labels": {},
        "column_labels": {(q[1] or q[0]): q[3] for q in questions},
        "measurement_levels": {(q[1] or q[0]): q[4] for q in questions},
    }
    return df, meta

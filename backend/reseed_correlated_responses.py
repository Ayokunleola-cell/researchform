"""
Re-seed demo survey responses with proper within-construct item correlation.
Each construct's items are generated using a correlated multivariate approach:
- Each respondent has a latent trait score per construct
- Item responses = round(latent_trait + small_noise), clipped to [1,5]
- This produces realistic Cronbach's Alpha (0.75-0.90 range)
"""
import sys, os, json, random, uuid
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, r"C:\Users\HP\Documents\My work\ResearchForm_Codebase\researchform\backend")

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DB_PATH = r"C:\Users\HP\Documents\My work\ResearchForm_Codebase\researchform\backend\researchform_dev.db"
SID = "9b5fb7be-bb48-4bd6-8eeb-a896cb6a65cb"
N = 500

engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

np.random.seed(42)
random.seed(42)

# ── Survey constructs and their items ──────────────────────────────────────────
CONSTRUCTS = {
    # (variable_name_prefix, n_items, mean, std_of_latent_trait)
    "DW": {"items": ["dw1","dw2","dw3","dw4","dw5"], "mean": 3.5, "std": 0.7},
    "TS": {"items": ["ts1","ts2","ts3","ts4","ts5"], "mean": 3.2, "std": 0.8},
    "PS": {"items": ["ps1","ps2","ps3","ps4","ps5"], "mean": 3.6, "std": 0.7},
    "LS": {"items": ["ls1","ls2","ls3","ls4","ls5"], "mean": 3.4, "std": 0.8},
    "JS": {"items": ["js1","js2","js3","js4","js5"], "mean": 3.5, "std": 0.7},
    "OC": {"items": ["oc1","oc2","oc3","oc4"],       "mean": 3.4, "std": 0.7},
    "WL": {"items": ["wl1","wl2","wl3","wl4"],       "mean": 3.3, "std": 0.8},
}

# Correlations between constructs (DW↔TS high positive; PS/LS↔JS positive; etc.)
INTER_CONSTRUCT_CORR = {
    ("DW","TS"):  0.55,
    ("DW","JS"): -0.35,
    ("DW","WL"): -0.30,
    ("TS","JS"): -0.40,
    ("TS","WL"): -0.30,
    ("PS","JS"):  0.45,
    ("PS","OC"):  0.40,
    ("LS","PS"):  0.45,
    ("LS","JS"):  0.40,
    ("LS","OC"):  0.35,
    ("JS","OC"):  0.50,
    ("JS","WL"):  0.35,
}

CONSTRUCTS_LIST = list(CONSTRUCTS.keys())

def build_corr_matrix():
    n = len(CONSTRUCTS_LIST)
    C = np.eye(n)
    idx = {k: i for i, k in enumerate(CONSTRUCTS_LIST)}
    for (a, b), r in INTER_CONSTRUCT_CORR.items():
        if a in idx and b in idx:
            i, j = idx[a], idx[b]
            C[i, j] = r
            C[j, i] = r
    # Ensure positive-definite
    eigvals = np.linalg.eigvalsh(C)
    if eigvals.min() <= 0:
        C += np.eye(n) * (abs(eigvals.min()) + 0.01)
    return C

def generate_responses(n=500):
    """
    Generate n response dicts with properly correlated Likert items.
    Each construct's items are generated as:
        item_score = latent_trait + item_noise (σ=0.6)
    This gives realistic alpha values in the 0.7-0.85 range.
    """
    C = build_corr_matrix()
    means = np.array([CONSTRUCTS[k]["mean"] for k in CONSTRUCTS_LIST])
    stds  = np.array([CONSTRUCTS[k]["std"]  for k in CONSTRUCTS_LIST])

    # Generate correlated latent trait scores for all respondents
    # Shape: (n, n_constructs)
    L = np.linalg.cholesky(C)
    z = np.random.randn(n, len(CONSTRUCTS_LIST))
    traits = z @ L.T  # correlated standard normal
    # Scale to actual means/stds
    traits = traits * stds[np.newaxis, :] + means[np.newaxis, :]

    # Build per-item responses (item = trait + noise, clipped to [1,5], rounded to int)
    ITEM_NOISE_SD = 0.55  # controls alpha — lower = higher alpha

    responses = []
    for i in range(n):
        ans = {}
        for ci, (cname, cinfo) in enumerate(CONSTRUCTS.items()):
            trait = traits[i, ci]
            for item in cinfo["items"]:
                noise = np.random.normal(0, ITEM_NOISE_SD)
                raw = trait + noise
                score = int(np.clip(np.round(raw), 1, 5))
                ans[item] = score
        responses.append(ans)
    return responses, traits


def demographic_value(col, idx):
    """Generate stable demographic value for respondent idx."""
    if col == "gender":
        return random.choice(["Male", "Female", "Non-binary", "Prefer not to say"])
    if col == "age_group":
        return random.choice(["18-24", "25-34", "35-44", "45-54", "55+"])
    if col == "education":
        return random.choice(["High school", "Bachelor's degree", "Master's degree", "Doctorate", "Other"])
    if col == "sector":
        return random.choice(["Technology", "Healthcare", "Education", "Finance", "Retail", "Government", "Other"])
    if col == "tenure":
        return random.choice(["Less than 1 year", "1-3 years", "3-5 years", "5-10 years", "More than 10 years"])
    if col == "work_arrangement":
        return random.choice(["Remote", "Hybrid", "On-site"])
    if col == "job_level":
        return random.choice(["Entry level", "Mid-level", "Senior", "Manager", "Director/VP", "C-suite"])
    return ""


async def reseed():
    async with AsyncSessionLocal() as db:
        # Get questions
        q_result = await db.execute(
            text("SELECT id, variable_name, type, text FROM questions WHERE survey_id = :sid ORDER BY position"),
            {"sid": SID}
        )
        questions = q_result.fetchall()
        print(f"Survey has {len(questions)} questions")

        # Map variable_name → question_id
        var_to_qid = {}
        for q in questions:
            qid, vname, qtype, qtext = q
            if vname:
                var_to_qid[vname.lower()] = qid

        print(f"Variable mappings: {len(var_to_qid)}")
        print("Sample:", dict(list(var_to_qid.items())[:5]))

        # Delete existing responses
        await db.execute(text("DELETE FROM responses WHERE survey_id = :sid"), {"sid": SID})
        await db.commit()
        print(f"Cleared existing responses")

        # Generate new responses
        item_responses, traits = generate_responses(N)
        print(f"Generated {len(item_responses)} response dicts")

        # Seed into DB
        base_time = datetime(2026, 1, 15)
        inserted = 0
        for i, item_ans in enumerate(item_responses):
            # Build full answer dict keyed by question_id
            full_answers = {}

            for var, val in item_ans.items():
                qid = var_to_qid.get(var)
                if qid:
                    full_answers[qid] = val

            # Add demographics
            for dvar in ["gender","age_group","education","sector","tenure","work_arrangement","job_level"]:
                qid = var_to_qid.get(dvar)
                if qid:
                    full_answers[qid] = demographic_value(dvar, i)

            # Add wellbeing_rating (correlated with JS and PS)
            wb_qid = var_to_qid.get("wellbeing_rating")
            if wb_qid:
                js_trait = traits[i, CONSTRUCTS_LIST.index("JS")]
                ps_trait = traits[i, CONSTRUCTS_LIST.index("PS")]
                wb_raw = (js_trait * 0.5 + ps_trait * 0.3) / 5 * 10 + np.random.normal(0, 0.8)
                full_answers[wb_qid] = int(np.clip(np.round(wb_raw), 1, 10))

            # Add NPS score
            nps_qid = var_to_qid.get("nps_score")
            if nps_qid:
                js_idx = CONSTRUCTS_LIST.index("JS")
                nps_raw = (traits[i, js_idx] - 1) / 4 * 10 + np.random.normal(0, 1.5)
                full_answers[nps_qid] = int(np.clip(np.round(nps_raw), 0, 10))

            # Add open text
            open_qid = var_to_qid.get("challenge_open")
            open_responses = [
                "Managing back-to-back video calls is exhausting.",
                "I struggle to disconnect after work hours.",
                "Too many tools and platforms to manage simultaneously.",
                "Clear priorities from leadership would help enormously.",
                "Flexible hours have improved my work-life balance.",
                "The constant notifications make it hard to focus.",
                "Remote work has improved my productivity.",
                "I need better boundaries between work and personal time.",
                "My manager is very supportive of mental health.",
                "The digital overload is a real challenge.",
            ]
            if open_qid:
                full_answers[open_qid] = random.choice(open_responses)

            if not full_answers:
                continue

            submitted_at = base_time + timedelta(
                days=random.randint(0, 120),
                hours=random.randint(8, 22),
                minutes=random.randint(0, 59)
            )

            resp_id = str(uuid.uuid4())
            await db.execute(
                text("INSERT INTO responses (id, survey_id, answers, submitted_at) VALUES (:id, :sid, :ans, :ts)"),
                {"id": resp_id, "sid": SID, "ans": json.dumps(full_answers), "ts": submitted_at.isoformat()}
            )
            inserted += 1

        await db.commit()
        print(f"\nInserted {inserted} responses")

        # Quick sanity check — compute alpha for DW
        r_result = await db.execute(
            text("SELECT answers FROM responses WHERE survey_id = :sid"),
            {"sid": SID}
        )
        all_responses = r_result.fetchall()
        print(f"\nSanity check on {len(all_responses)} responses:")
        
        dw_items = ["dw1","dw2","dw3","dw4","dw5"]
        dw_qids  = [var_to_qid.get(v) for v in dw_items if var_to_qid.get(v)]
        
        rows = []
        for row in all_responses:
            ans = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            r = {}
            for vi, (var, qid) in enumerate(zip(dw_items, dw_qids)):
                r[var] = ans.get(qid)
            rows.append(r)
        
        import pandas as pd
        df = pd.DataFrame(rows).apply(pd.to_numeric, errors="coerce").dropna()
        print(f"  DW items — n={len(df)}, means: {df.mean().round(2).to_dict()}")
        k = len(dw_qids)
        iv = df.var(axis=0, ddof=1).sum()
        tv = df.sum(axis=1).var(ddof=1)
        alpha = (k/(k-1)) * (1 - iv/tv) if tv > 0 else 0
        print(f"  DW Cronbach's Alpha (manual): {round(alpha, 3)}")

asyncio.run(reseed())
print("\nDone! Re-seeded 500 responses with proper within-construct correlation.")

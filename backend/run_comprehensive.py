"""
Create a highly comprehensive synthetic survey and run the analysis pipeline.

Usage:
    venv/Scripts/python.exe run_comprehensive.py
"""
from __future__ import annotations

import os
import random
import sys
import time
from typing import Any
from datetime import datetime, timedelta

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
EMAIL = "synthetic.runner@test.com"
PASSWORD = "Secure123!"
# Number of synthetic responses to generate
N_RESPONSES = 500
POLL_INTERVAL = 1.0
MAX_WAIT_SECONDS = 600

def log(msg: str) -> None:
    print(f"  {msg}", flush=True)

def authenticate() -> dict[str, str]:
    client = httpx.Client(timeout=10.0)
    r = client.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "full_name": "Synthetic Runner",
            "institution": "QA University",
            "role": "researcher",
        },
    )
    if r.status_code == 400 and "already" in r.json().get("detail", "").lower():
        r = client.post(f"{BASE_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def create_survey(client: httpx.Client, headers: dict[str, str]) -> dict[str, Any]:
    survey = client.post(
        f"{BASE_URL}/surveys",
        json={
            "title": "Comprehensive Wellbeing and Performance Study",
            "description": "Synthetic dataset for advanced pipeline validation",
            "project_brief": {
                "topic": "Wellbeing and performance",
                "objectives": [
                    "Evaluate factors affecting job performance",
                    "Analyze burnout predictors",
                    "Understand demographic differences"
                ],
                "hypotheses": [
                    "H1: The probability of turnover intent can be predicted from salary and emotional burnout (Logistic Regression)",
                    "H2: The underlying factors of burnout can be identified via Principal Component Analysis (PCA)",
                    "H3: There is a significant difference between pre-test performance and post-test performance (Paired T-test)",
                    "H4: There is a significant association between department and whether an employee was promoted (Chi-Square)",
                    "H5: The median emotional burnout differs between employees who were promoted and those who were not (Mann-Whitney)",
                    "H6: Median performance differs significantly across various departments (Kruskal-Wallis)",
                    "H7: There is a non-parametric correlation between satisfaction with manager and satisfaction with pay (Spearman)"
                ],
                "population": "Tech employees",
                "sample_size": N_RESPONSES,
                "academic_tradition": "psychology",
            },
            "allow_multiple": True,
        },
        headers=headers,
    )
    survey.raise_for_status()
    return survey.json()

def add_questions(client: httpx.Client, headers: dict[str, str], survey_id: str) -> dict[str, str]:
    specs = [
        {"type": "single_choice", "text": "Gender", "options": ["Male", "Female", "Other"], "variable_name": "gender", "position": 0},
        {"type": "single_choice", "text": "Department", "options": ["Engineering", "Sales", "HR", "Marketing", "Product"], "variable_name": "department", "position": 1},
        {"type": "single_choice", "text": "Education Level", "options": ["Bachelors", "Masters", "PhD", "Other"], "variable_name": "education", "position": 2},
        {"type": "number", "text": "Age", "variable_name": "age", "position": 3},
        {"type": "number", "text": "Years of Experience", "variable_name": "tenure", "position": 4},
        {"type": "number", "text": "Annual Salary (USD)", "variable_name": "salary", "position": 5},
        
        {"type": "likert", "text": "I feel supported by my manager", "options": ["1", "2", "3", "4", "5"], "scale_min": 1, "scale_max": 5, "variable_name": "sat_manager", "position": 6},
        {"type": "likert", "text": "I am satisfied with my pay", "options": ["1", "2", "3", "4", "5"], "scale_min": 1, "scale_max": 5, "variable_name": "sat_pay", "position": 7},
        {"type": "likert", "text": "I am satisfied with company culture", "options": ["1", "2", "3", "4", "5"], "scale_min": 1, "scale_max": 5, "variable_name": "sat_culture", "position": 8},
        
        {"type": "likert", "text": "I feel emotionally drained from my work", "options": ["1", "2", "3", "4", "5", "6", "7"], "scale_min": 1, "scale_max": 7, "variable_name": "burnout_emotional", "position": 9},
        {"type": "likert", "text": "I feel used up at the end of the workday", "options": ["1", "2", "3", "4", "5", "6", "7"], "scale_min": 1, "scale_max": 7, "variable_name": "burnout_usedup", "position": 10},
        {"type": "likert", "text": "I feel fatigued when I wake up in the morning", "options": ["1", "2", "3", "4", "5", "6", "7"], "scale_min": 1, "scale_max": 7, "variable_name": "burnout_fatigue", "position": 11},
        
        {"type": "rating", "text": "Recent Performance Score", "scale_min": 0, "scale_max": 100, "variable_name": "performance", "position": 12},
        {"type": "single_choice", "text": "Promoted in last year?", "options": ["Yes", "No"], "variable_name": "promoted", "position": 13},
        {"type": "single_choice", "text": "Intent to leave in 6 months?", "options": ["1", "0"], "variable_name": "turnover_intent", "position": 14},
        {"type": "rating", "text": "Pre-Test Performance Score", "scale_min": 0, "scale_max": 100, "variable_name": "pre_test", "position": 15},
        {"type": "rating", "text": "Post-Test Performance Score", "scale_min": 0, "scale_max": 100, "variable_name": "post_test", "position": 16},
        {"type": "single_choice", "text": "Manager ID", "options": ["M1", "M2", "M3", "M4", "M5"], "variable_name": "manager_id", "position": 17},
    ]

    qid_map = {}
    for spec in specs:
        r = client.post(f"{BASE_URL}/surveys/{survey_id}/questions", json=spec, headers=headers)
        r.raise_for_status()
        qid_map[spec["variable_name"]] = r.json()["id"]

    client.post(f"{BASE_URL}/surveys/{survey_id}/publish", headers=headers).raise_for_status()
    return qid_map

def generate_responses(client: httpx.Client, public_slug: str, qid_map: dict[str, str]) -> None:
    for i in range(N_RESPONSES):
        dep = random.choice(["Engineering", "Sales", "HR", "Marketing", "Product"])
        gender = random.choices(["Male", "Female", "Other"], weights=[0.45, 0.45, 0.1])[0]
        
        # Correlated values
        age = int(random.normalvariate(35, 8))
        age = max(18, min(65, age))
        tenure = max(0.5, age - 22 + random.normalvariate(0, 3))
        
        # Salary depends on tenure and department
        base_sal = {"Engineering": 100000, "Sales": 80000, "Product": 110000, "HR": 70000, "Marketing": 75000}[dep]
        salary = int(base_sal + tenure * 3000 + random.normalvariate(0, 10000))
        
        # Burnout depends on department
        if dep in ["Sales", "Engineering"]:
            bo_base = random.normalvariate(4.5, 1)
        else:
            bo_base = random.normalvariate(3.0, 1)
            
        b1 = max(1, min(7, int(bo_base + random.normalvariate(0, 0.5))))
        b2 = max(1, min(7, int(bo_base + random.normalvariate(0, 0.5))))
        b3 = max(1, min(7, int(bo_base + random.normalvariate(0, 0.5))))
        
        sat_mgr = max(1, min(5, int(random.normalvariate(3, 1))))
        
        # Performance is negatively correlated with burnout, positively with sat_manager
        perf_base = 70 - (bo_base - 3.5)*5 + (sat_mgr - 3)*5 + random.normalvariate(0, 5)
        perf = max(0, min(100, int(perf_base)))
        
        turnover = 1 if bo_base > 5 or perf < 50 else random.choice([0, 0, 0, 1])
        promoted = "Yes" if perf > 80 and tenure > 2 else "No"
        
        pre_test = max(0, min(100, int(perf_base - random.normalvariate(5, 5))))
        post_test = max(0, min(100, int(perf_base + random.normalvariate(5, 5))))
        
        # Convert answers list to a dictionary as expected by the backend SubmitRequest
        answers_dict = {
            qid_map["gender"]: gender,
            qid_map["department"]: dep,
            qid_map["education"]: random.choice(["Bachelors", "Masters", "PhD", "Other"]),
            qid_map["age"]: str(age),
            qid_map["tenure"]: str(round(tenure, 1)),
            qid_map["salary"]: str(salary),
            qid_map["sat_manager"]: str(sat_mgr),
            qid_map["sat_pay"]: str(max(1, min(5, int(random.normalvariate(3, 1))))),
            qid_map["sat_culture"]: str(max(1, min(5, int(random.normalvariate(3, 1))))),
            qid_map["burnout_emotional"]: str(b1),
            qid_map["burnout_usedup"]: str(b2),
            qid_map["burnout_fatigue"]: str(b3),
            qid_map["performance"]: str(perf),
            qid_map["promoted"]: promoted,
            qid_map["turnover_intent"]: turnover,
            qid_map["pre_test"]: str(pre_test),
            qid_map["post_test"]: str(post_test),
            qid_map["manager_id"]: random.choice(["M1", "M2", "M3", "M4", "M5"]),
        }
        
        r = client.post(f"{BASE_URL}/public/surveys/{public_slug}/respond", json={"answers": answers_dict})
        r.raise_for_status()

        if (i + 1) % 25 == 0:
            log(f"Submitted {i + 1}/{N_RESPONSES} responses")

def wait_for_status(
    client: httpx.Client,
    headers: dict[str, str],
    job_id: str,
    target: str | set[str],
    timeout: float = MAX_WAIT_SECONDS,
) -> dict[str, Any]:
    targets = {target} if isinstance(target, str) else set(target)
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        r = client.get(f"{BASE_URL}/analysis/jobs/{job_id}/status", headers=headers)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")
        if status != last_status:
            log(f"  Job status: {status}")
            last_status = status
        if status in targets:
            return data
        if status == "failed":
            raise RuntimeError(f"Analysis failed: {data.get('error')}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Timed out waiting for status in {targets}. Last status: {last_status}")


def run_analysis(client: httpx.Client, headers: dict[str, str], survey_id: str) -> dict[str, Any]:
    r = client.post(
        f"{BASE_URL}/analysis/start",
        json={"survey_id": survey_id},
        headers=headers,
    )
    r.raise_for_status()
    job = r.json()
    job_id = job["id"]
    log(f"Analysis job started: {job_id}")

    wait_for_status(client, headers, job_id, "awaiting_preprocessing_choice")
    r = client.post(
        f"{BASE_URL}/analysis/jobs/{job_id}/preprocessing-choice",
        json={"mode": "auto", "manual_choices": {}},
        headers=headers,
    )
    r.raise_for_status()
    log("  Preprocessing choice submitted (auto)")

    wait_for_status(client, headers, job_id, "decode_review", timeout=MAX_WAIT_SECONDS)
    r = client.post(
        f"{BASE_URL}/analysis/jobs/{job_id}/approve-decode",
        json={"variable_overrides": {}, "missing_strategy": "preprocessed"},
        headers=headers,
    )
    r.raise_for_status()
    log("  Decode approved - running stages 3-9")

    wait_for_status(client, headers, job_id, "complete", timeout=MAX_WAIT_SECONDS)
    r = client.get(f"{BASE_URL}/analysis/jobs/{job_id}", headers=headers)
    r.raise_for_status()
    return r.json()



def main():
    print("=" * 70)
    print("  Comprehensive Synthetic Survey -> Analysis Pipeline")
    print("=" * 70)

    try:
        with httpx.Client(timeout=30.0) as client:
            log("[1/5] Authenticating...")
            headers = authenticate()

            log("[2/5] Creating survey and questions...")
            survey_data = create_survey(client, headers)
            survey_id = survey_data["id"]
            public_slug = survey_data["slug"]
            log(f"Survey ID: {survey_id}")
            log(f"Public slug: {public_slug}")

            qid_map = add_questions(client, headers, survey_id)
            log(f"Added {len(qid_map)} questions")

            log(f"[3/5] Generating and submitting {N_RESPONSES} synthetic responses...")
            generate_responses(client, public_slug, qid_map)

            log("[4/5] Starting analysis pipeline...")
            final_data = run_analysis(client, headers, survey_id)

            log("")
            print("\n  [5/5] Analysis complete!")
            import json
            print(json.dumps(final_data, indent=2).encode('ascii', 'replace').decode('ascii'))
            
            # Print URL
            print(f"\n--> VIEW RESULTS HERE: http://localhost:3000/analysis/{final_data['id']}\n")
            
            log(f"Job ID:     {final_data['id']}")
            log(f"Rows:       {final_data.get('n_rows')}")
            log(f"Columns:    {final_data.get('n_columns')}")
            log(f"Report:     {final_data.get('report_path')}")

            print("\\nDone.")

    except httpx.HTTPStatusError as e:
        print(f"\\nHTTP Error: {e}")
        try:
            print(f"Details: {e.response.json()}")
        except:
            print(f"Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
Create a synthetic survey, submit responses, and run the full analysis pipeline.

Usage (backend server must be running on BASE_URL):
    venv/Scripts/python.exe run_synthetic_survey_analysis.py
"""
from __future__ import annotations

import os
import random
import sys
import time
from typing import Any

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8001")
EMAIL = "synthetic.runner@test.com"
PASSWORD = "Secure123!"
N_RESPONSES = 100
POLL_INTERVAL = 1.0
MAX_WAIT_SECONDS = 600


def log(msg: str) -> None:
    print(msg, flush=True)


def auth_headers(client: httpx.Client) -> dict[str, str]:
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
            "title": "Employee Satisfaction Study (Synthetic)",
            "description": "Synthetic dataset for pipeline validation",
            "project_brief": {
                "topic": "Employee satisfaction and performance",
                "objectives": [
                    "Measure overall job satisfaction across departments",
                    "Compare satisfaction by gender and age group",
                ],
                "hypotheses": [
                    "H1: Job satisfaction differs by department",
                    "H2: Satisfaction is associated with performance rating",
                ],
                "study_type": "quantitative",
                "population": "University staff",
                "dependent_variable": "satisfaction",
                "independent_variable": "department",
                "significance_level": 0.05,
            },
            "require_email": False,
            "allow_multiple": True,
        },
        headers=headers,
    )
    survey.raise_for_status()
    return survey.json()


def add_questions(client: httpx.Client, headers: dict[str, str], survey_id: str) -> dict[str, str]:
    specs = [
        {
            "type": "single_choice",
            "text": "What is your gender?",
            "options": ["Male", "Female", "Other"],
            "variable_name": "gender",
            "position": 0,
        },
        {
            "type": "single_choice",
            "text": "Which department do you work in?",
            "options": ["Engineering", "Sales", "HR", "Operations"],
            "variable_name": "department",
            "position": 1,
        },
        {
            "type": "single_choice",
            "text": "What is your age group?",
            "options": ["18-25", "26-35", "36-45", "46+"],
            "variable_name": "age_group",
            "position": 2,
        },
        {
            "type": "likert",
            "text": "I am satisfied with my job overall",
            "options": ["1", "2", "3", "4", "5"],
            "scale_min": 1,
            "scale_max": 5,
            "variable_name": "sat_overall",
            "position": 3,
        },
        {
            "type": "likert",
            "text": "I receive adequate support from my manager",
            "options": ["1", "2", "3", "4", "5"],
            "scale_min": 1,
            "scale_max": 5,
            "variable_name": "sat_manager",
            "position": 4,
        },
        {
            "type": "likert",
            "text": "My workload is manageable",
            "options": ["1", "2", "3", "4", "5"],
            "scale_min": 1,
            "scale_max": 5,
            "variable_name": "sat_workload",
            "position": 5,
        },
        {
            "type": "rating",
            "text": "Rate your performance this quarter (1-10)",
            "scale_min": 1,
            "scale_max": 10,
            "variable_name": "performance",
            "position": 6,
        },
        {
            "type": "single_choice",
            "text": "Would you recommend this organisation as a place to work?",
            "options": ["Yes", "No", "Maybe"],
            "variable_name": "recommend",
            "position": 7,
        },
    ]

    question_ids: dict[str, str] = {}
    for spec in specs:
        r = client.post(
            f"{BASE_URL}/surveys/{survey_id}/questions",
            json={**spec, "required": True},
            headers=headers,
        )
        r.raise_for_status()
        q = r.json()
        question_ids[spec["variable_name"]] = q["id"]
    return question_ids


def generate_responses(
    question_ids: dict[str, str],
    n: int,
) -> list[dict[str, str | int]]:
    genders = ["Male", "Female", "Other"]
    departments = ["Engineering", "Sales", "HR", "Operations"]
    age_groups = ["18-25", "26-35", "36-45", "46+"]
    dept_bias = {"Engineering": 0.3, "Sales": -0.2, "HR": 0.1, "Operations": 0.0}
    rows: list[dict[str, str | int]] = []

    rng = random.Random(42)
    for _ in range(n):
        gender = rng.choice(genders)
        department = rng.choice(departments)
        age_group = rng.choice(age_groups)
        base = 3.2 + dept_bias[department] + rng.uniform(-0.8, 0.8)
        sat_overall = str(max(1, min(5, round(base + rng.uniform(-0.5, 0.5)))))
        sat_manager = str(max(1, min(5, round(float(sat_overall) + rng.uniform(-1.0, 1.0)))))
        sat_workload = str(max(1, min(5, round(float(sat_overall) + rng.uniform(-1.2, 0.8)))))
        performance = str(max(1, min(10, round(float(sat_overall) * 1.6 + rng.uniform(-1.5, 1.5)))))
        avg_sat = (int(sat_overall) + int(sat_manager) + int(sat_workload)) / 3
        if avg_sat >= 4:
            recommend = "Yes"
        elif avg_sat <= 2.5:
            recommend = "No"
        else:
            recommend = rng.choice(["Yes", "No", "Maybe"])

        rows.append(
            {
                question_ids["gender"]: gender,
                question_ids["department"]: department,
                question_ids["age_group"]: age_group,
                question_ids["sat_overall"]: sat_overall,
                question_ids["sat_manager"]: sat_manager,
                question_ids["sat_workload"]: sat_workload,
                question_ids["performance"]: performance,
                question_ids["recommend"]: recommend,
            }
        )
    return rows


def submit_responses(client: httpx.Client, slug: str, responses: list[dict]) -> None:
    for i, answers in enumerate(responses, start=1):
        r = client.post(f"{BASE_URL}/public/surveys/{slug}/respond", json={"answers": answers})
        r.raise_for_status()
        if i % 25 == 0 or i == len(responses):
            log(f"  Submitted {i}/{len(responses)} responses")


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


def main() -> int:
    log("=" * 70)
    log("  Synthetic Survey -> Analysis Pipeline")
    log("=" * 70)

    try:
        health = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        health.raise_for_status()
    except Exception as exc:
        log(f"ERROR: Backend not reachable at {BASE_URL} ({exc})")
        log("Start the server first:")
        log("  cd backend")
        log("  .\\venv\\Scripts\\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001")
        return 1

    with httpx.Client(timeout=120.0) as client:
        log("\n[1/5] Authenticating...")
        headers = auth_headers(client)

        log("[2/5] Creating survey and questions...")
        survey = create_survey(client, headers)
        survey_id, slug = survey["id"], survey["slug"]
        log(f"  Survey ID: {survey_id}")
        log(f"  Public slug: {slug}")

        question_ids = add_questions(client, headers, survey_id)
        log(f"  Added {len(question_ids)} questions")

        client.post(f"{BASE_URL}/surveys/{survey_id}/publish", headers=headers).raise_for_status()
        log("  Survey published")

        log(f"[3/5] Generating and submitting {N_RESPONSES} synthetic responses...")
        responses = generate_responses(question_ids, N_RESPONSES)
        submit_responses(client, slug, responses)

        stats = client.get(f"{BASE_URL}/surveys/{survey_id}/stats", headers=headers).json()
        log(f"  Survey stats: {stats}")

        log("[4/5] Starting analysis pipeline...")
        job = run_analysis(client, headers, survey_id)

        log("\n[5/5] Analysis complete!")
        log(f"  Job ID:     {job.get('id')}")
        log(f"  Status:     {job.get('status')}")
        log(f"  Rows:       {job.get('n_rows')}")
        log(f"  Columns:    {job.get('n_columns')}")
        log(f"  Report:     {job.get('report_path') or '(none)'}")
        selected = job.get("selected_tests") or []
        if selected:
            log(f"  Tests run:  {len(selected)}")
            for t in selected[:8]:
                name = t.get("test_name") or t.get("name") or str(t)
                log(f"    - {name}")
            if len(selected) > 8:
                log(f"    ... and {len(selected) - 8} more")

        log("\nDone.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

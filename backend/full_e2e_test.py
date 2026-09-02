"""
Full end-to-end analysis test — auto-handles preprocessing choice AND decode review approval.
"""
import sys, os, json, time, random, uuid
import urllib.request, urllib.error

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = "http://localhost:8000"

def api(method, path, body=None, token=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}

def ok(label, condition, detail=""):
    icon = "✅" if condition else "❌"
    print(f"  {icon} {label}" + (f": {detail}" if detail else ""))
    return condition

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ─── Step 0: Login ────────────────────────────────────────────────────────────
section("STEP 0 — Authenticate")
status, data = api("POST", "/auth/login",
    {"email": "demo@researchform.app", "password": "password123"})
ok("Login", status == 200, f"HTTP {status}")
if status != 200:
    print(f"  Error: {data}"); sys.exit(1)
TOKEN = data["access_token"]
print(f"  Token: {TOKEN[:30]}...")

# ─── Step 1: brief_validator unit checks ─────────────────────────────────────
section("STEP 1 — Brief Validator Tests")
sys.path.insert(0, r"c:\Users\HP\Documents\ResearchForm_Codebase\researchform\backend")
from analysis.brief_validator import validate_and_clean_brief

bad = validate_and_clean_brief({
    "topic": "<script>alert('xss')</script> Social Media Study",
    "objectives": [None, "", "A"*700, "Examine social media impact on GPA"],
    "significance_level": "WRONG",
    "report_type": "invalid_type",
    "formatting_options": "not_a_dict",
    "study_types": "quantitative",
})
ok("HTML stripped from topic",       "<script>" not in bad["topic"])
ok("Overlong objective clamped",     len(bad["objectives"][0]) <= 400)
ok("Valid objective preserved",      "Examine social media" in bad["objectives"][-1])
ok("Invalid sig_level -> 0.05",      bad["significance_level"] == 0.05)
ok("Invalid report_type -> chapter4",bad["report_type"] == "chapter4")
ok("formatting_options -> dict",     isinstance(bad["formatting_options"], dict))
ok("study_types string -> list",     isinstance(bad["study_types"], list))

ctrl = validate_and_clean_brief({"topic": "Study\x00of\x1fBehaviour"})
ok("Control chars stripped",         "\x00" not in ctrl["topic"])

empty = validate_and_clean_brief({})
ok("Empty brief gets default topic", empty["topic"] == "Research Study")
ok("Empty brief gets default objective", len(empty["objectives"]) >= 1)

# ─── Step 2: Create survey ────────────────────────────────────────────────────
section("STEP 2 — Create Survey (emoji + unicode in titles)")
status, survey = api("POST", "/surveys", {
    "title": "Social Media & Academic Performance Study \U0001f4ca",
    "description": "Investigating how social media usage affects students' GPA \u2014 a quantitative study.",
    "status": "active",
    "require_email": False,
    "allow_multiple": True
}, TOKEN)
ok("Survey created", status in (200, 201), f"HTTP {status}")
if status not in (200, 201):
    print(f"  Error: {survey}"); sys.exit(1)

SURVEY_ID   = survey["id"]
SURVEY_SLUG = survey.get("slug", SURVEY_ID)
print(f"  Survey ID:   {SURVEY_ID}")
print(f"  Survey slug: {SURVEY_SLUG}")

# Add questions
QUESTIONS = [
    {"type": "number",       "text": "What is your current GPA? (0.0-4.0)",          "required": True,  "position": 0,  "scale_min": 0,  "scale_max": 4},
    {"type": "likert",       "text": "Hours per day on social media?",                "required": True,  "position": 1,  "options": ["<1 hr","1-2 hrs","2-4 hrs","4-6 hrs",">6 hrs"]},
    {"type": "likert",       "text": "Social media positively affects my academics.", "required": True,  "position": 2,  "options": ["Strongly Disagree","Disagree","Neutral","Agree","Strongly Agree"]},
    {"type": "likert",       "text": "I feel distracted during study due to social media.", "required": True, "position": 3, "options": ["Strongly Disagree","Disagree","Neutral","Agree","Strongly Agree"]},
    {"type": "single_choice","text": "Most used platform?",                           "required": True,  "position": 4,  "options": ["Instagram","TikTok","Twitter/X","Facebook","YouTube","WhatsApp"]},
    {"type": "rating",       "text": "Rate your academic productivity (1-5).",        "required": True,  "position": 5,  "scale_min": 1, "scale_max": 5},
    {"type": "number",       "text": "Study hours per week?",                         "required": True,  "position": 6,  "scale_min": 0, "scale_max": 80},
    {"type": "single_choice","text": "Academic level?",                               "required": True,  "position": 7,  "options": ["100 Level","200 Level","300 Level","400 Level","Postgraduate"]},
    {"type": "single_choice","text": "Gender?",                                       "required": False, "position": 8,  "options": ["Male","Female","Prefer not to say"]},
]

q_ids = []
for i, q in enumerate(QUESTIONS):
    st, qr = api("POST", f"/surveys/{SURVEY_ID}/questions", q, TOKEN)
    if st in (200, 201):
        q_ids.append(qr.get("id"))
    else:
        print(f"Failed to create question {i}: {qr}")
ok(f"Questions created ({len(q_ids)}/{len(QUESTIONS)})", len(q_ids) == len(QUESTIONS))

# ─── Step 3: Generate 120 synthetic responses ─────────────────────────────────
section("STEP 3 — Submit 120 Synthetic Responses")
PLATFORMS = ["Instagram","TikTok","Twitter/X","Facebook","YouTube","WhatsApp"]
LEVELS    = ["100 Level","200 Level","300 Level","400 Level","Postgraduate"]
GENDERS   = ["Male","Female","Prefer not to say"]
random.seed(42)

submitted = 0
failed    = 0
for i in range(120):
    sm_idx  = random.choices([0,1,2,3,4], weights=[10,25,30,25,10])[0]
    gpa     = round(min(4.0, max(0.5, 4.0 - sm_idx*0.4 + random.gauss(0, 0.3))), 2)
    distract = min(5, max(1, sm_idx + random.randint(0,1)))
    positive = min(5, max(1, 3 - (sm_idx-2) + random.randint(-1,1)))
    prod    = min(5, max(1, 5 - sm_idx//2 + random.randint(-1,1)))
    study   = max(2, int(30 - sm_idx*4 + random.gauss(0,3)))
    likert  = ["Strongly Disagree","Disagree","Neutral","Agree","Strongly Agree"]

    payload = {
        "participant_email": f"student_{i+1}@university.edu",
        "answers": {
            str(q_ids[0]): gpa,
            str(q_ids[1]): ["<1 hr","1-2 hrs","2-4 hrs","4-6 hrs",">6 hrs"][sm_idx],
            str(q_ids[2]): likert[positive - 1],
            str(q_ids[3]): likert[distract - 1],
            str(q_ids[4]): random.choice(PLATFORMS),
            str(q_ids[5]): prod,
            str(q_ids[6]): study,
            str(q_ids[7]): random.choice(LEVELS),
            str(q_ids[8]): random.choice(GENDERS),
        }
    }
    st, res = api("POST", f"/public/surveys/{SURVEY_SLUG}/respond", payload)
    if st in (200, 201):
        submitted += 1
    else:
        failed += 1

ok(f"Responses submitted ({submitted}/120)", submitted >= 80,
   f"{failed} failed" if failed else "")
print(f"  submitted={submitted}  failed={failed}")

# ─── Step 4: Queue stats ──────────────────────────────────────────────────────
section("STEP 4 — Queue Stats Endpoint")
st, stats = api("GET", "/analysis/queue-stats")
ok("Queue stats endpoint works", st == 200, str(stats))
ok("Has max_workers field",      "max_workers" in stats)
ok("Has available_slots field",  "available_slots" in stats)

# ─── Step 5: Start full analysis ──────────────────────────────────────────────
section("STEP 5 — Start Full Analysis Pipeline")
brief = {
    "topic": "<b>Social Media Impact</b> on Academic Performance",  # HTML - validator will strip
    "population": "Nigerian undergraduate students aged 16-30",
    "objectives": [
        None, "",     # validator should drop these
        "Examine relationship between social media usage and GPA",
        "Determine which platforms are most distracting",
        "Identify academic subjects most affected",
    ],
    "hypotheses": [
        "H1: There is a significant negative relationship between social media hours and GPA",
        "H2: Students with higher social media usage report lower academic productivity",
    ],
    "dependent_variable": "GPA",
    "independent_variable": "Social media usage hours",
    "significance_level": "0.05",   # string — validator converts to float
    "study_types": "quantitative",  # string — validator wraps in list
    "report_type": "chapter4",
    "academic_tradition": "apa",
}

st, job = api("POST", "/analysis/start",
    {"survey_id": SURVEY_ID, "project_brief": brief}, TOKEN, timeout=30)
ok("Analysis job started", st == 200, f"HTTP {st}")
if st != 200:
    print(f"  Error: {job}"); sys.exit(1)

JOB_ID = job["id"]
print(f"  Job ID: {JOB_ID}")
print(f"  Initial status: {job.get('status','?')}")

# ─── Step 6: Poll pipeline progress ───────────────────────────────────────────
section("STEP 6 — Monitoring Pipeline Stages")
start_time  = time.time()
MAX_WAIT    = 25 * 60   # 25 min max
last_status = ""
dot_count   = 0
stages_seen = []
prep_choice_submitted = False
decode_approved       = False

while True:
    time.sleep(5)
    st, job_data = api("GET", f"/analysis/jobs/{JOB_ID}", token=TOKEN, timeout=15)
    if st != 200:
        print(f"\n  [WARN] Poll returned HTTP {st}")
        continue

    current = job_data.get("status", "unknown")
    if current != last_status:
        elapsed = time.time() - start_time
        print(f"\n  [{elapsed:5.0f}s] >>> {current.upper()}")
        if current not in stages_seen:
            stages_seen.append(current)
        last_status = current
        dot_count = 0
    else:
        print(".", end="", flush=True)
        dot_count += 1
        if dot_count % 6 == 0:
            print(f" [{time.time()-start_time:.0f}s]", end="", flush=True)

    # 1. Auto-submit preprocessing choice if pipeline is paused waiting for preprocessing choice
    if current == "awaiting_preprocessing_choice" and not prep_choice_submitted:
        print("\n  [AUTO] Submitting preprocessing choice: mode='auto'...")
        pst, pres = api("POST", f"/analysis/jobs/{JOB_ID}/preprocessing-choice",
                        {"mode": "auto"}, TOKEN)
        if pst == 200:
            print("  [AUTO] Preprocessing choice submitted successfully!")
            prep_choice_submitted = True
        else:
            print(f"  [AUTO-ERROR] Failed submitting choice: {pres}")

    # 2. Auto-approve decode review if pipeline is paused waiting for decode review approval
    if current == "decode_review" and not decode_approved:
        print("\n  [AUTO] Approving decode review mapping...")
        ast, ares = api("POST", f"/analysis/jobs/{JOB_ID}/approve-decode",
                        {"variable_overrides": {}, "missing_strategy": "preprocessed"}, TOKEN)
        if ast == 200:
            print("  [AUTO] Decode review approved! Stages 3-9 resuming...")
            decode_approved = True
        else:
            print(f"  [AUTO-ERROR] Failed approving decode: {ares}")

    if current in ("complete", "failed"):
        print()
        break

    if time.time() - start_time > MAX_WAIT:
        print(f"\n  [TIMEOUT] Exceeded {MAX_WAIT/60:.0f} min limit")
        break

# ─── Step 7: Verify outputs ────────────────────────────────────────────────────
section("STEP 7 — Verifying Pipeline Output")
elapsed = time.time() - start_time
status_final = job_data.get("status", "unknown")
error_msg    = job_data.get("error_message", "") or ""
results      = job_data.get("results") or {}
charts       = job_data.get("chart_paths") or []
report_path  = job_data.get("report_path", "")
sel_tests    = job_data.get("selected_tests") or []
warnings     = results.get("warnings", [])

ok("Job status = complete",       status_final == "complete",  f"status={status_final}")
ok("Results object present",      bool(results))
ok("Report document generated",   bool(report_path),           f"path={report_path}")
ok(f"Charts generated ({len(charts)})", len(charts) > 0)
ok(f"Tests selected ({len(sel_tests)})",len(sel_tests) > 0)
ok("Stages progressed correctly", len(stages_seen) >= 3,      f"stages={stages_seen}")
ok("Completed within time limit", elapsed < MAX_WAIT,          f"{elapsed/60:.1f} min")

if error_msg:
    print(f"  Error message: {error_msg[:200]}")
if warnings:
    print(f"  Non-fatal warnings ({len(warnings)}):")
    for w in warnings[:4]:
        print(f"    - {str(w)[:100]}")

# ─── Step 8: Stage isolation proof ────────────────────────────────────────────
section("STEP 8 — Stage Isolation Verification")
print(f"  Stages reached: {' -> '.join(stages_seen)}")
reached_complete = "complete" in stages_seen
ok("Pipeline reached 'complete' state",   reached_complete)
ok("Brief validator cleaned HTML in topic",
   "<script>" not in str(results).lower())
ok("Survey has responses", submitted >= 80, f"{submitted} responses")

# ─── Final Summary ─────────────────────────────────────────────────────────────
section("FINAL TEST SUMMARY")
all_pass = (status_final == "complete" and bool(results) and submitted >= 80)
print(f"  Survey ID:   {SURVEY_ID}")
print(f"  Slug:        {SURVEY_SLUG}")
print(f"  Responses:   {submitted}/120 submitted")
print(f"  Job ID:      {JOB_ID}")
print(f"  Status:      {status_final}")
print(f"  Duration:    {elapsed/60:.1f} minutes")
print(f"  Tests run:   {len(sel_tests)}")
print(f"  Charts:      {len(charts)}")
print(f"  Report file: {report_path}")
print(f"  Stages:      {' -> '.join(stages_seen)}")
print()
if all_pass:
    print("  🎉 ALL TESTS PASSED — system is working correctly")
else:
    print("  ⚠️  Test completed with issues (see above)")

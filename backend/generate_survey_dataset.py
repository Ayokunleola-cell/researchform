#!/usr/bin/env python
"""
generate_survey_dataset.py
==========================
Generates a realistic, comprehensive Employee Wellbeing & Performance Survey
dataset (n=350) that covers EVERY variable type needed to run all 145+
statistical tests in the ResearchForm analysis engine.

Dataset: "Employee Wellbeing, Stress & Organizational Performance Study"
Context: HR/Organizational Psychology survey across 5 departments, 3 regions.

Run:
    python generate_survey_dataset.py
Output:
    survey_dataset.csv          (the main dataset)
    survey_codebook.txt         (variable descriptions)
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(2024)
N = 350

# ─── Department / Region structure ────────────────────────────────────────────
departments  = np.tile(["Engineering","Marketing","HR","Finance","Operations"], N // 5 + 1)[:N]
regions      = np.tile(["North","South","East"], N // 3 + 1)[:N]
teams        = np.tile([f"T{i}" for i in range(1, 11)], N // 10 + 1)[:N]  # 10 teams
managers     = np.tile([f"MGR{i}" for i in range(1, 21)], N // 20 + 1)[:N]  # 20 managers

# ─── Demographics ─────────────────────────────────────────────────────────────
age          = RNG.normal(38, 10, N).clip(22, 65).round(0).astype(int)
gender       = RNG.choice(["Male", "Female", "Non-binary"], N, p=[0.50, 0.46, 0.04])
education    = RNG.choice(["High School","Bachelor","Master","PhD"], N, p=[0.12, 0.50, 0.30, 0.08])
tenure_years = RNG.gamma(2.5, 2, N).clip(0.5, 35).round(1)
years_exp    = (tenure_years + RNG.uniform(0, 5, N)).clip(0.5, 40).round(1)
is_manager   = (RNG.random(N) < 0.20).astype(int)   # 20% are managers
employment   = RNG.choice(["Full-time","Part-time","Contract"], N, p=[0.72, 0.18, 0.10])

# ─── Likert Survey Scales (1–5) ───────────────────────────────────────────────
# Burnout Scale (5 items) — higher = more burned out
burnout_base = RNG.normal(2.8, 0.8, N).clip(1, 5)
burnout_1    = (burnout_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
burnout_2    = (burnout_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
burnout_3    = (burnout_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
burnout_4    = (burnout_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
burnout_5    = (burnout_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
burnout_total = (burnout_1 + burnout_2 + burnout_3 + burnout_4 + burnout_5) / 5.0

# Job Satisfaction Scale (5 items) — higher = more satisfied
sat_base     = RNG.normal(3.3, 0.9, N).clip(1, 5)
satisfaction_1 = (sat_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
satisfaction_2 = (sat_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
satisfaction_3 = (sat_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
satisfaction_4 = (sat_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
satisfaction_5 = (sat_base + RNG.normal(0, 0.4, N)).clip(1, 5).round(0).astype(int)
satisfaction_total = (satisfaction_1 + satisfaction_2 + satisfaction_3 + satisfaction_4 + satisfaction_5) / 5.0

# Engagement Scale (3 items)
engage_base  = RNG.normal(3.4, 0.85, N).clip(1, 5)
engagement_1 = (engage_base + RNG.normal(0, 0.35, N)).clip(1, 5).round(0).astype(int)
engagement_2 = (engage_base + RNG.normal(0, 0.35, N)).clip(1, 5).round(0).astype(int)
engagement_3 = (engage_base + RNG.normal(0, 0.35, N)).clip(1, 5).round(0).astype(int)

# ─── Continuous / Ratio Variables ─────────────────────────────────────────────
salary       = (30000 + age * 800 + tenure_years * 600
                + (education == "Master") * 5000
                + (education == "PhD") * 12000
                + RNG.normal(0, 4000, N)).clip(28000, 180000).round(-2)
performance  = (3.2 + (satisfaction_total - 3) * 0.3 + (burnout_total - 3) * (-0.2)
                + RNG.normal(0, 0.5, N)).clip(1, 5).round(2)
productivity = (75 + (engagement_1 + engagement_2 + engagement_3) * 2.5
                - burnout_total * 3.5 + RNG.normal(0, 8, N)).clip(0, 100).round(1)
stress_score = (burnout_total * 15 + RNG.normal(0, 5, N)).clip(0, 100).round(1)
wellbeing    = (satisfaction_total * 12 + engagement_1 * 5
                - burnout_total * 8 + RNG.normal(0, 5, N)).clip(0, 100).round(1)

# ─── Pre / Post Intervention (Stress Reduction Program) ───────────────────────
stress_pre   = stress_score.copy()
stress_post  = (stress_pre * 0.82 + RNG.normal(0, 4, N)).clip(0, 100).round(1)  # ~18% improvement
stress_fu3m  = (stress_pre * 0.79 + RNG.normal(0, 5, N)).clip(0, 100).round(1)  # 3-month follow-up

# ─── Binary Outcomes ──────────────────────────────────────────────────────────
turnover_prob = 1 / (1 + np.exp(-(burnout_total * 0.6 - satisfaction_total * 0.5
                                  - tenure_years * 0.1 + RNG.normal(0, 0.3, N))))
turnover_intent = (turnover_prob > 0.45).astype(int)

promoted_prob = 1 / (1 + np.exp(-(performance * 0.8 + tenure_years * 0.05
                                   + is_manager * 0.5 + RNG.normal(0, 0.4, N) - 2)))
promoted = (promoted_prob > 0.5).astype(int)

received_training = (RNG.random(N) < 0.65).astype(int)

# KR-20 binary items (pass/fail competency test, 6 items)
comp_base  = (age / 65 * 0.3 + years_exp / 40 * 0.4 + RNG.random(N) * 0.3)
comp_item1 = (comp_base + RNG.random(N) * 0.3 > 0.5).astype(int)
comp_item2 = (comp_base + RNG.random(N) * 0.3 > 0.52).astype(int)
comp_item3 = (comp_base + RNG.random(N) * 0.3 > 0.48).astype(int)
comp_item4 = (comp_base + RNG.random(N) * 0.3 > 0.55).astype(int)
comp_item5 = (comp_base + RNG.random(N) * 0.3 > 0.50).astype(int)
comp_item6 = (comp_base + RNG.random(N) * 0.3 > 0.53).astype(int)

# ─── Count Variables ──────────────────────────────────────────────────────────
absences      = RNG.poisson(lam=3 + burnout_total * 0.8, size=N).clip(0, 30).astype(int)
training_sessions = RNG.poisson(lam=4, size=N).clip(0, 20).astype(int)
incidents     = RNG.poisson(lam=1.5, size=N).clip(0, 15).astype(int)
accomplishments = RNG.poisson(lam=6, size=N).clip(0, 25).astype(int)

# ─── Survival Data (Time to Promotion) ────────────────────────────────────────
time_to_promotion = (RNG.exponential(scale=36, size=N) + 6).clip(6, 120).round(0).astype(int)  # months
promotion_event   = promoted.copy()  # 1 = promoted during observation period

# ─── Ordinal Variables ────────────────────────────────────────────────────────
perf_rating_ord  = pd.cut(performance, bins=[0, 2.0, 3.0, 4.0, 5.01],
                           labels=[1, 2, 3, 4], right=True).astype(int)
stress_category  = pd.cut(stress_score, bins=[0, 30, 60, 100],
                           labels=["Low", "Moderate", "High"])

# ─── Time / Panel variables ───────────────────────────────────────────────────
observation_month = np.arange(N) % 24 + 1          # months 1-24 (panel wave)
quarter          = ((observation_month - 1) // 3 + 1).clip(1, 8)
fiscal_year      = (2023 + (observation_month > 12).astype(int))

# Time-series style variable (monthly KPI over 350 "records" ~ 2 years)
kpi_trend        = (np.sin(np.arange(N) * 2 * np.pi / 12) * 8  # seasonal
                    + np.arange(N) * 0.05                        # trend
                    + RNG.normal(0, 3, N)).round(2)               # noise

# ─── Mediator / Moderator ─────────────────────────────────────────────────────
workload         = (burnout_total * 12 + RNG.normal(0, 5, N)).clip(10, 70).round(1)
autonomy         = (satisfaction_total * 10 + RNG.normal(0, 5, N)).clip(10, 60).round(1)
social_support   = (5.0 - burnout_total * 0.5 + RNG.normal(0, 0.8, N)).clip(1, 5).round(2)

# ─── Assemble DataFrame ───────────────────────────────────────────────────────
df = pd.DataFrame({
    # ── ID & Structure ──────────────────────────────────────────────
    "employee_id":        np.arange(1, N + 1),
    "department":         departments,
    "region":             regions,
    "team":               teams,
    "manager_id":         managers,
    "observation_month":  observation_month,
    "quarter":            quarter,
    "fiscal_year":        fiscal_year,

    # ── Demographics ────────────────────────────────────────────────
    "age":                age,
    "gender":             gender,
    "education":          education,
    "tenure_years":       tenure_years,
    "years_experience":   years_exp,
    "is_manager":         is_manager,
    "employment_type":    employment,

    # ── Burnout Scale (5-item Likert 1-5) ───────────────────────────
    "burnout_1":          burnout_1,
    "burnout_2":          burnout_2,
    "burnout_3":          burnout_3,
    "burnout_4":          burnout_4,
    "burnout_5":          burnout_5,
    "burnout_total":      burnout_total.round(2),

    # ── Satisfaction Scale (5-item Likert 1-5) ──────────────────────
    "satisfaction_1":     satisfaction_1,
    "satisfaction_2":     satisfaction_2,
    "satisfaction_3":     satisfaction_3,
    "satisfaction_4":     satisfaction_4,
    "satisfaction_5":     satisfaction_5,
    "satisfaction_total": satisfaction_total.round(2),

    # ── Engagement Scale (3-item Likert 1-5) ────────────────────────
    "engagement_1":       engagement_1,
    "engagement_2":       engagement_2,
    "engagement_3":       engagement_3,

    # ── Continuous Outcomes ─────────────────────────────────────────
    "salary":             salary,
    "performance_score":  performance,
    "productivity_pct":   productivity,
    "stress_score":       stress_score,
    "wellbeing_index":    wellbeing,
    "workload_score":     workload,
    "autonomy_score":     autonomy,
    "social_support":     social_support,

    # ── Pre / Post (Repeated Measures) ─────────────────────────────
    "stress_pre":         stress_pre,
    "stress_post":        stress_post,
    "stress_3m_followup": stress_fu3m,

    # ── Binary Outcomes ─────────────────────────────────────────────
    "turnover_intent":    turnover_intent,
    "promoted":           promoted,
    "received_training":  received_training,

    # ── Competency Test Items (0/1) — for KR-20 ─────────────────────
    "comp_item1":         comp_item1,
    "comp_item2":         comp_item2,
    "comp_item3":         comp_item3,
    "comp_item4":         comp_item4,
    "comp_item5":         comp_item5,
    "comp_item6":         comp_item6,

    # ── Count Variables ─────────────────────────────────────────────
    "absences_count":     absences,
    "training_sessions":  training_sessions,
    "incidents_count":    incidents,
    "accomplishments":    accomplishments,

    # ── Survival ────────────────────────────────────────────────────
    "time_to_promotion":  time_to_promotion,
    "promotion_event":    promotion_event,

    # ── Ordinal ─────────────────────────────────────────────────────
    "perf_rating_1to4":   perf_rating_ord,
    "stress_category":    stress_category,

    # ── Time Series / Panel ─────────────────────────────────────────
    "kpi_score":          kpi_trend,
})

# ─── Save Dataset ─────────────────────────────────────────────────────────────
out = Path(__file__).parent / "survey_dataset.csv"
df.to_csv(out, index=False)
print(f"Dataset saved: {out}")
print(f"Shape: {df.shape[0]} rows × {df.shape[1]} columns")
print(f"\nColumn types summary:")
print(df.dtypes.value_counts())
print(f"\nSample (first 3 rows):")
print(df.head(3).to_string())

# ─── Write Codebook ───────────────────────────────────────────────────────────
codebook = """
SURVEY DATASET CODEBOOK
"Employee Wellbeing, Stress & Organizational Performance Study"
N = 350 participants | Variables = 56
================================================================

STUDY DESIGN
------------
Cross-sectional + longitudinal hybrid survey conducted across 5 departments
and 3 geographic regions. Includes pre/post stress intervention measures,
panel observations over 24 months, and linked HR records.

GROUPING VARIABLES (Categorical / Nominal)
-------------------------------------------
employee_id         : Unique participant ID (1–350)
department          : Work unit [Engineering, Marketing, HR, Finance, Operations]
region              : Geographic area [North, South, East]
team                : Team assignment [T1–T10]
manager_id          : Direct manager [MGR1–MGR20]
gender              : Gender identity [Male, Female, Non-binary]
education           : Highest qualification [High School, Bachelor, Master, PhD]
employment_type     : Contract type [Full-time, Part-time, Contract]
stress_category     : Stress level [Low, Moderate, High] — derived from stress_score

TIME / PANEL VARIABLES
-----------------------
observation_month   : Survey wave (1–24 months)
quarter             : Fiscal quarter (1–8)
fiscal_year         : Year of observation (2023 or 2024)
kpi_score           : Monthly KPI metric (continuous, seasonal trend + noise)

DEMOGRAPHIC CONTINUOUS
-----------------------
age                 : Age in years (22–65)
tenure_years        : Years at current organization (0.5–35)
years_experience    : Total work experience in years (0.5–40)
is_manager          : Manager status [0=No, 1=Yes]

BURNOUT SCALE (5-item, Likert 1–5; higher = more burned out)
-------------------------------------------------------------
burnout_1–burnout_5 : Individual item responses (1–5)
burnout_total       : Mean score across 5 items (1.0–5.0)
Expected Cronbach α ≈ 0.85

SATISFACTION SCALE (5-item, Likert 1–5; higher = more satisfied)
-----------------------------------------------------------------
satisfaction_1–satisfaction_5 : Individual responses (1–5)
satisfaction_total  : Mean score (1.0–5.0)
Expected Cronbach α ≈ 0.87

ENGAGEMENT SCALE (3-item, Likert 1–5)
---------------------------------------
engagement_1–engagement_3 : Item responses (1–5)

CONTINUOUS OUTCOMES
--------------------
salary              : Annual salary in GBP (£28,000–£180,000; log-normal)
performance_score   : Supervisor-rated performance (1.0–5.0)
productivity_pct    : Self-reported productivity % (0–100)
stress_score        : Derived stress index (0–100; higher = more stressed)
wellbeing_index     : Composite wellbeing score (0–100; higher = better)
workload_score      : Perceived workload (10–70; higher = more workload)
autonomy_score      : Job autonomy perception (10–60; higher = more autonomy)
social_support      : Perceived social support (1–5; higher = more support)

PRE/POST INTERVENTION (Repeated Measures)
------------------------------------------
stress_pre          : Stress score before intervention (0–100)
stress_post         : Stress score after 12-week program (0–100)
stress_3m_followup  : Stress score at 3-month follow-up (0–100)
Note: intervention reduces stress by ~18–21% on average

BINARY OUTCOMES [0 = No, 1 = Yes]
-----------------------------------
turnover_intent     : Intention to leave the organization
promoted            : Was promoted during observation period
received_training   : Participated in formal training program

COMPETENCY TEST ITEMS [0=Fail, 1=Pass] — for KR-20 Reliability
----------------------------------------------------------------
comp_item1–comp_item6 : Binary knowledge assessment items
Expected KR-20 ≈ 0.70–0.80

COUNT VARIABLES (non-negative integers)
-----------------------------------------
absences_count      : Days absent in last 12 months (0–30; Poisson λ≈5)
training_sessions   : # training sessions attended (0–20; Poisson λ=4)
incidents_count     : # workplace incidents reported (0–15; Poisson λ=1.5)
accomplishments     : # achievements logged (0–25; Poisson λ=6)

SURVIVAL ANALYSIS VARIABLES
-----------------------------
time_to_promotion   : Months from hire to promotion or end of study (6–120)
promotion_event     : Event indicator [1=promoted, 0=censored]

ORDINAL VARIABLES
------------------
perf_rating_1to4    : Ordinal performance band [1=Poor, 2=Fair, 3=Good, 4=Excellent]

SUGGESTED VARIABLE MAPPINGS FOR STATISTICAL TESTS
===================================================
Independent t-test    : gender × performance_score / salary / wellbeing_index
Paired t-test         : stress_pre × stress_post
One-way ANOVA         : department × performance_score / salary / productivity_pct
Two-way ANOVA         : department × gender × performance_score
ANCOVA                : department × wellbeing_index (covariate: age)
MANOVA                : department × [performance_score, wellbeing_index, stress_score]
Repeated ANOVA        : [stress_pre, stress_post, stress_3m_followup]
Pearson Correlation   : satisfaction_total × performance_score
Spearman Correlation  : burnout_total × absences_count
Chi-Square            : department × gender
Logistic Regression   : turnover_intent ← burnout_total + satisfaction_total + tenure_years
Poisson Regression    : absences_count ← burnout_total + workload_score + age
Neg. Binomial         : absences_count ← burnout_total + workload_score
Ordinal Regression    : perf_rating_1to4 ← engagement_1 + satisfaction_total
Multinomial Logistic  : department ← age + salary + satisfaction_total
Multiple Regression   : performance_score ← satisfaction_total + workload_score + autonomy_score
Mediation             : workload → burnout_total → performance_score
Moderation            : workload × autonomy_score → performance_score
Cox PH                : time_to_promotion + promotion_event ← performance_score + tenure_years
Kaplan-Meier          : time_to_promotion + promotion_event
Log-rank Test         : time_to_promotion + promotion_event + gender
LMM/LME               : performance_score ← satisfaction_total | team (random)
GLMM                  : turnover_intent ← burnout_total + age | department (random)
GEE                   : turnover_intent ← burnout_total + satisfaction_total | team
ICC                   : [burnout_1, burnout_2, burnout_3, burnout_4, burnout_5]
Cronbach α            : [burnout_1, burnout_2, burnout_3, burnout_4, burnout_5]
KR-20                 : [comp_item1, comp_item2, comp_item3, comp_item4, comp_item5, comp_item6]
Time Series           : kpi_score (observation_month as index)
Mann-Kendall          : kpi_score
ARIMA                 : kpi_score
Kaplan-Meier          : time_to_promotion + promotion_event
Factor Analysis       : [burnout_1..5, satisfaction_1..5, engagement_1..3]
PCA                   : [burnout_total, satisfaction_total, stress_score, wellbeing_index, performance_score, workload_score, autonomy_score]
"""

codebook_path = Path(__file__).parent / "survey_codebook.txt"
codebook_path.write_text(codebook.strip())
print(f"\nCodebook saved: {codebook_path}")

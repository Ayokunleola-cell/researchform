#!/usr/bin/env python
"""
generate_clinical_dataset.py
============================
Generates a realistic Clinical Patient Outcomes & Mental Health Study
dataset (n=400) — completely different domain from the HR survey.

Study: "Multisite Clinical Trial: CBT + Pharmacotherapy vs. Standard Care
        for Anxiety & Depression across 6 NHS Trusts"

Covers all variable types needed to exercise all 131 registered tests:
  - Continuous / ratio: biomarkers, scale scores, physiological measures
  - Likert (1–5 / 1–7): PHQ-9, GAD-7, WHODAS, SF-36 subscales
  - Binary items: symptom checklist (0/1) for KR-20
  - Binary outcomes: remission, readmission, adverse_event
  - Count: hospital_visits, medications_count, therapy_sessions
  - Repeated measures: anxiety_pre / post / 6m / 12m (4 timepoints)
  - Survival: days_to_remission, remission_event
  - Ordinal: severity_grade (1–4), treatment_response (1–5)
  - Categorical: treatment_arm, hospital, diagnosis, sex, ethnicity
  - Panel / time-series: daily_steps (12-month wearable KPI)
  - Multilevel groups: hospital (6), ward (15), clinician (30)

Run:
    python generate_clinical_dataset.py
Output:
    clinical_dataset.csv
    clinical_codebook.txt
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(2025)
N = 400

# ─── Study Structure ──────────────────────────────────────────────────────────
hospitals   = np.tile(["NHS_North", "NHS_South", "NHS_East",
                       "NHS_West", "NHS_Central", "NHS_Metro"], N // 6 + 1)[:N]
wards       = np.tile([f"Ward_{i}" for i in range(1, 16)], N // 15 + 1)[:N]
clinicians  = np.tile([f"Clin_{i:02d}" for i in range(1, 31)], N // 30 + 1)[:N]

# Two-arm RCT: CBT+Pharma vs Standard Care
treatment_arm = np.where(RNG.random(N) < 0.50, "CBT_Pharma", "Standard_Care")
study_month   = np.arange(N) % 18 + 1   # 18-month follow-up window

# ─── Demographics ─────────────────────────────────────────────────────────────
age         = RNG.normal(42, 14, N).clip(18, 80).round(0).astype(int)
sex         = RNG.choice(["Male", "Female"], N, p=[0.38, 0.62])
ethnicity   = RNG.choice(["White", "Asian", "Black", "Mixed", "Other"],
                          N, p=[0.62, 0.16, 0.11, 0.07, 0.04])
education   = RNG.choice(["None", "GCSE", "A-Level", "Degree", "Postgrad"],
                          N, p=[0.08, 0.22, 0.28, 0.30, 0.12])
employed    = (RNG.random(N) < 0.55).astype(int)
comorbid    = RNG.poisson(1.2, N).clip(0, 6).astype(int)  # number of comorbidities
bmi         = RNG.normal(26.8, 5.2, N).clip(16, 50).round(1)

# ─── Diagnosis ────────────────────────────────────────────────────────────────
diagnosis   = RNG.choice(["MDD", "GAD", "MDD+GAD", "PTSD", "Dysthymia"],
                          N, p=[0.30, 0.25, 0.22, 0.13, 0.10])
duration_months = RNG.gamma(3, 8, N).clip(1, 120).round(0).astype(int)  # illness duration

# ─── PHQ-9 Depression Scale (9 items, 0–3 each) — Pre-treatment ───────────────
phq_severity = RNG.normal(14, 4.5, N).clip(5, 27)   # baseline total PHQ-9
phq_item = lambda s: (s / 27 * 3 + RNG.normal(0, 0.3, N)).clip(0, 3).round(0).astype(int)
phq9_1 = phq_item(phq_severity)
phq9_2 = phq_item(phq_severity)
phq9_3 = phq_item(phq_severity)
phq9_4 = phq_item(phq_severity)
phq9_5 = phq_item(phq_severity)
phq9_6 = phq_item(phq_severity)
phq9_7 = phq_item(phq_severity)
phq9_8 = phq_item(phq_severity)
phq9_9 = phq_item(phq_severity)
phq9_total_pre = (phq9_1 + phq9_2 + phq9_3 + phq9_4 + phq9_5 +
                  phq9_6 + phq9_7 + phq9_8 + phq9_9).clip(0, 27)

# ─── GAD-7 Anxiety Scale (7 items, 0–3) — Pre-treatment ──────────────────────
gad_severity = RNG.normal(12, 3.8, N).clip(4, 21)
gad_item = lambda s: (s / 21 * 3 + RNG.normal(0, 0.3, N)).clip(0, 3).round(0).astype(int)
gad7_1 = gad_item(gad_severity)
gad7_2 = gad_item(gad_severity)
gad7_3 = gad_item(gad_severity)
gad7_4 = gad_item(gad_severity)
gad7_5 = gad_item(gad_severity)
gad7_6 = gad_item(gad_severity)
gad7_7 = gad_item(gad_severity)
gad7_total_pre = (gad7_1 + gad7_2 + gad7_3 + gad7_4 +
                  gad7_5 + gad7_6 + gad7_7).clip(0, 21)

# ─── SF-36 Quality of Life Subscales (0–100, higher = better) ────────────────
qol_base  = RNG.normal(45, 15, N).clip(0, 100)
physical_function  = (qol_base + RNG.normal(0, 8, N)).clip(0, 100).round(1)
mental_health_sf   = (qol_base - phq_severity * 1.5 + RNG.normal(0, 8, N)).clip(0, 100).round(1)
social_function    = (qol_base - gad_severity * 1.2 + RNG.normal(0, 8, N)).clip(0, 100).round(1)
vitality_score     = (qol_base + RNG.normal(0, 10, N)).clip(0, 100).round(1)

# ─── Biomarkers ───────────────────────────────────────────────────────────────
cortisol_am    = (RNG.lognormal(2.5, 0.4, N)).clip(5, 80).round(2)  # nmol/L
crp_mg_l       = (RNG.lognormal(0.8, 0.7, N)).clip(0.1, 50).round(2)  # C-reactive protein
bdnf_pg_ml     = (RNG.normal(28, 8, N) - phq_severity * 0.3 + RNG.normal(0, 2, N)).clip(5, 60).round(2)
heart_rate     = RNG.normal(74, 10, N).clip(50, 110).round(0).astype(int)
systolic_bp    = RNG.normal(122, 14, N).clip(90, 180).round(0).astype(int)

# ─── Treatment Response: Post (6-week) ────────────────────────────────────────
# CBT+Pharma arm gets stronger improvement
cbt_effect = (treatment_arm == "CBT_Pharma").astype(float)
phq9_post  = (phq9_total_pre * (0.65 - 0.15 * cbt_effect) + RNG.normal(0, 2, N)).clip(0, 27).round(1)
gad7_post  = (gad7_total_pre * (0.68 - 0.14 * cbt_effect) + RNG.normal(0, 2, N)).clip(0, 21).round(1)

# ─── Repeated Measures (4 timepoints: baseline, 6-wk, 6-mo, 12-mo) ───────────
phq9_baseline = phq9_total_pre.astype(float)
phq9_6wk      = phq9_post
phq9_6mo      = (phq9_post * 0.85 + RNG.normal(0, 1.5, N)).clip(0, 27).round(1)
phq9_12mo     = (phq9_post * 0.78 + RNG.normal(0, 2, N)).clip(0, 27).round(1)

gad7_baseline = gad7_total_pre.astype(float)
gad7_6wk      = gad7_post
gad7_6mo      = (gad7_post * 0.83 + RNG.normal(0, 1.5, N)).clip(0, 21).round(1)
gad7_12mo     = (gad7_post * 0.76 + RNG.normal(0, 1.8, N)).clip(0, 21).round(1)

# ─── Remission (binary: ~40% rate, higher in CBT_Pharma arm) ────────────────
remission_logit = (cbt_effect * 1.2 - phq9_baseline * 0.08
                   + age * 0.008 + RNG.normal(0, 0.4, N))
# Force ~40% remission rate using percentile threshold
threshold = np.percentile(remission_logit, 60)  # top 40% → remission
remission = (remission_logit > threshold).astype(int)

# ─── Binary Outcomes ──────────────────────────────────────────────────────────
readmission_prob = 1 / (1 + np.exp(-(comorbid * 0.3 - cbt_effect * 0.5
                                      + phq9_6mo * 0.08 + RNG.normal(0, 0.3, N) - 2.5)))
readmitted    = (readmission_prob > 0.4).astype(int)
adverse_event = (RNG.random(N) < 0.12).astype(int)
dropout       = (RNG.random(N) < 0.18).astype(int)

# ─── Symptom Checklist (binary items for KR-20) ───────────────────────────────
sev_base = phq_severity / 27
sym_item = lambda: (sev_base + RNG.random(N) * 0.4 > 0.55).astype(int)
sym_item1 = sym_item(); sym_item2 = sym_item(); sym_item3 = sym_item()
sym_item4 = sym_item(); sym_item5 = sym_item(); sym_item6 = sym_item()
sym_item7 = sym_item(); sym_item8 = sym_item()

# ─── Count Variables ──────────────────────────────────────────────────────────
hospital_visits   = RNG.poisson(lam=3 + comorbid * 0.8, size=N).clip(0, 25).astype(int)
therapy_sessions  = RNG.poisson(lam=12 * (treatment_arm == "CBT_Pharma") + 3, size=N).clip(0, 30).astype(int)
medications_count = RNG.poisson(lam=2.5 + comorbid * 0.5, size=N).clip(0, 12).astype(int)
adverse_events_n  = RNG.poisson(lam=0.8, size=N).clip(0, 8).astype(int)

# ─── Survival (Days to Remission) ─────────────────────────────────────────────
days_to_remission = (RNG.exponential(scale=120, size=N) * (1 - 0.3 * cbt_effect)
                     + 14).clip(14, 365).round(0).astype(int)
remission_event   = remission.copy()  # 1 = remission observed, 0 = censored

# ─── Numeric treatment indicator (for DiD, propensity matching, etc.) ────────
treatment_numeric = (treatment_arm == "CBT_Pharma").astype(int)  # 1=CBT, 0=Standard

# ─── Ordinal Variables ────────────────────────────────────────────────────────
severity_grade    = pd.cut(phq9_baseline, bins=[0, 9, 14, 19, 28],
                           labels=[1, 2, 3, 4], right=True).astype(int)
treatment_response = pd.cut(phq9_baseline - phq9_12mo,
                             bins=[-30, 0, 5, 10, 16, 30],
                             labels=[1, 2, 3, 4, 5], right=True).astype(int)

# ─── Time-Series / Panel Variable ────────────────────────────────────────────
# Daily steps (wearable, monthly average) — improves with treatment
daily_steps = (6000 + (1 - phq9_baseline / 27) * 3000
               + np.sin(np.arange(N) * 2 * np.pi / 12) * 500  # seasonal
               + np.arange(N) * 2.5                             # trend
               + RNG.normal(0, 400, N)).clip(1000, 15000).round(0).astype(int)

# ─── Assemble DataFrame ───────────────────────────────────────────────────────
df = pd.DataFrame({
    # ── ID & Structure ──────────────────────────────────────────────────────
    "patient_id":         np.arange(1, N + 1),
    "hospital":           hospitals,
    "ward":               wards,
    "clinician":          clinicians,
    "study_month":        study_month,

    # ── Grouping / Categorical ──────────────────────────────────────────────
    "treatment_arm":      treatment_arm,
    "treatment_numeric":  treatment_numeric,   # 1=CBT_Pharma, 0=Standard_Care
    "diagnosis":          diagnosis,
    "sex":                sex,
    "ethnicity":          ethnicity,
    "education":          education,

    # ── Demographics ────────────────────────────────────────────────────────
    "age":                age,
    "employed":           employed,
    "comorbidities":      comorbid,
    "bmi":                bmi,
    "duration_months":    duration_months,

    # ── PHQ-9 Items (0–3 each) ───────────────────────────────────────────────
    "phq9_1": phq9_1, "phq9_2": phq9_2, "phq9_3": phq9_3,
    "phq9_4": phq9_4, "phq9_5": phq9_5, "phq9_6": phq9_6,
    "phq9_7": phq9_7, "phq9_8": phq9_8, "phq9_9": phq9_9,

    # ── GAD-7 Items (0–3 each) ───────────────────────────────────────────────
    "gad7_1": gad7_1, "gad7_2": gad7_2, "gad7_3": gad7_3,
    "gad7_4": gad7_4, "gad7_5": gad7_5, "gad7_6": gad7_6, "gad7_7": gad7_7,

    # ── Scale Totals ────────────────────────────────────────────────────────
    "phq9_total_pre":     phq9_total_pre,
    "gad7_total_pre":     gad7_total_pre,

    # ── SF-36 Subscales ─────────────────────────────────────────────────────
    "physical_function":  physical_function,
    "mental_health_sf":   mental_health_sf,
    "social_function":    social_function,
    "vitality_score":     vitality_score,

    # ── Biomarkers ──────────────────────────────────────────────────────────
    "cortisol_am":        cortisol_am,
    "crp_mg_l":           crp_mg_l,
    "bdnf_pg_ml":         bdnf_pg_ml,
    "heart_rate":         heart_rate,
    "systolic_bp":        systolic_bp,

    # ── Repeated Measures (4 timepoints) ────────────────────────────────────
    "phq9_baseline":      phq9_baseline,
    "phq9_6wk":           phq9_6wk,
    "phq9_6mo":           phq9_6mo,
    "phq9_12mo":          phq9_12mo,
    "gad7_baseline":      gad7_baseline,
    "gad7_6wk":           gad7_6wk,
    "gad7_6mo":           gad7_6mo,
    "gad7_12mo":          gad7_12mo,

    # ── Binary Outcomes ─────────────────────────────────────────────────────
    "remission":          remission,
    "readmitted":         readmitted,
    "adverse_event":      adverse_event,
    "dropout":            dropout,
    "employed":           employed,

    # ── Symptom Checklist Items (0/1) — for KR-20 ───────────────────────────
    "sym_item1": sym_item1, "sym_item2": sym_item2, "sym_item3": sym_item3,
    "sym_item4": sym_item4, "sym_item5": sym_item5, "sym_item6": sym_item6,
    "sym_item7": sym_item7, "sym_item8": sym_item8,

    # ── Count Variables ─────────────────────────────────────────────────────
    "hospital_visits":    hospital_visits,
    "therapy_sessions":   therapy_sessions,
    "medications_count":  medications_count,
    "adverse_events_n":   adverse_events_n,

    # ── Survival ────────────────────────────────────────────────────────────
    "days_to_remission":  days_to_remission,
    "remission_event":    remission_event,

    # ── Ordinal ─────────────────────────────────────────────────────────────
    "severity_grade":     severity_grade,
    "treatment_response": treatment_response,

    # ── Time Series / Panel ─────────────────────────────────────────────────
    "daily_steps":        daily_steps,
})

# Drop duplicate 'employed' column
df = df.loc[:, ~df.columns.duplicated()]

out = Path(__file__).parent / "clinical_dataset.csv"
df.to_csv(out, index=False)
print(f"Clinical dataset saved: {out}")
print(f"Shape: {df.shape[0]} rows × {df.shape[1]} columns")
print(f"\nColumn types:")
print(df.dtypes.value_counts())
print(f"\nSample (first 2 rows):")
print(df.iloc[:, :15].head(2).to_string())

# ─── Codebook ─────────────────────────────────────────────────────────────────
codebook = """
CLINICAL DATASET CODEBOOK
"Multisite RCT: CBT+Pharmacotherapy vs Standard Care for Anxiety & Depression"
N = 400 patients | Variables = 68+ | Sites = 6 NHS Trusts

STUDY DESIGN
------------
Parallel-arm randomised controlled trial across 6 NHS hospital sites.
Patients with MDD, GAD, or comorbid presentations randomised 1:1 to:
  - CBT_Pharma: Cognitive Behavioural Therapy + Pharmacotherapy
  - Standard_Care: Treatment as usual (medication only)
Primary outcome: PHQ-9 remission at 12 months (score < 5)

SUGGESTED VARIABLE MAPPINGS FOR STATISTICAL TESTS
===================================================
Independent t-test     : treatment_arm × phq9_12mo
Paired t-test          : phq9_baseline vs phq9_6wk (or gad7_baseline vs gad7_6wk)
Repeated ANOVA         : phq9_baseline, phq9_6wk, phq9_6mo, phq9_12mo
One-way ANOVA          : diagnosis × phq9_total_pre
Welch ANOVA            : hospital × phq9_12mo
Two-way ANOVA          : treatment_arm × sex × phq9_12mo
ANCOVA                 : treatment_arm × phq9_12mo (covariate: phq9_baseline)
MANOVA                 : treatment_arm × [phq9_12mo, gad7_12mo, vitality_score]
Cronbach α             : phq9_1 … phq9_9
McDonald Omega         : gad7_1 … gad7_7
ICC                    : phq9_1 … phq9_9
KR-20                  : sym_item1 … sym_item8 (binary)
Pearson Correlation    : phq9_12mo × mental_health_sf
Spearman Correlation   : severity_grade × treatment_response
Logistic Regression    : remission ← treatment_arm + age + phq9_baseline + comorbidities
Poisson Regression     : hospital_visits ← comorbidities + phq9_baseline + age
Neg. Binomial          : hospital_visits ← comorbidities + medications_count
Ordinal Regression     : severity_grade ← phq9_total_pre + age + bmi
Multinomial Logistic   : diagnosis ← age + bmi + phq9_total_pre
Mediation              : phq9_baseline → mental_health_sf → phq9_12mo
Moderation             : phq9_baseline × treatment_arm → phq9_12mo
Cox PH                 : days_to_remission + remission_event ← treatment_arm + age + phq9_baseline
Kaplan-Meier           : days_to_remission + remission_event
Log-rank Test          : days_to_remission + remission_event + treatment_arm
LMM                    : phq9_12mo ← phq9_baseline + treatment_arm | hospital (random)
GLMM                   : remission ← phq9_baseline + age | hospital (random)
GEE                    : remission ← phq9_baseline + treatment_arm | ward (clustered)
PCA                    : phq9_total_pre, gad7_total_pre, cortisol_am, bdnf_pg_ml, crp_mg_l
Factor Analysis        : phq9_1..9 (depression factor)
CFA                    : phq9_1..9 (1-factor model)
SEM                    : phq9_baseline → bdnf_pg_ml → phq9_12mo
Synthetic Control      : phq9_12mo, study_month, hospital (treatment=NHS_North)
Time Series            : daily_steps
Mann-Kendall           : daily_steps (trend test)
Difference-in-Diff     : treatment_arm, study_month, phq9_12mo
"""
(Path(__file__).parent / "clinical_codebook.txt").write_text(codebook.strip())
print("\nCodebook saved: clinical_codebook.txt")

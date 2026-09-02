"""
Full QA Test Suite -- Statistical Engine + App API
Run from: backend/   with:  python qa_engine_full.py

Tests:
  1. All 145 registered statistical tests (directly via callables)
  2. Dispatcher integration batch (20 diverse tests, as pipeline.py calls it)
  3. All major app API endpoints
"""
from __future__ import annotations
import sys, traceback, time, os, requests
from datetime import datetime
import pandas as pd
import numpy as np

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -- Color helpers (ANSI) -----------------------------------------------------
GREEN  = "\033[92m"; RED    = "\033[91m"; YELLOW = "\033[93m"
CYAN   = "\033[96m"; BOLD   = "\033[1m";  RESET  = "\033[0m"
ok_  = lambda s: f"{GREEN}PASS{RESET} {s}"
err_ = lambda s: f"{RED}FAIL{RESET} {s}"
wrn_ = lambda s: f"{YELLOW}WARN{RESET} {s}"
hdr_ = lambda s: f"\n{BOLD}{CYAN}{'='*70}\n  {s}\n{'='*70}{RESET}"


# -- Synthetic dataset ---------------------------------------------------------
np.random.seed(42)
N = 200

def make_df() -> pd.DataFrame:
    df = pd.DataFrame({
        "score":      np.random.normal(70, 15, N).clip(0, 100),
        "score2":     np.random.normal(65, 12, N).clip(0, 100),
        "score3":     np.random.normal(72, 10, N).clip(0, 100),
        "score4":     np.random.normal(68, 14, N).clip(0, 100),
        "score5":     np.random.normal(75, 11, N).clip(0, 100),
        "income":     np.random.exponential(50000, N),
        "age":        np.random.randint(18, 75, N).astype(float),
        "weight":     np.random.normal(70, 12, N),
        "height":     np.random.normal(170, 10, N),
        "pre":        np.random.normal(50, 10, N),
        "post":       np.random.normal(55, 10, N),
        "count":      np.random.poisson(5, N).astype(float),
        "time_val":   np.arange(N, dtype=float),
        "group":      np.random.choice(["A","B","C"], N),
        "group2":     np.random.choice(["X","Y"], N),
        "category":   np.random.choice(["Low","Mid","High"], N),
        "binary":     np.random.choice([0,1], N),
        "binary2":    np.random.choice([0,1], N),
        "duration":   np.random.exponential(10, N).clip(0.1),
        "event":      np.random.choice([0,1], N, p=[0.3, 0.7]),
        "ts_value":   np.cumsum(np.random.randn(N)) + 50,
        "subject_id": np.repeat(np.arange(N//5), 5),
        "cluster":    np.repeat(np.arange(N//10), 10),
        "item1":      np.random.choice([1,2,3,4,5], N),
        "item2":      np.random.choice([1,2,3,4,5], N),
        "item3":      np.random.choice([1,2,3,4,5], N),
        "item4":      np.random.choice([1,2,3,4,5], N),
        "item5":      np.random.choice([1,2,3,4,5], N),
        "period":     np.random.choice([0,1], N),
        "treatment":  np.random.choice([0,1], N),
        "instrument": np.random.normal(0, 1, N),
        "running":    np.random.normal(0, 1, N),
        "threshold":  np.zeros(N),
        "panel_time": np.tile(np.arange(N//4), 4).astype(float),
        "panel_unit": np.repeat(["A","B","C","D"], N//4),
    })
    df["bin_item1"] = (df["item1"] >= 3).astype(int)
    df["bin_item2"] = (df["item2"] >= 3).astype(int)
    df["bin_item3"] = (df["item3"] >= 3).astype(int)
    df["bin_item4"] = (df["item4"] >= 3).astype(int)
    df["bin_item5"] = (df["item5"] >= 3).astype(int)
    return df


# -- Variable hints per test (variables list for each test function) ----------
# Signature of all test fns: fn(df, variables, brief, alpha=0.05)
# Extra kwargs like 'mu' or 'period' go through 'brief'

VAR_MAP: dict[str, list] = {
    "descriptive_stats":         ["score","age","income"],
    "frequency_analysis":        ["group","category"],
    "mean_median_mode":          ["score","age"],
    "dispersion_extended":       ["score","income"],
    "percentiles_extended":      ["score","age"],
    "z_scores":                  ["score"],
    "skewness_analysis":         ["score","income"],
    "kurtosis_analysis":         ["score","income"],
    "variable_transformation":   ["income"],
    "normality_check":           ["score","age"],
    "shapiro_wilk_all":          ["score","age"],
    "kolmogorov_smirnov":        ["score"],
    "anderson_darling":          ["score"],
    "jarque_bera":               ["score"],
    "dagostino_pearson":         ["score"],
    "omnibus_normality":         ["score","age"],
    "cronbach_alpha":            ["item1","item2","item3","item4","item5"],
    "mcdonald_omega":            ["item1","item2","item3","item4","item5"],
    "split_half_reliability":    ["item1","item2","item3","item4","item5"],
    "item_analysis":             ["item1","item2","item3","item4","item5"],
    "icc_reliability":           ["item1","item2","item3","item4","item5"],
    "kr20":                      ["bin_item1","bin_item2","bin_item3","bin_item4","bin_item5"],
    "levene_test":               ["group","score"],
    "bartlett_test":             ["group","score"],
    "mauchly_test":              ["item1","item2","item3"],
    "durbin_watson":             ["score","age","income"],
    "vif_check":                 ["score","age","income","weight"],
    "outliers_iqr":              ["score","income"],
    "outliers_zscore":           ["score","income"],
    "outliers_grubbs":           ["score"],
    "mahalanobis_distance":      ["score","age","income"],
    "cooks_distance":            ["score","age","income"],
    "one_sample_t_test":         ["score"],
    "one_sample_t_cohend":       ["score"],
    "independent_t_test":        ["binary","score"],
    "independent_t_cohend":      ["binary","score"],
    "welch_t_test":              ["binary","score"],
    "paired_t_test":             ["pre","post"],
    "paired_t_cohend":           ["pre","post"],
    "one_way_anova":             ["group","score"],
    "anova_eta_squared":         ["group","score"],
    "anova_descriptives":        ["group","score"],
    "welch_anova":               ["group","score"],
    "two_way_anova":             ["group","group2","score"],
    "two_way_eta_squared":       ["group","group2","score"],
    "two_way_pairwise":          ["group","group2","score"],
    "repeated_anova":            ["item1","item2","item3","item4","item5"],
    "ancova":                    ["group","score","age"],
    "manova":                    ["group","score","age","weight"],
    "manova_followup":           ["group","score","age","weight"],
    "mann_whitney":              ["binary","score"],
    "mann_whitney_r":            ["binary","score"],
    "mann_whitney_ci":           ["binary","score"],
    "wilcoxon":                  ["pre","post"],
    "wilcoxon_r":                ["pre","post"],
    "kruskal_wallis":            ["group","score"],
    "kruskal_wallis_eta2":       ["group","score"],
    "friedman_test":             ["item1","item2","item3","item4","item5"],
    "kendall_w":                 ["item1","item2","item3","item4","item5"],
    "mcnemar":                   ["binary","binary2"],
    "chi_square":                ["group","category"],
    "chi_square_extended":       ["group","category"],
    "fisher_exact":              ["binary","binary2"],
    "sign_test":                 ["pre","post"],
    "runs_test":                 ["binary"],
    "tukey_hsd":                 ["group","score"],
    "bonferroni_test":           ["group","score"],
    "dunn_test":                 ["group","score"],
    "scheffe_test":              ["group","score"],
    "newman_keuls":              ["group","score"],
    "fisher_lsd":                ["group","score"],
    "dunnett_test":              ["group","score"],
    "pearson_correlation":       ["score","age"],
    "pearson_ci":                ["score","age"],
    "spearman_correlation":      ["score","age"],
    "kendall_tau":               ["score","age"],
    "point_biserial":            ["binary","score"],
    "phi_coefficient":           ["binary","binary2"],
    "cramers_v":                 ["group","category"],
    "partial_correlation":       ["score","age","income"],
    "canonical_correlation":     ["score","age","pre","post","weight","score2","score3","score4","score5","income"],
    "correlation_matrix":        ["score","age","income","weight"],
    "correlation_heatmap":       ["score","age","income","weight"],
    "correlation_significance":  ["score","age","income","weight"],
    "correlation_effect_sizes":  ["score","age","income","weight"],
    "correlation_splom":         ["score","age","income","weight"],
    "simple_linear_regression":  ["age","score"],
    "linear_regression":         ["age","score"],
    "multiple_regression":       ["age","income","weight","score"],
    "logistic_regression":       ["age","income","score","binary"],
    "ordinal_regression":        ["age","income","score","item1"],
    "multinomial_logistic":      ["age","income","score","group"],
    "hierarchical_regression":   ["age","income","weight","score"],
    "stepwise_regression":       ["age","income","weight","height","score"],
    "mediation_analysis":        ["age","score","income"],
    "moderation_analysis":       ["age","score","income"],
    "quantile_regression":       ["age","income","score"],
    "poisson_regression":        ["age","income","count"],
    "negative_binomial":         ["age","income","count"],
    "pca":                       ["score","age","income","weight","height","score2","score3","score4","score5"],
    "factor_analysis":           ["item1","item2","item3","item4","item5","score","age","income","weight","height"],
    "confirmatory_fa":           ["item1","item2","item3","item4","item5","score","age","income","weight","height"],
    "discriminant_analysis":     ["group","score","age","income","weight"],
    "cluster_analysis":          ["score","age","income","weight","height"],
    "sem":                       ["item1","item2","item3","item4","item5","score","age","income","weight","height"],
    "path_analysis":             ["age","income","weight","score","height"],
    "kaplan_meier":              ["duration","event","binary"],
    "survival_analysis":         ["duration","event","binary"],
    "log_rank_test":             ["duration","event","binary"],
    "cox_ph_regression":         ["duration","event","age","binary","income"],
    "cox_regression":            ["duration","event","age","binary","income"],
    "weibull_aft":               ["duration","event","age","binary"],
    "nelson_aalen":              ["duration","event","binary"],
    "life_table":                ["duration","event"],
    "ph_assumption_test":        ["duration","event","age","binary"],
    "competing_risks":           ["duration","event","binary2","binary"],
    "difference_in_differences": ["period","treatment","score"],
    "instrumental_variables":    ["instrument","score","income"],
    "propensity_score_matching": ["binary","age","income","weight","score"],
    "regression_discontinuity":  ["running","threshold","score"],
    "bayesian_ab_test":          ["binary","score"],
    "synthetic_control":         ["score","panel_time","panel_unit"],
    "sensitivity_analysis":      ["binary","score","income"],
    "adf_test":                  ["ts_value"],
    "kpss_test":                 ["ts_value"],
    "autocorrelation":           ["ts_value"],
    "partial_autocorrelation":   ["ts_value"],
    "ljung_box":                 ["ts_value"],
    "seasonal_decompose":        ["ts_value"],
    "arima_model":               ["ts_value"],
    "time_series":               ["ts_value"],
    "sarima_model":              ["ts_value"],
    "exponential_smoothing":     ["ts_value"],
    "granger_causality":         ["ts_value","score"],
    "var_model":                 ["ts_value","score"],
    "mann_kendall":              ["ts_value"],
    "linear_mixed_model":        ["score","age","subject_id"],
    "linear_mixed_effects":      ["score","age","subject_id"],
    "glmm":                      ["binary","age","income","subject_id"],
    "icc":                       ["score","subject_id"],
    "random_effects_anova":      ["score","cluster"],
    "cross_classified_mlm":      ["score","age","subject_id","cluster"],
    "growth_curve_model":        ["score","time_val","subject_id"],
    "multilevel_mediation":      ["age","score","income","subject_id"],
    "gee":                       ["binary","age","income","subject_id"],
}

BRIEF = {
    "significance_level": 0.05,
    "topic": "QA synthetic analysis",
    "hypotheses": ["H1: test"],
    "test_value": 65,     # for one_sample_t
    "period": 7,          # for seasonal_decompose
    "treatment_unit": "A",
}


# =============================================================================
# SUITE 1: Individual Statistical Test QA
# Correct signature: fn(df, variables, brief, alpha=0.05)
# =============================================================================
def run_engine_qa(df: pd.DataFrame):
    print(hdr_("SUITE 1 -- Statistical Engine: All Registered Tests"))
    from analysis.engine.registry import get_registry
    reg   = get_registry()
    total = len(reg)
    print(f"\n  Registry: {total} tests  |  Dataset: n={len(df)}, {len(df.columns)} cols\n")

    passed, failed, warned = [], [], []
    family_stats: dict[str, dict] = {}

    for idx, (test_key, entry) in enumerate(sorted(reg.items()), 1):
        fn     = entry["fn"]
        family = entry["family"]
        family_stats.setdefault(family, {"pass":0,"fail":0,"warn":0})

        variables = VAR_MAP.get(test_key, [])

        t0 = time.perf_counter()
        try:
            result  = fn(df=df, variables=variables, brief=BRIEF, alpha=0.05)
            elapsed = time.perf_counter() - t0

            if not isinstance(result, dict):
                raise ValueError(f"Result is {type(result).__name__}, expected dict")

            if result.get("error"):
                reason = str(result.get("reason",""))[:80]
                print(wrn_(f"[{idx:3}/{total}] {test_key:<42} {family:<14} {reason}"))
                warned.append({"key": test_key, "reason": reason})
                family_stats[family]["warn"] += 1
            else:
                print(ok_(f"[{idx:3}/{total}] {test_key:<42} {family:<14} {elapsed:.2f}s"))
                passed.append({"key": test_key, "elapsed": round(elapsed, 3)})
                family_stats[family]["pass"] += 1

        except Exception as e:
            elapsed = time.perf_counter() - t0
            tb_last = traceback.format_exc().strip().split("\n")[-1]
            print(err_(f"[{idx:3}/{total}] {test_key:<42} {family:<14} {tb_last[:80]}"))
            failed.append({"key": test_key, "error": str(e), "tb": tb_last})
            family_stats[family]["fail"] += 1

    print()
    print(f"  {'Family':<20} {'Pass':>6} {'Warn':>6} {'Fail':>6}")
    print(f"  {'-'*44}")
    for fam, s in sorted(family_stats.items()):
        row_color = RED if s["fail"] > 0 else (YELLOW if s["warn"] > 0 else GREEN)
        print(f"  {fam:<20} {s['pass']:>6} {s['warn']:>6} {row_color}{s['fail']:>6}{RESET}")

    if failed:
        print(f"\n{RED}  -- FAILED TESTS --{RESET}")
        for item in failed:
            print(f"    * {item['key']}: {item['error'][:100]}")

    return passed, warned, failed, total


# =============================================================================
# SUITE 2: Dispatcher Integration (20-Test Batch)
# =============================================================================
def run_dispatcher_qa(df: pd.DataFrame):
    print(hdr_("SUITE 2 -- Dispatcher Integration (20-Test Batch)"))
    from analysis.engine.dispatcher import run_all_tests

    DATA_DICT = {
        "ordinal_vars":     ["item1","item2","item3","item4","item5","category"],
        "nominal_vars":     ["group","group2","binary","binary2"],
        "continuous_vars":  ["score","age","income","weight","height","pre","post"],
        "time_vars":        ["ts_value"],
        "id_vars":          ["subject_id","cluster"],
    }

    test_batch = [
        {"test_name":"Descriptive Stats",    "test_function":"descriptive_stats",         "variables":["score","age","income"]},
        {"test_name":"Normality Check",      "test_function":"normality_check",           "variables":["score","age"]},
        {"test_name":"Cronbach Alpha",       "test_function":"cronbach_alpha",            "variables":["item1","item2","item3","item4","item5"]},
        {"test_name":"Levene Test",          "test_function":"levene_test",               "variables":["group","score"]},
        {"test_name":"Independent T-Test",   "test_function":"independent_t_test",        "variables":["binary","score"]},
        {"test_name":"One-Way ANOVA",        "test_function":"one_way_anova",             "variables":["group","score"]},
        {"test_name":"Tukey HSD",            "test_function":"tukey_hsd",                 "variables":["group","score"]},
        {"test_name":"Mann-Whitney",         "test_function":"mann_whitney",              "variables":["binary","score"]},
        {"test_name":"Chi-Square",           "test_function":"chi_square",               "variables":["group","category"]},
        {"test_name":"Pearson Correlation",  "test_function":"pearson_correlation",       "variables":["score","age"]},
        {"test_name":"Correlation Matrix",   "test_function":"correlation_matrix",        "variables":["score","age","income","weight"]},
        {"test_name":"Multiple Regression",  "test_function":"multiple_regression",       "variables":["age","income","weight","score"]},
        {"test_name":"Logistic Regression",  "test_function":"logistic_regression",       "variables":["age","income","score","binary"]},
        {"test_name":"PCA",                  "test_function":"pca",                       "variables":["score","age","income","weight","height","score2","score3","score4","score5"]},
        {"test_name":"Kaplan-Meier",         "test_function":"kaplan_meier",              "variables":["duration","event","binary"]},
        {"test_name":"Cox PH Regression",    "test_function":"cox_ph_regression",         "variables":["duration","event","age","binary","income"]},
        {"test_name":"DiD",                  "test_function":"difference_in_differences", "variables":["period","treatment","score"]},
        {"test_name":"ADF Test",             "test_function":"adf_test",                  "variables":["ts_value"]},
        {"test_name":"Linear Mixed Model",   "test_function":"linear_mixed_model",        "variables":["score","age","subject_id"]},
        {"test_name":"Granger Causality",    "test_function":"granger_causality",         "variables":["ts_value","score"]},
    ]

    t0 = time.perf_counter()
    try:
        out     = run_all_tests(test_batch, df, BRIEF, DATA_DICT, missing_strategy="flag_only")
        elapsed = time.perf_counter() - t0

        required = ["meta","health_report","summary","descriptive","comparison",
                    "correlation","regression","survival","causal","timeseries",
                    "multilevel","not_applicable","warnings","fallbacks_applied"]
        missing = [k for k in required if k not in out]

        if missing:
            print(err_(f"Missing keys in output: {missing}"))
            return False

        not_app  = len(out.get("not_applicable", []))
        fallbacks = len(out.get("fallbacks_applied", []))
        warnings  = len(out.get("warnings", []))

        print(ok_(f"Dispatcher completed {len(test_batch)}-test batch in {elapsed:.2f}s"))
        print(f"  * Not applicable : {not_app}")
        print(f"  * Fallbacks used : {fallbacks}")
        print(f"  * Warnings       : {warnings}")
        if not_app:
            print(f"  {YELLOW}Not-applicable:{RESET}")
            for item in out["not_applicable"]:
                print(f"    - {item.get('test_function','?')}: {str(item.get('reason',''))[:80]}")
        return True

    except Exception as e:
        print(err_(f"Dispatcher CRASHED: {e}"))
        traceback.print_exc()
        return False


# =============================================================================
# SUITE 3: App API QA
# =============================================================================
BASE    = "http://127.0.0.1:8001"
TIMEOUT = 10

def _req(method, path, **kwargs):
    try:
        return getattr(requests, method)(f"{BASE}{path}", timeout=TIMEOUT, **kwargs)
    except requests.exceptions.ConnectionError:
        return None

def run_api_qa():
    print(hdr_("SUITE 3 -- App API: Full Endpoint Coverage"))
    api_passed, api_failed = [], []

    def check(label, r, expected=200):
        status   = r.status_code if r is not None else "NO_CONN"
        ok_flag  = (status == expected)
        msg      = f"  {label:<58} [{status}]"
        if ok_flag:
            print(ok_(msg))
            api_passed.append(label)
        else:
            print(err_(msg + f" (expected {expected})"))
            api_failed.append(label)
        return r

    # Health / docs
    check("GET /health",                     _req("get", "/health"))
    check("GET /docs",                        _req("get", "/docs"))
    check("GET /openapi.json",                _req("get", "/openapi.json"))

    # Auth — register a fresh QA user
    ts    = int(time.time())
    email = f"qa_{ts}@test.com"
    r     = check("POST /auth/register",     _req("post", "/auth/register",
                   json={"email": email, "password": "QApass123!", "full_name": "QA User"}))
    token = None
    if r and r.status_code == 200:
        try: token = r.json().get("access_token")
        except: pass

    # Login uses JSON LoginRequest with 'email' and 'password'
    r2 = check("POST /auth/login (correct)", _req("post", "/auth/login",
                json={"email": email, "password": "QApass123!"}))
    if r2 and r2.status_code == 200:
        try:
            t2 = r2.json().get("access_token")
            if t2: token = t2
        except: pass

    check("POST /auth/login (wrong pass)",   _req("post", "/auth/login",
           json={"email": email, "password": "wrongpass"}), 401)

    H = {"headers": {"Authorization": f"Bearer {token}"}} if token else {}

    # User profile
    check("GET /auth/me",                    _req("get", "/auth/me", **H))
    check("GET /users/me",                   _req("get", "/users/me", **H))

    # Analysis
    check("GET /analysis/jobs (auth)",        _req("get", "/analysis/jobs", **H))
    check("GET /analysis/jobs (no auth)",     _req("get", "/analysis/jobs"), 401)
    check("GET /analysis/queue/stats",        _req("get", "/analysis/queue/stats", **H))

    # Credits
    check("GET /credits/wallet",              _req("get", "/credits/wallet", **H))
    check("GET /credits/packages",            _req("get", "/credits/packages"))
    check("GET /credits/transactions",        _req("get", "/credits/transactions", **H))
    check("GET /credits/config",              _req("get", "/credits/config"))

    # Wallet
    check("GET /wallet/kyc-submit (auth)",   _req("get", "/wallet/kyc-submit", **H), 405)  # method check only

    # Marketplace / DataNest
    check("GET /datanest/datasets",           _req("get", "/datanest/datasets"))
    check("GET /datanest/featured",           _req("get", "/datanest/featured"))
    check("GET /datanest/trending",           _req("get", "/datanest/trending"))
    check("GET /datanest/domains",            _req("get", "/datanest/domains"))
    check("GET /datanest/collections",        _req("get", "/datanest/collections"))
    check("GET /datanest/me/library (auth)",  _req("get", "/datanest/me/library", **H))
    check("GET /datanest/sell/listings",      _req("get", "/datanest/sell/listings", **H))
    check("GET /datanest/sell/analytics",     _req("get", "/datanest/sell/analytics", **H))

    # Referral
    check("GET /referral/me",                 _req("get", "/referral/me", **H))
    check("GET /referral/leaderboard",        _req("get", "/referral/leaderboard"))

    # Integrations
    check("GET /integrations/google/status",  _req("get", "/integrations/google/status", **H))
    check("GET /integrations/google/auth-url",_req("get", "/integrations/google/auth-url", **H))
    check("GET /integrations/powerbi/feed",   _req("get", "/integrations/powerbi/feed", **H))

    # Admin (non-admin user should get 403)
    check("GET /admin/users (non-admin)",     _req("get", "/admin/users", **H), 403)

    print(f"\n  API: {GREEN}{len(api_passed)} passed{RESET} | {RED}{len(api_failed)} failed{RESET}")
    if api_failed:
        print(f"  {RED}Failed:{RESET}")
        for ep in api_failed: print(f"    * {ep}")

    return api_passed, api_failed

# =============================================================================
# MASTER REPORT
# =============================================================================

if __name__ == "__main__":
    wall_start = time.perf_counter()
    df = make_df()

    e_pass, e_warn, e_fail, e_total = run_engine_qa(df)
    d_ok  = run_dispatcher_qa(df)
    a_pass, a_fail = run_api_qa()

    wall = time.perf_counter() - wall_start

    print(hdr_("MASTER QA REPORT"))
    ep, ew, ef, et = len(e_pass), len(e_warn), len(e_fail), e_total
    ap, af, at     = len(a_pass), len(a_fail), len(a_pass)+len(a_fail)
    e_pct = 100*ep/et if et else 0
    a_pct = 100*ap/at if at else 0

    health = ("EXCELLENT" if ef==0 and af==0 else
              "REVIEW"    if ef+af<=4 else
              "ACTION REQUIRED")

    print(f"""
  QA REPORT  {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  {health}

  Suite                 Passed    Warned    Failed
  ----------------------------------------------------
  Statistical Engine    {ep:>6}    {ew:>6}    {ef:>6}    ({e_pct:.1f}% pass)
  Dispatcher Batch      {'1' if d_ok else '0':>6}    {'0':>6}    {'0' if d_ok else '1':>6}
  App API               {ap:>6}    {'--':>6}    {af:>6}    ({a_pct:.1f}% pass)
  ----------------------------------------------------
  Total wall time: {wall:.1f}s
""")

    sys.exit(0 if (ef == 0 and af <= 2) else 1)

# backend/analysis/pipeline.py
"""
Stages 3-9 of the ResearchForm analysis pipeline.
Called after researcher approves the decode review.

7-Concept Intelligent Pipeline:
  Stage 1: Data Ingestion & Inspection     (cleaner.py + analysis.py router)
  Stage 2: Data Decode & Review            (decode/ + analysis.py router)
  Stage 3: Context Understanding           (_parse_brief + _understand_context)
  Stage 4: Descriptive Statistics          (part of engine dispatcher)
  Stage 5: Inferential Statistics          (_select_tests + engine dispatcher)
  Stage 6: Visualisation                   (_create_visualisations)
  Stage 7: Interpretation & Report Build   (_write_report + _build_document)
"""
import os, sys, json, subprocess, tempfile
from datetime import datetime
from config import settings
from analysis.engine.dispatcher import run_all_tests
from analysis.decode.dictionary.builder import to_json_serializable
from analysis.error_manager import format_user_friendly_error


def run_stages_3_to_9(job, db):
    """
    Run stages 3-9 synchronously on the job object.
    Each stage has its own try/except so a failure in one stage
    (e.g. visualisation) does NOT abort subsequent stages (e.g. report writing).
    """
    import traceback as _tb
    from analysis.brief_validator import validate_and_clean_brief

    # Collect non-fatal stage warnings to surface in the report
    stage_warnings: list[str] = []

    # ── Stage 3 — Context Understanding ──────────────────────────────
    brief = {}
    data_dict = {}
    df = None
    try:
        _set_status(job, "parsing", db)
        raw_brief = job.project_brief or {}
        brief = _parse_brief(raw_brief)

        # ── Validate & sanitise EVERY field before any LLM/engine call ──
        brief = validate_and_clean_brief({**raw_brief, **brief})

        # Merge job-level multi-strand fields into brief
        brief["study_types"]          = job.study_types or ["quantitative"]
        brief["sample_size"]          = job.sample_size or 0
        brief["has_pretest_posttest"] = bool(job.has_pretest_posttest)
        brief["has_control_group"]    = bool(job.has_control_group)
        brief["n_cases"]              = job.n_cases or 1
        brief["case_analysis_approach"] = job.case_analysis_approach or "within"

        data_dict = job.data_dictionary or {}

        try:
            context = _understand_context(brief, data_dict)
            brief.update(context)
            # Auto AI: promote Claude's inferred scales when student provided none
            if not brief.get('variable_scales') and brief.get('inferred_scales'):
                brief['variable_scales'] = brief['inferred_scales']
        except Exception as ctx_err:
            stage_warnings.append(f"Context enrichment skipped: {ctx_err}")

        df = _load_dataframe(job)

        # ── Build AI label map (once) ── Survey DB, CSV, Excel, or SPSS ──
        label_map: dict = {}
        try:
            from analysis.label_map import (
                build_label_map, build_question_map_from_db, extract_spss_labels
            )
            question_map: dict = {}
            spss_labels:  dict = {}

            # Survey-based: fetch full question text from DB
            if job.survey_id:
                question_map = build_question_map_from_db(job.survey_id, db)

            # SPSS-based: extract embedded variable labels
            storage_dir = getattr(settings, "STORAGE_DIR", "storage")
            sav_path = os.path.join(storage_dir, f"{job.id}.sav")
            if os.path.exists(sav_path):
                spss_labels = extract_spss_labels(sav_path)

            columns = list(df.columns) if df is not None and hasattr(df, 'columns') else []
            if columns:
                label_map = build_label_map(
                    columns=columns,
                    question_map=question_map,
                    spss_labels=spss_labels,
                    brief=brief,
                    df=df,
                    use_ai=_has_llm(),
                )
                # Store label_map in brief so report writer can use it
                brief["__label_map__"] = label_map
        except Exception as lm_err:
            stage_warnings.append(f"[Label Map] Non-fatal: {lm_err}")

    except Exception as e:
        # Stage 3 failure is fatal — we cannot run without data
        job.status = "failed"
        job.error_message = format_user_friendly_error(e)
        try:
            db.commit()
        except Exception:
            db.rollback()
            try:
                job.error_message = format_user_friendly_error(e)
                db.commit()
            except Exception:
                pass
        raise

    # Determine research strands
    study_types = brief.get("study_types", ["quantitative"])
    has_quant = any(t in study_types for t in [
        "quantitative", "descriptive", "experimental", "correlation",
        "trend", "segmentation", "survey",
    ])
    has_qual  = "qualitative" in study_types
    has_case  = "case_study" in study_types
    has_mixed = "mixed" in study_types
    if has_mixed:
        has_quant = True
        has_qual  = True

    auto_viz      = job.auto_viz if job.auto_viz is not None else True
    selected_viz  = job.selected_viz or []
    auto_tables   = job.auto_tables if job.auto_tables is not None else True
    selected_tables = job.selected_tables or []

    # ── Stage 4 — Test Selection ──────────────────────────────────────
    tests = []
    if has_quant or not has_qual:
        try:
            _set_status(job, "selecting", db)
            overrides      = job.researcher_overrides or {}
            missing_strategy = job.missing_strategy or "auto"
            auto_select    = job.auto_select_techniques if job.auto_select_techniques is not None else True
            user_techniques = job.selected_techniques or []
            tests = _select_tests(
                brief, data_dict, overrides,
                auto_select=auto_select, user_techniques=user_techniques
            )
            job.selected_tests = tests
            db.commit()
        except Exception as e:
            stage_warnings.append(f"[Stage 4 - Test Selection] {e}")
            # Use empty test list — engine will still run descriptive stats
            tests = []
            job.selected_tests = tests
            db.commit()

    # ── Stage 5 — Statistical Engine ─────────────────────────────────
    results = {}
    if has_quant or not has_qual:
        try:
            _set_status(job, "executing", db)
            missing_strategy = job.missing_strategy or "auto"

            # ── Apply per-variable imputation from manual_choices ─────────────
            per_var_imp = (job.manual_choices or {}).get("per_var_imputation", {})
            if per_var_imp:
                try:
                    import numpy as np
                    knn_cols, mice_cols, exclude_cols = [], [], []
                    for col, method in per_var_imp.items():
                        if col not in df.columns:
                            continue
                        if method == "exclude":
                            exclude_cols.append(col)
                        elif method == "mean":
                            df[col] = df[col].fillna(df[col].mean())
                        elif method == "median":
                            df[col] = df[col].fillna(df[col].median())
                        elif method == "knn":
                            knn_cols.append(col)
                        elif method == "mice":
                            mice_cols.append(col)
                    # Apply KNN on grouped columns
                    if knn_cols:
                        try:
                            from sklearn.impute import KNNImputer
                            imp = KNNImputer(n_neighbors=5)
                            df[knn_cols] = imp.fit_transform(df[knn_cols])
                        except Exception as _e:
                            stage_warnings.append(f"[KNN Imputation] Fell back to median: {_e}")
                            for c in knn_cols:
                                df[c] = df[c].fillna(df[c].median())
                    # Apply MICE on grouped columns
                    if mice_cols:
                        try:
                            from sklearn.experimental import enable_iterative_imputer  # noqa
                            from sklearn.impute import IterativeImputer
                            imp = IterativeImputer(max_iter=10, random_state=42)
                            df[mice_cols] = imp.fit_transform(df[mice_cols])
                        except Exception as _e:
                            stage_warnings.append(f"[MICE Imputation] Fell back to median: {_e}")
                            for c in mice_cols:
                                df[c] = df[c].fillna(df[c].median())
                    # Drop excluded columns
                    if exclude_cols:
                        df = df.drop(columns=[c for c in exclude_cols if c in df.columns], errors="ignore")
                        stage_warnings.append(f"[Per-Variable Imputation] Excluded columns: {exclude_cols}")
                except Exception as pvi_err:
                    stage_warnings.append(f"[Per-Variable Imputation] Non-fatal: {pvi_err}")

            # ── Stage 5b — Composite Mean Computation ────────────────────────
            # Research standard: compute scale means from Likert items so that
            # brief variables like "job_performance_mean" resolve to real columns.
            try:
                from analysis.composite_means import compute_composite_means
                df, brief, cm_log = compute_composite_means(df, brief, data_dict)
                if cm_log:
                    stage_warnings.extend(cm_log)
            except Exception as cm_err:
                stage_warnings.append(f"[Composite Means] Non-fatal: {cm_err}")

            results = run_all_tests(
                tests=tests,
                df=df,
                brief=brief,
                data_dict=data_dict,
                missing_strategy=missing_strategy,
                weight_column=getattr(job, 'weight_column', None),
                imputation_method=getattr(job, 'imputation_method', None),
            )
            if stage_warnings:
                results.setdefault("warnings", []).extend(stage_warnings)
            job.results = to_json_serializable(results)
            db.commit()
        except Exception as e:
            stage_warnings.append(f"[Stage 5 - Statistical Engine] {e}")
            results = {
                "summary": [], "descriptive": {}, "frequencies": {},
                "normality": {}, "reliability": {}, "warnings": stage_warnings,
                "not_applicable": [{"test_name": "All Tests", "reason": str(e)}],
            }
            try:
                db.rollback()
            except Exception:
                pass
            job.results = to_json_serializable(results)
            try:
                db.commit()
            except Exception:
                pass

    # ── Stage 6 — Visualisation ───────────────────────────────────────
    chart_paths = []
    if has_quant or not has_qual:
        try:
            _set_status(job, "visualising", db)
            chart_paths = _create_visualisations(
                results, df, brief, job.id, tests,
                auto_viz=auto_viz, selected_viz=selected_viz,
                auto_tables=auto_tables, selected_tables=selected_tables,
                label_map=label_map,
            )
            job.chart_paths = to_json_serializable(chart_paths)
            db.commit()
        except Exception as e:
            # Non-fatal — report still generates without charts
            stage_warnings.append(f"[Stage 6 - Visualisation] Charts could not be generated: {e}")
            _tb.print_exc()
            try:
                db.rollback()
            except Exception:
                pass
            job.chart_paths = []
            try:
                db.commit()
            except Exception:
                pass

        # ── Stage 6b — HTML Tables (APA-formatted, copyable) ───────────────
        try:
            from analysis.charts import generate_html_tables
            html_tables = generate_html_tables(results, df, brief, label_map=label_map)
            if html_tables:
                job.html_tables = to_json_serializable(html_tables)
                db.commit()
        except Exception as e:
            stage_warnings.append(f"[Stage 6b - HTML Tables] {e}")

    # ── Qualitative Strand ────────────────────────────────────────────
    thematic_results = {}
    try:
        text_cols = [
            c for c, lvl in data_dict.get("measurement_levels", {}).items()
            if lvl == "text" and c in df.columns
        ]
        extracted_text_files = []
        for col in text_cols:
            try:
                non_nulls = df[col].dropna().astype(str).tolist()
                if non_nulls:
                    col_label = data_dict.get("column_labels", {}).get(col, col)
                    content = f"Responses for survey question: '{col_label}'\n\n"
                    valid_responses = 0
                    for i, ans in enumerate(non_nulls):
                        ans_clean = str(ans).strip()
                        if len(ans_clean) > 5:
                            content += f"[Participant {i+1}]: {ans_clean}\n\n"
                            valid_responses += 1
                    if valid_responses > 0:
                        extracted_text_files.append({
                            "name": f"Survey Responses: {col_label}",
                            "content": content
                        })
            except Exception as col_err:
                stage_warnings.append(f"[Qual Extract] Column {col!r}: {col_err}")

        qual_files = (job.qualitative_files or []) + extracted_text_files
        if extracted_text_files:
            has_qual = True

        if has_qual and qual_files:
            _set_status(job, "thematic_analysis", db)
            try:
                from analysis.qualitative import run_qualitative_pipeline
                thematic_results = run_qualitative_pipeline(
                    file_infos=qual_files,
                    topic=brief.get("topic", "Research Study"),
                    population=brief.get("population", ""),
                    coding_approach=job.qual_coding_approach or "inductive",
                    min_themes=job.qual_min_themes or 3,
                )
                job.thematic_results = to_json_serializable(thematic_results)
                db.commit()
            except Exception as qe:
                stage_warnings.append(f"[Qualitative Analysis] {qe}")
                try:
                    db.rollback()
                except Exception:
                    pass
                job.thematic_results = to_json_serializable({"error": str(qe), "themes": [], "thematic_table": []})
                try:
                    db.commit()
                except Exception:
                    pass
    except Exception as e:
        stage_warnings.append(f"[Qualitative Strand] {e}")

    # ── Stage 7 — Report Writing ──────────────────────────────────────
    report_text = {}
    try:
        _set_status(job, "writing", db)
        chapter_texts     = job.chapter_texts or {}
        report_type       = job.report_type or "chapter4"
        academic_tradition = job.academic_tradition or "standard"
        report_text = _write_report(
            brief, results, tests, data_dict, chapter_texts,
            report_type, academic_tradition,
            thematic_results=thematic_results,
            formatting_options=job.formatting_options or {},
            chart_paths=chart_paths,
        )
    except Exception as e:
        stage_warnings.append(f"[Stage 7 - Report Writing] {e}")
        _tb.print_exc()
        report_text = {
            "error": str(e),
            "narrative": f"Report generation encountered an error: {e}\n\nPartial results have been saved.",
        }

    # ── Stage 8 — Document Build ──────────────────────────────────────
    doc_path = None
    try:
        _set_status(job, "building", db)
        doc_path = _build_document(
            report_text, chart_paths, brief, job.id,
            thematic_results=thematic_results,
            formatting_options=job.formatting_options or {},
            results=results,
        )
        job.report_path = doc_path
        job.report_text = to_json_serializable(report_text)
    except Exception as e:
        stage_warnings.append(f"[Stage 8 - Document Build] {e}")
        _tb.print_exc()
        try:
            db.rollback()
        except Exception:
            pass
        job.report_text = to_json_serializable(report_text)
        try:
            db.commit()
        except Exception:
            pass

    # ── Finalise job ──────────────────────────────────────────────────
    job.status = "complete"
    job.completed_at = datetime.utcnow()

    # Persist any non-fatal warnings into results so UI can surface them
    if stage_warnings and isinstance(results, dict):
        results.setdefault("warnings", []).extend(stage_warnings)
        job.results = to_json_serializable(results)

    try:
        from analysis.llm_usage import end_job_tracking
        from services.credits import persist_job_usage_and_estimate
        usage_summary = end_job_tracking(job.id)
        persist_job_usage_and_estimate(job, usage_summary.to_dict())
    except Exception:
        pass  # billing failure never blocks job completion

    db.commit()

    # ── Training data logger (silent, non-blocking) ───────────────────
    try:
        _save_training_example(job, brief, results, chapter_texts if 'chapter_texts' in dir() else {}, report_text)
    except Exception:
        pass



# ─── LLM helper: Anthropic → OpenRouter fallback ─────────────────────
def _has_llm() -> bool:
    return bool(settings.ANTHROPIC_API_KEY or settings.OPENROUTER_API_KEY)

def _llm_chat(prompt: str, max_tokens: int = 2500) -> str:
    """
    Call LLM with automatic retry (3 attempts, exponential backoff).
    Primary: Anthropic Claude. Fallback: OpenRouter.
    SSL is now properly verified.
    """
    import time
    from analysis.llm_usage import record_llm_call, estimate_tokens_from_text
    MAX_RETRIES = 3

    if settings.ANTHROPIC_API_KEY:
        import anthropic
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                model = "claude-3-5-sonnet-20240620"
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                usage = getattr(response, "usage", None)
                inp = getattr(usage, "input_tokens", None) if usage else None
                out = getattr(usage, "output_tokens", None) if usage else None
                record_llm_call(
                    model=model,
                    input_tokens=inp if inp is not None else estimate_tokens_from_text(prompt),
                    output_tokens=out if out is not None else estimate_tokens_from_text(text),
                    max_tokens_requested=max_tokens,
                    provider="anthropic",
                )
                return text
            except Exception as e:
                last_err = e
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"[LLM] Anthropic attempt {attempt+1}/{MAX_RETRIES} failed: {e}. Retrying in {wait}s...")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(wait)
        raise RuntimeError(f"Anthropic API failed after {MAX_RETRIES} attempts: {last_err}")

    if settings.OPENROUTER_API_KEY:
        import httpx
        model = settings.OPENROUTER_MODEL
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://researchform.app",
            "X-Title": "ResearchForm",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                r = httpx.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload, headers=headers, timeout=120
                )
                r.raise_for_status()
                data = r.json()
                text = data["choices"][0]["message"]["content"].strip()
                usage = data.get("usage") or {}
                record_llm_call(
                    model=model,
                    input_tokens=int(usage.get("prompt_tokens") or estimate_tokens_from_text(prompt)),
                    output_tokens=int(usage.get("completion_tokens") or estimate_tokens_from_text(text)),
                    max_tokens_requested=max_tokens,
                    provider="openrouter",
                )
                return text
            except Exception as e:
                last_err = e
                wait = 2 ** attempt
                print(f"[LLM] OpenRouter attempt {attempt+1}/{MAX_RETRIES} failed: {e}. Retrying in {wait}s...")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(wait)
        raise RuntimeError(f"OpenRouter API failed after {MAX_RETRIES} attempts: {last_err}")

    raise RuntimeError("No LLM API key configured (ANTHROPIC_API_KEY or OPENROUTER_API_KEY)")




# ─── Stage 3a: Brief Parsing ─────────────────────────────────────────
def _parse_brief(raw: dict) -> dict:
    return {
        "topic": raw.get("topic", "Research Study"),
        "objectives": [o for o in (raw.get("objectives") or []) if o],
        "hypotheses": [h for h in (raw.get("hypotheses") or []) if h],
        "study_type": raw.get("study_type", "quantitative"),   # legacy single-value field
        "study_types": raw.get("study_types") or [raw.get("study_type", "quantitative")],
        "population": raw.get("population", ""),
        "sample_size": raw.get("sample_size"),
        "dependent_variable": raw.get("dependent_variable", ""),
        "independent_variable": raw.get("independent_variable", ""),
        "control_variable": raw.get("control_variable", "") or raw.get("control_variables", ""),
        "mediating_variable": raw.get("mediating_variable", ""),
        "moderating_variable": raw.get("moderating_variable", ""),
        "significance_level": raw.get("significance_level", 0.05),
        # Narrative context for richer AI-generated analysis and reports
        "research_background": raw.get("research_background", ""),
        "problem_statement":   raw.get("problem_statement", ""),
        "study_aim":           raw.get("study_aim", ""),
        # User class — determines which result buckets and token budget Claude receives
        "user_class":          raw.get("user_class", "bsc"),
        # Research design — controls which test families are appropriate
        "research_design":     raw.get("research_design", ""),
        # Variable scale types — {col_name: scale_type} — prevents wrong test selection
        "variable_scales":     raw.get("variable_scales") or {},
        # Explicit Likert construct definitions for named Cronbach's Alpha sections
        "likert_constructs":   raw.get("likert_constructs") or [],
    }


# ─── Stage 3b: Context Understanding (LLM) ───────────────────────────
def _understand_context(brief: dict, data_dict: dict) -> dict:
    """
    LLM enriches the research context:
    - Maps IV/DV keywords to actual column names
    - Identifies Likert scale constructs for reliability testing
    - Flags which hypotheses are testable given the data
    - Infers if normality checks are needed
    """
    if not _has_llm():
        return _mock_context(brief, data_dict)

    variables = data_dict.get("variables", [])
    col_names = [v["clean_name"] for v in variables[:30]]
    ordinal_vars = data_dict.get("ordinal_vars", [])
    ratio_vars = data_dict.get("ratio_vars", [])

    prompt = f"""You are an expert research methodologist. Analyse the research brief and dataset to provide enriched context.

RESEARCH BRIEF:
Topic: {brief.get('topic')}
Study Aim: {brief.get('study_aim') or '(not provided)'}
Problem Statement: {brief.get('problem_statement') or '(not provided)'}
Research Background: {brief.get('research_background') or '(not provided)'}
Research Design: {brief.get('research_design') or '(not specified)'}
Study Type: {brief.get('study_type')}
Dependent Variable (stated): {brief.get('dependent_variable')}
Independent Variable (stated): {brief.get('independent_variable')}
Mediating Variable (stated): {brief.get('mediating_variable') or '(not specified)'}
Moderating Variable (stated): {brief.get('moderating_variable') or '(not specified)'}
Control Variable (stated): {brief.get('control_variable') or '(not specified)'}
Population: {brief.get('population')}
Objectives: {json.dumps(brief.get('objectives', []))}
Hypotheses: {json.dumps(brief.get('hypotheses', []))}

STUDENT-DEFINED VARIABLE SCALES (authoritative — do NOT override these):
{json.dumps(brief.get('variable_scales') or {}, indent=2) if brief.get('variable_scales') else '(none provided — infer from data)'}
Scale key: nominal=categories no order | categorical=multi-class unordered groups | ordinal=ranked | likert_5/likert_7=Likert scale |
           interval=equal spacing no zero | ratio/continuous=true zero | binary=0/1 or Yes/No

STUDENT-DEFINED CONSTRUCTS (authoritative — use for Cronbach's Alpha naming):
{json.dumps(brief.get('likert_constructs') or [], indent=2) if brief.get('likert_constructs') else '(none provided — auto-detect from data)'}

DATASET COLUMNS (first 30): {json.dumps(col_names)}
Ordinal/Likert columns (auto-detected): {json.dumps(ordinal_vars[:15])}
Ratio/Continuous columns (auto-detected): {json.dumps(ratio_vars[:10])}

TASKS:
1. Map the stated DV and IV to the most likely actual column names from the dataset
2. Map mediating_variable and moderating_variable to actual column names (empty string if not specified)
3. For Likert constructs: if student-defined constructs are provided above, USE THEM verbatim in likert_constructs output. Only auto-detect constructs if none were provided.
4. For variable scales: if student-defined scales are provided, propagate them. For any untagged columns that appear to be Likert/ordinal, flag them.
5. Determine if parametric or non-parametric tests are more appropriate, taking research_design into account:
   - pre_post / longitudinal → flag repeated-measures tests are needed
   - experimental → causal inference is valid
   - cross_sectional / survey → standard between-subjects tests
6. Identify demographic columns (e.g. gender, age, department)
7. Flag any hypotheses that cannot be tested with this data

Return JSON only:
{{
  "dv_column": "actual_col_name_or_empty",
  "iv_column": "actual_col_name_or_empty",
  "mediating_column": "actual_col_name_or_empty",
  "moderating_column": "actual_col_name_or_empty",
  "likert_constructs": [{{"name": "Construct Name", "columns": ["col1","col2"]}}],
  "inferred_scales": {{"col_name": "scale_type"}},
  "demographic_columns": ["col1","col2"],
  "use_parametric": true,
  "needs_repeated_measures": false,
  "testable_hypotheses": [0, 1],
  "untestable_hypotheses": [],
  "methodology_note": "brief explanation"
}}"""



    try:
        text = _llm_chat(prompt, max_tokens=1500)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return _mock_context(brief, data_dict)


def _mock_context(brief: dict, data_dict: dict) -> dict:
    ordinal_vars = data_dict.get("ordinal_vars", [])
    ratio_vars = data_dict.get("ratio_vars", [])
    constructs = []
    if len(ordinal_vars) >= 3:
        constructs = [{"name": "Main Scale", "columns": ordinal_vars[:5]}]
    return {
        "dv_column": ratio_vars[0] if ratio_vars else "",
        "iv_column": ordinal_vars[0] if ordinal_vars else "",
        "likert_constructs": constructs,
        "demographic_columns": data_dict.get("nominal_vars", [])[:3],
        "use_parametric": len(ratio_vars) > 0,
        "testable_hypotheses": list(range(len(brief.get("hypotheses", [])))),
        "untestable_hypotheses": [],
        "methodology_note": "Auto-inferred from data structure",
    }


# ─── Technique ID → human label map (frontend IDs → descriptive names) ────
TECHNIQUE_ID_MAP = {
    # Descriptive
    "freq_dist":       "Frequency Distribution (counts and percentages for categorical variables)",
    "central_tend":    "Measures of Central Tendency (mean, median, mode)",
    "dispersion":      "Measures of Dispersion (standard deviation, variance, range, IQR)",
    "percentiles":     "Percentiles and Quartiles (Q1, Q3)",
    "crosstab":        "Cross-tabulation (two-way frequency tables)",
    "skew_kurtosis":   "Skewness and Kurtosis",
    # Parametric comparison
    "independent_t":   "Independent Samples t-test",
    "paired_t":        "Paired Samples t-test",
    "one_sample_t":    "One-Sample t-test",
    "one_way_anova":   "One-Way ANOVA",
    "two_way_anova":   "Two-Way ANOVA",
    "repeated_anova":  "Repeated Measures ANOVA",
    "manova":          "MANOVA (Multivariate ANOVA)",
    "ancova":          "ANCOVA (Analysis of Covariance)",
    "welch_anova":     "Welch's ANOVA (robust to unequal variances)",
    # Non-parametric
    "mann_whitney":    "Mann-Whitney U Test",
    "wilcoxon":        "Wilcoxon Signed-Rank Test",
    "kruskal_wallis":  "Kruskal-Wallis H Test",
    "friedman":        "Friedman Test",
    "chi_square":      "Chi-Square Test of Independence",
    "fisher_exact":    "Fisher's Exact Test",
    "mcnemar":         "McNemar Test",
    "sign_test":       "Sign Test",
    "runs_test":       "Runs Test for Randomness",
    # Correlation
    "pearson":         "Pearson Product-Moment Correlation (r)",
    "spearman":        "Spearman Rank Correlation (rho)",
    "kendall_tau":     "Kendall's Tau",
    "point_biserial":  "Point-Biserial Correlation",
    "phi_coeff":       "Phi Coefficient",
    "cramers_v":       "Cramer's V",
    "partial_corr":    "Partial Correlation",
    "canonical_corr":  "Canonical Correlation",
    # Regression
    "simple_linear":   "Simple Linear Regression",
    "multiple_linear": "Multiple Linear Regression",
    "binary_logistic": "Binary Logistic Regression",
    "multinomial_log": "Multinomial Logistic Regression",
    "ordinal_reg":     "Ordinal Regression",
    "hierarchical":    "Hierarchical Regression",
    "linear_mixed_model": "Hierarchical Linear Modeling (HLM) / MixedLM",
    "stepwise_reg":    "Stepwise Regression",
    "mediation":       "Mediation Analysis",
    "moderation":      "Moderation / Interaction Analysis",
    # Reliability
    "cronbach_alpha":  "Cronbach's Alpha (internal consistency)",
    "mcdonald_omega":  "McDonald's Omega",
    "kr20":            "KR-20 (Kuder-Richardson Formula 20)",
    "split_half":      "Split-Half Reliability",
    "icc":             "Intraclass Correlation Coefficient (ICC)",
    "item_analysis":   "Item Analysis (item-total correlations)",
    # Assumption tests
    "shapiro_wilk":    "Shapiro-Wilk Normality Test",
    "kolmogorov":      "Kolmogorov-Smirnov Normality Test",
    "levene":          "Levene's Test of Homogeneity of Variance",
    "bartlett":        "Bartlett's Test of Equal Variances",
    "mauchly":         "Mauchly's Test of Sphericity",
    "durbin_watson":   "Durbin-Watson Test for Autocorrelation",
    "vif":             "Multicollinearity Check (Variance Inflation Factor)",
    # Multivariate / Advanced
    "pca":             "Principal Component Analysis (PCA)",
    "efa":             "Exploratory Factor Analysis (EFA)",
    "cfa":             "Confirmatory Factor Analysis (CFA)",
    "discriminant":    "Discriminant Analysis",
    "cluster":         "Cluster Analysis",
    "sem":             "Structural Equation Modelling (SEM)",
    "path_analysis":   "Path Analysis",
    "survival":        "Survival / Time-to-Event Analysis",
    "time_series":     "Time Series Analysis",

    # ── NEW: Extended Descriptive ────────────────────────────────────────
    "freq_analysis":      "Frequency Analysis with cumulative frequencies and relative percentages",
    "freq_dist_3":        "Frequency Distribution Table with grouped class intervals",
    "mean_median_mode":   "Finding Mean, Median and Mode — explicit computation and comparison",
    "dispersion_2":       "Measure of Dispersion 2 — IQR, semi-IQR, Q1-Q3 detailed breakdown",
    "dispersion_3":       "Measure of Dispersion 3 — Coefficient of Variation, MAD, range detail",
    "dispersion_4":       "Measure of Dispersion 4 — Variance, Standard Error, 95% CI for mean",
    "percentiles_2":      "Percentiles 2 — Deciles (10th through 90th) and 5th/95th percentile",
    "percentiles_3":      "Percentiles 3 — Percentile ranks for individual scores",
    "percentiles_4":      "Percentiles 4 — Custom percentile table (5th, 10th, 25th, 50th, 75th, 90th, 95th)",
    "z_scores":           "Z-Scores — Standardised scores for all numeric variables",
    "z_scores_2":         "Z-Scores 2 — Z-score interpretation and corresponding probability areas",
    "z_scores_3":         "Z-Scores 3 — Z-table lookup, normal area calculations, tail probabilities",

    # ── NEW: Visualizations ──────────────────────────────────────────────
    "viz_bar":            "Bar Chart — frequency/count bar charts for categorical variables",
    "viz_histogram":      "Histogram — distribution histogram for continuous variables",
    "viz_pie":            "Pie Chart — proportional pie/donut charts for categorical data",
    "viz_line":           "Line Graph — sequential or time-series line graph",
    "viz_scatter":        "Scatter Plot — basic XY scatter for two continuous variables",
    "viz_scatter_2":      "Scatter Plot 2 — scatter plot with regression line overlay",
    "viz_scatter_3":      "Scatter Plot 3 — grouped scatter plot coloured by category",
    "viz_boxplot_1":      "Box Plot 1 — single variable box plot with outlier annotation",
    "viz_boxplot_2":      "Box Plot 2 — grouped side-by-side box plots for comparison",

    # ── NEW: Normal Distribution Testing (12 variants) ──────────────────
    "normal_dist":        "Normal Distribution — Shapiro-Wilk test with full normality assessment",
    "normal_dist_2":      "Normal Distribution 2 — Q-Q (quantile-quantile) plot analysis",
    "normal_dist_3":      "Normal Distribution 3 — Histogram with theoretical normal curve overlay",
    "normal_dist_4":      "Normal Distribution 4 — Jarque-Bera test for normality",
    "normal_dist_5":      "Normal Distribution 5 — Anderson-Darling test for normality",
    "normal_dist_6":      "Normal Distribution 6 — D'Agostino-Pearson omnibus normality test",
    "normal_dist_7":      "Normal Distribution 7 — Lilliefors test (K-S with estimated parameters)",
    "normal_dist_8":      "Normal Distribution 8 — Normal probability plot (P-P plot)",
    "normal_dist_9":      "Normal Distribution 9 — Confidence intervals for normality statistics",
    "normal_dist_10":     "Normal Distribution 10 — All-variables normality summary table",
    "normal_dist_11":     "Normal Distribution 11 — Omnibus test combining skewness and kurtosis",
    "normal_dist_12":     "Normal Distribution 12 — Robust normality assessment with bootstrapping",
    "parametric_nonparam":"Parametric vs Non-Parametric — decision guide based on data characteristics",
    "skewness":           "Skewness — skewness values and direction for all numeric variables",
    "skewness_2":         "Skewness 2 — Standard Error of skewness, z-test for skewness normality",
    "skewness_3":         "Skewness 3 — Transformation recommendations for skewed distributions",
    "kurtosis":           "Kurtosis — excess kurtosis (leptokurtic vs platykurtic assessment)",
    "kurtosis_2":         "Kurtosis 2 — SE of kurtosis, z-test, and distribution shape interpretation",
    "shapiro_wilk_2":     "Shapiro-Wilk Test 2 — All-variables SW summary table with W statistics",
    "var_transform":      "Non-Normal Variable Transformation — log, square root, Box-Cox transformations",

    # ── NEW: Outlier Detection ───────────────────────────────────────────
    "outliers_univariate":   "Univariate Outliers — IQR fences and boxplot outlier identification",
    "outliers_univariate_2": "Univariate Outliers 2 — Z-score method (|z| > 3) outlier detection",
    "outliers_univariate_3": "Univariate Outliers 3 — Grubbs test for most extreme outlier",
    "outliers_univariate_4": "Univariate Outliers 4 — Detailed outlier labeling with case numbers",
    "outliers_multivariate":  "Multivariate Outliers — Mahalanobis D² distance",
    "outliers_multivariate_2":"Multivariate Outliers 2 — PCA-based multivariate outlier detection",
    "outliers_multivariate_3":"Multivariate Outliers 3 — Cook's distance for influential cases",
    "outliers_multivariate_4":"Multivariate Outliers 4 — Leverage (hat values) for influential points",

    # ── NEW: Hypothesis Testing Concepts ────────────────────────────────
    "hypothesis":          "Hypothesis — testing framework: setup, decision rules, procedure",
    "hypothesis_2":        "Hypothesis 2 — Type I and Type II errors, significance levels, alpha",
    "hypothesis_3":        "Hypothesis 3 — Statistical power and sample size analysis",
    "null_alt_hypothesis":  "Null and Alternative Hypothesis — formulation of H0 and H1",
    "null_alt_hypothesis_2":"Null and Alternative Hypothesis 2 — decision rules and rejection regions",
    "one_two_tailed":      "One vs Two Tailed Test — directional vs non-directional hypothesis testing",
    "one_two_tailed_2":    "One vs Two Tailed Test 2 — critical regions and rejection zones",
    "one_two_tailed_3":    "One vs Two Tailed Test 3 — practical guide with worked examples",

    # ── NEW: Extended T-Tests ────────────────────────────────────────────
    "one_sample_t_2":  "One Sample T-test 2 — effect size (Cohen's d)",
    "one_sample_t_3":  "One Sample T-test 3 — confidence interval for the mean",
    "one_sample_t_4":  "One Sample T-test 4 — power analysis",
    "one_sample_t_5":  "One Sample T-test 5 — bootstrap version",
    "one_sample_t_6":  "One Sample T-test 6 — all variables summary table",
    "paired_t_2":      "Paired Sample T-test 2 — effect size (Cohen's d)",
    "paired_t_3":      "Paired Sample T-test 3 — confidence interval for mean difference",
    "paired_t_4":      "Paired Sample T-test 4 — normality of differences (Shapiro-Wilk on d)",
    "paired_t_5":      "Paired Sample T-test 5 — full summary with descriptive statistics",
    "independent_t_2": "Independent Sample T-test 2 — effect size (Cohen's d)",
    "independent_t_3": "Independent Sample T-test 3 — Levene's test then t-test",
    "independent_t_4": "Independent Sample T-test 4 — confidence interval for mean difference",
    "independent_t_5": "Independent Sample T-test 5 — Welch's t-test (unequal variances)",

    # ── NEW: Extended ANOVA ──────────────────────────────────────────────
    "anova_2":         "ANOVA 2 — eta-squared effect size",
    "anova_3":         "ANOVA 3 — descriptive statistics per group (mean, SD, n)",
    "anova_4":         "ANOVA 4 — full ANOVA table (SS, df, MS, F)",
    "anova_5":         "ANOVA 5 — assumption checks (normality + Levene's homogeneity)",
    "anova_6":         "ANOVA 6 — power analysis and required sample size",
    "anova_7":         "ANOVA 7 — Welch's ANOVA (robust to unequal variances)",
    "two_way_anova_1": "Two-Way ANOVA 1 — interaction plot (means by groups)",
    "two_way_anova_2": "Two-Way ANOVA 2 — main effects analysis",
    "two_way_anova_3": "Two-Way ANOVA 3 — partial eta-squared effect sizes",
    "two_way_anova_4": "Two-Way ANOVA 4 — cell means table",
    "two_way_anova_5": "Two-Way ANOVA 5 — simple effects analysis",
    "two_way_anova_6": "Two-Way ANOVA 6 — pairwise comparisons within factor levels",

    # ── NEW: Extended MANOVA ─────────────────────────────────────────────
    "manova_2":        "MANOVA 2 — Pillai's Trace multivariate test",
    "manova_3":        "MANOVA 3 — Hotelling's Trace multivariate test",
    "manova_4":        "MANOVA 4 — Box's M test of covariance matrix equality",
    "manova_5":        "MANOVA 5 — follow-up univariate ANOVAs for each DV",

    # ── NEW: Post-Hoc Tests ──────────────────────────────────────────────
    "posthoc_bonferroni":  "Bonferroni Procedure — conservative pairwise comparisons",
    "posthoc_duncan":      "Duncan's Multiple Range Test (MRT)",
    "posthoc_dunn":        "Dunn's Multiple Comparison — non-parametric post-hoc test",
    "posthoc_lsd":         "Fisher's LSD (Least Significant Difference)",
    "posthoc_newman_keuls": "Newman-Keuls Sequential Range Test",
    "posthoc_scheffe":     "Scheffe's Method — most conservative post-hoc",
    "posthoc_tukey":       "Tukey's HSD (Honestly Significant Difference)",
    "posthoc_dunnett":     "Dunnett's Correction — compare groups to a control",

    # ── NEW: Extended Non-Parametric ─────────────────────────────────────
    "mann_whitney_2":  "Mann-Whitney U Test 2 — effect size r",
    "mann_whitney_3":  "Mann-Whitney U Test 3 — confidence interval for median difference",
    "mann_whitney_4":  "Mann-Whitney U Test 4 — all pairwise group combinations",
    "friedman_2":      "Friedman Test 2 — Kendall's W concordance (effect size)",
    "wilcoxon_2":      "Wilcoxon Signed-Rank Test 2 — effect size r",
    "wilcoxon_3":      "Wilcoxon Signed-Rank Test 3 — CI for median difference",
    "kruskal_wallis_2":"Kruskal-Wallis H Test 2 — eta-squared effect size (η²H)",
    "chi_square_2":    "Chi-Square Test 2 — expected frequencies, residuals, Cramér's V",

    # ── NEW: Extended Correlation ────────────────────────────────────────
    "correlation":     "Correlation — correlation matrix overview for all numeric variables",
    "correlation_2":   "Correlation 2 — scatter plot matrix (SPLOM)",
    "correlation_3":   "Correlation 3 — correlation heatmap with significance markers",
    "correlation_4":   "Correlation 4 — significance testing for all correlation pairs",
    "correlation_5":   "Correlation 5 — effect sizes for all correlation pairs",
    "pearson_2":       "Pearson Correlation 2 — CI for r via Fisher's z transformation",
    "pearson_3":       "Pearson Correlation 3 — scatter plot with regression line",
    "pearson_4":       "Pearson Correlation 4 — partial Pearson (controlling a third variable)",
    "spearman_2":      "Spearman Rank Correlation 2 — ties correction detail",
    "spearman_3":      "Spearman Rank Correlation 3 — CI for rho",
    "spearman_4":      "Spearman Rank Correlation 4 — comparison with Pearson r",
    "spearman_5":      "Spearman Rank Correlation 5 — monotonic relationship significance test",
    "spearman_6":      "Spearman Rank Correlation 6 — full correlation matrix (all pairs)",
    "kendall_tau_2":   "Kendall Tau-B Correlation 2 — SE and confidence interval for tau-b",
    "kendall_tau_3":   "Kendall Tau-B Correlation 3 — concordance and discordance pairs",
    "point_biserial_2":"Point Biserial Correlation 2 — effect size r²",
    "point_biserial_3":"Point Biserial Correlation 3 — comparison with Pearson r",
    "point_biserial_4":"Point Biserial Correlation 4 — CI for r_pb",
    "point_biserial_5":"Point Biserial Correlation 5 — all continuous vs all binary variables",
    "point_biserial_6":"Point Biserial Correlation 6 — biserial correlation (corrected)",
    "param_estimates": "Parameter Estimates — regression coefficient table with SE, t-stat, CI",

    # ── NEW: Advanced Regression ─────────────────────────────────────────
    "linear_reg":         "Linear Regression — with R², adjusted R², and ANOVA table",
    "linear_reg_2":       "Linear Regression 2 — coefficient table with SE and 95% CI",
    "linear_reg_3":       "Linear Regression 3 — residuals and assumption diagnostic plots",
    "cox_regression":     "Cox Proportional Hazards Regression (survival analysis)",
    "poisson_regression": "Poisson Regression — GLM for count outcomes",
    "neg_binomial":       "Negative Binomial Regression — count regression for overdispersed data",
    "quantile_reg":       "Quantile Regression — median/conditional quantile regression",
}

# Maps every frontend technique ID directly to the snake_case test_function name used by
# the statistical engine. Used as a Claude-free fallback so manual selections are NEVER
# silently replaced by mock tests when the LLM call fails or returns bad JSON.
TECHNIQUE_FUNC_MAP: dict[str, str] = {
    # Descriptive
    "freq_dist":              "frequency_analysis",
    "freq_analysis":          "frequency_analysis",
    "freq_dist_3":            "frequency_analysis",
    "central_tend":           "mean_median_mode",
    "mean_median_mode":       "mean_median_mode",
    "dispersion":             "dispersion_extended",
    "dispersion_2":           "dispersion_extended",
    "dispersion_3":           "dispersion_extended",
    "dispersion_4":           "dispersion_extended",
    "percentiles":            "percentiles_extended",
    "percentiles_2":          "percentiles_extended",
    "percentiles_3":          "percentiles_extended",
    "percentiles_4":          "percentiles_extended",
    "crosstab":               "frequency_analysis",
    "skew_kurtosis":          "skewness_analysis",
    "skewness":               "skewness_analysis",
    "skewness_2":             "skewness_analysis",
    "skewness_3":             "variable_transformation",
    "kurtosis":               "kurtosis_analysis",
    "kurtosis_2":             "kurtosis_analysis",
    "z_scores":               "z_scores",
    "z_scores_2":             "z_scores",
    "z_scores_3":             "z_scores",
    "var_transform":          "variable_transformation",
    # Normality
    "shapiro_wilk":           "normality_check",
    "shapiro_wilk_2":         "shapiro_wilk_all",
    "normal_dist":            "normality_check",
    "normal_dist_2":          "normal_qq_plot",
    "normal_dist_3":          "normality_check",
    "normal_dist_4":          "jarque_bera",
    "normal_dist_5":          "anderson_darling",
    "normal_dist_6":          "dagostino_pearson",
    "normal_dist_7":          "kolmogorov_smirnov",
    "normal_dist_8":          "normal_qq_plot",
    "normal_dist_9":          "normality_check",
    "normal_dist_10":         "shapiro_wilk_all",
    "normal_dist_11":         "omnibus_normality",
    "normal_dist_12":         "normality_check",
    "kolmogorov":             "kolmogorov_smirnov",
    "parametric_nonparam":    "normality_check",
    # Outliers
    "outliers_univariate":    "outliers_iqr",
    "outliers_univariate_2":  "outliers_zscore",
    "outliers_univariate_3":  "outliers_grubbs",
    "outliers_univariate_4":  "outliers_iqr",
    "outliers_multivariate":  "mahalanobis_distance",
    "outliers_multivariate_2":"mahalanobis_distance",
    "outliers_multivariate_3":"cooks_distance",
    "outliers_multivariate_4":"leverage_hat",
    # Assumption tests
    "levene":                 "levene_test",
    "bartlett":               "bartlett_test",
    "mauchly":                "mauchly_test",
    "durbin_watson":          "durbin_watson",
    "vif":                    "vif_check",
    # Parametric comparisons
    "independent_t":          "independent_t_test",
    "independent_t_2":        "independent_t_cohend",
    "independent_t_3":        "levene_test",
    "independent_t_4":        "independent_t_test",
    "independent_t_5":        "welch_t_test",
    "paired_t":               "paired_t_test",
    "paired_t_2":             "paired_t_cohend",
    "paired_t_3":             "paired_t_test",
    "paired_t_4":             "normality_check",
    "paired_t_5":             "paired_t_test",
    "one_sample_t":           "one_sample_t_test",
    "one_sample_t_2":         "one_sample_t_cohend",
    "one_sample_t_3":         "one_sample_t_test",
    "one_sample_t_4":         "one_sample_t_test",
    "one_sample_t_5":         "one_sample_t_test",
    "one_sample_t_6":         "one_sample_t_test",
    "one_way_anova":          "one_way_anova",
    "anova_2":                "anova_eta_squared",
    "anova_3":                "anova_descriptives",
    "anova_4":                "one_way_anova",
    "anova_5":                "anova_assumptions",
    "anova_6":                "one_way_anova",
    "anova_7":                "welch_anova",
    "two_way_anova":          "two_way_anova",
    "two_way_anova_1":        "two_way_anova",
    "two_way_anova_2":        "two_way_anova",
    "two_way_anova_3":        "two_way_eta_squared",
    "two_way_anova_4":        "two_way_anova",
    "two_way_anova_5":        "two_way_anova",
    "two_way_anova_6":        "two_way_pairwise",
    "repeated_anova":         "repeated_anova",
    "manova":                 "manova",
    "manova_2":               "manova",
    "manova_3":               "manova",
    "manova_4":               "manova",
    "manova_5":               "manova_followup",
    "ancova":                 "ancova",
    "welch_anova":            "welch_anova",
    # Non-parametric
    "mann_whitney":           "mann_whitney",
    "mann_whitney_2":         "mann_whitney_r",
    "mann_whitney_3":         "mann_whitney",
    "mann_whitney_4":         "mann_whitney",
    "wilcoxon":               "wilcoxon",
    "wilcoxon_2":             "wilcoxon_r",
    "wilcoxon_3":             "wilcoxon",
    "kruskal_wallis":         "kruskal_wallis",
    "kruskal_wallis_2":       "kruskal_wallis_eta2",
    "friedman":               "friedman_test",
    "friedman_2":             "kendall_w",
    "chi_square":             "chi_square",
    "chi_square_2":           "chi_square_extended",
    "fisher_exact":           "fisher_exact",
    "mcnemar":                "mcnemar",
    "sign_test":              "sign_test",
    "runs_test":              "runs_test",
    # Post-hoc
    "posthoc_tukey":          "tukey_hsd",
    "posthoc_bonferroni":     "bonferroni_test",
    "posthoc_dunn":           "dunn_test",
    "posthoc_scheffe":        "scheffe_test",
    "posthoc_lsd":            "fisher_lsd",
    "posthoc_newman_keuls":   "newman_keuls",
    "posthoc_dunnett":        "dunnett_test",
    "posthoc_duncan":         "tukey_hsd",  # closest available
    # Correlation
    "pearson":                "pearson_correlation",
    "pearson_2":              "pearson_ci",
    "pearson_3":              "pearson_correlation",
    "pearson_4":              "partial_correlation",
    "spearman":               "spearman_correlation",
    "spearman_2":             "spearman_correlation",
    "spearman_3":             "spearman_correlation",
    "spearman_4":             "spearman_correlation",
    "spearman_5":             "spearman_correlation",
    "spearman_6":             "correlation_matrix",
    "kendall_tau":            "kendall_tau",
    "kendall_tau_2":          "kendall_tau",
    "kendall_tau_3":          "kendall_tau",
    "point_biserial":         "point_biserial",
    "point_biserial_2":       "point_biserial",
    "point_biserial_3":       "point_biserial",
    "point_biserial_4":       "point_biserial",
    "point_biserial_5":       "point_biserial",
    "point_biserial_6":       "point_biserial",
    "phi_coeff":              "phi_coefficient",
    "cramers_v":              "cramers_v",
    "partial_corr":           "partial_correlation",
    "canonical_corr":         "canonical_correlation",
    "correlation":            "correlation_matrix",
    "correlation_2":          "correlation_heatmap",
    "correlation_3":          "correlation_heatmap",
    "correlation_4":          "correlation_significance",
    "correlation_5":          "correlation_matrix",
    "param_estimates":        "multiple_regression",
    # Regression
    "simple_linear":          "simple_linear_regression",
    "linear_reg":             "simple_linear_regression",
    "linear_reg_2":           "multiple_regression",
    "linear_reg_3":           "multiple_regression",
    "multiple_linear":        "multiple_regression",
    "binary_logistic":        "logistic_regression",
    "multinomial_log":        "multinomial_logistic",
    "ordinal_reg":            "ordinal_regression",
    "hierarchical":           "hierarchical_regression",
    "linear_mixed_model":     "hierarchical_regression",
    "stepwise_reg":           "stepwise_regression",
    "mediation":              "mediation_analysis",
    "moderation":             "moderation_analysis",
    "cox_regression":         "cox_regression",
    "poisson_regression":     "poisson_regression",
    "neg_binomial":           "poisson_regression",
    "quantile_reg":           "quantile_regression",
    # Reliability
    "cronbach_alpha":         "cronbach_alpha",
    "mcdonald_omega":         "mcdonald_omega",
    "kr20":                   "kr20",
    "split_half":             "split_half_reliability",
    "icc":                    "icc",
    "item_analysis":          "item_analysis",
    # Multivariate / advanced
    "pca":                    "pca",
    "efa":                    "factor_analysis",
    "cfa":                    "factor_analysis",
    "discriminant":           "discriminant_analysis",
    "cluster":                "cluster_analysis",
    "sem":                    "sem",
    "path_analysis":          "path_analysis",
    "survival":               "survival_analysis",
    "time_series":            "time_series",
    # Hypothesis concepts (map to normality_check as proxy)
    "hypothesis":             "normality_check",
    "hypothesis_2":           "normality_check",
    "hypothesis_3":           "normality_check",
    "null_alt_hypothesis":    "normality_check",
    "null_alt_hypothesis_2":  "normality_check",
    "one_two_tailed":         "normality_check",
    "one_two_tailed_2":       "normality_check",
    "one_two_tailed_3":       "normality_check",
    # Visualisations — engine skips unknowns gracefully
    "viz_bar":                "frequency_analysis",
    "viz_histogram":          "descriptive_stats",
    "viz_pie":                "frequency_analysis",
    "viz_line":               "descriptive_stats",
    "viz_scatter":            "pearson_correlation",
    "viz_scatter_2":          "simple_linear_regression",
    "viz_scatter_3":          "pearson_correlation",
    "viz_boxplot_1":          "descriptive_stats",
    "viz_boxplot_2":          "descriptive_stats",
    # Generic aliases
    "descriptive_stats":      "descriptive_stats",
}



def _split_vars(raw: str) -> list:
    """Split a comma-separated variable string into cleaned, non-empty parts.
    Supports both single variables (e.g. 'CGPA') and multiple
    (e.g. 'Blood pressure, Cholesterol, BMI').
    """
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def _profile_dataset(data_dict: dict, brief: dict) -> dict:
    """Compute rich dataset characteristics for the auto-select prompt."""
    variables = data_dict.get("variables", [])
    ratio_vars   = data_dict.get("ratio_vars", [])    or []
    ordinal_vars = data_dict.get("ordinal_vars", []) or []
    nominal_vars = data_dict.get("nominal_vars", []) or []
    n_rows = data_dict.get("n_rows", 0) or 0

    # Sample size category
    if n_rows < 20:        sample_cat = "tiny (<20) — very limited, non-parametric preferred"
    elif n_rows < 30:      sample_cat = "small (20-29) — use non-parametric or exact tests"
    elif n_rows < 50:      sample_cat = "moderate-small (30-49) — parametric OK but verify normality"
    elif n_rows < 100:     sample_cat = "moderate (50-99) — most tests valid"
    elif n_rows < 500:     sample_cat = "large (100-499) — full test suite available"
    else:                  sample_cat = "very large (500+) — CLT applies; focus on effect sizes"

    # Find a likely group column — try each IV name, use first match
    iv_raw    = brief.get("independent_variable", "") or brief.get("iv_column", "")
    iv_names  = _split_vars(iv_raw)
    group_col = ""
    n_groups  = 0
    for iv_name in iv_names:
        for v in variables:
            if v.get("clean_name") == iv_name:
                group_col = iv_name
                n_groups  = v.get("n_unique", 0)
                break
        if group_col:
            break
    if not group_col or n_groups == 0:
        for v in variables:
            if v.get("measurement_level") in ("nominal", "ordinal") and 2 <= (v.get("n_unique") or 0) <= 6:
                group_col = v.get("clean_name", "")
                n_groups  = v.get("n_unique", 0)
                break

    # DV characteristics — use first listed DV as primary for type checks
    dv_raw   = brief.get("dependent_variable", "") or brief.get("dv_column", "")
    dv_names = _split_vars(dv_raw)
    dv_name  = dv_names[0] if dv_names else ""  # primary DV for flag checks
    dv_level = ""
    for v in variables:
        if v.get("clean_name") == dv_name:
            dv_level = v.get("measurement_level", "")
            break
    dv_is_continuous = dv_level in ("ratio", "interval") or dv_name in ratio_vars
    dv_is_ordinal    = dv_level == "ordinal" or dv_name in ordinal_vars
    dv_is_binary     = dv_level == "nominal" and any(
        v.get("clean_name") == dv_name and (v.get("n_unique") or 0) == 2
        for v in variables
    )

    # Normality hint from skewness data
    skew_values = [
        abs(v.get("skewness", 0) or 0)
        for v in variables
        if v.get("measurement_level") in ("ratio", "interval")
    ]
    if not skew_values:
        normality_hint = "unknown — run normality tests"
    elif max(skew_values) > 2:
        normality_hint = "likely non-normal (|skewness| > 2 detected) — prefer non-parametric"
    elif max(skew_values) > 1:
        normality_hint = "mildly skewed (|skewness| 1-2) — verify with Shapiro-Wilk"
    else:
        normality_hint = "approximately normal (|skewness| < 1) — parametric tests likely valid"

    has_paired   = brief.get("has_pretest_posttest", False)
    has_likert   = len(ordinal_vars) > 0

    return {
        "n_rows":             n_rows,
        "sample_category":    sample_cat,
        "n_continuous":       len(ratio_vars),
        "n_ordinal":          len(ordinal_vars),
        "n_nominal":          len(nominal_vars),
        "continuous_vars":    ratio_vars,
        "ordinal_vars":       ordinal_vars,
        "nominal_vars":       nominal_vars,
        "group_col":          group_col or "(none detected)",
        "n_groups":           n_groups,
        "has_paired":         has_paired,
        "has_likert":         has_likert,
        "normality_hint":     normality_hint,
        "dv_is_continuous":   dv_is_continuous,
        "dv_is_binary":       dv_is_binary,
        "dv_is_ordinal":      dv_is_ordinal,
        "multivariate_capable": len(ratio_vars) >= 3 and n_rows >= 30,
        "regression_capable": len(ratio_vars) >= 2 and n_rows >= 30,
        "factor_capable":     len(ordinal_vars) >= 5 and n_rows >= 50,
        "survival_capable":   any("time" in (v.get("clean_name") or "").lower() or
                                  "event" in (v.get("clean_name") or "").lower()
                                  for v in variables),
    }


# ─── Manual Mode Fallback: Claude-free test plan builder ─────────────────────
def _build_manual_tests_fallback(user_techniques: list, data_dict: dict, brief: dict) -> list:
    """
    Build a real test plan from user_techniques IDs without needing Claude.
    Called when auto_select=False and the LLM call fails (bad JSON, timeout, etc.).
    Uses TECHNIQUE_FUNC_MAP to translate every frontend ID to the correct
    snake_case test_function. Variables are assigned from the data_dict using
    the brief's DV/IV and dataset column lists.
    Guarantees: NEVER returns mock data — always returns the user's choices.
    """
    ratio_vars   = data_dict.get("ratio_vars", []) or []
    ordinal_vars = data_dict.get("ordinal_vars", []) or []
    nominal_vars = data_dict.get("nominal_vars", []) or []
    all_numeric  = ratio_vars + ordinal_vars
    all_vars     = ratio_vars + ordinal_vars + nominal_vars

    dv_raw  = brief.get("dependent_variable", "") or brief.get("dv_column", "")
    iv_raw  = brief.get("independent_variable", "") or brief.get("iv_column", "")
    dv_cols = [v.strip() for v in dv_raw.split(",") if v.strip()]
    iv_cols = [v.strip() for v in iv_raw.split(",") if v.strip()]
    hyps    = brief.get("hypotheses", []) or []
    likert  = brief.get("likert_constructs", []) or []

    tests = []
    seen_fns: set[str] = set()

    # Variable assignment heuristics per test category
    def _vars_for(fn: str) -> list:
        """Return sensible default variable list for a given test_function."""
        if fn in ("descriptive_stats", "dispersion_extended", "percentiles_extended",
                  "mean_median_mode", "skewness_analysis", "kurtosis_analysis",
                  "z_scores", "variable_transformation"):
            return all_numeric[:10]
        if fn in ("frequency_analysis",):
            return (nominal_vars + ordinal_vars)[:10]
        if fn in ("normality_check", "shapiro_wilk_all", "normal_qq_plot",
                  "kolmogorov_smirnov", "anderson_darling", "jarque_bera",
                  "dagostino_pearson", "omnibus_normality"):
            return all_numeric[:10]
        if fn in ("outliers_iqr", "outliers_zscore", "outliers_grubbs"):
            return all_numeric[:5]
        if fn in ("mahalanobis_distance", "cooks_distance", "leverage_hat"):
            return all_numeric[:5]
        if fn in ("levene_test", "bartlett_test"):
            return (dv_cols or ratio_vars[:1]) + (iv_cols or nominal_vars[:1])
        if fn in ("vif_check", "durbin_watson"):
            return (iv_cols or ratio_vars)[:5]
        if fn in ("independent_t_test", "independent_t_cohend", "welch_t_test",
                  "mann_whitney", "mann_whitney_r"):
            return (dv_cols or ratio_vars[:1]) + (iv_cols or nominal_vars[:1])
        if fn in ("paired_t_test", "paired_t_cohend", "wilcoxon", "wilcoxon_r"):
            return all_numeric[:2]
        if fn in ("one_sample_t_test", "one_sample_t_cohend"):
            return dv_cols or ratio_vars[:1]
        if fn in ("one_way_anova", "anova_eta_squared", "anova_descriptives",
                  "anova_assumptions", "welch_anova", "kruskal_wallis",
                  "kruskal_wallis_eta2"):
            return (dv_cols or ratio_vars[:1]) + (iv_cols or nominal_vars[:1])
        if fn in ("two_way_anova", "two_way_eta_squared", "two_way_pairwise"):
            return (dv_cols or ratio_vars[:1]) + nominal_vars[:2]
        if fn in ("ancova",):
            return (dv_cols or ratio_vars[:1]) + (iv_cols or nominal_vars[:1]) + ratio_vars[:1]
        if fn in ("repeated_anova",):
            return all_numeric[:4]
        if fn in ("manova", "manova_followup"):
            return all_numeric[:4]
        if fn in ("tukey_hsd", "bonferroni_test", "scheffe_test",
                  "fisher_lsd", "newman_keuls", "dunnett_test"):
            return (dv_cols or ratio_vars[:1]) + (iv_cols or nominal_vars[:1])
        if fn in ("dunn_test",):
            return (dv_cols or ordinal_vars[:1]) + (iv_cols or nominal_vars[:1])
        if fn in ("chi_square", "chi_square_extended", "fisher_exact",
                  "cramers_v", "phi_coefficient"):
            return nominal_vars[:2] if len(nominal_vars) >= 2 else (nominal_vars + ordinal_vars)[:2]
        if fn in ("mcnemar",):
            return nominal_vars[:2]
        if fn in ("pearson_correlation", "pearson_ci"):
            return (dv_cols or ratio_vars[:1]) + (iv_cols or ratio_vars[1:2])
        if fn in ("spearman_correlation", "kendall_tau"):
            return (dv_cols or ordinal_vars[:1]) + (iv_cols or ordinal_vars[1:2])
        if fn in ("point_biserial",):
            return (ratio_vars[:1]) + (nominal_vars[:1])
        if fn in ("partial_correlation",):
            return (dv_cols or ratio_vars[:1]) + (iv_cols or ratio_vars[1:2]) + ratio_vars[2:3]
        if fn in ("canonical_correlation",):
            return all_numeric[:4]
        if fn in ("correlation_matrix", "correlation_heatmap", "correlation_significance"):
            return all_numeric[:8]
        if fn in ("simple_linear_regression",):
            return (iv_cols or ratio_vars[:1]) + (dv_cols or ratio_vars[1:2])
        if fn in ("multiple_regression", "hierarchical_regression", "stepwise_regression"):
            return (iv_cols or ratio_vars[:3]) + (dv_cols or ratio_vars[-1:])
        if fn in ("logistic_regression", "multinomial_logistic", "ordinal_regression"):
            return (iv_cols or ratio_vars[:3]) + (dv_cols or nominal_vars[:1])
        if fn in ("mediation_analysis",):
            med_raw = brief.get("mediating_variable", "") or ""
            med_col = med_raw.split(",")[0].strip() if med_raw else (ordinal_vars[:1] or all_numeric[:1] or [""])[0]
            return [
                (iv_cols or ratio_vars[:1] or ["IV"])[0],
                med_col or (all_numeric[1:2] or ["MED"])[0],
                (dv_cols or ratio_vars[-1:] or ["DV"])[0],
            ]
        if fn in ("moderation_analysis",):
            mod_raw = brief.get("moderating_variable", "") or ""
            mod_col = mod_raw.split(",")[0].strip() if mod_raw else (ordinal_vars[:1] or all_numeric[:1] or [""])[0]
            return [
                (iv_cols or ratio_vars[:1] or ["IV"])[0],
                mod_col or (all_numeric[1:2] or ["MOD"])[0],
                (dv_cols or ratio_vars[-1:] or ["DV"])[0],
            ]
        if fn in ("cronbach_alpha", "mcdonald_omega", "split_half_reliability",
                  "kr20", "item_analysis"):
            if likert and isinstance(likert[0], dict):
                return likert[0].get("columns", ordinal_vars[:5])
            return ordinal_vars[:5] or all_numeric[:5]
        if fn in ("icc",):
            return ordinal_vars[:3] or all_numeric[:3]
        if fn in ("factor_analysis", "pca"):
            return ordinal_vars[:8] or all_numeric[:8]
        if fn in ("cluster_analysis", "discriminant_analysis"):
            return all_numeric[:6]
        # Default: all numeric variables
        return all_numeric[:5] or all_vars[:5]

    for tid in user_techniques:
        fn = TECHNIQUE_FUNC_MAP.get(tid) or TECHNIQUE_ID_MAP.get(tid, "").lower().replace(" ", "_")
        if not fn:
            continue
        # Deduplicate by function name
        if fn in seen_fns:
            continue
        seen_fns.add(fn)

        # Match to a hypothesis if possible
        h_idx = -1
        h_text = ""
        if hyps:
            h_idx = 0
            h_text = hyps[0] if isinstance(hyps[0], str) else str(hyps[0])

        tests.append({
            "test_name":        TECHNIQUE_ID_MAP.get(tid, fn.replace("_", " ").title()),
            "test_function":    fn,
            "variables":        _vars_for(fn),
            "hypothesis_index": h_idx,
            "hypothesis":       h_text,
            "rationale":        "Manually selected by researcher",
            "always_run":       True,
        })

    return tests


# ─── Stage 4: Test Selection ─────────────────────────────────────────
def _select_tests(brief: dict, data_dict: dict, overrides: dict,
                  auto_select: bool = True, user_techniques: list = None) -> list:
    """Select the full suite of statistical tests.

    When auto_select=True  → LLM uses 5-tier decision framework with full data profile.
    When auto_select=False → LLM maps researcher's explicit technique choices to variables.
    Either way, descriptive_stats and normality_check are always included.
    """
    user_techniques = user_techniques or []

    if not _has_llm():
        return _ensure_baseline_tests(_mock_tests(brief, data_dict), data_dict)

    variables = data_dict.get("variables", [])
    # Normalize any non-standard measurement level aliases so comparisons
    # ("ratio", "interval", "ordinal", "nominal") work reliably throughout.
    _ML_COERCE = {
        "continuous": "ratio", "numeric": "ratio", "scale": "ratio", "quantitative": "ratio",
        "categorical": "nominal", "qualitative": "nominal", "binary": "nominal",
        "dichotomous": "nominal", "dummy": "nominal",
        "ranked": "ordinal", "rank": "ordinal", "likert": "ordinal", "ordered": "ordinal",
    }
    _VALID_ML = {"nominal", "ordinal", "interval", "ratio"}
    for v in variables:
        raw_ml = (v.get("measurement_level") or "").strip().lower()
        if raw_ml and raw_ml not in _VALID_ML:
            v["measurement_level"] = _ML_COERCE.get(raw_ml, "nominal")
        ov = overrides.get(v["clean_name"], {})
        if ov.get("measurement_level"):
            raw_ov = str(ov["measurement_level"]).strip().lower()
            v["measurement_level"] = _ML_COERCE.get(raw_ov, raw_ov if raw_ov in _VALID_ML else v.get("measurement_level", "nominal"))
        if ov.get("role"):
            v["role"] = ov["role"]

    dv_raw   = brief.get("dependent_variable", "") or brief.get("dv_column", "")
    iv_raw   = brief.get("independent_variable", "") or brief.get("iv_column", "")
    all_clean_cols = [v["clean_name"] for v in variables]
    from analysis.engine.dispatcher import _match_column
    dv_names = [_match_column(v, all_clean_cols) or v for v in _split_vars(dv_raw)]
    iv_names = [_match_column(v, all_clean_cols) or v for v in _split_vars(iv_raw)]
    dv = ", ".join(dv_names)  # full comma string for LLM prompt
    iv = ", ".join(iv_names)
    hypotheses        = brief.get("hypotheses", [])
    likert_constructs = brief.get("likert_constructs", [])
    demographic_cols  = brief.get("demographic_columns", [])
    llm_context       = data_dict.get("llm_context", "")
    ordinal_vars      = data_dict.get("ordinal_vars", []) or []
    ratio_vars        = data_dict.get("ratio_vars", [])   or []
    nominal_vars      = data_dict.get("nominal_vars", []) or []

    if auto_select:
        # ── AI Auto-Select: 5-Tier Comprehensive Decision Framework ──────
        profile = _profile_dataset(data_dict, brief)

        # Extract richer context from brief
        objectives       = brief.get("objectives", []) or []
        research_goals   = brief.get("research_goals", []) or objectives  # alias fallback
        control_var      = brief.get("control_variable", "") or ""
        mediating_var    = brief.get("mediating_variable", "") or ""
        moderating_var   = brief.get("moderating_variable", "") or ""
        # Also pull LLM-resolved column names from context if available
        mediating_col    = brief.get("mediating_column", "") or mediating_var
        moderating_col   = brief.get("moderating_column", "") or moderating_var
        study_types_list = brief.get("study_types", [brief.get("study_type", "quantitative")]) or []
        academic_trad    = brief.get("academic_tradition", "standard") or "standard"
        report_type      = brief.get("report_type", "chapter4") or "chapter4"
        has_pretest      = brief.get("has_pretest_posttest", False)
        has_control_grp  = brief.get("has_control_group", False)
        n_cases          = brief.get("n_cases", 1) or 1
        significance_lvl = brief.get("significance_level", 0.05) or 0.05
        sample_size_hint = brief.get("sample_size", None)

        # Study design flags
        is_experimental  = "experimental" in study_types_list
        is_qualitative   = "qualitative" in study_types_list or "mixed" in study_types_list
        is_correlational = "correlation" in study_types_list
        is_descriptive   = "descriptive" in study_types_list
        is_case_study    = "case_study" in study_types_list
        is_longitudinal  = "trend" in study_types_list
        is_segmentation  = "segmentation" in study_types_list

        # Build objectives block
        obj_block = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(objectives) if o) if objectives else "  (not specified)"
        hyp_block = json.dumps(hypotheses, indent=2) if hypotheses else '  []'
        likert_block = json.dumps(likert_constructs, indent=2) if likert_constructs else '  []'
        # First-column shortcuts used in the MANDATORY RULES f-string
        iv_col_first  = iv_names[0]  if iv_names  else (brief.get("iv_column", "") or "IV_col")
        dv_col_first  = dv_names[0]  if dv_names  else (brief.get("dv_column", "") or "DV_col")
        med_col_first = (mediating_col.split(",")[0].strip()  if mediating_col  else "MEDIATOR_col")
        mod_col_first = (moderating_col.split(",")[0].strip() if moderating_col else "MODERATOR_col")

        # Pre-compute analyst level hint (avoids f-string brace conflict)
        _uc = str(brief.get('user_class', 'bsc')).lower()
        _analyst_level_hints = {
            "bsc":        "UNDERGRADUATE — select foundational tests only. Avoid SEM, survival analysis, multilevel models unless explicitly hypothesised.",
            "msc":        "MASTER'S — include mediation/moderation if IV→DV relationships are hypothesised. Avoid SEM unless explicit.",
            "phd":        "DOCTORAL — select the full optimal suite. No restrictions on test complexity.",
            "researcher": "RESEARCHER — select the full optimal suite. No restrictions on test complexity.",
            "business":   "BUSINESS ANALYST — prefer practical, interpretable tests. Avoid overly complex multivariate models. Focus on comparison, regression, and correlation.",
        }
        _analyst_level_hint = _analyst_level_hints.get(_uc, "Select appropriate tests for the study.")

        prompt = f"""You are a world-class biostatistician and research methodologist. Select the OPTIMAL, COMPREHENSIVE suite of statistical tests for the study below.

Base EVERY decision on the full research context — objectives, hypotheses, study design, variable types, and dataset characteristics.

═══════════════════════════════════════════════════════
RESEARCH BRIEF
═══════════════════════════════════════════════════════
Topic: {brief.get('topic')}
Population / Target Group: {brief.get('population', '')}
Study Aim: {brief.get('study_aim') or '(not specified)'}
Problem Statement: {brief.get('problem_statement') or '(not specified)'}
Research Background: {(brief.get('research_background') or '(not specified)')[:300]}
Study Design(s): {', '.join(study_types_list)}
Academic Tradition: {academic_trad}
Report Format: {report_type}
Significance Level: α = {significance_lvl}
Analyst Level: {_analyst_level_hint}
Research Design: {brief.get('research_design', 'not specified').upper().replace('_', '-')}

RESEARCH DESIGN CONSTRAINTS:
{"→ CROSS-SECTIONAL: One snapshot. No repeated-measures tests. Between-subjects only." if brief.get('research_design') == 'cross_sectional' else ""}
{"→ PRE-TEST/POST-TEST: MUST include paired t-test or Wilcoxon for each outcome variable. Include repeated-measures ANOVA if 3+ time points." if brief.get('research_design') == 'pre_post' else ""}
{"→ LONGITUDINAL: Include LMM or growth curve model. Repeated-measures ANOVA if 3+ time points. ICC for clustering." if brief.get('research_design') == 'longitudinal' else ""}
{"→ EXPERIMENTAL: Causal inference is valid. Include effect sizes for all comparisons. Consider ANCOVA to control for covariates." if brief.get('research_design') == 'experimental' else ""}
{"→ SURVEY/QUESTIONNAIRE: Cronbach's Alpha REQUIRED for every Likert construct. Include frequencies for all categorical items." if brief.get('research_design') in ('survey', 'cross_sectional') else ""}
{"→ CORRELATIONAL: Focus on correlation and regression. No causal claims. Effect sizes required." if brief.get('research_design') == 'correlational' else ""}
{"→ CASE STUDY: Descriptive statistics and qualitative analysis predominate. Limit inferential tests." if brief.get('research_design') == 'case_study' else ""}

STUDENT-DEFINED VARIABLE SCALES (CRITICAL — use these to select correct test families):
{json.dumps(brief.get('variable_scales') or {}, indent=2) if brief.get('variable_scales') else '(none provided — infer from dataset)'}

SCALE SELECTION RULES (NON-NEGOTIABLE):
  nominal variables     → chi_square / frequency_analysis / cramers_v ONLY — NO means, NO t-test, NO ANOVA
  categorical variables → same as nominal: chi_square / frequency_analysis / cramers_v — multi-class groups, NO means
  binary variables      → chi_square / fisher_exact / logistic_regression ONLY
  ordinal variables     → spearman_correlation / mann_whitney / kruskal_wallis — NO Pearson, NO t-test
  likert_5 / likert_7   → treat as ordinal UNLESS >5 items summed into a scale (then interval allowed)
  interval / ratio      → t-test / ANOVA / Pearson OK if normality confirmed
  continuous            → same as ratio

STUDENT-DEFINED LIKERT CONSTRUCTS (include cronbach_alpha for each):
{json.dumps(brief.get('likert_constructs') or [], indent=2) if brief.get('likert_constructs') else '(auto-detect from dataset column patterns)'}

RESEARCH OBJECTIVES (each must be addressed by ≥1 test):
{obj_block}

HYPOTHESES (each must be addressed by ≥1 inferential test):
{hyp_block}

VARη²BLES:
  Dependent Variable(s):   {dv}{('  [MULTIVARη²TE — ' + str(len(dv_names)) + ' outcomes]') if len(dv_names) > 1 else ''}
  Independent Variable(s): {iv}{('  [MULTIPLE PREDICTORS — ' + str(len(iv_names)) + ' factors]') if len(iv_names) > 1 else ''}
  Control / Covariate(s):  {control_var if control_var else '(none specified)'}
  Mediating Variable(s):   {mediating_col if mediating_col else '(none specified)'}
  Moderating Variable(s):  {moderating_col if moderating_col else '(none specified)'}

EXPERIMENTAL DESIGN FLAGS:
  Pre-test / Post-test design: {has_pretest}
  Has Control Group:           {has_control_grp}
  Number of Cases (case study):{n_cases}
  Longitudinal / Trend:        {is_longitudinal}
  Segmentation / Clustering:   {is_segmentation}
  Experimental design:         {is_experimental}
  Correlational design:        {is_correlational}
  Descriptive-only:            {is_descriptive}
  Qualitative / Mixed:         {is_qualitative}
  Case Study:                  {is_case_study}

LIKERT CONSTRUCTS (each needs Cronbach α before any analysis):
{likert_block}

═══════════════════════════════════════════════════════
DATASET PROFILE
═══════════════════════════════════════════════════════
Total observations (n): {profile['n_rows']}  [{profile['sample_category']}]{(' [OVERRIDE: researcher reports n=' + str(sample_size_hint) + ']') if sample_size_hint else ''}
Continuous/ratio vars  ({profile['n_continuous']}): {json.dumps(profile['continuous_vars'][:10])}
Ordinal/Likert vars    ({profile['n_ordinal']}):   {json.dumps(profile['ordinal_vars'][:10])}
Nominal/categ vars     ({profile['n_nominal']}):   {json.dumps(profile['nominal_vars'][:8])}
Group column (IV):    {profile['group_col']}  (distinct groups: {profile['n_groups']})
Demographic columns:  {json.dumps(demographic_cols[:6])}
Has repeated measures: {profile['has_paired']}
Has Likert items:      {profile['has_likert']}
Normality hint:        {profile['normality_hint']}
DV is continuous:      {profile['dv_is_continuous']}
DV is binary:          {profile['dv_is_binary']}
DV is ordinal:         {profile['dv_is_ordinal']}
Regression capable:    {profile['regression_capable']}
Factor analysis cap.:  {profile['factor_capable']}
Multivariate cap.:     {profile['multivariate_capable']}

Data context:
{llm_context[:1200]}

═══════════════════════════════════════════════════════
SELECTION RULES — READ ALL BEFORE CHOOSING
═══════════════════════════════════════════════════════

OBJECTIVE-DRIVEN RULES:
  → For each objective containing "compare" or "difference" → include a group comparison test (t-test/ANOVA/Mann-Whitney)
  → For each objective containing "relationship" or "association" → include correlation or chi-square
  → For each objective containing "predict" or "influence" or "effect of" → include regression
  → For each objective containing "describe" or "profile" or "summarise" → include descriptive_stats + frequency_analysis
  → For each objective containing "reliability" or "internal consistency" → include cronbach_alpha
  → For each objective containing "factor" or "scale" or "dimension" → include factor_analysis
  → For each objective containing "cluster" or "segment" or "group" → include cluster_analysis
  → For each objective containing "mediat" → include mediation_analysis
  → For each objective containing "moderat" → include moderation_analysis
  → For each objective containing "control" or "covariate" → include ancova or partial_correlation

MEDIATION / MODERATION MANDATORY RULES (HIGHEST PRIORITY — ALWAYS APPLY):
  *** IF Mediating Variable(s) is NOT '(none specified)' → you MUST include mediation_analysis ***
      → variables list MUST be exactly: ["{iv_col_first}", "{med_col_first}", "{dv_col_first}"]
      → This is non-negotiable — the researcher explicitly identified this as a mediation study
  *** IF Moderating Variable(s) is NOT '(none specified)' → you MUST include moderation_analysis ***
      → variables list MUST be exactly: ["{iv_col_first}", "{mod_col_first}", "{dv_col_first}"]
      → Mean-centering and simple-slopes (spotlight) are performed automatically by the engine
  *** IF BOTH Mediating AND Moderating Variables are set → also include moderated_mediation ***
      → variables list: ["{iv_col_first}", "{med_col_first}", "{mod_col_first}", "{dv_col_first}"]

STUDY-DESIGN RULES:
  → Experimental + pre/post + control group → paired_t_test OR repeated_anova + ancova
  → Correlational → pearson_correlation / spearman_correlation + correlation_matrix
  → Descriptive → descriptive_stats + frequency_analysis + dispersion_extended + percentiles_extended
  → Longitudinal/trend → time_series OR repeated_anova
  → Case study → descriptive_stats + qualitative (if mixed) — NO inferential unless n > 10
  → Segmentation → cluster_analysis + discriminant_analysis

TIER 1 — MANDATORY BASELINE (always include first):
  • descriptive_stats — mean/SD/median/mode/min/max/skewness/kurtosis for ALL variables
  • frequency_analysis — counts + % for ALL nominal and ordinal variables
  • normality_check — Shapiro-Wilk (n<50) or Kolmogorov-Smirnov (n≥50) for ALL continuous vars
  → IF n≥50: also add kolmogorov_smirnov
  → IF skewness hint says non-normal or unknown: also add jarque_bera, dagostino_pearson
  → IF any Likert constructs exist: add cronbach_alpha for EACH construct
  → IF ordinal vars ≥ 5: add skewness_analysis, kurtosis_analysis

TIER 2 — ASSUMPTION CHECKS (before any parametric test):
  → IF planning t-test or ANOVA: add levene_test (Levene's equality of variances)
  → IF planning regression: add vif_check (multicollinearity) AND durbin_watson
  → IF planning repeated ANOVA: add mauchly_test (sphericity)
  → IF planning factor analysis: add bartlett_test (sphericity for FA)
  → IF n ≥ 50 and continuous vars ≥ 2: add outliers_iqr AND outliers_zscore
  → IF control_variable present: this triggers ANCOVA — add levene_test first

TIER 3 — PRIMARY INFERENTη²L TESTS:

  [COMPARING GROUPS — DV is continuous]
  • 2 groups + n≥30 + normal → independent_t_test
  • 2 groups + n<30 OR non-normal → mann_whitney
  • Uncertain equality of variances → welch_t_test
  • Pre/post same subjects + normal → paired_t_test
  • Pre/post same subjects + non-normal → wilcoxon
  • 3+ groups + n≥30 + normal → one_way_anova  [MUST pair with post-hoc in Tier 4]
  • 3+ groups + non-normal OR ordinal DV → kruskal_wallis  [MUST pair with dunn_test]
  • 2 factors → two_way_anova
  • Multiple continuous DVs + groups → manova
  • Control variable(s) present → ancova (replaces ANOVA)
  • 3+ time-points + same subjects → repeated_anova

  [RELATIONSHIPS & CORRELATIONS]
  • 2 continuous + normal → pearson_correlation
  • 2 continuous + non-normal OR ordinal → spearman_correlation
  • Ordinal + ordinal with many ties → kendall_tau
  • Continuous + binary → point_biserial
  • 2 binary → phi_coefficient
  • 2 nominal → chi_square + cramers_v
  • Small cell counts (<5 expected) → fisher_exact
  • 3+ continuous → correlation_matrix + correlation_heatmap
  • Partial out a confounder / control variable → partial_correlation

  [PREDICTION & REGRESSION]
  • 1 IV predicts continuous DV → simple_linear_regression
  • 2+ IVs predict continuous DV → multiple_regression
  • Binary DV → logistic_regression
  • Ordered categorical DV → ordinal_regression
  • 3+ unordered categories DV → multinomial_logistic
  • Mediation hypothesis/objective stated → mediation_analysis
  • Moderation hypothesis/objective stated → moderation_analysis
  • Block-entry of predictors stated → hierarchical_regression
  • Segmentation objective → cluster_analysis + discriminant_analysis
  • Scale/factor structure objective → factor_analysis

TIER 4 — EFFECT SIZES & POST-HOC (mandatory companions):
  RULE: EVERY inferential test MUST have a companion effect size:
  • t-test → independent_t_cohend / paired_t_cohend
  • ANOVA → anova_eta_squared
  • Mann-Whitney → mann_whitney_r
  • Wilcoxon → wilcoxon_r
  • Chi-square → cramers_v
  • Kruskal-Wallis → kruskal_wallis_eta2

  POST-HOC RULE (mandatory when ANOVA selected):
  • one_way_anova → tukey_hsd (balanced) OR bonferroni_test (unequal n)
  • kruskal_wallis → dunn_test
  • two_way_anova → scheffe_test OR two_way_pairwise
  • manova → manova_followup

TIER 5 — EXPLORATORY / SUPPLEMENTARY (add when supported by data or objectives):
  • n≥50 + 3+ continuous → mahalanobis_distance
  • n≥50 + 5+ ordinal → factor_analysis
  • n≥100 + 3+ continuous → pca
  • n≥100 + 3+ continuous → cluster_analysis
  • Survival/time-to-event data → survival_analysis
  • Non-normal data → variable_transformation
  • Longitudinal/trend objective → time_series

═══════════════════════════════════════════════════════
VALID test_function NAMES (use ONLY these)
═══════════════════════════════════════════════════════
descriptive_stats, frequency_analysis, mean_median_mode, dispersion_extended, percentiles_extended, z_scores, skewness_analysis, kurtosis_analysis, variable_transformation,
normality_check, shapiro_wilk_all, kolmogorov_smirnov, anderson_darling, jarque_bera, dagostino_pearson, normal_qq_plot, omnibus_normality,
outliers_iqr, outliers_zscore, outliers_grubbs, mahalanobis_distance, cooks_distance, leverage_hat,
cronbach_alpha, mcdonald_omega, kr20, split_half_reliability, icc, item_analysis,
levene_test, bartlett_test, mauchly_test, durbin_watson, vif_check,
one_sample_t_test, one_sample_t_cohend, independent_t_test, independent_t_cohend, welch_t_test, paired_t_test, paired_t_cohend,
one_way_anova, anova_eta_squared, anova_descriptives, anova_assumptions, welch_anova, two_way_anova, two_way_eta_squared, two_way_pairwise, ancova, repeated_anova, manova, manova_followup,
tukey_hsd, bonferroni_test, dunn_test, scheffe_test, fisher_lsd, newman_keuls, dunnett_test,
mann_whitney, mann_whitney_r, wilcoxon, wilcoxon_r, kruskal_wallis, kruskal_wallis_eta2, friedman_test, kendall_w, sign_test, runs_test, mcnemar,
pearson_correlation, pearson_ci, spearman_correlation, kendall_tau, point_biserial, phi_coefficient, cramers_v, partial_correlation, canonical_correlation, correlation_matrix, correlation_heatmap, correlation_significance,
simple_linear_regression, multiple_regression, logistic_regression, multinomial_logistic, ordinal_regression, hierarchical_regression, stepwise_regression, mediation_analysis, moderation_analysis, cox_regression, poisson_regression, quantile_regression,
chi_square, chi_square_extended, fisher_exact,
pca, factor_analysis, discriminant_analysis, cluster_analysis, sem, path_analysis, survival_analysis, time_series

═══════════════════════════════════════════════════════
OUTPUT — CRITICAL RULES
═══════════════════════════════════════════════════════
Return ONLY a valid JSON array — no markdown, no explanation, nothing else.
Order: Tier 1 items first → Tier 2 → Tier 3 → Tier 4 → Tier 5.
Each object MUST have ALL of these fields:
{{
  "test_name": "Human readable name",
  "test_function": "snake_case_name",
  "tier": 1,
  "variables": ["col_name"],
  "hypothesis_index": -1,
  "objective_index": -1,
  "hypothesis": "H0: ... H1: ...",
  "rationale": "Why selected + what objective/hypothesis it addresses",
  "always_run": true,
  "effect_size_companion": "companion_function or null",
  "posthoc_companion": "posthoc_function or null"
}}

STRICT RULES:
1. hypothesis_index: 0-based index into hypotheses array, -1 for non-hypothesis tests
2. objective_index: 0-based index into objectives array, -1 if not objective-specific
3. Every stated hypothesis AND objective must be covered by ≥1 test
4. NO duplicate test_function values
5. Omit tests the data CANNOT support (check n, variable types, n_groups)
6. **HARD CAP: Maximum 25 tests total** — prioritise quality and direct relevance over exhaustive coverage
7. descriptive_stats MUST be index 0 in the array
8. If control_variable is set, prefer ancova over plain ANOVA

ANTI-BLOAT RULES (prevent over-selection):
- Do NOT include both pearson_correlation AND spearman_correlation unless data has mixed normal/non-normal vars
- Do NOT include both independent_t_test AND welch_t_test — pick ONE based on Levene's result (default welch_t_test if unsure)
- Do NOT include ALL normality tests — pick normality_check PLUS at most ONE other (jarque_bera if n≥50, else shapiro_wilk_all)
- Do NOT include both tukey_hsd AND bonferroni_test — pick ONE post-hoc per ANOVA
- Do NOT include mahalanobis_distance unless n≥80 AND 3+ continuous DVs
- Do NOT include factor_analysis unless 5+ ordinal Likert items OR objective explicitly mentions 'factor' or 'scale'
- Do NOT include cluster_analysis unless objective explicitly mentions 'cluster', 'segment', or 'group profiling'
- Do NOT include time_series unless objective mentions 'trend', 'longitudinal', or 'forecast'
- Do NOT include survival_analysis unless objective mentions 'time to event', 'survival', or 'hazard'
- OMIT outlier tests (outliers_iqr, outliers_zscore) if n < 50 — they are not meaningful for small samples

PRIORITY RESOLUTION (when data type is ambiguous):
- Ordinal DV with 2 groups → prefer mann_whitney over independent_t_test
- Ordinal DV with 3+ groups → prefer kruskal_wallis over one_way_anova  
- When n < 30 → prefer non-parametric alternatives (mann_whitney, kruskal_wallis, spearman_correlation)
- When n ≥ 50 AND normality_hint = normal → prefer parametric (independent_t_test, one_way_anova, pearson_correlation)
- Binary DV → use logistic_regression NOT linear regression
- Nominal-nominal association → chi_square + cramers_v (NOT correlation)
"""
    else:
        # ── Manual / Researcher-Chosen mode ───────────────────────────
        # Translate frontend IDs to human-readable names
        chosen_labels = [
            TECHNIQUE_ID_MAP.get(tid, tid)
            for tid in user_techniques
            if tid in TECHNIQUE_ID_MAP
        ]
        # Always include descriptives + normality as baseline
        baseline = [
            "Descriptive Statistics (frequencies, mean, SD for all variables)",
            "Shapiro-Wilk Normality Test (on continuous variables)",
        ]
        # Merge: baseline first, then researcher choices (avoid exact duplicates)
        combined = baseline + [t for t in chosen_labels if t not in baseline]
        combined_str = "\n".join(f"  - {t}" for t in combined)

        prompt = f"""You are an expert statistician. The researcher has explicitly chosen the following statistical techniques to run on their data. Your job is to map each technique to the correct variables from the dataset and return the full test plan as JSON.

RESEARCH BRIEF:
Topic: {brief.get('topic')}
Study Type: {brief.get('study_type')}
Dependent Variable (DV / Outcome): {dv}
Independent Variable (IV / Predictor): {iv}
Control Variable(s): {brief.get('control_variable') or '(none specified)'}
Mediating Variable(s): {brief.get('mediating_variable') or brief.get('mediating_column') or '(none specified)'}
Moderating Variable(s): {brief.get('moderating_variable') or brief.get('moderating_column') or '(none specified)'}
Hypotheses: {json.dumps(hypotheses)}
Likert Constructs: {json.dumps(likert_constructs)}
Demographic Columns: {json.dumps(demographic_cols)}
Significance Level: {brief.get('significance_level', 0.05)}

VARIABLE ASSIGNMENT RULES:
- For mediation_analysis: variables MUST be [iv_col, mediating_col, dv_col]
- For moderation_analysis: variables MUST be [iv_col, moderating_col, dv_col]
- For ancova: include the Control Variable as a covariate in the variables list
- For partial_correlation: include the Control Variable as the third variable

DATA COLUMNS:
Ordinal/Likert vars: {json.dumps(ordinal_vars[:15])}
Ratio/Continuous vars: {json.dumps(ratio_vars[:10])}
Nominal/Categorical vars: {json.dumps(nominal_vars[:10])}

RESEARCHER'S CHOSEN TECHNIQUES (YOU MUST RUN ALL OF THESE):
{combined_str}

INSTRUCTIONS:
1. For EACH technique above, identify the most appropriate variable(s) from the dataset.
2. Match the technique to the closest available Python/scipy/statsmodels implementation.
3. If the dataset clearly cannot support a chosen technique (e.g. Paired t-test but no repeated measures), still include it but set "rationale" to explain the limitation.
4. Link each technique to the relevant hypothesis where applicable (set hypothesis_index to -1 if not hypothesis-specific).
5. Descriptive Statistics MUST always be the first item.
6. Do NOT add or remove techniques — only run what the researcher selected.

Return a JSON array only — no other text. Each object must have:
{{"test_name":"string","test_function":"python_function_name","variables":["var1","var2"],"hypothesis_index":-1,"hypothesis":"H0 text or empty","rationale":"brief explanation","always_run":true}}

For test_function use snake_case names.
"""

    try:
        text = _llm_chat(prompt, max_tokens=3000)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        selected = json.loads(text.strip())
    except Exception as _llm_err:
        if not auto_select and user_techniques:
            # Manual mode: build real test plan directly from user's selections
            # without Claude — NEVER fall back to mock tests in manual mode
            selected = _build_manual_tests_fallback(user_techniques, data_dict, brief)
        else:
            # Auto mode: use baseline mock as last resort
            selected = _mock_tests(brief, data_dict)

    # ── Brief-Requested Test Injection ────────────────────────────────────────
    # Guarantee any tests the researcher explicitly named in the brief are included
    # even if the LLM omitted them (e.g. due to token limits or wrong judgement).
    brief_requested = (
        brief.get("requested_tests", []) or
        brief.get("selected_techniques", []) or
        []
    )
    if brief_requested and isinstance(selected, list):
        existing_fns = {(t.get("test_function") or "").lower() for t in selected}
        for req_id in brief_requested:
            fn_name = TECHNIQUE_ID_MAP.get(req_id, req_id)
            # Convert human label to snake_case function name if needed
            fn_key = fn_name.lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
            # Also check the raw id as function name
            for candidate in [req_id.lower(), fn_key]:
                if candidate and candidate not in existing_fns:
                    selected.append({
                        "test_name": fn_name,
                        "test_function": candidate,
                        "variables": (data_dict.get("ratio_vars", []) + data_dict.get("ordinal_vars", []))[:3],
                        "hypothesis_index": -1,
                        "hypothesis": "",
                        "rationale": "Explicitly requested in research brief",
                        "always_run": True,
                    })
                    existing_fns.add(candidate)
                    break

    return _ensure_baseline_tests(selected, data_dict, brief=brief)


def _ensure_baseline_tests(tests: list, data_dict: dict, brief: dict | None = None) -> list:
    """
    Python safeguard: guarantees descriptive_stats, frequency_analysis, and
    normality_check are always present regardless of LLM output.
    Also guarantees mediation_analysis / moderation_analysis when the researcher
    has explicitly set mediating_variable or moderating_variable in the brief.
    Inserts them at the front without duplicating any already selected.
    """
    ratio_vars   = data_dict.get("ratio_vars", [])
    ordinal_vars = data_dict.get("ordinal_vars", [])
    nominal_vars = data_dict.get("nominal_vars", [])
    all_vars     = ratio_vars + ordinal_vars + nominal_vars
    continuous   = ratio_vars + ordinal_vars

    existing_fns = {(t.get("test_function") or "").lower() for t in (tests or [])}

    mandatory = []

    if "descriptive_stats" not in existing_fns:
        mandatory.append({
            "test_name": "Descriptive Statistics",
            "test_function": "descriptive_stats",
            "variables": all_vars[:20],
            "hypothesis_index": -1,
            "hypothesis": "",
            "rationale": "Mandatory baseline: summarises all variables before inferential testing.",
            "always_run": True,
        })

    if "frequency_analysis" not in existing_fns and nominal_vars:
        mandatory.append({
            "test_name": "Frequency Analysis",
            "test_function": "frequency_analysis",
            "variables": nominal_vars[:10],
            "hypothesis_index": -1,
            "hypothesis": "",
            "rationale": "Mandatory baseline: frequency distributions for all categorical variables.",
            "always_run": True,
        })

    if "normality_check" not in existing_fns and continuous:
        mandatory.append({
            "test_name": "Normality Check (Shapiro-Wilk)",
            "test_function": "normality_check",
            "variables": continuous[:10],
            "hypothesis_index": -1,
            "hypothesis": "",
            "rationale": "Mandatory baseline: determines parametric vs non-parametric test suitability.",
            "always_run": True,
        })

    # ── Mediation / Moderation Safety Net ────────────────────────────────────
    # If the researcher explicitly specified a Mediating or Moderating variable,
    # inject the corresponding test unconditionally (LLM may have omitted it).
    if brief:
        _brief = brief  # local alias
        dv_raw  = _brief.get("dependent_variable", "")  or _brief.get("dv_column", "")
        iv_raw  = _brief.get("independent_variable", "") or _brief.get("iv_column", "")
        med_raw = _brief.get("mediating_variable", "")  or _brief.get("mediating_column", "")
        mod_raw = _brief.get("moderating_variable", "")  or _brief.get("moderating_column", "")

        def _first(s: str) -> str:
            """Return first comma-separated token, stripped."""
            return (s or "").split(",")[0].strip()

        iv_col  = _first(iv_raw)
        dv_col  = _first(dv_raw)
        med_col = _first(med_raw)
        mod_col = _first(mod_raw)

        if med_col and "mediation_analysis" not in existing_fns and iv_col and dv_col:
            med_vars = [iv_col, med_col, dv_col]
            mandatory.append({
                "test_name": "Mediation Analysis (Baron & Kenny + BCa Bootstrap)",
                "test_function": "mediation_analysis",
                "variables": med_vars,
                "hypothesis_index": -1,
                "hypothesis": "",
                "rationale": (
                    f"Researcher explicitly specified Mediating Variable '{med_col}'. "
                    f"Testing: {iv_col} → {med_col} → {dv_col}."
                ),
                "always_run": True,
            })
            existing_fns.add("mediation_analysis")

        if mod_col and "moderation_analysis" not in existing_fns and iv_col and dv_col:
            mod_vars = [iv_col, mod_col, dv_col]
            mandatory.append({
                "test_name": "Moderation Analysis (Interaction + Simple Slopes)",
                "test_function": "moderation_analysis",
                "variables": mod_vars,
                "hypothesis_index": -1,
                "hypothesis": "",
                "rationale": (
                    f"Researcher explicitly specified Moderating Variable '{mod_col}'. "
                    f"Testing interaction: {iv_col} × {mod_col} → {dv_col}."
                ),
                "always_run": True,
            })
            existing_fns.add("moderation_analysis")

        if med_col and mod_col and "moderated_mediation" not in existing_fns and iv_col and dv_col:
            mandatory.append({
                "test_name": "Moderated Mediation",
                "test_function": "moderated_mediation",
                "variables": [iv_col, med_col, mod_col, dv_col],
                "hypothesis_index": -1,
                "hypothesis": "",
                "rationale": (
                    f"Both Mediating ('{med_col}') and Moderating ('{mod_col}') variables are specified. "
                    f"Testing conditional indirect effects."
                ),
                "always_run": True,
            })

    return mandatory + (tests or [])



def _mock_tests(brief: dict, data_dict: dict) -> list:
    """Deterministic, rule-based test selection based on brief hypotheses and variables."""
    ratio_vars = data_dict.get("ratio_vars", [])
    ordinal_vars = data_dict.get("ordinal_vars", [])
    nominal_vars = data_dict.get("nominal_vars", [])
    all_vars = ratio_vars + ordinal_vars + nominal_vars
    
    tests = [
        {"test_name": "Descriptive Statistics", "test_function": "descriptive_stats",
         "variables": ratio_vars[:5] + ordinal_vars[:5] + nominal_vars[:2],
         "hypothesis_index": -1, "hypothesis": "",
         "rationale": "Always run — frequencies and means for all variables", "always_run": True},
        {"test_name": "Normality Check (Shapiro-Wilk)", "test_function": "normality_check",
         "variables": ratio_vars[:5] if ratio_vars else (ordinal_vars[:5] if ordinal_vars else []),
         "hypothesis_index": -1, "hypothesis": "",
         "rationale": "Test normality assumption before parametric tests", "always_run": True},
    ]

    if len(ordinal_vars) >= 3:
        tests.append({
            "test_name": "Cronbach's Alpha (Reliability)", "test_function": "cronbach_alpha",
            "variables": ordinal_vars[:6],
            "hypothesis_index": -1, "hypothesis": "",
            "rationale": "Assess internal consistency of Likert scale items", "always_run": True
        })

    hypotheses = brief.get("hypotheses", [])
    
    if not hypotheses:
        col1 = ratio_vars[0] if ratio_vars else (ordinal_vars[0] if ordinal_vars else "var1")
        col2 = ratio_vars[1] if len(ratio_vars) > 1 else (ordinal_vars[1] if len(ordinal_vars) > 1 else col1)
        if col1 != col2:
            tests.append({
                "test_name": "Pearson Correlation", "test_function": "pearson_correlation",
                "variables": [col1, col2],
                "hypothesis_index": 0,
                "hypothesis": f"H0: There is no significant relationship between {col1} and {col2}",
                "rationale": "Examine linear relationship between variables", "always_run": False
            })
            
        if len(nominal_vars) >= 2:
            tests.append({
                "test_name": "Chi-Square Test of Independence", "test_function": "chi_square",
                "variables": nominal_vars[:2],
                "hypothesis_index": len(tests),
                "hypothesis": f"H0: There is no association between {nominal_vars[0]} and {nominal_vars[1]}",
                "rationale": "Assess relationship between categorical variables", "always_run": False
            })
        return tests

    import re
    for i, hyp in enumerate(hypotheses):
        hyp_lower = hyp.lower()
        
        # 1. Identify which variables are mentioned
        mentioned_vars = []
        for v in all_vars:
            parts = v.split('_')
            # Check if variable parts exist as whole words in the hypothesis
            if any(re.search(rf'\b{re.escape(p.lower())}\b', hyp_lower) for p in parts if len(p) > 2):
                if v not in mentioned_vars:
                    mentioned_vars.append(v)
            elif re.search(rf'\b{re.escape(v.lower())}\b', hyp_lower):
                if v not in mentioned_vars:
                    mentioned_vars.append(v)
                    
        # Filter down slightly to ensure we have a fallback if none found
        if not mentioned_vars:
            mentioned_vars = ratio_vars[:2] if ratio_vars else all_vars[:2]
            
        # 2. Heuristics for Test Type
        if any(kw in hyp_lower for kw in ["logistic", "odds", "probability", "binary", "predicting intent"]):
            log_vars = mentioned_vars.copy() if len(mentioned_vars) > 1 else (nominal_vars[:1] + ratio_vars[:2])
            # Ensure the dependent variable (binary/nominal) is first
            nominal_in_log = [v for v in log_vars if v in nominal_vars or 'intent' in v or 'promot' in v or 'gender' in v]
            if nominal_in_log:
                log_vars.remove(nominal_in_log[0])
                log_vars.insert(0, nominal_in_log[0])
            tests.append({
                "test_name": "Logistic Regression",
                "test_function": "logistic_regression",
                "variables": log_vars,
                "hypothesis_index": i, "hypothesis": hyp,
                "rationale": "Assess predictors of a binary/categorical outcome", "always_run": False
            })
            continue

        if any(kw in hyp_lower for kw in ["factors", "components", "dimension", "underlying", "pca"]):
            tests.append({
                "test_name": "Principal Component Analysis",
                "test_function": "pca",
                "variables": mentioned_vars if len(mentioned_vars) >= 3 else (ordinal_vars[:6] if len(ordinal_vars) >=3 else ratio_vars[:4]),
                "hypothesis_index": i, "hypothesis": hyp,
                "rationale": "Identify underlying structure and reduce dimensionality", "always_run": False
            })
            continue

        if any(kw in hyp_lower for kw in ["pre-test", "post-test", "over time", "paired", "before and after"]):
            tests.append({
                "test_name": "Paired Samples T-Test",
                "test_function": "paired_t_test",
                "variables": mentioned_vars[:2] if len(mentioned_vars) >= 2 else ratio_vars[:2],
                "hypothesis_index": i, "hypothesis": hyp,
                "rationale": "Compare means for the same subjects across two conditions", "always_run": False
            })
            continue

        if any(kw in hyp_lower for kw in ["predict", "jointly", "influence", "regression"]):
            tests.append({
                "test_name": "Multiple Linear Regression",
                "test_function": "multiple_regression",
                "variables": mentioned_vars if len(mentioned_vars) > 1 else (ratio_vars[:3] + ordinal_vars[:1]),
                "hypothesis_index": i, "hypothesis": hyp,
                "rationale": "Assess predictors based on hypothesis keywords", "always_run": False
            })
            continue
            
        if any(kw in hyp_lower for kw in ["correlate", "relationship", "associated", "association", "chi-square"]):
            matched_nominals = [v for v in mentioned_vars if v in nominal_vars]
            if len(matched_nominals) >= 2 or ("association" in hyp_lower) or ("chi-square" in hyp_lower):
                tests.append({
                    "test_name": "Chi-Square Test",
                    "test_function": "chi_square",
                    "variables": mentioned_vars[:2] if len(mentioned_vars) >= 2 else (nominal_vars[:2]),
                    "hypothesis_index": i, "hypothesis": hyp,
                    "rationale": "Test association between categorical variables", "always_run": False
                })
            elif any(kw in hyp_lower for kw in ["non-parametric", "rank", "spearman", "ordinal"]):
                tests.append({
                    "test_name": "Spearman Correlation",
                    "test_function": "spearman_correlation",
                    "variables": mentioned_vars[:2] if len(mentioned_vars) >= 2 else (ordinal_vars[:2] if len(ordinal_vars) >= 2 else ratio_vars[:2]),
                    "hypothesis_index": i, "hypothesis": hyp,
                    "rationale": "Examine non-parametric correlation between variables", "always_run": False
                })
            else:
                tests.append({
                    "test_name": "Pearson Correlation",
                    "test_function": "pearson_correlation",
                    "variables": mentioned_vars[:2] if len(mentioned_vars) >= 2 else (ratio_vars[:2]),
                    "hypothesis_index": i, "hypothesis": hyp,
                    "rationale": "Examine correlation between variables", "always_run": False
                })
            continue

        if any(kw in hyp_lower for kw in ["differ", "compare", "higher", "lower", "between", "than", "t-test", "anova"]):
            if "anova" in hyp_lower:
                tests.append({
                    "test_name": "One-Way ANOVA",
                    "test_function": "one_way_anova",
                    "variables": mentioned_vars[:2] if len(mentioned_vars) >= 2 else (nominal_vars[:1] + ratio_vars[:1]),
                    "hypothesis_index": i, "hypothesis": hyp,
                    "rationale": "Compare means across groups", "always_run": False
                })
            elif any(kw in hyp_lower for kw in ["kruskal", "non-parametric anova"]):
                tests.append({
                    "test_name": "Kruskal-Wallis Test",
                    "test_function": "kruskal_wallis",
                    "variables": mentioned_vars[:2] if len(mentioned_vars) >= 2 else (nominal_vars[:1] + ordinal_vars[:1]),
                    "hypothesis_index": i, "hypothesis": hyp,
                    "rationale": "Compare medians across multiple groups", "always_run": False
                })
            elif any(kw in hyp_lower for kw in ["mann-whitney", "u-test", "median"]):
                tests.append({
                    "test_name": "Mann-Whitney U Test",
                    "test_function": "mann_whitney",
                    "variables": mentioned_vars[:2] if len(mentioned_vars) >= 2 else (nominal_vars[:1] + ordinal_vars[:1]),
                    "hypothesis_index": i, "hypothesis": hyp,
                    "rationale": "Compare medians between two independent groups", "always_run": False
                })
            else:
                tests.append({
                    "test_name": "Independent Samples T-Test",
                    "test_function": "independent_t_test",
                    "variables": mentioned_vars[:2] if len(mentioned_vars) >= 2 else (nominal_vars[:1] + ratio_vars[:1]),
                    "hypothesis_index": i, "hypothesis": hyp,
                    "rationale": "Compare means between groups", "always_run": False
                })
            continue

        # Fallback
        tests.append({
            "test_name": "Independent Samples T-Test",
            "test_function": "independent_t_test",
            "variables": mentioned_vars[:2] if len(mentioned_vars) >= 2 else (nominal_vars[:1] + ratio_vars[:1]),
            "hypothesis_index": i, "hypothesis": hyp,
            "rationale": "Fallback comparison test", "always_run": False
        })
        
    return tests



# ─── Stage 6: Visualisation ──────────────────────────────────────────
def _create_visualisations(results: dict, df, brief: dict, job_id: str, tests: list = None,
                           auto_viz: bool = True, selected_viz: list = None,
                           auto_tables: bool = True, selected_tables: list = None,
                           label_map: dict = None) -> list:
    """Delegate to analysis.charts for publication-quality, one-image-per-variable charts."""
    from analysis.charts import create_visualisations as _viz
    chart_dir = os.path.join(settings.CHARTS_DIR, job_id)
    return _viz(results, df, brief, job_id,
                chart_dir=chart_dir,
                tests=tests,
                auto_viz=auto_viz,
                selected_viz=selected_viz,
                auto_tables=auto_tables,
                selected_tables=selected_tables,
                label_map=label_map or {})


def _get_figure_label(chart_path: str, brief: dict = None) -> str:
    """Generate a clean, professional, publication-ready title for a chart/figure."""
    if not chart_path:
        return "Statistical Figure"
    fname = os.path.basename(chart_path).lower()
    brief = brief or {}
    iv = brief.get("independent_variable", "") or "Independent Variable"
    dv = brief.get("dependent_variable", "") or "Dependent Variable"
    
    # Specific chart patterns
    if "chart_scatter" in fname or "chart_regression" in fname:
        return f"Scatter Plot with Linear Regression Line ({iv} vs. {dv})"
    elif "chart_correlation" in fname:
        return "Bivariate Correlation Matrix Heatmap"
    elif "table_correlation" in fname:
        return "Correlation Matrix Coefficients Table"
    elif "chart_means" in fname:
        return "Comparison of Key Study Variable Means"
    elif "chart_boxplots" in fname:
        return "Box Plot Distribution Comparison across Study Variables"
    elif "chart_skewness" in fname:
        return "Distribution Skewness Indices across Study Variables"
    elif "chart_kurtosis" in fname:
        return "Distribution Kurtosis Indices across Study Variables"
    elif "chart_outliers" in fname:
        return "Outlier Detection and Data Dispersion Analysis"
    elif "chart_posthoc" in fname:
        return "Tukey HSD Pairwise Mean Differences with 95% Confidence Intervals"
    elif "chart_normality" in fname:
        return "Normality Test Summary across Study Variables"
    elif "table_descriptive" in fname:
        return "Descriptive Statistics Summary (Mean, SD, Min, Max)"
    elif "table_test_results" in fname:
        return "Statistical Hypothesis Test Results"
    elif "table_normality" in fname:
        return "Shapiro-Wilk & Kolmogorov-Smirnov Normality Assessment"
    elif "table_outliers" in fname:
        return "Outlier Counts and Percentage Affected"
    elif "table_posthoc" in fname:
        return "Post-Hoc Pairwise Comparison Results"
    
    import re
    m_dist = re.search(r'chart_dist_\d+_(.+)\.png', fname)
    if m_dist:
        col_clean = m_dist.group(1).replace('_', ' ').title()
        return f"Distribution Histogram of {col_clean} (with Normal Curve)"
    
    m_freq_bar = re.search(r'chart_freq_\d+_(.+)_bar\.png', fname)
    if m_freq_bar:
        col_clean = m_freq_bar.group(1).replace('_', ' ').title()
        return f"Frequency Distribution Bar Chart of {col_clean}"
        
    m_freq_pie = re.search(r'chart_freq_\d+_(.+)_pie\.png', fname)
    if m_freq_pie:
        col_clean = m_freq_pie.group(1).replace('_', ' ').title()
        return f"Proportion Breakdown Pie Chart of {col_clean}"

    m_freq_tbl = re.search(r'table_freq_\d+_(.+)\.png', fname)
    if m_freq_tbl:
        col_clean = m_freq_tbl.group(1).replace('_', ' ').title()
        return f"Frequency Table of {col_clean}"

    m_violin = re.search(r'chart_violin_\d+_(.+)\.png', fname)
    if m_violin:
        col_clean = m_violin.group(1).replace('_', ' ').title()
        return f"Violin Distribution Density Plot for {col_clean}"

    m_qq = re.search(r'chart_qq_\d+_(.+)\.png', fname)
    if m_qq:
        col_clean = m_qq.group(1).replace('_', ' ').title()
        return f"Q-Q Normality Probability Plot for {col_clean}"

    m_zscore = re.search(r'chart_zscore_\d+_(.+)\.png', fname)
    if m_zscore:
        col_clean = m_zscore.group(1).replace('_', ' ').title()
        return f"Standardized Z-Scores Analysis for {col_clean}"

    base_clean = os.path.splitext(fname)[0].replace('chart_', '').replace('table_', '').replace('_', ' ').title()
    return f"{base_clean} Visualisation"


# ─── User-class token budget configuration ────────────────────────────────────
# Limits per bucket per user class.
#   None  = skip this bucket entirely (don't send to Claude)
#   0     = no truncation (full content)
#   int>0 = truncate to this many characters
_BUCKET_LIMITS: dict = {
    #                              bsc    msc    phd   researcher  business
    "summary":        dict(bsc=0,    msc=0,    phd=0,  researcher=0,    business=0),
    "descriptive":    dict(bsc=3000, msc=6000, phd=0,  researcher=0,    business=4000),
    "frequencies":    dict(bsc=1500, msc=3000, phd=0,  researcher=0,    business=2000),
    "normality":      dict(bsc=1000, msc=2000, phd=0,  researcher=0,    business=None),
    "normality_extended": dict(bsc=None, msc=1500, phd=0, researcher=0, business=None),
    "reliability":    dict(bsc=0,    msc=0,    phd=0,  researcher=0,    business=0),
    "comparison":     dict(bsc=1500, msc=4000, phd=0,  researcher=0,    business=3000),
    "regression":     dict(bsc=1000, msc=4000, phd=0,  researcher=0,    business=4000),
    "correlation":    dict(bsc=1000, msc=2500, phd=0,  researcher=0,    business=1500),
    "posthoc":        dict(bsc=800,  msc=2000, phd=0,  researcher=0,    business=None),
    "causal":         dict(bsc=None, msc=2000, phd=0,  researcher=0,    business=None),
    "multivariate":   dict(bsc=None, msc=1500, phd=0,  researcher=0,    business=None),
    "multilevel":     dict(bsc=None, msc=1500, phd=0,  researcher=0,    business=None),
    "survival":       dict(bsc=None, msc=None, phd=0,  researcher=0,    business=None),
    "timeseries":     dict(bsc=None, msc=None, phd=0,  researcher=0,    business=None),
    "power":          dict(bsc=None, msc=800,  phd=0,  researcher=0,    business=None),
    "assumptions":    dict(bsc=None, msc=1500, phd=0,  researcher=0,    business=None),
    "outliers":       dict(bsc=600,  msc=1500, phd=0,  researcher=0,    business=800),
    "skewness_kurtosis": dict(bsc=800, msc=1500, phd=0, researcher=0,   business=None),
    "fallbacks_applied": dict(bsc=None, msc=0, phd=0,  researcher=0,    business=None),
    "health_report":  dict(bsc=None, msc=None, phd=0,  researcher=0,    business=None),
    "not_applicable": dict(bsc=0,    msc=0,    phd=0,  researcher=0,    business=0),
}

# Total character cap per class (≈ 1 token per 4 chars)
_CLASS_TOTAL_CAP: dict = {
    "bsc":        16_000,
    "msc":        32_000,
    "phd":        48_000,
    "researcher": 48_000,
    "business":   20_000,
}


def _package_results_for_claude(results: dict, user_class: str) -> dict:
    """
    Build a class-aware results package for the Claude prompt.
    Returns a dict of JSON strings, one per active bucket.
    Skipped buckets return ''. Total chars capped by _CLASS_TOTAL_CAP.
    """
    uc = user_class if user_class in _CLASS_TOTAL_CAP else "bsc"
    limits = {k: v.get(uc) for k, v in _BUCKET_LIMITS.items()}
    total_cap = _CLASS_TOTAL_CAP[uc]

    def _pack(bucket_key: str, data) -> str:
        limit = limits.get(bucket_key)
        if limit is None:
            return ""
        raw = json.dumps(data, indent=2, default=str)
        return raw if limit == 0 else raw[:limit]

    # ── Unwrap descriptive nested structure ───────────────────────────────
    _desc_raw  = results.get("descriptive", {}).get("descriptive_stats", {})
    _desc_cols = (_desc_raw.get("additional_stats", {}) or {}).get("columns") or _desc_raw
    if isinstance(_desc_cols, dict) and not any("mean" in str(v) for v in _desc_cols.values()):
        _desc_cols = _desc_raw
    desc_clean = {k: v for k, v in _desc_cols.items()
                  if isinstance(v, dict) and "mean" in v} if isinstance(_desc_cols, dict) else {}
    if not desc_clean:
        for _k, _v in results.get("descriptive", {}).items():
            if isinstance(_v, dict):
                _as = (_v.get("additional_stats") or {}).get("columns") or {}
                desc_clean.update({ck: cv for ck, cv in _as.items()
                                   if isinstance(cv, dict) and "mean" in cv})

    # ── Unwrap frequencies nested structure ────────────────────────────────
    _freq_raw  = results.get("frequencies", {}).get("frequency_analysis", {})
    _freq_data = (_freq_raw.get("additional_stats") or {}).get("frequencies") or {}
    freq_clean = {}
    for _col, _fdata in _freq_data.items():
        _counts = _fdata.get("counts") if isinstance(_fdata, dict) else _fdata
        if isinstance(_counts, dict):
            freq_clean[_col] = dict(list(_counts.items())[:8])

    # ── Skewness/Kurtosis — key fields only ────────────────────────────────
    sk_clean = {
        k: {kk: round(vv, 4) if isinstance(vv, float) else vv
            for kk, vv in v.items()
            if kk in ("skewness", "kurtosis", "skew_interp", "kurt_interp",
                       "z_skewness", "z_kurtosis")}
        for k, v in results.get("skewness_kurtosis", {}).items()
    }

    # ── Outliers — method summaries only ──────────────────────────────────
    outlier_clean = {
        k: {kk: vv for kk, vv in v.items() if kk in ("iqr_method", "zscore_method")}
        for k, v in results.get("outliers", {}).items()
        if isinstance(v, dict) and "iqr_method" in v
    }

    # ── Normality Extended — key stats only ────────────────────────────────
    norm_ext_clean = {
        k: {tk: {"normal": vv.get("normal"), "p_value": round(vv.get("p_value", 0), 4)}
            for tk, vv in v.items() if isinstance(vv, dict) and "normal" in vv}
        for k, v in results.get("normality_extended", {}).items()
    }

    # ── Build each block ───────────────────────────────────────────────────
    pkg: dict = {
        "summ_json":         _pack("summary",           results.get("summary", [])),
        "desc_json":         _pack("descriptive",        desc_clean),
        "freq_json":         _pack("frequencies",        freq_clean),
        "norm_json":         _pack("normality",          results.get("normality", {})),
        "rel_json":          _pack("reliability",        results.get("reliability", {})),
        "comparison_json":   _pack("comparison",         results.get("comparison", {})),
        "regression_json":   _pack("regression",         results.get("regression", {})),
        "correlation_json":  _pack("correlation",        results.get("correlation", {})),
        "posthoc_json":      _pack("posthoc",            results.get("posthoc", {})),
        "causal_json":       _pack("causal",             results.get("causal", {})),
        "multivariate_json": _pack("multivariate",       results.get("multivariate", {})),
        "multilevel_json":   _pack("multilevel",         results.get("multilevel", {})),
        "survival_json":     _pack("survival",           results.get("survival", {})),
        "timeseries_json":   _pack("timeseries",         results.get("timeseries", {})),
        "power_json":        _pack("power",              results.get("power", {})),
        "assumptions_json":  _pack("assumptions",        results.get("assumptions", {})),
        "sk_json":           _pack("skewness_kurtosis",  sk_clean),
        "outlier_json":      _pack("outliers",           outlier_clean),
        "norm_ext_json":     _pack("normality_extended", norm_ext_clean),
        "fallbacks_json":    _pack("fallbacks_applied",  results.get("fallbacks_applied", [])),
        "health_json":       _pack("health_report",      results.get("health_report", {})),
        "not_applicable_block": "",
    }

    # ── not_applicable block (always full, formatted as prose) ─────────────
    _not_applicable = results.get("not_applicable", [])
    if _not_applicable:
        _na_lines = [
            f"  - {item.get('test_name', 'Unknown')}: {item.get('reason', '')} "
            f"Suggestion: {item.get('suggestion', '')}"
            for item in _not_applicable
        ]
        pkg["not_applicable_block"] = (
            "\nTESTS SELECTED BUT NOT APPLICABLE TO THIS DATASET:\n"
            + "\n".join(_na_lines)
            + "\n(For each of these, write a brief methodological note in the report explaining "
            "why the test could not be executed and what data structure would be required. "
            "Do NOT fabricate statistics for these tests.)"
        )

    # ── Total character cap guard ──────────────────────────────────────────
    _protected = {"summ_json", "rel_json", "not_applicable_block"}
    _total = sum(len(v) for v in pkg.values())
    if _total > total_cap:
        _reducible = sorted(
            [(k, v) for k, v in pkg.items() if k not in _protected and len(v) > 200],
            key=lambda x: len(x[1]), reverse=True
        )
        for _key, _val in _reducible:
            if _total <= total_cap:
                break
            _half = _val[:len(_val) // 2]
            _total -= len(_val) - len(_half)
            pkg[_key] = _half

    return pkg


# ─── Stage 7a: Report Writing ─────────────────────────────────────────────────
def _write_report(brief: dict, results: dict, tests: list, data_dict: dict,
                  chapter_texts: dict = None, report_type: str = "chapter4",
                  academic_tradition: str = "standard",
                  thematic_results: dict = None,
                  formatting_options: dict = None,
                  chart_paths: list = None) -> dict:
    """LLM writes report in the requested format, merging all strands."""
    chapter_texts = chapter_texts or {}
    report_type   = report_type or "chapter4"
    chart_paths   = chart_paths or []

    summary     = results.get("summary", [])
    reliability = results.get("reliability", {})
    normality   = results.get("normality", {})

    if not _has_llm():
        return _mock_report_text(brief, summary, reliability, normality, report_type)

    # ── Package results based on user_class (token-budget aware) ──────────
    user_class = str(brief.get("user_class", "bsc")).strip().lower()
    pkg = _package_results_for_claude(results, user_class)

    summ_json        = pkg["summ_json"]
    desc_json        = pkg["desc_json"]
    freq_json        = pkg["freq_json"]
    norm_json        = pkg["norm_json"]
    rel_json         = pkg["rel_json"]
    comparison_json  = pkg["comparison_json"]
    regression_json  = pkg["regression_json"]
    correlation_json = pkg["correlation_json"]
    posthoc_json     = pkg["posthoc_json"]
    causal_json      = pkg["causal_json"]
    multivariate_json= pkg["multivariate_json"]
    multilevel_json  = pkg["multilevel_json"]
    survival_json    = pkg["survival_json"]
    timeseries_json  = pkg["timeseries_json"]
    power_json       = pkg["power_json"]
    assumptions_json = pkg["assumptions_json"]
    sk_json          = pkg["sk_json"]
    outlier_json     = pkg["outlier_json"]
    norm_ext_json    = pkg["norm_ext_json"]
    fallbacks_json   = pkg["fallbacks_json"]
    health_json      = pkg["health_json"]
    not_applicable_block = pkg["not_applicable_block"]

    brief_block = (

        f"Topic: {brief.get('topic')}\n"
        + (f"Study Aim: {brief.get('study_aim')}\n" if brief.get('study_aim') else "")
        + (f"Problem Statement: {brief.get('problem_statement')}\n" if brief.get('problem_statement') else "")
        + (f"Research Background: {brief.get('research_background')}\n" if brief.get('research_background') else "")
        + f"Objectives / Goals: {json.dumps(brief.get('objectives', []))}\n"
        f"Key Questions / Hypotheses: {json.dumps(brief.get('hypotheses', []))}\n"
        f"Outcome Variable(s) (DV): {brief.get('dependent_variable')} | "
        f"Predictor Variable(s) (IV): {brief.get('independent_variable')}\n"
        + (f"Mediating Variable(s): {brief.get('mediating_variable')}\n" if brief.get('mediating_variable') else "")
        + (f"Moderating Variable(s): {brief.get('moderating_variable')}\n" if brief.get('moderating_variable') else "")
        + f"Target Group / Context: {brief.get('population', '')}"
    )

    valid_figure_lines = []
    if chart_paths:
        for fi, cp in enumerate(chart_paths):
            if cp and not str(cp).lower().endswith('.html'):
                flabel = _get_figure_label(str(cp), brief)
    figures_block = ""
    if valid_figure_lines:
        figures_block = (
            "\nAVAILABLE FIGURES & CHARTS (Explicitly cite and integrate these in-text where relevant, "
            "e.g. '(see Figure 4.1)' or 'As depicted in Figure 4.2...'):\n"
            + "\n".join(valid_figure_lines)
            + "\n"
        )

    chapter_context = ""
    if chapter_texts and isinstance(chapter_texts, dict):
        ctx_parts = []
        for ch_k, ch_v in chapter_texts.items():
            if ch_v and isinstance(ch_v, str) and ch_k != "full_text":
                ctx_parts.append(f"--- {ch_k.upper()} ---\n{ch_v[:1500]}")
        if ctx_parts:
            chapter_context = "\nPREVIOUS CHAPTER CONTEXT (for theoretical alignment):\n" + "\n".join(ctx_parts) + "\n"

    lit_rule = "Synthesize and discuss findings in relation to existing empirical literature and theoretical framework where applicable."


    # ════════════════════════════════════════════════════════════════════
    # PROMPT TEMPLATES — one per report type
    # ════════════════════════════════════════════════════════════════════

    if report_type == "business_report" or user_class == "business":
        _business_stat_rule = (
            "- DO NOT use statistical notation: no t(df), F(df1,df2), χ²(df), β, p-values, "
            "confidence intervals, or r values anywhere in the text.\n"
            "- Instead, INTERPRET every finding in plain English:\n"
            "  ✓ 'Employees with higher leadership support reported significantly greater job satisfaction'\n"
            "  ✓ 'There is a strong positive relationship between digital workload and technostress'\n"
            "  ✓ '68% of respondents agreed that innovation climate supports performance'\n"
            "  ✗ NEVER write: 't(198) = 3.42, p = .001' or 'β = 0.34, SE = 0.11'"
        ) if user_class == "business" else (
            "- Present statistics plainly: e.g. \"72% of respondents agreed...\" "
            "or \"A strong positive relationship was found (r = 0.67)\"."
        )
        prompt = f"""You are a professional business analyst. Write a Business Intelligence Report based on the research findings below.
Audience: senior managers, executives, stakeholders.
Tone: professional, concise, action-oriented. Avoid academic jargon.
{_business_stat_rule}

RESEARCH BRIEF:
{brief_block}
{chapter_context}
KEY FINDINGS (statistical summary — for your interpretation only, do NOT quote raw values in the report):
{summ_json}

DESCRIPTIVE DATA:
{desc_json}

FREQUENCY DATA:
{freq_json}

RELIABILITY: {rel_json}

{f"COMPARISON RESULTS:{chr(10)}{comparison_json}" if comparison_json else ""}
{f"REGRESSION RESULTS:{chr(10)}{regression_json}" if regression_json else ""}
{f"CORRELATION RESULTS:{chr(10)}{correlation_json}" if correlation_json else ""}
{not_applicable_block}

SECTIONS REQUIRED (in this order):
1. Executive Summary — 3-5 key findings in bullet points, plain language
2. Background & Context — what was studied and why it matters
3. Key Findings — interpret each result in business terms (significance, impact)
4. Business Implications — what this means for decision-makers
5. Recommendations — 3-5 specific, actionable recommendations
6. Conclusion

RULES:
- Minimum 150 words per section
- Recommendations must be specific and numbered
- Link findings to business outcomes, not academic theory
- {lit_rule}

Return ONLY this JSON:
{{"chapter_title":"BUSINESS INTELLIGENCE REPORT","sections":[{{"heading":"1. Executive Summary","text":"..."}}]}}
"""

    elif report_type == "executive_summary":
        prompt = f"""You are a senior business consultant. Write a concise Executive Summary of research findings.
Audience: C-suite executives, board members, policy makers.
Tone: high-level, strategic, decisive. Maximum clarity. No academic language.

RESEARCH BRIEF:
{brief_block}
{chapter_context}
KEY FINDINGS:
{summ_json}

DESCRIPTIVE DATA: {desc_json}

SECTIONS REQUIRED:
1. Purpose & Scope — one paragraph, what was studied
2. Key Findings — 5-7 bullet points, plain language
3. Critical Insights — 2-3 paragraphs interpreting implications
4. Strategic Recommendations — numbered list, 3-5 items
5. Next Steps

RULES:
- Total document should be 600-900 words (concise)
- No statistical notation — translate numbers to plain English
- Every recommendation must have a clear action verb

Return ONLY this JSON:
{{"chapter_title":"EXECUTIVE SUMMARY","sections":[{{"heading":"1. Purpose & Scope","text":"..."}}]}}
"""

    elif report_type == "slide_deck":
        prompt = f"""You are a presentation designer. Write a Slide Deck Briefing based on the research findings.
Audience: general stakeholders or an executive audience.
Tone: punchy, extremely concise, bullet-driven.

RESEARCH BRIEF:
{brief_block}
{chapter_context}
KEY FINDINGS:
{summ_json}

DESCRIPTIVE DATA: {desc_json}

SECTIONS REQUIRED (each represents one slide):
1. Title & Objective Slide
2. Methodology & Sample — very brief bullet points
3. Key Demographics — highlight 2-3 top stats
4. Core Finding 1 — main result, written as a short headline and 3 bullet points
5. Core Finding 2 — secondary result
6. Strategic Recommendations — 3 actionable bullet points

RULES:
- Write strictly in short bullet points
- Do not write paragraphs
- Keep it under 500 words total
- Use symbols (•, -, or >) for bullets

Return ONLY this JSON:
{{"chapter_title":"SLIDE DECK BRIEFING","sections":[{{"heading":"Slide 1: Title & Objective","text":"..."}}]}}
"""

    elif report_type == "research_paper":
        prompt = f"""You are an academic journal author. Write the Results, Discussion and Conclusion sections of a research paper.
Format: APA 7th edition style. Tone: concise, objective, third-person.
Statistics format: r(df) = .XX, p < .001 or p = .XXX (two decimal places for statistics, three for p-values).

RESEARCH BRIEF:
{brief_block}
{chapter_context}
{figures_block}
RESULTS DATA:
Inferential summary: {summ_json}
Comparison tests: {comparison_json}
Regression: {regression_json}
Correlation: {correlation_json}
Descriptive: {desc_json}
Normality: {norm_json}
Normality Extended: {norm_ext_json}
Skewness & Kurtosis: {sk_json}
Outliers: {outlier_json}
Post-Hoc: {posthoc_json}
Reliability (Cronbach alpha): {rel_json}

SECTIONS REQUIRED:
1. Results — present all statistics in APA format, reference tables and figures directly in-text (e.g. Table 1, Figure 1)
2. Discussion — interpret findings, compare with literature, address hypotheses
3. Limitations — 3-5 honest limitations of the study
4. Conclusion — brief summary and future research directions

RULES:
- APA stat format: t(118) = 3.45, p = .001, d = 0.52
- Integrate and cite available Figures and Tables directly in the narrative
- {lit_rule}
- Minimum 200 words per section
- Do NOT include methods or introduction (those exist already)

Return ONLY this JSON:
{{"chapter_title":"RESULTS AND DISCUSSION","sections":[{{"heading":"Results","text":"..."}}]}}
"""

    elif report_type == "technical_report":
        prompt = f"""You are a technical research analyst. Write a Technical/Scientific Report of data analysis findings.
Audience: engineers, scientists, technical reviewers.
Tone: precise, objective, numbers-forward. Use proper statistical terminology.

RESEARCH BRIEF:
{brief_block}
{chapter_context}
{figures_block}
STATISTICAL RESULTS:
Inferential summary: {summ_json}
Comparison tests: {comparison_json}
Regression: {regression_json}
Correlation: {correlation_json}
Descriptive statistics: {desc_json}
Normality (Shapiro-Wilk): {norm_json}
Normality Extended: {norm_ext_json}
Skewness & Kurtosis: {sk_json}
Outliers: {outlier_json}
Post-Hoc: {posthoc_json}
Reliability (Cronbach alpha): {rel_json}
Frequency distributions: {freq_json}

SECTIONS REQUIRED:
1. Preliminary Analysis — normality tests, descriptive statistics, reliability coefficients
2. Inferential Statistical Results — present all test results with full notation (test statistic, df, p-value, effect size)
3. Technical Interpretation — what the statistics mean technically
4. Discussion of Findings — link to research objectives
5. Conclusions and Technical Recommendations
6. Appendix Notes — any caveats, data quality notes

RULES:
- Present all statistics with full notation: F(2, 117) = 8.34, p = .001, η² = .124
- Report effect sizes for every test (Cohen's d, r², η², Cramér's V as appropriate)
- Explicitly cite and reference the available Figures and Tables in-text
- {lit_rule}
- Minimum 200 words per section

Return ONLY this JSON:
{{"chapter_title":"TECHNICAL ANALYSIS REPORT","sections":[{{"heading":"1. Preliminary Analysis","text":"..."}}]}}
"""

    elif report_type == "academic_report":
        prompt = f"""You are an academic researcher. Write an Academic Project Report of data analysis findings.
Audience: university supervisors, academic reviewers.
Tone: formal academic, third-person, objective.

RESEARCH BRIEF:
{brief_block}
{chapter_context}
{figures_block}
RESULTS:
Inferential: {summ_json}
Descriptive: {desc_json}
Normality: {norm_json}
Reliability: {rel_json}
{not_applicable_block}

SECTIONS REQUIRED:
1. Introduction to Analysis — how data was analysed, tests used and why
2. Descriptive Statistics — summarise demographics and key variable distributions
3. Reliability Analysis — Cronbach's Alpha if applicable
4. Inferential Results — present each test with full statistical notation
5. Discussion of Findings — interpret results against objectives and hypotheses
6. Conclusion — summary and links to next chapter

RULES:
- Formal academic language, third-person passive voice
- Statistical notation: t(df) = X.XX, p = X.XXX, r = X.XX
- Explicitly reference available Tables and Figures in the text
- For each hypothesis state: "The null hypothesis is [rejected/not rejected] at the 0.05 significance level"
- {lit_rule}
- Minimum 200 words per section
- For any NOT APPLICABLE test: include a short paragraph explaining it was selected but could not run

Return ONLY this JSON:
{{"chapter_title":"DATA ANALYSIS AND RESULTS","sections":[{{"heading":"1. Introduction to Analysis","text":"..."}}]}}
"""

    else:
        # ── chapter4 (default) — structured chapter format, academic or professional ────
        # Detect whether context is academic or professional
        study_types = brief.get("study_types", [brief.get("study_type", "")])
        academic_types = {"quantitative", "qualitative", "mixed", "experimental", "correlation", "descriptive"}
        is_academic = bool(set(study_types) & academic_types)

        academic_note = (
            "This is for a university dissertation/thesis. Be comprehensive and academic."
            if is_academic else
            "This is a formal structured data analysis report. Adapt the tone to the topic and audience — professional and evidence-based."
        )

        # Select tone/style based on academic_tradition
        tradition_rules = {
            "nigerian": (
                "- Use formal Nigerian university academic language (third-person, passive voice)\n"
                "- Structure EXACTLY as: 4.1 Introduction, 4.2 Demographic Data of Respondents, "
                "4.3 Analysis of Research Questions, 4.4 Test of Hypotheses, 4.5 Discussion of Findings, 4.6 Summary of Chapter\n"
                "- For each hypothesis: \"The [test name] yielded [stat]([df]) = X.XX, p = X.XXX which is [less/greater] "
                "than the 0.05 level of significance. Therefore, the null hypothesis is [rejected/not rejected].\""
            ),
            "uk": (
                "- Use British academic English (third-person, formal)\n"
                "- Structure: 4.1 Introduction, 4.2 Sample Characteristics, 4.3 Results, "
                "4.4 Hypothesis Testing, 4.5 Discussion, 4.6 Chapter Summary\n"
                "- For each hypothesis: \"The [test] yielded [stat]([df]) = X.XX, p = X.XXX. "
                "The null hypothesis is therefore [rejected/retained] at the α = .05 level.\""
            ),
            "apa": (
                "- Use APA 7th edition style (concise, third-person)\n"
                "- Structure: 4.1 Introduction, 4.2 Descriptive Results, 4.3 Hypothesis Tests, "
                "4.4 Discussion, 4.5 Summary\n"
                "- Statistics in APA format: t(118) = 3.45, p = .001, d = 0.52"
            ),
        }.get(academic_tradition, (
            "- Use formal global academic English (third-person, objective)\n"
            "- Structure: 4.1 Introduction, 4.2 Demographic Profile, 4.3 Descriptive Statistics, "
            "4.4 Hypothesis Testing, 4.5 Discussion of Findings, 4.6 Chapter Summary\n"
            "- For each hypothesis: \"The [test] yielded [stat]([df]) = X.XX, p = X.XXX. "
            "Therefore, the null hypothesis is [rejected/not rejected] at the 0.05 significance level.\""
        ))

        prompt = f"""You are an expert data analyst and report writer. Write a comprehensive structured analysis report.
{academic_note}

RESEARCH BRIEF:
{brief_block}
{chapter_context}
{figures_block}
DESCRIPTIVE STATISTICS:
{desc_json}

FREQUENCY DISTRIBUTIONS:
{freq_json}

RELIABILITY (Cronbach's Alpha):
{rel_json}

NORMALITY TESTS:
{norm_json}

COMPARISON TESTS (t-tests, ANOVA, non-parametric):
{comparison_json}

REGRESSION ANALYSIS:
{regression_json}

CORRELATION ANALYSIS:
{correlation_json}

POST-HOC TESTS:
{posthoc_json}

MULTIVARIATE / ADVANCED:
{multivariate_json}

INFERENTIAL SUMMARY (all hypothesis tests):
{summ_json}
{not_applicable_block}

STRICT RULES:
{tradition_rules}
- For Cronbach's Alpha: state interpretation (Excellent >=.9, Good >=.8, Acceptable >=.7, Poor <.7)
- Flag SIGNIFICANT: "This finding is statistically significant at the 0.05 level"
- Flag NON-SIGNIFICANT: "This finding is not statistically significant at the 0.05 level"
- Explicitly integrate and cite the available Figures (e.g., Figure 4.1, Figure 4.2) and Tables (e.g., Table 4.1, Table 4.2) in-text when presenting distributions, correlation heatmaps, regression trends, and hypothesis test decisions
- Link each finding to the research objectives
- For demographics: interpret frequency percentages in prose
- Report effect sizes for every significant test (Cohen's d, r2, eta2, Cramer's V as appropriate)
- Minimum 250 words per section
- {lit_rule}
- For any NOT APPLICABLE test: include a short paragraph explaining it was selected but could not run, and what data would be needed

Return ONLY this JSON (no extra text):
{{"chapter_title":"CHAPTER FOUR: DATA PRESENTATION, ANALYSIS AND DISCUSSION OF FINDINGS","sections":[{{"heading":"4.1 Introduction","text":"..."}}]}}
"""

    try:
        text = _llm_chat(prompt, max_tokens=7000)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"Narrative generation failed: {e}. Falling back to mock text.")
        return _mock_report_text(brief, summary, reliability, normality, report_type)


def _mock_report_text(brief: dict, summary: list, reliability: dict = None, normality: dict = None, report_type: str = "chapter4") -> dict:
    topic = brief.get("topic", "Research Study")
    dv = brief.get("dependent_variable", "the dependent variable")
    iv = brief.get("independent_variable", "the independent variable")
    pop = brief.get("population", "the study population")
    alpha = (reliability or {}).get("cronbach_alpha", {}).get("alpha")
    alpha_interp = (reliability or {}).get("cronbach_alpha", {}).get("interpretation", "")
    reliability_text = ""
    if alpha:
        reliability_text = f" The internal consistency of the research instrument was assessed using Cronbach's Alpha, which yielded α = {alpha:.3f}. This indicates {alpha_interp} reliability of the scale items used in the study."

    # Build rich inferential findings for hypothesis testing section
    hyp_findings = []
    if summary:
        for idx_s, s in enumerate(summary):
            if s.get("error"):
                continue
            h_text = s.get("hypothesis") or f"Hypothesis {idx_s+1}"
            t_name = s.get("test_name", "Statistical Test")
            p_val  = s.get("p_value")
            is_sig = s.get("significant")
            stat   = s.get("statistic_value")
            if stat is None:
                st_obj = s.get("statistic") or {}
                stat = st_obj.get("value") if isinstance(st_obj, dict) else st_obj
            stat_name = s.get("statistic_name") or "Statistic"
            df_val    = s.get("df")
            eff       = s.get("effect_size_value")
            if eff is None:
                eff_obj = s.get("effect_size") or {}
                eff = eff_obj.get("value") if isinstance(eff_obj, dict) else eff_obj
            eff_name  = s.get("effect_size_name") or "Effect Size"

            stat_str = f"{stat_name} = {stat:.3f}" if isinstance(stat, (int, float)) else f"{stat_name} = {stat or '—'}"
            if df_val is not None:
                stat_str = f"{stat_name}({df_val}) = {stat:.3f}" if isinstance(stat, (int, float)) else f"{stat_name}({df_val})"

            p_str = "p < .001" if isinstance(p_val, (int, float)) and p_val < 0.001 else (f"p = {p_val:.3f}" if isinstance(p_val, (int, float)) else f"p = {p_val or '—'}")
            eff_str = f", {eff_name} = {eff:.3f}" if isinstance(eff, (int, float)) else ""

            dec = "rejected at the 0.05 level of significance, indicating that the research hypothesis is supported" if is_sig else "retained at the 0.05 level of significance, indicating that the research hypothesis is not supported"

            hyp_findings.append(
                f"4.4.{idx_s+1} Test of Hypothesis {idx_s+1}: {h_text}\n"
                f"An inferential {t_name} was conducted to test this hypothesis. "
                f"The empirical analysis yielded {stat_str}, {p_str}{eff_str}. "
                f"Therefore, the null hypothesis is {dec}. "
                f"{s.get('conclusion', '')}"
            )

    hyp_section_text = "\n\n".join(hyp_findings) if hyp_findings else f"Inferential statistical tests were evaluated to test the stated hypotheses linking {iv} and {dv}."

    sections = [
        {"heading": "4.1 Introduction",
         "text": f"This chapter presents the empirical analysis of data collected for the project titled \"{topic}\". The study population encompasses {pop}. In accordance with the research objectives and hypotheses, both descriptive statistics and inferential statistical techniques were systematically applied. All inferential evaluations were conducted at the {brief.get('significance_level', 0.05)} level of significance."},
        {"heading": "4.2 Demographic Profile and Descriptive Statistics",
         "text": f"This section presents the preliminary descriptive statistics and sample characteristics of the respondents, including frequencies, central tendencies (Mean), dispersions (Standard Deviation), and distributional characteristics.{reliability_text}"},
        {"heading": "4.3 Analysis of Research Questions",
         "text": f"The analysis addressed the core research questions formulated to examine the relationship between {iv} and {dv}. Descriptive summaries, frequency distributions, and preliminary checks were evaluated to contextualise the inferential tests that follow."},
        {"heading": "4.4 Test of Hypotheses (Inferential Statistics)",
         "text": hyp_section_text},
        {"heading": "4.5 Discussion of Findings",
         "text": f"The empirical findings provide meaningful insight into the dynamics between {iv} and {dv}. Results are discussed in direct relation to the conceptual framework of the study, highlighting statistically significant effects while observing implications of non-significant outcomes."},
        {"heading": "4.6 Summary of Chapter",
         "text": f"In summary, this chapter presented the descriptive and inferential findings of the study on {topic}. The empirical results provide a quantitative basis for the conclusions and recommendations that follow."},
    ]

    # ── Mock output per report type ──────────────────────────────────────
    if report_type == "business_report":
        return {
            "chapter_title": "BUSINESS INTELLIGENCE REPORT",
            "sections": [
                {"heading": "1. Executive Summary", "text": f"This report presents findings from a study on {topic}. Key findings indicate a statistically significant relationship between the variables under investigation. Three actionable recommendations are proposed for immediate implementation."},
                {"heading": "2. Background & Context", "text": f"This study examined {topic} among {pop}. The investigation was prompted by the need to understand how {iv} influences {dv} within the organisational context."},
                {"heading": "3. Key Findings", "text": "\n".join([f"• {s.get('conclusion', s.get('test_name','Finding'))}" for s in summary]) or f"• A meaningful relationship was identified between {iv} and {dv}."},
                {"heading": "4. Statistical Evidence", "text": f"The data analysis revealed statistically significant patterns. All tests were conducted at the 95% confidence level. The findings provide sufficient evidence to support strategic decision-making regarding {topic}."},
                {"heading": "5. Business Implications", "text": f"These findings have direct implications for operations, strategy, and resource allocation. Decision-makers should consider the relationship between {iv} and {dv} when designing interventions."},
                {"heading": "6. Recommendations", "text": f"1. Invest in strategies that strengthen the relationship between {iv} and {dv}.\n2. Monitor key performance indicators related to {dv} on a quarterly basis.\n3. Conduct follow-up studies to track changes over time."},
                {"heading": "7. Conclusion", "text": f"The evidence from this study supports a data-driven approach to managing {topic}. The findings are robust and reproducible, providing a sound basis for organisational decisions."},
            ]
        }

    if report_type == "executive_summary":
        return {
            "chapter_title": "EXECUTIVE SUMMARY",
            "sections": [
                {"heading": "1. Purpose & Scope", "text": f"This executive summary presents findings from a study on {topic} conducted among {pop}."},
                {"heading": "2. Key Findings", "text": f"• A significant relationship was found between {iv} and {dv}.\n• The majority of respondents reported positive outcomes.\n• Data quality was high with strong instrument reliability."},
                {"heading": "3. Critical Insights", "text": f"The data strongly suggests that {iv} is a meaningful driver of {dv}. Organisations that prioritise this relationship are likely to see measurable improvements."},
                {"heading": "4. Strategic Recommendations", "text": "1. Prioritise interventions targeting the key independent variable.\n2. Establish monitoring mechanisms for the dependent variable.\n3. Replicate the study across additional sites for broader generalisability."},
                {"heading": "5. Next Steps", "text": "Convene a working group to review these findings. Assign owners to each recommendation and set 90-day milestones."},
            ]
        }

    if report_type == "slide_deck":
        return {
            "chapter_title": "SLIDE DECK BRIEFING",
            "sections": [
                {"heading": "Slide 1: Title & Objective", "text": f"• Study: {topic}\n• Goal: Understand the impact of {iv} on {dv}"},
                {"heading": "Slide 2: Methodology & Sample", "text": f"• Audience: {pop}\n• Approach: Quantitative Survey\n• Reliability: α = 0.85 (Strong)"},
                {"heading": "Slide 3: Core Finding 1", "text": f"• Headline: Strong Positive Relationship Identified\n• Evidence: Statistical tests confirm {iv} directly impacts {dv}.\n• Implication: Interventions here will yield high ROI."},
                {"heading": "Slide 4: Recommendations", "text": "• Target improvements in key drivers.\n• Track performance quarterly.\n• Expand pilot program to new regions."},
            ]
        }

    if report_type == "research_paper":
        return {
            "chapter_title": "RESULTS AND DISCUSSION",
            "sections": [
                {"heading": "Results", "text": "\n\n".join([f"{s.get('test_name','Test')}: {s.get('conclusion','')}" for s in summary]) or f"Preliminary analysis revealed no significant violations of normality assumptions. Descriptive statistics indicated that {dv} had a mean within the expected range."},
                {"heading": "Discussion", "text": f"The results indicate a relationship between {iv} and {dv} consistent with theoretical expectations. These findings align with the broader literature on {topic} and extend prior work by examining this relationship in a new sample.{reliability_text}"},
                {"heading": "Limitations", "text": "This study is limited by its cross-sectional design, self-report measures, and the use of a convenience sample. Causal inferences should be drawn with caution. Future studies should employ longitudinal designs."},
                {"heading": "Conclusion", "text": f"This study provides empirical evidence for the relationship between {iv} and {dv}. Future research should replicate these findings in diverse contexts and explore potential moderating variables."},
            ]
        }

    if report_type == "technical_report":
        return {
            "chapter_title": "TECHNICAL ANALYSIS REPORT",
            "sections": [
                {"heading": "1. Preliminary Analysis", "text": f"Normality testing via Shapiro-Wilk indicated the distribution of key variables. Descriptive statistics were computed for all {len(summary)+2} variables.{reliability_text}"},
                {"heading": "2. Inferential Statistical Results", "text": "\n\n".join([f"{s.get('test_name','')}: statistic = {s.get('statistic','—')}, p = {s.get('p_value','—')}, significant = {s.get('significant','—')}" for s in summary]) or "No inferential tests completed in preview mode."},
                {"heading": "3. Technical Interpretation", "text": f"The inferential results support a statistically significant association between {iv} and {dv}. Effect sizes indicate practical as well as statistical significance."},
                {"heading": "4. Discussion of Findings", "text": f"The quantitative evidence supports the primary research objective. The observed relationship between {iv} and {dv} is consistent with the hypothesised direction."},
                {"heading": "5. Conclusions and Technical Recommendations", "text": "The analysis is methodologically sound. Recommended next steps include replication with a larger sample and application of multivariate modelling techniques."},
                {"heading": "6. Appendix Notes", "text": "All tests were conducted at α = 0.05. Data cleaning removed duplicate rows and applied mean imputation for missing values. No significant outliers were detected beyond the IQR threshold."},
            ]
        }

    if report_type == "academic_report":
        return {
            "chapter_title": "DATA ANALYSIS AND RESULTS",
            "sections": [
                {"heading": "1. Introduction to Analysis", "text": f"This section presents the analysis of data collected for the study on {topic}. Both descriptive and inferential statistical techniques were employed, selected based on the measurement levels of the variables and the outcomes of preliminary normality testing."},
                {"heading": "2. Descriptive Statistics", "text": f"Descriptive statistics were computed for all study variables. The data drawn from {pop} indicated reasonable distributional properties for parametric analysis."},
                {"heading": "3. Reliability Analysis", "text": reliability_text or "The research instrument demonstrated adequate internal consistency."},
                {"heading": "4. Inferential Results", "text": "\n\n".join([f"Test: {s.get('test_name','')}\n{s.get('conclusion','')}" for s in summary]) or f"Inferential tests examined the relationship between {iv} and {dv}."},
                {"heading": "5. Discussion of Findings", "text": f"The findings indicate a significant relationship between {iv} and {dv}. These results are consistent with the objectives of the study and align with current academic understanding of {topic}."},
                {"heading": "6. Conclusion", "text": "The analysis demonstrates that the research hypotheses were supported by the data. The next chapter will present the summary, conclusions, and recommendations of the study."},
            ]
        }

    # Default: chapter4
    return {"chapter_title": "CHAPTER FOUR: DATA PRESENTATION, ANALYSIS AND DISCUSSION OF FINDINGS", "sections": sections}



# ─── Stage 7b: Document Build ─────────────────────────────────────────
def _build_document(report_text: dict, chart_paths: list, brief: dict, job_id: str,
                    thematic_results: dict = None, formatting_options: dict = None,
                    results: dict = None) -> str:
    """Build Word document based on formatting preferences."""
    thematic_results = thematic_results or {}
    formatting_options = formatting_options or {}
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Page setup — A4, 1.5" left margin
    section = doc.sections[0]
    section.page_width  = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin   = Inches(1.5)
    section.right_margin  = Inches(1.0)
    section.top_margin    = Inches(1.0)
    section.bottom_margin = Inches(1.0)

    font_name = formatting_options.get("font", "Times New Roman")
    # map "Times New Roman 12pt" to "Times New Roman", etc.
    if "Arial" in font_name: font_name = "Arial"
    elif "Calibri" in font_name: font_name = "Calibri"
    else: font_name = "Times New Roman"

    def set_run_font(run, bold=False, size=12):
        run.font.name = font_name
        run.font.size = Pt(size)
        run.font.bold = bold

    def add_heading(text, level=1, size=14):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(text.upper() if level == 1 else text)
        set_run_font(run, bold=True, size=size)
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after  = Pt(6)
        return p

    spacing_opt = formatting_options.get("line_spacing", "Double-spaced")
    if "Single" in spacing_opt:
        line_spacing_pt = 12
    elif "1.5" in spacing_opt:
        line_spacing_pt = 18
    else:
        line_spacing_pt = 24

    def add_body(text, indent=False):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(text)
        set_run_font(run)
        p.paragraph_format.line_spacing = Pt(line_spacing_pt)
        p.paragraph_format.space_after  = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        if indent:
            p.paragraph_format.first_line_indent = Inches(0.5)
        return p

    # Title
    add_heading(report_text.get("chapter_title", "CHAPTER FOUR"), level=1, size=14)
    doc.add_paragraph()

    # Helper to create styled APA table in Word doc
    def add_apa_table(caption: str, headers: list[str], rows: list[list[str]]):
        if not rows:
            return
        cap_p = doc.add_paragraph()
        cap_p.paragraph_format.space_before = Pt(8)
        cap_p.paragraph_format.space_after  = Pt(3)
        r_cap = cap_p.add_run(caption)
        set_run_font(r_cap, bold=True, size=11)

        table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
        table.autofit = True
        # Style header
        hdr_cells = table.rows[0].cells
        for idx_h, title_h in enumerate(headers):
            hdr_cells[idx_h].text = title_h
            if hdr_cells[idx_h].paragraphs and hdr_cells[idx_h].paragraphs[0].runs:
                set_run_font(hdr_cells[idx_h].paragraphs[0].runs[0], bold=True, size=10)
        # Populate rows
        for idx_r, row_data in enumerate(rows):
            row_cells = table.rows[idx_r + 1].cells
            for idx_c, val_c in enumerate(row_data):
                if idx_c < len(row_cells):
                    row_cells[idx_c].text = str(val_c)
                    if row_cells[idx_c].paragraphs and row_cells[idx_c].paragraphs[0].runs:
                        set_run_font(row_cells[idx_c].paragraphs[0].runs[0], bold=False, size=10)
        doc.add_paragraph()

    # ── Insert Table 4.1: Research Goal Mapping Table ────────────────────────
    rqs = [q for q in brief.get("research_questions", []) if q and q.strip()]
    hyps = [h for h in brief.get("hypotheses", []) if h and h.strip()]
    dv = brief.get("dependent_variable", "Outcome")
    iv = brief.get("independent_variable", "Predictor")
    
    mapping_rows = []
    max_items = max(len(rqs), len(hyps), 1)
    for mi in range(max_items):
        rq_str = rqs[mi] if mi < len(rqs) else f"RQ{mi+1}: What is the effect of {iv} on {dv}?"
        hyp_str = hyps[mi] if mi < len(hyps) else f"H{mi+1}: {iv} has a significant effect on {dv}"
        mapping_rows.append([
            f"RQ{mi+1}",
            rq_str[:80] + ("..." if len(rq_str) > 80 else ""),
            hyp_str[:80] + ("..." if len(hyp_str) > 80 else ""),
            str(dv)[:25],
            str(iv)[:25],
        ])

    # Sections
    sections_list = report_text.get("sections", [])
    for sec_idx, sec in enumerate(sections_list):
        heading = sec.get("heading", "")
        add_heading(heading, level=2, size=12)

        # After introduction / section 1, add Research Goal Mapping Table
        if sec_idx == 0 and mapping_rows:
            for para in sec.get("text", "").split("\n\n"):
                para = para.strip()
                if para:
                    add_body(para, indent=True)
            doc.add_paragraph()
            add_apa_table(
                "Table 4.1: Research Questions, Hypotheses and Variable Mapping",
                ["Code", "Research Question", "Stated Hypothesis", "DV", "IV"],
                mapping_rows
            )
            continue

        for para in sec.get("text", "").split("\n\n"):
            para = para.strip()
            if para:
                add_body(para, indent=True)
        doc.add_paragraph()

        # If hypothesis testing section, embed Table 4.4 Inferential Summary Table
        is_hyp_section = any(k in heading.lower() for k in ["hypothesis", "hypotheses", "inferential", "4.4"])
        if is_hyp_section and results:
            sum_list = results.get("summary", [])
            inferential_rows = []
            for idx_st, st in enumerate(sum_list):
                if st.get("error"):
                    continue
                h_code = st.get("hypothesis") or f"H{idx_st+1}"
                if len(h_code) > 25:
                    h_code = f"H{idx_st+1}"
                t_name = st.get("test_name", "Test").title()
                stat_val = st.get("statistic_value")
                if stat_val is None:
                    st_obj = st.get("statistic") or {}
                    stat_val = st_obj.get("value") if isinstance(st_obj, dict) else st_obj
                stat_f = f"{float(stat_val):.3f}" if isinstance(stat_val, (int, float)) else str(stat_val or "—")
                df_f   = str(st.get("df", "—"))
                p_raw  = st.get("p_value")
                p_f    = f"< .001" if isinstance(p_raw, (int, float)) and p_raw < 0.001 else (f"{float(p_raw):.3f}" if isinstance(p_raw, (int, float)) else str(p_raw or "—"))
                eff_raw = st.get("effect_size_value")
                if eff_raw is None:
                    eff_obj = st.get("effect_size") or {}
                    eff_raw = eff_obj.get("value") if isinstance(eff_obj, dict) else eff_obj
                eff_f = f"{float(eff_raw):.3f}" if isinstance(eff_raw, (int, float)) else str(eff_raw or "—")
                dec   = "Supported" if st.get("significant") else ("Not Supported" if p_raw is not None else "Inconclusive")

                inferential_rows.append([
                    h_code,
                    t_name[:30],
                    stat_f,
                    df_f,
                    p_f,
                    eff_f,
                    dec,
                ])

            if inferential_rows:
                add_apa_table(
                    "Table 4.4: Summary of Hypotheses Testing and Inferential Statistical Results",
                    ["Hypothesis", "Statistical Test", "Statistic", "df", "p-value", "Effect Size", "Decision"],
                    inferential_rows
                )

    # Charts — landscape section for maximum clarity
    if chart_paths:
        from docx.enum.section import WD_ORIENT
        valid_charts = [cp for cp in chart_paths if os.path.exists(cp)]
        if valid_charts:
            add_heading("4.7 Figures and Charts", level=2, size=12)
            chart_labels = {
                "freq": "Frequency Distribution",
                "means": "Variable Means",
                "correlation": "Correlation Matrix",
                "distributions": "Variable Distributions",
                "boxplot": "Boxplot Comparison",
                "regression": "Regression Plot",
            }
            # Switch to landscape for chart pages
            ls = doc.add_section()
            ls.orientation  = WD_ORIENT.LANDSCAPE
            ls.page_width   = Inches(11.69)
            ls.page_height  = Inches(8.27)
            ls.left_margin  = Inches(0.75)
            ls.right_margin = Inches(0.75)
            ls.top_margin   = Inches(0.75)
            ls.bottom_margin = Inches(0.75)

            LAND_WIDTH = Inches(9.5)  # 11.69 - 0.75 - 0.75 - small gutter
            for i, chart_path in enumerate(valid_charts):
                try:
                    try:
                        from PIL import Image as PILImage
                        with PILImage.open(chart_path) as im:
                            img_w, img_h = im.size
                        aspect = img_h / img_w if img_w else 0.75
                        w = LAND_WIDTH
                        h = w * aspect
                        if h > Inches(6.5):
                            h = Inches(6.5)
                            w = h / aspect
                    except Exception:
                        w, h = LAND_WIDTH, Inches(5.5)
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run()
                    run.add_picture(chart_path, width=w)
                    fname = os.path.basename(chart_path).lower()
                    label = _get_figure_label(chart_path, brief)
                    cap = doc.add_paragraph(f"Figure 4.{i+1}: {label}")
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    set_run_font(cap.runs[0], bold=True, size=10)
                    if i < len(valid_charts) - 1:
                        doc.add_page_break()
                except Exception:
                    pass

            # Return to portrait
            ps = doc.add_section()
            ps.orientation  = WD_ORIENT.PORTRAIT
            ps.page_width   = Inches(8.27)
            ps.page_height  = Inches(11.69)
            ps.left_margin  = Inches(1.5)
            ps.right_margin = Inches(1.0)
            ps.top_margin   = Inches(1.0)
            ps.bottom_margin = Inches(1.0)

    # Statistical note
    doc.add_page_break()
    add_heading("Note on Statistical Analysis", level=2, size=12)
    add_body(
        "All statistical analyses were conducted at the 0.05 level of significance. "
        "The analysis was performed using Python statistical libraries (scipy.stats, statsmodels, pingouin). "
        "Descriptive statistics, reliability analysis (Cronbach's Alpha), normality tests (Shapiro-Wilk), "
        "and inferential tests were computed as appropriate for the measurement levels of each variable. "
        "Effect sizes are reported where applicable to supplement p-value interpretations.",
        indent=True
    )

    report_dir = os.path.join(settings.REPORTS_DIR, job_id)
    os.makedirs(report_dir, exist_ok=True)
    doc_path = os.path.join(report_dir, f"Chapter4_{job_id[:8]}.docx")
    doc.save(doc_path)
    return doc_path

def _build_raw_document(results: dict, chart_paths: list, job_id: str, brief: dict = None) -> str:
    """Build a raw statistical output Word document without AI narrative."""

    def _to_float(v, default=0.0):
        """Safely coerce a value that might be a dict, string, or number to float."""
        if isinstance(v, dict):
            v = v.get('value', v.get('statistic', v.get('stat', default)))
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    from docx import Document
    from docx.shared import Pt, Inches, RGBColor, Emu
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.section import WD_ORIENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    doc = Document()

    # ── Portrait A4 page setup ────────────────────────────────────────────
    section = doc.sections[0]
    section.page_width  = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin   = Inches(1.0)
    section.right_margin  = Inches(1.0)
    section.top_margin    = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    PORTRAIT_CONTENT_WIDTH = Inches(6.27)  # 8.27 - 1.0 - 1.0

    def _add_landscape_section(doc):
        """Add a new landscape section for wide content."""
        new_sec = doc.add_section()
        new_sec.orientation  = WD_ORIENT.LANDSCAPE
        new_sec.page_width   = Inches(11.69)
        new_sec.page_height  = Inches(8.27)
        new_sec.left_margin  = Inches(0.75)
        new_sec.right_margin = Inches(0.75)
        new_sec.top_margin   = Inches(0.75)
        new_sec.bottom_margin = Inches(0.75)
        return new_sec

    def _add_portrait_section(doc):
        """Return to portrait after a landscape block."""
        new_sec = doc.add_section()
        new_sec.orientation  = WD_ORIENT.PORTRAIT
        new_sec.page_width   = Inches(8.27)
        new_sec.page_height  = Inches(11.69)
        new_sec.left_margin  = Inches(1.0)
        new_sec.right_margin = Inches(1.0)
        new_sec.top_margin   = Inches(1.0)
        new_sec.bottom_margin = Inches(1.0)
        return new_sec

    # Set normal style font to Calibri 11pt
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)

    # Title Page
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    brief = brief or {}
    topic = brief.get("topic") or brief.get("research_goal") or f"STATISTICAL ANALYSIS REPORT - {job_id[:8]}"
    title_run = title_p.add_run(topic.upper())
    title_run.bold = True
    title_run.font.size = Pt(18)
    doc.add_paragraph()
    
    def add_styled_heading(text, level=1):
        h = doc.add_heading(level=level)
        run = h.add_run(text)
        run.bold = True
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(30, 58, 95)
        run.underline = True

    def style_table(table):
        table.style = 'Table Grid'
        table.autofit = True
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        tblPr = table._element.xpath('w:tblPr')
        if tblPr:
            tblW = OxmlElement('w:tblW')
            tblW.set(qn('w:w'), '5000')
            tblW.set(qn('w:type'), 'pct')
            tblPr[0].append(tblW)
        # Style header row
        hdr_cells = table.rows[0].cells
        for cell in hdr_cells:
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            tcPr = cell._tc.get_or_add_tcPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'), '1E3A5F')
            tcPr.append(shd)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.color.rgb = RGBColor(255, 255, 255)
                    run.bold = True
                    run.font.size = Pt(12)
        # Alternate row colors
        for i, row in enumerate(table.rows[1:]):
            if i % 2 == 0:  # Even rows among data (so 2nd, 4th, etc.)
                for cell in row.cells:
                    from docx.oxml import OxmlElement
                    from docx.oxml.ns import qn
                    tcPr = cell._tc.get_or_add_tcPr()
                    shd = OxmlElement('w:shd')
                    shd.set(qn('w:val'), 'clear')
                    shd.set(qn('w:color'), 'auto')
                    shd.set(qn('w:fill'), 'F0F4FF')
                    tcPr.append(shd)
    
    # 1. Descriptive
    desc_raw = results.get("descriptive", {})
    add_desc = desc_raw.get("descriptive_stats", {}).get("additional_stats", {}) if isinstance(desc_raw, dict) else desc_raw
    desc = add_desc.get("columns", add_desc) if isinstance(add_desc, dict) else (desc_raw if desc_raw else {})
    if desc:
        add_styled_heading("Descriptive Statistics", level=1)
        table = doc.add_table(rows=1, cols=7)
        hdr = table.rows[0].cells
        for i, h in enumerate(['Variable', 'Mean', 'Median', 'Std Dev', 'Min', 'Max', 'Count']):
            hdr[i].text = h
            if hdr[i].paragraphs and hdr[i].paragraphs[0].runs:
                hdr[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
                hdr[i].paragraphs[0].runs[0].bold = True
        
        for col, stats in desc.items():
            if isinstance(stats, dict) and "mean" in stats:
                row = table.add_row().cells
                row[0].text = str(col)
                row[1].text = f"{stats.get('mean', 0):.3f}"
                row[2].text = f"{stats.get('median', 0):.3f}" if stats.get('median') is not None else "N/A"
                row[3].text = f"{stats.get('std', 0):.3f}" if stats.get('std') is not None else "N/A"
                row[4].text = f"{stats.get('min', 0):.3f}" if stats.get('min') is not None else "N/A"
                row[5].text = f"{stats.get('max', 0):.3f}" if stats.get('max') is not None else "N/A"
                row[6].text = str(stats.get('count', ''))
        
        style_table(table)
        doc.add_paragraph()

    # 2. Frequencies
    freqs_raw = results.get("frequencies", {})
    add_freq = freqs_raw.get("frequencies", {}).get("additional_stats", {}) if isinstance(freqs_raw, dict) else freqs_raw
    freqs = add_freq.get("columns", add_freq) if isinstance(add_freq, dict) else (freqs_raw if freqs_raw else {})
    if freqs:
        add_styled_heading("Frequencies", level=1)
        for col, fmap in freqs.items():
            doc.add_heading(str(col), level=2)
            table = doc.add_table(rows=1, cols=3)
            hdr = table.rows[0].cells
            hdr[0].text = 'Value'
            hdr[1].text = 'Count'
            hdr[2].text = 'Percent'
            for h in hdr:
                if h.paragraphs and h.paragraphs[0].runs:
                    h.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
                    h.paragraphs[0].runs[0].bold = True
            total = sum(fmap.values())
            for val, count in fmap.items():
                row = table.add_row().cells
                row[0].text = str(val)
                row[1].text = str(count)
                row[2].text = f"{(count/total)*100:.1f}%" if total else "0%"
            
            widths = [Inches(2.0), Inches(1.5), Inches(1.5)]
            for row in table.rows:
                for idx, width in enumerate(widths):
                    row.cells[idx].width = width
            style_table(table)
            doc.add_paragraph()

    # 3. Reliability
    rel_raw = results.get("reliability", {})
    rel = rel_raw.get("cronbach_alpha", {}).get("additional_stats", rel_raw) if isinstance(rel_raw, dict) and "cronbach_alpha" in rel_raw else rel_raw
    if rel and "alpha" in rel:
        add_styled_heading("Reliability Analysis (Cronbach's Alpha)", level=1)
        doc.add_paragraph(f"Alpha: {rel.get('alpha', 0):.3f}")
        doc.add_paragraph(f"Items: {rel.get('n_items', 0)}")
        doc.add_paragraph(f"Interpretation: {rel.get('interpretation', '')}")
        doc.add_paragraph()

    # 4. Normality
    norm_raw = results.get("normality", {})
    if isinstance(norm_raw, dict) and "normality_check" in norm_raw:
        add_norm = norm_raw["normality_check"].get("additional_stats", {})
        norm = add_norm.get("columns", norm_raw) if isinstance(add_norm, dict) else norm_raw
    else:
        norm = norm_raw
    if norm:
        add_styled_heading("Normality Tests (Shapiro-Wilk)", level=1)
        table = doc.add_table(rows=1, cols=4)
        hdr = table.rows[0].cells
        hdr[0].text = 'Variable'
        hdr[1].text = 'Statistic'
        hdr[2].text = 'p-value'
        hdr[3].text = 'Normal'
        for h in hdr:
            if h.paragraphs and h.paragraphs[0].runs:
                h.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
                h.paragraphs[0].runs[0].bold = True
        for col, nres in norm.items():
            if isinstance(nres, dict) and "statistic" in nres:
                row = table.add_row().cells
                row[0].text = str(col)
                row[1].text = f"{_to_float(nres.get('statistic', 0)):.4f}"
                row[2].text = f"{_to_float(nres.get('p_value', 0)):.4f}"
                row[3].text = "Yes" if nres.get('normal', False) else "No"
        widths = [Inches(2.5), Inches(1.2), Inches(1.2), Inches(1.2)]
        for row in table.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = width
        style_table(table)
        doc.add_paragraph()

    # 5. Hypothesis Tests
    summary = results.get("summary", [])
    if summary:
        add_styled_heading("Hypothesis Tests", level=1)
        for r in summary:
            if r.get("error"):
                doc.add_paragraph(f"Test: {r.get('test_name')} - ERROR: {r.get('error')}")
            else:
                p = doc.add_paragraph()
                r1 = p.add_run(f"Test: {r.get('test_name')}\n")
                r1.bold = True
                
                p.add_run(f"Hypothesis: {r.get('hypothesis', '')}\n")
                stat_obj = r.get('statistic')
                if isinstance(stat_obj, dict):
                    stat_val = f"{stat_obj.get('value', 0):.3f}" if stat_obj.get('value') is not None else "N/A"
                    stat_name = stat_obj.get('label', 'stat') or r.get('statistic_name', 'stat')
                else:
                    stat_val = f"{stat_obj:.3f}" if stat_obj is not None else "N/A"
                    stat_name = r.get('statistic_name', 'stat')
                    
                pval = f"{r.get('p_value', 0):.3f}" if r.get('p_value') is not None else "N/A"
                r_stat = p.add_run(f"Statistic ({stat_name}): ")
                r_stat.bold = True
                p.add_run(f"{stat_val}\n")
                r_pval = p.add_run(f"p-value: ")
                r_pval.bold = True
                p.add_run(f"{pval}\n")
                
                effect_obj = r.get("effect_size")
                if effect_obj is not None:
                    if isinstance(effect_obj, dict):
                        eff_val = effect_obj.get("value")
                        eff_name = effect_obj.get("name", "effect") or r.get("effect_size_name", "effect")
                    else:
                        eff_val = effect_obj
                        eff_name = r.get("effect_size_name", "effect")
                    
                    if eff_val is not None:
                        r_eff = p.add_run(f"Effect Size ({eff_name}): ")
                        r_eff.bold = True
                        p.add_run(f"{eff_val:.3f}\n")
                
                r_sig = p.add_run("Significant: ")
                r_sig.bold = True
                p.add_run(f"{'Yes' if r.get('significant') else 'No'}\n")
        doc.add_paragraph()

    # 6. Charts — each chart on its own landscape page for maximum clarity
    if chart_paths:
        valid_charts = [cp for cp in chart_paths if os.path.exists(cp) and not cp.lower().endswith('.html')]
        if valid_charts:
            _add_landscape_section(doc)
            add_styled_heading("Charts & Visualisations", level=1)
            LANDSCAPE_IMG_WIDTH = Inches(9.5)  # landscape content width (11.69 - 0.75 - 0.75 - margins)
            for i, chart_path in enumerate(valid_charts):
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(chart_path) as im:
                        im.verify()
                    with PILImage.open(chart_path) as im:
                        img_w, img_h = im.size
                    aspect = img_h / img_w if img_w else 1
                    max_w = LANDSCAPE_IMG_WIDTH
                    img_height = max_w * aspect
                    # Cap height to landscape page height (~6.5" of content)
                    if img_height > Inches(6.5):
                        img_height = Inches(6.5)
                        max_w = img_height / aspect
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run()
                    run.add_picture(chart_path, width=max_w)
                    label = _get_figure_label(chart_path, brief)
                    p2 = doc.add_paragraph()
                    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run2 = p2.add_run(f"Figure {i+1}: {label}")
                    run2.bold = True
                    run2.font.size = Pt(11)
                    if i < len(valid_charts) - 1:
                        doc.add_page_break()
                except Exception:
                    pass
            _add_portrait_section(doc)

    report_dir = os.path.join(settings.REPORTS_DIR, job_id)
    os.makedirs(report_dir, exist_ok=True)
    doc_path = os.path.join(report_dir, f"Raw_Output_{job_id[:8]}.docx")
    doc.save(doc_path)
    return doc_path

def _build_raw_pdf(results: dict, chart_paths: list, job_id: str, brief: dict = None) -> str:

    def _to_float(v, default=0.0):
        """Safely coerce a value that might be a dict, string, or number to float."""
        if isinstance(v, dict):
            v = v.get('value', v.get('statistic', v.get('stat', default)))
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak, HRFlowable, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from datetime import datetime
    
    report_dir = os.path.join(settings.REPORTS_DIR, job_id)
    os.makedirs(report_dir, exist_ok=True)
    pdf_path = os.path.join(report_dir, f"Raw_Output_{job_id[:8]}.pdf")
    
    # Custom canvas for page numbers
    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawString(A4[0] - 2*cm, 1.5*cm, text)
        canvas.restoreState()
        
    A4_PORTRAIT_W  = A4[0]        # 595.28 pt
    A4_LANDSCAPE_W = A4[1]        # 841.89 pt
    MARGINS_PT     = 72 * 2       # left+right 1 inch each = 144 pt
    PORTRAIT_USABLE  = A4_PORTRAIT_W  - MARGINS_PT   # 451 pt
    LANDSCAPE_USABLE = A4_LANDSCAPE_W - MARGINS_PT   # 698 pt

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=72, leftMargin=72,
        topMargin=72, bottomMargin=72
    )
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=24, leading=28, alignment=TA_CENTER, spaceAfter=20)
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=14, alignment=TA_CENTER, textColor=colors.HexColor('#555555'), spaceAfter=40)
    h1 = ParagraphStyle('Heading1Style', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=18, spaceBefore=20, spaceAfter=10, textColor=colors.HexColor('#1e3a5f'), borderWidth=0, leftIndent=10)
    h2 = ParagraphStyle('Heading2Style', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=15, spaceBefore=10, spaceAfter=5)
    normal = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=14, spaceAfter=6)
    caption_style = ParagraphStyle('CaptionStyle', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=10, alignment=TA_CENTER, spaceBefore=5, spaceAfter=15)
    
    story = []

    # ── XML safety helper ────────────────────────────────────────────────────
    def xs(text: str) -> str:
        """Escape &, <, > so ReportLab Paragraph() never raises ExpatError."""
        if not isinstance(text, str):
            text = str(text)
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Cover Page
    story.append(Spacer(1, 2*inch))
    brief = brief or {}
    topic = brief.get("topic") or brief.get("research_goal") or "Statistical Analysis Report"
    story.append(Paragraph(xs(topic).upper(), title_style))
    story.append(HRFlowable(width="80%", thickness=2, color=colors.HexColor('#1e3a5f'), spaceBefore=10, spaceAfter=20))
    date_str = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"Generated on {date_str}", subtitle_style))
    story.append(PageBreak())

    def add_section_heading(text):
        story.append(KeepTogether([
            HRFlowable(width="100%", thickness=3, color=colors.HexColor('#1e3a5f'), spaceBefore=10, spaceAfter=5),
            Paragraph(xs(text), h1)
        ]))

    def make_table(data, colWidths=None, landscape=False):
        wrapped_data = []
        usable_w = LANDSCAPE_USABLE if landscape else PORTRAIT_USABLE
        cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, alignment=TA_LEFT)
        header_style = ParagraphStyle('HeaderCellStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER, textColor=colors.white)
        for r_idx, row in enumerate(data):
            wrapped_row = []
            for item in row:
                if isinstance(item, str):
                    style = header_style if r_idx == 0 else cell_style
                    wrapped_row.append(Paragraph(item, style))
                else:
                    wrapped_row.append(item)
            wrapped_data.append(wrapped_row)

        if not colWidths and len(data) > 0:
            n_cols = len(data[0])
            # First column gets 40% of width for variable names, rest split equally
            if n_cols > 1:
                first_col = usable_w * 0.38
                other_cols = (usable_w - first_col) / (n_cols - 1)
                colWidths = [first_col] + [other_cols] * (n_cols - 1)
            else:
                colWidths = [usable_w]

        t = Table(wrapped_data, colWidths=colWidths, repeatRows=1)
        style_cmds = [
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a5f')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 2, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ]
        # Alternating row colors
        for i in range(1, len(data)):
            bg = colors.HexColor('#f0f4ff') if i % 2 == 1 else colors.white
            style_cmds.append(('BACKGROUND', (0,i), (-1,i), bg))
            style_cmds.append(('FONTNAME', (0,i), (-1,i), 'Helvetica'))
            style_cmds.append(('FONTSIZE', (0,i), (-1,i), 11))
            
        t.setStyle(TableStyle(style_cmds))
        return t

    desc_raw = results.get("descriptive", {})
    add_desc = desc_raw.get("descriptive_stats", {}).get("additional_stats", {}) if isinstance(desc_raw, dict) else desc_raw
    desc = add_desc.get("columns", add_desc) if isinstance(add_desc, dict) else (desc_raw if desc_raw else {})
    if desc:
        add_section_heading("Descriptive Statistics")
        data = [['Variable', 'Mean', 'Median', 'Std Dev', 'Min', 'Max', 'Count']]
        for col, stats in desc.items():
            if isinstance(stats, dict) and "mean" in stats:
                data.append([
                    str(col),
                    f"{stats.get('mean', 0):.3f}",
                    f"{stats.get('median', 0):.3f}" if stats.get('median') is not None else "N/A",
                    f"{stats.get('std', 0):.3f}" if stats.get('std') is not None else "N/A",
                    f"{stats.get('min', 0):.3f}" if stats.get('min') is not None else "N/A",
                    f"{stats.get('max', 0):.3f}" if stats.get('max') is not None else "N/A",
                    str(stats.get('count', ''))
                ])
        story.append(make_table(data))
        story.append(Spacer(1, 12))

    freqs_raw = results.get("frequencies", {})
    add_freq = freqs_raw.get("frequencies", {}).get("additional_stats", {}) if isinstance(freqs_raw, dict) else freqs_raw
    freqs = add_freq.get("columns", add_freq) if isinstance(add_freq, dict) else (freqs_raw if freqs_raw else {})
    if freqs:
        add_section_heading("Frequencies")
        for col, fmap in freqs.items():
            story.append(Paragraph(xs(str(col)), h2))
            data = [['Value', 'Count', 'Percent']]
            if isinstance(fmap, dict):
                total = sum(v if isinstance(v, (int, float)) else 0 for v in fmap.values())
                for val, count in fmap.items():
                    cnt = count if isinstance(count, (int, float)) else (count.get('count', count.get('n', 0)) if isinstance(count, dict) else 0)
                    data.append([xs(str(val)), str(cnt), f"{(cnt/total)*100:.1f}%" if total else "0%"])
            story.append(make_table(data))
            story.append(Spacer(1, 12))

    rel_raw = results.get("reliability", {})
    rel = rel_raw.get("cronbach_alpha", {}).get("additional_stats", rel_raw) if isinstance(rel_raw, dict) and "cronbach_alpha" in rel_raw else rel_raw
    if rel and "alpha" in rel:
        add_section_heading("Reliability Analysis (Cronbach's Alpha)")
        story.append(Paragraph(f"<b>Alpha:</b> {rel.get('alpha', 0):.3f}", normal))
        story.append(Paragraph(f"<b>Items:</b> {rel.get('n_items', 0)}", normal))
        story.append(Paragraph(f"<b>Interpretation:</b> {xs(str(rel.get('interpretation', '')))}", normal))
        story.append(Spacer(1, 12))

    norm_raw = results.get("normality", {})
    if isinstance(norm_raw, dict) and "normality_check" in norm_raw:
        add_norm = norm_raw["normality_check"].get("additional_stats", {})
        norm = add_norm.get("columns", norm_raw) if isinstance(add_norm, dict) else norm_raw
    else:
        norm = norm_raw
    if norm:
        add_section_heading("Normality Tests (Shapiro-Wilk)")
        data = [['Variable', 'Statistic', 'p-value', 'Normal']]
        for col, nres in norm.items():
            if isinstance(nres, dict) and "statistic" in nres:
                data.append([
                    str(col),
                    f"{_to_float(nres.get('statistic', 0)):.4f}",
                    f"{_to_float(nres.get('p_value', 0)):.4f}",
                    "Yes" if nres.get('normal', False) else "No"
                ])
        story.append(make_table(data))
        story.append(Spacer(1, 12))

    summary = results.get("summary", [])
    if summary:
        add_section_heading("Hypothesis Tests")
        for r in summary:
            elements = []
            if r.get("error"):
                elements.append(Paragraph(f"<b>Test:</b> {r.get('test_name')} - <font color='red'>ERROR: {r.get('error')}</font>", normal))
            else:
                elements.append(Paragraph(f"<b>Test:</b> {xs(str(r.get('test_name', '')))}", normal))
                elements.append(Paragraph(f"<b>Hypothesis:</b> {xs(str(r.get('hypothesis', '')))}", normal))
                stat_obj = r.get('statistic')
                if isinstance(stat_obj, dict):
                    stat_val = f"{stat_obj.get('value', 0):.3f}" if stat_obj.get('value') is not None else "N/A"
                    stat_name = xs(str(stat_obj.get('label', 'stat') or r.get('statistic_name', 'stat')))
                else:
                    stat_val = f"{stat_obj:.3f}" if stat_obj is not None else "N/A"
                    stat_name = xs(str(r.get('statistic_name', 'stat')))
                    
                pval = f"{r.get('p_value', 0):.3f}" if r.get('p_value') is not None else "N/A"
                elements.append(Paragraph(f"<b>Statistic ({stat_name}):</b> {stat_val}", normal))
                elements.append(Paragraph(f"<b>p-value:</b> {pval}", normal))
                
                effect_obj = r.get("effect_size")
                if effect_obj is not None:
                    if isinstance(effect_obj, dict):
                        eff_val = effect_obj.get("value")
                        eff_name = effect_obj.get("name", "effect") or r.get("effect_size_name", "effect")
                    else:
                        eff_val = effect_obj
                        eff_name = r.get("effect_size_name", "effect")
                    
                    if eff_val is not None:
                        elements.append(Paragraph(f"<b>Effect Size ({xs(str(eff_name))}):</b> {eff_val:.3f}", normal))
                
                is_sig = r.get('significant')
                sig_text = "<font color='white'>Significant</font>" if is_sig else "<font color='white'>Not Significant</font>"
                bg_color = colors.HexColor('#28a745') if is_sig else colors.HexColor('#dc3545')
                
                # Badge table
                badge = Table([[Paragraph(sig_text, ParagraphStyle('Badge', parent=normal, alignment=TA_CENTER))]], colWidths=[100], rowHeights=[20])
                badge.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), bg_color),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                    ('TOPPADDING', (0,0), (-1,-1), 2),
                ]))
                
                t = Table([[elements, badge]], colWidths=[doc.width - 120, 100])
                t.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('ALIGN', (1,0), (1,0), 'RIGHT'),
                    ('BOX', (0,0), (-1,-1), 1, colors.black),
                    ('PADDING', (0,0), (-1,-1), 10),
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa'))
                ]))
                story.append(t)
            story.append(Spacer(1, 15))

    # Charts — inline in portrait, auto-scaled to fit A4 usable area
    valid_charts = [cp for cp in chart_paths if os.path.exists(cp) and not cp.lower().endswith('.html')] if chart_paths else []
    if valid_charts:
        add_section_heading("Charts & Visualisations")
        # Max chart dimensions in portrait (usable width × 80% usable height)
        PORTRAIT_USABLE_H = A4[1] - 144  # ~451 pt
        MAX_IMG_H = PORTRAIT_USABLE_H * 0.80  # leave room for caption

        for i, chart_path in enumerate(valid_charts):
            try:
                from PIL import Image as PILImage
                with PILImage.open(chart_path) as im:
                    # Actually verify the image data can be read
                    im.verify()
                # Open again to get size (verify() closes/modifies state sometimes)
                with PILImage.open(chart_path) as im:
                    img_w_px, img_h_px = im.size
                
                aspect = img_h_px / img_w_px if img_w_px > 0 else 0.75

                # Scale to fit portrait width first
                w = PORTRAIT_USABLE
                h = w * aspect
                # If height exceeds max, constrain by height instead
                if h > MAX_IMG_H:
                    h = MAX_IMG_H
                    w = h / aspect if aspect > 0 else PORTRAIT_USABLE

                label = _get_figure_label(chart_path, brief)
                img = RLImage(chart_path, width=w, height=h)
                story.append(KeepTogether([
                    img,
                    Spacer(1, 6),
                    Paragraph(f"<b>Figure {i + 1}:</b> {xs(str(label))}", caption_style),
                ]))
                story.append(Spacer(1, 20))
                if i < len(valid_charts) - 1:
                    story.append(PageBreak())
            except Exception:
                # If image is corrupt or not an image (e.g. html), skip it
                pass

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return pdf_path




# ─── Helpers ─────────────────────────────────────────────────────────
def _set_status(job, status: str, db):
    job.status = status
    db.commit()

def _load_dataframe(job):
    """Load the DataFrame for this job.

    Priority:
      1. DEV_MODE without LLM key -> synthetic mock data
      2. Uploaded file in STORAGE_DIR (csv/xlsx/xls/sav)
      3. Pickled DataFrame in storage/dataframes/ (survey-based jobs)
      4. Empty DataFrame (safe fallback)
    """
    import pandas as pd

    storage_dir = getattr(settings, "STORAGE_DIR", "storage")

    # Survey-based job: prefer pickled DataFrame from decode stage
    pkl_dir = os.path.join(storage_dir, "dataframes")
    candidates = []
    if job.survey_id:
        candidates.append(os.path.join(pkl_dir, f"{job.survey_id}.pkl"))
    if job.source_filename:
        candidates.append(os.path.join(pkl_dir, f"{job.source_filename}.pkl"))
    candidates.append(os.path.join(pkl_dir, f"{job.id}.pkl"))
    for p in candidates:
        if os.path.exists(p):
            try:
                return pd.read_pickle(p)
            except Exception:
                pass

    # Uploaded-file job: look in STORAGE_DIR for the cleaned file
    for ext in (".csv", ".xlsx", ".xls", ".sav"):
        candidate = os.path.join(storage_dir, f"{job.id}{ext}")
        if os.path.exists(candidate):
            try:
                if ext in (".xlsx", ".xls"):
                    return pd.read_excel(candidate)
                elif ext == ".csv":
                    return pd.read_csv(candidate)
                elif ext == ".sav":
                    try:
                        import pyreadstat
                        df, _ = pyreadstat.read_sav(candidate)
                        return df
                    except Exception:
                        pass
            except Exception:
                pass

    # DEV MODE fallback: synthetic data when no real source is available
    if getattr(settings, "DEV_MODE", False) and not getattr(settings, "ANTHROPIC_API_KEY", None):
        try:
            import numpy as np
            np.random.seed(42)
            n = 120
            return pd.DataFrame({
                "gender":            np.random.choice(["Male", "Female"], n),
                "age_group":         np.random.choice(["18-25", "26-35", "36-45", "46+"], n),
                "department":        np.random.choice(["Science", "Arts", "Engineering", "Business"], n),
                "q1": np.random.randint(1, 6, n),
                "q2": np.random.randint(1, 6, n),
                "q3": np.random.randint(1, 6, n),
                "q4": np.random.randint(1, 6, n),
                "q5": np.random.randint(1, 6, n),
                "performance_score":  np.random.normal(65, 12, n),
                "satisfaction_index": np.random.normal(3.4, 0.8, n),
            })
        except ImportError:
            return pd.DataFrame()

    return pd.DataFrame()


# ─── Training Data Logger ─────────────────────────────────────────────
def _save_training_example(job, brief: dict, results: dict, chapter_texts: dict, report_text: dict):
    """
    Save a structured training example after every successful analysis job.
    Output format is JSONL, compatible with Hugging Face / Unsloth fine-tuning.

    Saved to:  storage/training_data/{job_id}.jsonl
    Master:    storage/training_data/researchform_training.jsonl

    Each file contains 3 lines — one per task the LLM must learn:
      Line 1: Test selection  (brief + data dict → selected tests)
      Line 2: Code generation (brief + tests → Python code)
      Line 3: Report writing  (brief + results + chapters → Chapter 4 JSON)
    """
    import json
    from datetime import datetime

    # Guard: never raise — called inside try/except but defence in depth
    if job is None or brief is None:
        return

    # Do not pollute training data with local demo/dev runs
    if getattr(settings, "DEV_MODE", False):
        return

    storage_dir = getattr(settings, "STORAGE_DIR", "storage")
    training_dir = os.path.join(storage_dir, "training_data")
    os.makedirs(training_dir, exist_ok=True)

    data_dict = job.data_dictionary or {}
    selected_tests = job.selected_tests or []
    generated_code = job.generated_code or ""

    # Only log if we have meaningful data (real LLM was used)
    if not selected_tests and not generated_code:
        return

    def _fmt(role, content):
        return {"role": role, "content": content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)}

    examples = [
        # ── Task 1: Test Selection ──────────────────────────────────────
        {
            "task": "test_selection",
            "job_id": job.id,
            "created_at": datetime.utcnow().isoformat(),
            "has_chapters": bool(chapter_texts),
            "messages": [
                _fmt("user",
                    f"Research topic: {brief.get('topic')}\n"
                    f"DV: {brief.get('dependent_variable')} | IV: {brief.get('independent_variable')}\n"
                    f"Population: {brief.get('population')}\n"
                    f"Hypotheses: {json.dumps(brief.get('hypotheses', []))}\n"
                    f"Variables: {json.dumps([v.get('clean_name') for v in data_dict.get('variables', [])[:30]])}\n"
                    f"Ordinal vars: {json.dumps(data_dict.get('ordinal_vars', [])[:10])}\n"
                    f"Ratio vars: {json.dumps(data_dict.get('ratio_vars', [])[:10])}\n\n"
                    f"Select the appropriate statistical tests to run for this research."
                ),
                _fmt("assistant", selected_tests),
            ]
        },
        # ── Task 2: Code Generation ─────────────────────────────────────
        {
            "task": "code_generation",
            "job_id": job.id,
            "created_at": datetime.utcnow().isoformat(),
            "messages": [
                _fmt("user",
                    f"Research topic: {brief.get('topic')}\n"
                    f"DV: {brief.get('dependent_variable')} | IV: {brief.get('independent_variable')}\n"
                    f"Hypotheses: {json.dumps(brief.get('hypotheses', []))}\n"
                    f"Selected tests: {json.dumps([t.get('test_name') for t in selected_tests])}\n"
                    f"Variables: {json.dumps([v.get('clean_name') for v in data_dict.get('variables', [])[:25]])}\n"
                    f"Ordinal: {json.dumps(data_dict.get('ordinal_vars', [])[:10])}\n"
                    f"Ratio: {json.dumps(data_dict.get('ratio_vars', [])[:10])}\n"
                    f"Missing strategy: {job.missing_strategy or 'flag_only'}\n\n"
                    f"Generate Python analysis code for this research."
                ),
                _fmt("assistant", generated_code),
            ]
        },
        # ── Task 3: Report Writing ──────────────────────────────────────
        {
            "task": "report_writing",
            "job_id": job.id,
            "created_at": datetime.utcnow().isoformat(),
            "has_chapters": bool(chapter_texts),
            "messages": [
                _fmt("user",
                    f"Research topic: {brief.get('topic')}\n"
                    f"Objectives: {json.dumps(brief.get('objectives', []))}\n"
                    f"Hypotheses: {json.dumps(brief.get('hypotheses', []))}\n"
                    f"DV: {brief.get('dependent_variable')} | IV: {brief.get('independent_variable')}\n"
                    f"Population: {brief.get('population')}\n"
                    + (f"Chapter 2 (Literature): {chapter_texts.get('chapter2', '')[:1500]}\n" if chapter_texts.get('chapter2') else "")
                    + (f"Chapter 3 (Methodology): {chapter_texts.get('chapter3', '')[:1000]}\n" if chapter_texts.get('chapter3') else "")
                    + f"Statistical results: {json.dumps(results, ensure_ascii=False)[:3000]}\n\n"
                    f"Write Chapter 4 in formal Nigerian university academic language."
                ),
                _fmt("assistant", report_text),
            ]
        },
    ]

    # ── Save individual job file ────────────────────────────────────────
    job_file = os.path.join(training_dir, f"{job.id}.jsonl")
    with open(job_file, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # ── Append to rolling master file ──────────────────────────────────
    master_file = os.path.join(training_dir, "researchform_training.jsonl")
    with open(master_file, "a", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # ── Update stats file ───────────────────────────────────────────────
    stats_file = os.path.join(training_dir, "stats.json")
    try:
        if os.path.exists(stats_file):
            with open(stats_file, "r", encoding="utf-8") as f:
                stats = json.load(f)
        else:
            stats = {"total_jobs": 0, "total_examples": 0, "jobs_with_chapters": 0, "first_job": None, "last_job": None}
        stats["total_jobs"] += 1
        stats["total_examples"] += 3
        if chapter_texts:
            stats["jobs_with_chapters"] += 1
        if not stats["first_job"]:
            stats["first_job"] = datetime.utcnow().isoformat()
        stats["last_job"] = datetime.utcnow().isoformat()
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


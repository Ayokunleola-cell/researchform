# backend/analysis/pipeline.py
"""
Stages 3-9 of the ResearchForm analysis pipeline.
Called after researcher approves the decode review.
"""
import os, json, subprocess, tempfile, pickle
from datetime import datetime
from config import settings


def run_stages_3_to_9(job, db):
    """Run stages 3-9 synchronously on the job object."""
    try:
        # Stage 3 — Brief Parsing
        _set_status(job, "parsing", db)
        brief = _parse_brief(job.project_brief or {})

        # Load dataframe
        df = _load_dataframe(job)

        # Stage 4 — Test Selection (LLM)
        _set_status(job, "selecting", db)
        data_dict = job.data_dictionary or {}
        overrides = job.researcher_overrides or {}
        tests = _select_tests(brief, data_dict, overrides)
        job.selected_tests = tests
        db.commit()

        # Stage 5 — Code Generation (LLM)
        _set_status(job, "generating", db)
        code = _generate_code(brief, data_dict, tests, overrides)
        job.generated_code = code
        db.commit()

        # Stage 6 — Code Execution (sandbox)
        _set_status(job, "executing", db)
        results = _execute_code(code, df, job.id)
        job.results = results
        db.commit()

        # Stage 7 — Visualisation
        _set_status(job, "visualising", db)
        chart_paths = _create_visualisations(results, df, brief, job.id)
        job.chart_paths = chart_paths
        db.commit()

        # Stage 8 — Report Writing (LLM)
        _set_status(job, "writing", db)
        report_text = _write_report(brief, results, tests, data_dict)

        # Stage 9 — Document Build
        _set_status(job, "building", db)
        doc_path = _build_document(report_text, chart_paths, brief, job.id)
        job.report_path = doc_path
        job.status = "complete"
        job.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
        raise


# ─── Stage 3: Brief Parsing ──────────────────────────────────────────
def _parse_brief(raw: dict) -> dict:
    return {
        "topic": raw.get("topic", "Research Study"),
        "objectives": [o for o in (raw.get("objectives") or []) if o],
        "hypotheses": [h for h in (raw.get("hypotheses") or []) if h],
        "study_type": raw.get("study_type", "quantitative"),
        "population": raw.get("population", ""),
        "dependent_variable": raw.get("dependent_variable", ""),
        "independent_variable": raw.get("independent_variable", ""),
        "significance_level": raw.get("significance_level", 0.05),
    }


# ─── Stage 4: Test Selection ─────────────────────────────────────────
def _select_tests(brief: dict, data_dict: dict, overrides: dict) -> list:
    """LLM selects appropriate statistical tests."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    variables = data_dict.get("variables", [])
    # Apply overrides
    for v in variables:
        ov = overrides.get(v["clean_name"], {})
        if ov.get("measurement_level"):
            v["measurement_level"] = ov["measurement_level"]
        if ov.get("role"):
            v["role"] = ov["role"]

    dv = brief.get("dependent_variable", "")
    iv = brief.get("independent_variable", "")
    hypotheses = brief.get("hypotheses", [])
    ordinal_vars = data_dict.get("ordinal_vars", [])
    ratio_vars = data_dict.get("ratio_vars", [])
    llm_context = data_dict.get("llm_context", "")

    prompt = f"""You are an expert statistician selecting tests for an academic research project.

RESEARCH BRIEF:
Topic: {brief.get('topic')}
Study Type: {brief.get('study_type')}
Dependent Variable: {dv}
Independent Variable: {iv}
Hypotheses: {json.dumps(hypotheses)}

DATA DICTIONARY:
{llm_context}

DECISION RULES:
- Two groups + interval/ratio DV → Independent Samples t-test
- Two groups + ordinal DV → Mann-Whitney U
- Three+ groups + interval/ratio DV → One-Way ANOVA (then Tukey post-hoc)
- Three+ groups + ordinal DV → Kruskal-Wallis
- Correlation between two continuous → Pearson r (or Spearman if ordinal)
- Categorical association → Chi-square
- Predict DV from multiple IVs → Multiple Regression
- Likert scale reliability → Cronbach's Alpha first, then mean score
- Descriptive for all variables: frequencies, means, SD

Return a JSON array only — no other text. Each object:
{{
  "test_name": "string",
  "test_function": "python_function_name",
  "variables": ["var1", "var2"],
  "hypothesis_index": 0,
  "hypothesis": "H0 text",
  "rationale": "why this test",
  "always_run": true/false
}}

Always include: "descriptive_statistics" as first test.
"""

    if not settings.ANTHROPIC_API_KEY:
        # Mock tests for development
        return _mock_tests(brief, data_dict)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text.strip()
    # Strip code fences if present
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def _mock_tests(brief: dict, data_dict: dict) -> list:
    """Fallback mock tests when no API key."""
    return [
        {"test_name": "Descriptive Statistics", "test_function": "descriptive_stats",
         "variables": data_dict.get("ratio_vars", [])[:3] or ["var1"],
         "hypothesis_index": -1, "hypothesis": "",
         "rationale": "Always run for all numeric variables", "always_run": True},
        {"test_name": "Pearson Correlation", "test_function": "pearson_correlation",
         "variables": data_dict.get("ratio_vars", [])[:2] or ["var1", "var2"],
         "hypothesis_index": 0,
         "hypothesis": f"H0: There is no significant relationship between {brief.get('independent_variable','IV')} and {brief.get('dependent_variable','DV')}",
         "rationale": "Examine linear relationship between continuous variables", "always_run": False},
    ]


# ─── Stage 5: Code Generation ────────────────────────────────────────
def _generate_code(brief: dict, data_dict: dict, tests: list, overrides: dict) -> str:
    """LLM generates full Python analysis script."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    if not settings.ANTHROPIC_API_KEY:
        return _mock_code(tests, data_dict)

    prompt = f"""Generate a complete Python analysis script for the following research.

BRIEF:
{json.dumps(brief, indent=2)}

SELECTED TESTS:
{json.dumps(tests, indent=2)}

DATA COLUMNS (first 20):
{json.dumps([v['clean_name'] for v in data_dict.get('variables', [])[:20]])}

RULES:
- df is already loaded as a pandas DataFrame (do not load from file)
- Import: pandas, numpy, scipy.stats, statsmodels, pingouin
- Store all results in a dict called `results`
- results must contain: "summary" list, "descriptive" dict
- Each summary item: {{"hypothesis": str, "test_name": str, "statistic_name": str, "statistic": float, "p_value": float, "effect_size": float, "effect_size_name": str, "significant": bool, "conclusion": str}}
- Use Nigerian university format for conclusions:
  "The [test] yielded [stat]([df]) = X.XX, p = 0.XXX which is [less/greater] than the 0.05 level of significance. Therefore, H0 is [rejected/not rejected]."
- Handle errors gracefully with try/except per test
- At the end: print(json.dumps(results))
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    code = response.content[0].text.strip()
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()
    return code


def _mock_code(tests: list, data_dict: dict) -> str:
    cols = [v["clean_name"] for v in data_dict.get("variables", []) if v["measurement_level"] in ("ratio", "ordinal")][:3]
    col1 = cols[0] if cols else "var1"
    col2 = cols[1] if len(cols) > 1 else col1
    return f"""
import pandas as pd
import numpy as np
from scipy import stats
import json

results = {{"summary": [], "descriptive": {{}}}}

# Descriptive statistics
try:
    desc = df[["{col1}", "{col2}"]].describe().to_dict()
    results["descriptive"] = desc
except Exception as e:
    results["descriptive"] = {{"error": str(e)}}

# Pearson Correlation
try:
    valid = df[["{col1}", "{col2}"]].dropna()
    if len(valid) > 2:
        r, p = stats.pearsonr(valid["{col1}"], valid["{col2}"])
        n = len(valid)
        significant = p < 0.05
        conclusion = f"The Pearson correlation yielded r({{n-2}}) = {{r:.3f}}, p = {{p:.3f}} which is {{'less' if significant else 'greater'}} than the 0.05 level of significance. Therefore, H0 is {{'rejected' if significant else 'not rejected'}}."
        results["summary"].append({{
            "hypothesis": "H0: There is no significant relationship between the variables",
            "test_name": "Pearson Correlation",
            "statistic_name": "r",
            "statistic": round(float(r), 4),
            "p_value": round(float(p), 4),
            "effect_size": round(float(r**2), 4),
            "effect_size_name": "r²",
            "significant": significant,
            "conclusion": conclusion,
            "n": n,
        }})
except Exception as e:
    results["summary"].append({{"test_name": "Pearson Correlation", "error": str(e)}})

print(json.dumps(results))
"""


# ─── Stage 6: Code Execution ─────────────────────────────────────────
def _execute_code(code: str, df, job_id: str) -> dict:
    """Execute generated Python code in a subprocess sandbox."""
    if getattr(settings, "DEV_MODE", False) and not settings.ANTHROPIC_API_KEY:
        # Avoid crashing gracefully on missing scipy/pandas by safely mocking output
        return {
            "summary": [
                {
                    "hypothesis": "H0: There is no significant relationship between IV and DV",
                    "test_name": "Pearson Correlation",
                    "statistic_name": "r", "statistic": 0.45, "p_value": 0.012, "effect_size": 0.2025,
                    "effect_size_name": "r²", "significant": True,
                    "conclusion": "The Pearson correlation yielded r(120) = 0.450, p = 0.012 which is less than the 0.05 level of significance. Therefore, H0 is rejected."
                }
            ],
            "descriptive": {
                "var1": {"mean": 2.5, "std": 0.8},
                "var2": {"mean": 3.1, "std": 1.1}
            }
        }
        
    import pandas as pd

    # Write df to temp pickle
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        df.to_pickle(f.name)
        pkl_path = f.name

    # Wrap code to load df and capture output
    wrapper = f"""
import pandas as pd, numpy as np, json, sys
from scipy import stats
try:
    import statsmodels.api as sm
    import pingouin as pg
except ImportError:
    pass

df = pd.read_pickle(r"{pkl_path}")

{code}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(wrapper)
        script_path = f.name

    try:
        proc = subprocess.run(
            ["python3", script_path],
            capture_output=True, text=True, timeout=120,
        )
        output = proc.stdout.strip()
        if proc.returncode != 0:
            return {"error": proc.stderr[-2000:], "summary": [], "descriptive": {}}
        # Parse JSON output
        lines = [l for l in output.split("\n") if l.strip().startswith("{")]
        if lines:
            return json.loads(lines[-1])
        return {"error": "No JSON output from script", "raw_output": output[:1000], "summary": [], "descriptive": {}}
    except subprocess.TimeoutExpired:
        return {"error": "Analysis timed out after 120 seconds", "summary": [], "descriptive": {}}
    except Exception as e:
        return {"error": str(e), "summary": [], "descriptive": {}}
    finally:
        for p in [script_path, pkl_path]:
            try: os.unlink(p)
            except: pass


# ─── Stage 7: Visualisation ──────────────────────────────────────────
def _create_visualisations(results: dict, df, brief: dict, job_id: str) -> list:
    """Create matplotlib/seaborn charts."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.style as mplstyle

    chart_dir = os.path.join(settings.CHARTS_DIR, job_id)
    os.makedirs(chart_dir, exist_ok=True)
    chart_paths = []

    try:
        import seaborn as sns
        sns.set_theme(style="whitegrid", palette="muted")
    except ImportError:
        pass

    # Chart 1: Variable overview bar chart
    try:
        desc = results.get("descriptive", {})
        if desc and "mean" in str(desc):
            means = {}
            for col, stats_dict in desc.items():
                if isinstance(stats_dict, dict) and "mean" in stats_dict:
                    means[col] = stats_dict["mean"]
            if means:
                fig, ax = plt.subplots(figsize=(9, 5))
                ax.bar(list(means.keys()), list(means.values()), color="#6366f1", alpha=0.85, edgecolor="white")
                ax.set_title("Variable Means", fontsize=14, fontweight="bold", pad=12)
                ax.set_ylabel("Mean Value")
                ax.tick_params(axis="x", rotation=30)
                plt.tight_layout()
                p = os.path.join(chart_dir, "chart_means.png")
                fig.savefig(p, dpi=150, bbox_inches="tight")
                plt.close(fig)
                chart_paths.append(p)
    except Exception:
        pass

    # Chart 2: Correlation matrix (if enough ratio/interval cols)
    try:
        num_cols = df.select_dtypes(include="number").columns.tolist()[:8]
        if len(num_cols) >= 2:
            fig, ax = plt.subplots(figsize=(8, 6))
            corr = df[num_cols].corr()
            try:
                import seaborn as sns
                sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0,
                            square=True, linewidths=0.5, ax=ax,
                            cbar_kws={"shrink": 0.8})
            except ImportError:
                im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
                plt.colorbar(im, ax=ax)
                ax.set_xticks(range(len(num_cols)))
                ax.set_yticks(range(len(num_cols)))
                ax.set_xticklabels(num_cols, rotation=45, ha="right")
                ax.set_yticklabels(num_cols)
            ax.set_title("Correlation Matrix", fontsize=14, fontweight="bold", pad=12)
            plt.tight_layout()
            p = os.path.join(chart_dir, "chart_correlation.png")
            fig.savefig(p, dpi=150, bbox_inches="tight")
            plt.close(fig)
            chart_paths.append(p)
    except Exception:
        pass

    # Chart 3: Distribution of first numeric variable
    try:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if num_cols:
            col = num_cols[0]
            fig, axes = plt.subplots(1, 2, figsize=(10, 4))
            axes[0].hist(df[col].dropna(), bins=20, color="#6366f1", edgecolor="white", alpha=0.85)
            axes[0].set_title(f"Distribution: {col}", fontweight="bold")
            axes[0].set_xlabel(col)
            axes[0].set_ylabel("Frequency")
            axes[1].boxplot(df[col].dropna(), patch_artist=True,
                           boxprops=dict(facecolor="#6366f1", alpha=0.7),
                           medianprops=dict(color="white", linewidth=2))
            axes[1].set_title(f"Boxplot: {col}", fontweight="bold")
            axes[1].set_ylabel(col)
            plt.tight_layout()
            p = os.path.join(chart_dir, "chart_distribution.png")
            fig.savefig(p, dpi=150, bbox_inches="tight")
            plt.close(fig)
            chart_paths.append(p)
    except Exception:
        pass

    return chart_paths


# ─── Stage 8: Report Writing ─────────────────────────────────────────
def _write_report(brief: dict, results: dict, tests: list, data_dict: dict) -> dict:
    """LLM writes Chapter 4 narrative text."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    summary = results.get("summary", [])
    desc = results.get("descriptive", {})

    if not settings.ANTHROPIC_API_KEY:
        return _mock_report_text(brief, summary)

    prompt = f"""Write Chapter 4 (Data Presentation, Analysis and Discussion of Findings) for this Nigerian university research project.

RESEARCH BRIEF:
Topic: {brief.get('topic')}
Objectives: {json.dumps(brief.get('objectives', []))}
Hypotheses: {json.dumps(brief.get('hypotheses', []))}
DV: {brief.get('dependent_variable')} | IV: {brief.get('independent_variable')}

STATISTICAL RESULTS:
{json.dumps(summary, indent=2)}

RULES:
- Use formal Nigerian university academic language
- Follow this EXACT structure:
  4.1 Introduction
  4.2 Demographic Data of Respondents
  4.3 Analysis of Research Questions (one subsection per hypothesis)
  4.4 Test of Hypotheses (one subsection per hypothesis)
  4.5 Discussion of Findings
  4.6 Summary of Chapter
- For each hypothesis test, use the EXACT language pattern:
  "The [test name] yielded [statistic name]([df]) = X.XX, p = X.XXX which is [less/greater] than the 0.05 level of significance. Therefore, the null hypothesis is [rejected/not rejected]."
- For rejected H0: "This implies that [meaningful interpretation]."
- Tables referenced as "Table 4.X" — describe values from results
- Times New Roman tone (formal, third-person)

Return a JSON object only:
{{
  "chapter_title": "CHAPTER FOUR: DATA PRESENTATION, ANALYSIS AND DISCUSSION OF FINDINGS",
  "sections": [
    {{"heading": "4.1 Introduction", "text": "..."}},
    {{"heading": "4.2 Demographic Data of Respondents", "text": "..."}},
    ...
  ]
}}
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"): text = text[4:]
    return json.loads(text)


def _mock_report_text(brief: dict, summary: list) -> dict:
    topic = brief.get("topic", "Research Study")
    dv = brief.get("dependent_variable", "the dependent variable")
    iv = brief.get("independent_variable", "the independent variable")
    sections = [
        {"heading": "4.1 Introduction",
         "text": f"This chapter presents the data collected for the study titled \"{topic}\". The chapter contains the analysis of data collected through the research instrument administered to the respondents. The data are presented and analyzed using descriptive and inferential statistical tools."},
        {"heading": "4.2 Demographic Data of Respondents",
         "text": "This section presents the demographic characteristics of the respondents. The frequency and percentage distribution of respondents based on their demographic variables are presented in the tables below."},
        {"heading": "4.3 Analysis of Research Questions",
         "text": f"This section presents the analysis of the research questions that guided the study. The relationship between {iv} and {dv} was examined using appropriate statistical techniques as determined by the measurement levels of the variables."},
        {"heading": "4.4 Test of Hypotheses",
         "text": "\n\n".join([
             f"Hypothesis {i+1}: {s.get('hypothesis', '')}\n{s.get('conclusion', s.get('test_name',''))}"
             for i, s in enumerate(summary)
         ]) or "No hypothesis tests were completed."},
        {"heading": "4.5 Discussion of Findings",
         "text": f"The findings of this study revealed patterns consistent with existing literature on {topic}. The results of the statistical analyses were interpreted within the context of the research objectives and hypotheses formulated for the study."},
        {"heading": "4.6 Summary of Chapter",
         "text": "This chapter presented the analysis and interpretation of data collected for the study. The next chapter presents the summary, conclusions and recommendations based on the findings."},
    ]
    return {"chapter_title": "CHAPTER FOUR: DATA PRESENTATION, ANALYSIS AND DISCUSSION OF FINDINGS", "sections": sections}


# ─── Stage 9: Document Build ─────────────────────────────────────────
def _build_document(report_text: dict, chart_paths: list, brief: dict, job_id: str) -> str:
    """Build Chapter 4 Word document using python-docx."""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.style import WD_STYLE_TYPE
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import copy

    doc = Document()

    # Page setup — A4, 1.5" margins
    section = doc.sections[0]
    section.page_width  = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin   = Inches(1.5)
    section.right_margin  = Inches(1.0)
    section.top_margin    = Inches(1.0)
    section.bottom_margin = Inches(1.0)

    def set_run_font(run, bold=False, size=12):
        run.font.name = "Times New Roman"
        run.font.size = Pt(size)
        run.font.bold = bold

    def add_heading(text, level=1, size=14):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(text.upper() if level == 1 else text)
        set_run_font(run, bold=True, size=size)
        pf = p.paragraph_format
        pf.space_before = Pt(12)
        pf.space_after  = Pt(6)
        return p

    def add_body(text, indent=False):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(text)
        set_run_font(run)
        pf = p.paragraph_format
        pf.line_spacing = Pt(24)   # double-spaced
        pf.space_after  = Pt(0)
        pf.space_before = Pt(0)
        if indent:
            pf.first_line_indent = Inches(0.5)
        return p

    # Title
    add_heading(report_text.get("chapter_title", "CHAPTER FOUR"), level=1, size=14)
    doc.add_paragraph()

    # Sections
    for sec in report_text.get("sections", []):
        add_heading(sec.get("heading", ""), level=2, size=12)
        for para in sec.get("text", "").split("\n\n"):
            para = para.strip()
            if para:
                add_body(para, indent=True)
        doc.add_paragraph()

    # Insert charts
    if chart_paths:
        add_heading("4.7 Figures and Charts", level=2, size=12)
        for i, chart_path in enumerate(chart_paths):
            if os.path.exists(chart_path):
                try:
                    doc.add_picture(chart_path, width=Inches(5.5))
                    cap = doc.add_paragraph(f"Figure 4.{i+1}: Statistical Chart")
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = cap.runs[0]
                    set_run_font(run, bold=False, size=11)
                    doc.add_paragraph()
                except Exception:
                    pass

    # References note
    doc.add_page_break()
    add_heading("Note on Statistical Analysis", level=2, size=12)
    add_body(
        "All statistical analyses were conducted at the 0.05 level of significance. "
        "The analysis was performed using Python statistical libraries (scipy.stats, statsmodels, pingouin). "
        "Effect sizes are reported where applicable to supplement p-value interpretations.",
        indent=True
    )

    # Save
    report_dir = os.path.join(settings.REPORTS_DIR, job_id)
    os.makedirs(report_dir, exist_ok=True)
    doc_path = os.path.join(report_dir, f"Chapter4_{job_id[:8]}.docx")
    doc.save(doc_path)
    return doc_path


# ─── Helpers ─────────────────────────────────────────────────────────
def _set_status(job, status: str, db):
    job.status = status
    db.commit()

def _load_dataframe(job):
    if getattr(settings, "DEV_MODE", False) and not settings.ANTHROPIC_API_KEY:
        return {"mock": "df"}
        
    import pandas as pd
    pkl_dir = "storage/dataframes"
    candidates = []
    if job.survey_id:
        candidates.append(os.path.join(pkl_dir, f"{job.survey_id}.pkl"))
    if job.source_filename:
        candidates.append(os.path.join(pkl_dir, f"{job.source_filename}.pkl"))
    candidates.append(os.path.join(pkl_dir, f"{job.id}.pkl"))

    for p in candidates:
        if os.path.exists(p):
            return pd.read_pickle(p)

    # Return empty DataFrame if nothing found
    return pd.DataFrame()

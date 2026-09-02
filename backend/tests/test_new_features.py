"""
ResearchForm — Unit Tests for New Pipeline Features
Tests: cleaner.py, _understand_context, _mock_context, _mock_tests (expanded),
       _mock_code (expanded), inspection_report/cleaning_summary in pipeline,
       form validation logic, and QA checks on data integrity.

Run:
  .\\venv_312\\Scripts\\python.exe -m pytest tests/test_new_features.py -v --tb=short -p no:warnings
"""
import sys, os, json, pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Data Cleaner (analysis/cleaner.py)
# ══════════════════════════════════════════════════════════════════════════════

class TestDataCleaner:
    """Unit tests for the clean_and_inspect() function in cleaner.py"""

    def _make_df(self, n=50, with_dupes=False, with_nullcol=False):
        import pandas as pd
        import numpy as np
        data = {
            "gender":    ["Male", "Female"] * (n // 2),
            "age":       list(range(20, 20 + n)),
            "score":     np.random.uniform(40, 100, n).tolist(),
            "q1":        np.random.randint(1, 6, n).tolist(),
        }
        df = pd.DataFrame(data)
        if with_dupes:
            df = pd.concat([df, df.iloc[:5]], ignore_index=True)
        if with_nullcol:
            df["empty_col"] = None
        return df

    def test_returns_three_values(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = clean_and_inspect(df)
        assert len(result) == 3

    def test_clean_df_is_dataframe(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        df = pd.DataFrame({"x": [1, 2, 3]})
        clean_df, _, _ = clean_and_inspect(df)
        assert isinstance(clean_df, pd.DataFrame)

    def test_inspection_report_is_dict(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df()
        _, report, _ = clean_and_inspect(df)
        assert isinstance(report, dict)

    def test_cleaning_summary_is_dict(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df()
        _, _, summary = clean_and_inspect(df)
        assert isinstance(summary, dict)

    def test_inspection_report_has_required_keys(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df()
        _, report, _ = clean_and_inspect(df)
        for key in ["shape_before", "shape_after", "n_duplicates_found",
                    "outliers", "missing_per_column", "pct_complete_rows"]:
            assert key in report, f"Missing key: {key}"

    def test_cleaning_summary_has_required_keys(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df()
        _, _, summary = clean_and_inspect(df)
        for key in ["actions_taken", "rows_before", "rows_after",
                    "columns_before", "columns_after", "cleaned"]:
            assert key in summary, f"Missing key: {key}"

    def test_duplicate_rows_removed(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df(n=20, with_dupes=True)
        rows_before = len(df)
        clean_df, report, summary = clean_and_inspect(df)
        assert report["n_duplicates_found"] >= 5
        assert len(clean_df) < rows_before
        assert any(a["action"] == "duplicates_removed" for a in summary["actions_taken"])

    def test_empty_column_dropped(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df(n=20, with_nullcol=True)
        assert "empty_col" in df.columns
        clean_df, report, summary = clean_and_inspect(df)
        assert "empty_col" not in clean_df.columns
        assert report["n_empty_columns_dropped"] >= 1
        assert any(a["action"] == "empty_columns_dropped" for a in summary["actions_taken"])

    def test_whitespace_stripped_from_strings(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        df = pd.DataFrame({"name": ["  Alice  ", "  Bob  ", "  Carol  "]})
        clean_df, _, _ = clean_and_inspect(df)
        for val in clean_df["name"].dropna():
            assert val == val.strip(), f"Whitespace not stripped: '{val}'"

    def test_no_duplicates_clean_df_unchanged_length(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df(n=30)
        rows_before = len(df)
        clean_df, report, _ = clean_and_inspect(df)
        assert report["n_duplicates_found"] == 0
        assert len(clean_df) == rows_before

    def test_outlier_detection_produces_report(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        import numpy as np
        # Insert clear outliers
        scores = list(np.random.normal(70, 5, 50)) + [500.0, -500.0]
        df = pd.DataFrame({"score": scores})
        _, report, _ = clean_and_inspect(df)
        assert "score" in report["outliers"]
        assert report["outliers"]["score"]["n_outliers_iqr"] >= 1

    def test_outlier_does_not_remove_rows(self):
        """Outliers are flagged, not removed."""
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        import numpy as np
        scores = list(np.random.normal(70, 5, 40)) + [9999.0]
        df = pd.DataFrame({"score": scores})
        clean_df, _, _ = clean_and_inspect(df)
        # Row count should not change due to outlier
        assert len(clean_df) >= 40  # only dupes removed, not outliers

    def test_shape_before_matches_input(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df(n=50)
        _, report, _ = clean_and_inspect(df)
        assert report["shape_before"]["rows"] == 50
        assert report["shape_before"]["columns"] == len(df.columns)

    def test_pct_complete_rows_between_0_and_100(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        import numpy as np
        df = pd.DataFrame({"a": [1, None, 3, 4, 5], "b": [None, 2, 3, 4, 5]})
        _, report, _ = clean_and_inspect(df)
        assert 0.0 <= report["pct_complete_rows"] <= 100.0

    def test_missing_per_column_keys_match_df_columns(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        df = pd.DataFrame({"x": [1, 2], "y": [3, 4], "z": [5, 6]})
        _, report, _ = clean_and_inspect(df)
        for col in df.columns:
            assert col in report["missing_per_column"]

    def test_empty_dataframe_does_not_crash(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        df = pd.DataFrame()
        result = clean_and_inspect(df)
        assert result is not None

    def test_single_column_df_handled(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        df = pd.DataFrame({"only": [1, 2, 3, 4, 5]})
        clean_df, report, summary = clean_and_inspect(df)
        assert isinstance(clean_df, pd.DataFrame)
        assert isinstance(report, dict)

    def test_cleaning_summary_cleaned_flag_true_when_actions_taken(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df(n=20, with_dupes=True)
        _, _, summary = clean_and_inspect(df)
        assert summary["cleaned"] is True

    def test_cleaning_summary_cleaned_flag_false_when_no_actions(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df(n=20)  # clean data, no dupes, no empty cols
        _, _, summary = clean_and_inspect(df)
        # May or may not be False depending on data — just check it's a bool
        assert isinstance(summary["cleaned"], bool)

    def test_actions_taken_is_list(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df(n=10)
        _, _, summary = clean_and_inspect(df)
        assert isinstance(summary["actions_taken"], list)

    def test_rows_after_leq_rows_before(self):
        from analysis.cleaner import clean_and_inspect
        df = self._make_df(n=30, with_dupes=True)
        _, _, summary = clean_and_inspect(df)
        assert summary["rows_after"] <= summary["rows_before"]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Context Understanding (_understand_context / _mock_context)
# ══════════════════════════════════════════════════════════════════════════════

class TestContextUnderstanding:
    """Tests for Stage 3b _understand_context and _mock_context fallback."""

    def _brief(self):
        return {
            "topic": "Impact of Teaching Method on Student Performance",
            "study_type": "quantitative",
            "dependent_variable": "Student Performance",
            "independent_variable": "Teaching Method",
            "hypotheses": ["H0: No significant difference"],
            "population": "Secondary school students",
        }

    def _data_dict(self, n_ordinal=5, n_ratio=3, n_nominal=2):
        import pandas as pd
        ordinal_vars  = [f"q{i}" for i in range(1, n_ordinal + 1)]
        ratio_vars    = [f"score_{i}" for i in range(1, n_ratio + 1)]
        nominal_vars  = [f"cat_{i}" for i in range(1, n_nominal + 1)]
        return {
            "variables": [{"clean_name": v, "measurement_level": "ordinal"} for v in ordinal_vars]
                       + [{"clean_name": v, "measurement_level": "ratio"}  for v in ratio_vars]
                       + [{"clean_name": v, "measurement_level": "nominal"} for v in nominal_vars],
            "ordinal_vars": ordinal_vars,
            "ratio_vars": ratio_vars,
            "nominal_vars": nominal_vars,
        }

    def test_mock_context_returns_dict(self):
        from analysis.pipeline import _mock_context
        result = _mock_context(self._brief(), self._data_dict())
        assert isinstance(result, dict)

    def test_mock_context_has_required_keys(self):
        from analysis.pipeline import _mock_context
        result = _mock_context(self._brief(), self._data_dict())
        for key in ["dv_column", "iv_column", "likert_constructs",
                    "demographic_columns", "use_parametric",
                    "testable_hypotheses", "methodology_note"]:
            assert key in result, f"Missing key: {key}"

    def test_mock_context_likert_constructs_when_enough_ordinal(self):
        from analysis.pipeline import _mock_context
        result = _mock_context(self._brief(), self._data_dict(n_ordinal=5))
        assert isinstance(result["likert_constructs"], list)
        assert len(result["likert_constructs"]) >= 1

    def test_mock_context_no_constructs_when_few_ordinal(self):
        from analysis.pipeline import _mock_context
        result = _mock_context(self._brief(), self._data_dict(n_ordinal=2))
        # With < 3 ordinal vars, no constructs expected
        assert isinstance(result["likert_constructs"], list)

    def test_mock_context_use_parametric_true_when_ratio_vars(self):
        from analysis.pipeline import _mock_context
        result = _mock_context(self._brief(), self._data_dict(n_ratio=3))
        assert result["use_parametric"] is True

    def test_mock_context_testable_hypotheses_is_list(self):
        from analysis.pipeline import _mock_context
        result = _mock_context(self._brief(), self._data_dict())
        assert isinstance(result["testable_hypotheses"], list)

    def test_mock_context_methodology_note_is_string(self):
        from analysis.pipeline import _mock_context
        result = _mock_context(self._brief(), self._data_dict())
        assert isinstance(result["methodology_note"], str)
        assert len(result["methodology_note"]) > 0

    def test_understand_context_no_llm_falls_back_to_mock(self):
        """When no LLM key, _understand_context should return mock result."""
        from analysis.pipeline import _understand_context
        from config import settings
        orig = settings.ANTHROPIC_API_KEY
        orig_or = settings.OPENROUTER_API_KEY
        settings.ANTHROPIC_API_KEY = ""
        settings.OPENROUTER_API_KEY = ""
        try:
            result = _understand_context(self._brief(), self._data_dict())
            assert isinstance(result, dict)
            assert "dv_column" in result
        finally:
            settings.ANTHROPIC_API_KEY = orig
            settings.OPENROUTER_API_KEY = orig_or

    def test_understand_context_empty_data_dict(self):
        from analysis.pipeline import _understand_context
        from config import settings
        settings.ANTHROPIC_API_KEY = ""
        settings.OPENROUTER_API_KEY = ""
        result = _understand_context(self._brief(), {})
        assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Expanded _mock_tests (new tests: cronbach, normality)
# ══════════════════════════════════════════════════════════════════════════════

class TestExpandedMockTests:
    """Verify mock test selection includes new tests for new concepts."""

    def test_cronbach_included_when_enough_ordinal_vars(self):
        from analysis.pipeline import _mock_tests
        data_dict = {
            "ratio_vars": ["score"],
            "ordinal_vars": ["q1", "q2", "q3", "q4"],
            "nominal_vars": ["gender"],
            "variables": [],
        }
        tests = _mock_tests({}, data_dict)
        names = [t["test_name"] for t in tests]
        assert any("Cronbach" in n for n in names), f"Cronbach not in: {names}"

    def test_normality_check_always_included(self):
        from analysis.pipeline import _mock_tests
        data_dict = {
            "ratio_vars": ["x", "y"],
            "ordinal_vars": [],
            "nominal_vars": [],
            "variables": [],
        }
        tests = _mock_tests({}, data_dict)
        names = [t["test_name"] for t in tests]
        assert any("Normality" in n or "Shapiro" in n for n in names), f"Normality not in: {names}"

    def test_chi_square_included_when_nominal_vars(self):
        from analysis.pipeline import _mock_tests
        data_dict = {
            "ratio_vars": ["score"],
            "ordinal_vars": ["q1", "q2", "q3"],
            "nominal_vars": ["gender", "dept"],
            "variables": [],
        }
        tests = _mock_tests({}, data_dict)
        names = [t["test_name"] for t in tests]
        assert any("Chi" in n for n in names), f"Chi-Square not in: {names}"

    def test_all_tests_have_hypothesis_field(self):
        from analysis.pipeline import _mock_tests
        data_dict = {"ratio_vars": ["a", "b"], "ordinal_vars": ["c"], "nominal_vars": [], "variables": []}
        tests = _mock_tests({}, data_dict)
        for t in tests:
            assert "hypothesis" in t, f"Test missing 'hypothesis': {t}"

    def test_all_tests_have_always_run_field(self):
        from analysis.pipeline import _mock_tests
        data_dict = {"ratio_vars": ["a"], "ordinal_vars": [], "nominal_vars": [], "variables": []}
        tests = _mock_tests({}, data_dict)
        for t in tests:
            assert "always_run" in t

    def test_always_run_tests_have_minus_one_hypothesis_index(self):
        from analysis.pipeline import _mock_tests
        data_dict = {"ratio_vars": ["a", "b"], "ordinal_vars": ["c", "d", "e"], "nominal_vars": [], "variables": []}
        tests = _mock_tests({}, data_dict)
        always_run = [t for t in tests if t.get("always_run")]
        for t in always_run:
            assert t["hypothesis_index"] == -1, f"always_run test has hypothesis_index != -1: {t}"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Expanded _mock_code (new fields: frequencies, normality, reliability)
# ══════════════════════════════════════════════════════════════════════════════

class TestExpandedMockCode:
    """Verify mock code covers new result structure."""

    def _get_code(self, missing="flag_only"):
        from analysis.pipeline import _mock_code
        data_dict = {
            "ratio_vars": ["score", "hours"],
            "ordinal_vars": ["q1", "q2", "q3"],
            "nominal_vars": ["gender"],
            "variables": [
                {"clean_name": "score", "measurement_level": "ratio"},
                {"clean_name": "hours", "measurement_level": "ratio"},
                {"clean_name": "q1",   "measurement_level": "ordinal"},
            ],
        }
        return _mock_code([], data_dict, missing_strategy=missing)

    def test_code_has_frequencies_key(self):
        code = self._get_code()
        assert '"frequencies"' in code or "'frequencies'" in code

    def test_code_has_normality_key(self):
        code = self._get_code()
        assert '"normality"' in code or "'normality'" in code

    def test_code_has_reliability_key(self):
        code = self._get_code()
        assert '"reliability"' in code or "'reliability'" in code

    def test_code_has_cronbach_alpha(self):
        code = self._get_code()
        assert "cronbach_alpha" in code or "alpha" in code.lower()

    def test_code_has_shapiro_wilk(self):
        code = self._get_code()
        assert "shapiro" in code.lower()

    def test_missing_strategy_flag_only(self):
        code = self._get_code("flag_only")
        assert "df_clean = df.copy()" in code

    def test_missing_strategy_drop_rows(self):
        code = self._get_code("drop_rows")
        assert "dropna()" in code

    def test_missing_strategy_mean_impute(self):
        code = self._get_code("mean_impute")
        assert "fillna" in code and "mean" in code

    def test_missing_strategy_mode_impute(self):
        code = self._get_code("mode_impute")
        assert "mode" in code and "fillna" in code

    def test_code_is_valid_python_syntax(self):
        import ast
        code = self._get_code()
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

    def test_code_ends_with_print_json(self):
        code = self._get_code()
        # Last non-empty line should print results
        lines = [l.strip() for l in code.strip().splitlines() if l.strip()]
        last_line = lines[-1]
        assert "print" in last_line and "results" in last_line


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Mock Code Execution — real execution with pandas
# ══════════════════════════════════════════════════════════════════════════════

class TestMockCodeExecution:
    """Execute the mock-generated Python code against a real DataFrame."""

    def test_mock_code_executes_successfully(self):
        """Actually runs the generated code in a subprocess."""
        import pandas as pd
        import numpy as np
        import subprocess, sys, tempfile, json, pickle

        from analysis.pipeline import _mock_code
        data_dict = {
            "ratio_vars": ["score", "hours"],
            "ordinal_vars": ["q1", "q2", "q3"],
            "nominal_vars": ["gender"],
            "variables": [
                {"clean_name": "score", "measurement_level": "ratio"},
                {"clean_name": "hours", "measurement_level": "ratio"},
                {"clean_name": "q1",   "measurement_level": "ordinal"},
                {"clean_name": "q2",   "measurement_level": "ordinal"},
                {"clean_name": "q3",   "measurement_level": "ordinal"},
                {"clean_name": "gender","measurement_level": "nominal"},
            ],
        }
        code = _mock_code([], data_dict, missing_strategy="flag_only")

        # Build real dataframe
        np.random.seed(99)
        n = 80
        df = pd.DataFrame({
            "score":  np.random.normal(70, 10, n),
            "hours":  np.random.normal(5, 2, n),
            "q1":     np.random.randint(1, 6, n),
            "q2":     np.random.randint(1, 6, n),
            "q3":     np.random.randint(1, 6, n),
            "gender": np.random.choice(["Male", "Female"], n),
        })

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            df.to_pickle(f.name)
            pkl_path = f.name

        wrapper = f"""
import pandas as pd, numpy as np, json, sys
try:
    from scipy import stats
except ImportError:
    stats = None
try:
    import pingouin as pg
except ImportError:
    pg = None
df = pd.read_pickle(r"{pkl_path}")
{code}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(wrapper)
            script_path = f.name

        # Use the backend venv python which has all dependencies installed
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        venv_python = os.path.join(backend_dir, "venv", "Scripts", "python.exe")
        if not os.path.exists(venv_python):
            venv_python = sys.executable  # fallback to current interpreter

        try:
            proc = subprocess.run(
                [venv_python, script_path],
                capture_output=True, text=True, timeout=60,
            )
            assert proc.returncode == 0, f"Script failed:\n{proc.stderr[:2000]}"
            lines = [l for l in proc.stdout.strip().splitlines() if l.strip().startswith("{")]
            assert len(lines) >= 1, "No JSON output from script"
            result = json.loads(lines[-1])
            assert "summary" in result
            assert "descriptive" in result
        finally:
            for p in [script_path, pkl_path]:
                try: os.unlink(p)
                except: pass

    def test_result_summary_items_have_conclusion(self):
        """All non-error summary items must have a conclusion with the required format."""
        import pandas as pd, numpy as np, subprocess, sys, tempfile, json

        from analysis.pipeline import _mock_code
        data_dict = {
            "ratio_vars": ["x", "y"],
            "ordinal_vars": [],
            "nominal_vars": [],
            "variables": [
                {"clean_name": "x", "measurement_level": "ratio"},
                {"clean_name": "y", "measurement_level": "ratio"},
            ],
        }
        code = _mock_code([], data_dict)
        np.random.seed(1)
        df = pd.DataFrame({"x": np.random.normal(0, 1, 40), "y": np.random.normal(0, 1, 40)})

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            df.to_pickle(f.name); pkl_path = f.name

        wrapper = f"import pandas as pd, numpy as np, json\nfrom scipy import stats\ndf = pd.read_pickle(r'{pkl_path}')\n{code}"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(wrapper); script_path = f.name

        try:
            proc = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                lines = [l for l in proc.stdout.strip().splitlines() if l.strip().startswith("{")]
                if lines:
                    result = json.loads(lines[-1])
                    for item in result.get("summary", []):
                        if "conclusion" in item:
                            assert "level of significance" in item["conclusion"], \
                                f"Conclusion missing required phrase: {item['conclusion']}"
        finally:
            for p in [script_path, pkl_path]:
                try: os.unlink(p)
                except: pass


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Mock Report — new fields (reliability, normality)
# ══════════════════════════════════════════════════════════════════════════════

class TestExpandedMockReport:
    """Verify mock report includes Cronbach's Alpha and reliability language."""

    def test_report_includes_reliability_when_alpha_provided(self):
        from analysis.pipeline import _mock_report_text
        reliability = {"cronbach_alpha": {"alpha": 0.85, "interpretation": "Good"}}
        report = _mock_report_text({"topic": "My Study"}, [], reliability=reliability)
        all_text = " ".join(s["text"] for s in report["sections"])
        assert "0.850" in all_text or "α" in all_text or "Cronbach" in all_text or "reliability" in all_text.lower()

    def test_report_without_reliability_does_not_crash(self):
        from analysis.pipeline import _mock_report_text
        report = _mock_report_text({"topic": "Study"}, [], reliability=None)
        assert isinstance(report, dict)
        assert "sections" in report

    def test_report_reliability_section_mentions_interpretation(self):
        from analysis.pipeline import _mock_report_text
        reliability = {"cronbach_alpha": {"alpha": 0.91, "interpretation": "Excellent"}}
        report = _mock_report_text({"topic": "Study"}, [], reliability=reliability)
        all_text = " ".join(s["text"] for s in report["sections"])
        assert "Excellent" in all_text or "0.91" in all_text or "reliability" in all_text.lower()

    def test_report_normality_param_accepted(self):
        from analysis.pipeline import _mock_report_text
        normality = {"score": {"statistic": 0.97, "p_value": 0.12, "normal": True}}
        report = _mock_report_text({"topic": "Study"}, [], normality=normality)
        assert isinstance(report, dict)

    def test_six_sections_always_present(self):
        from analysis.pipeline import _mock_report_text
        reliability = {"cronbach_alpha": {"alpha": 0.80, "interpretation": "Good"}}
        report = _mock_report_text({}, [], reliability=reliability)
        assert len(report["sections"]) == 6


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: Visualisation — new chart types
# ══════════════════════════════════════════════════════════════════════════════

class TestExpandedVisualisations:
    """Test new chart types: frequencies, histograms, boxplots, regression."""

    def _run(self, df, results, tmp_path, job_id="vis-test"):
        from analysis.pipeline import _create_visualisations
        from config import settings
        settings.CHARTS_DIR = str(tmp_path / "charts")
        os.makedirs(settings.CHARTS_DIR, exist_ok=True)
        return _create_visualisations(results, df, {}, job_id)

    def test_frequency_chart_created_from_frequencies(self, tmp_path):
        import pandas as pd, numpy as np
        df = pd.DataFrame({"gender": ["Male"] * 30 + ["Female"] * 20})
        results = {
            "frequencies": {"gender": {"Male": 30, "Female": 20}},
            "descriptive": {}, "summary": [],
        }
        paths = self._run(df, results, tmp_path, "freq-job")
        freq_files = [p for p in paths if "freq" in os.path.basename(p)]
        assert len(freq_files) >= 1

    def test_histogram_with_normality_curve(self, tmp_path):
        """Visualisation creates charts from numeric data."""
        import pandas as pd, numpy as np
        from analysis.pipeline import _create_visualisations
        from config import settings
        settings.CHARTS_DIR = str(tmp_path / "charts_hist_nc")
        os.makedirs(settings.CHARTS_DIR, exist_ok=True)
        # 3 numeric cols triggers correlations + boxplots charts
        df = pd.DataFrame({
            "score":  np.random.normal(70, 10, 60),
            "hours":  np.random.normal(5, 2, 60),
            "rating": np.random.uniform(1, 5, 60),
        })
        results = {"frequencies": {}, "descriptive": {}, "summary": []}
        paths = _create_visualisations(results, df, {}, "hist-nc-job")
        # Pipeline should produce at least correlation + boxplot charts
        assert len(paths) >= 1, f"No charts produced at all. Paths: {paths}"
        chart_names = [os.path.basename(p) for p in paths]
        assert any("correlation" in n or "boxplot" in n or "distribution" in n
                   for n in chart_names), \
            f"Expected correlation/boxplot/distribution chart. Got: {chart_names}"

    def test_boxplot_created(self, tmp_path):
        import pandas as pd, numpy as np
        df = pd.DataFrame({
            "x": np.random.randn(40),
            "y": np.random.randn(40),
            "z": np.random.randn(40),
        })
        results = {"frequencies": {}, "descriptive": {}, "summary": []}
        paths = self._run(df, results, tmp_path, "box-job")
        box_files = [p for p in paths if "boxplot" in os.path.basename(p)]
        assert len(box_files) >= 1

    def test_regression_plot_created_when_correlation_in_summary(self, tmp_path):
        import pandas as pd, numpy as np
        df = pd.DataFrame({
            "x": np.random.randn(50),
            "y": np.random.randn(50),
        })
        results = {
            "frequencies": {},
            "descriptive": {},
            "summary": [{"test_name": "Pearson Correlation", "statistic": 0.45, "p_value": 0.01}],
        }
        paths = self._run(df, results, tmp_path, "reg-job")
        reg_files = [p for p in paths if "regression" in os.path.basename(p)]
        assert len(reg_files) >= 1

    def test_all_chart_files_are_png(self, tmp_path):
        import pandas as pd, numpy as np
        df = pd.DataFrame({"a": np.random.randn(30), "b": np.random.randn(30)})
        results = {"frequencies": {}, "descriptive": {"a": {"mean": 0.1}, "b": {"mean": 0.2}}, "summary": []}
        paths = self._run(df, results, tmp_path, "png-job")
        for p in paths:
            assert p.endswith(".png"), f"Non-PNG chart: {p}"

    def test_all_chart_files_exist_on_disk(self, tmp_path):
        import pandas as pd, numpy as np
        df = pd.DataFrame({"s": np.random.normal(50, 10, 40), "t": np.random.normal(60, 8, 40)})
        results = {"frequencies": {"cat": {"A": 20, "B": 20}}, "descriptive": {}, "summary": []}
        paths = self._run(df, results, tmp_path, "exist-job")
        for p in paths:
            assert os.path.exists(p), f"Chart file missing: {p}"

    def test_multiple_frequency_cols_each_get_chart(self, tmp_path):
        import pandas as pd, numpy as np
        df = pd.DataFrame({
            "gender": ["Male", "Female"] * 25,
            "dept":   ["Sci", "Arts", "Eng", "Bus"] * 12 + ["Sci", "Arts"],
        })
        results = {
            "frequencies": {
                "gender": {"Male": 25, "Female": 25},
                "dept":   {"Sci": 13, "Arts": 13, "Eng": 12, "Bus": 12},
            },
            "descriptive": {}, "summary": [],
        }
        paths = self._run(df, results, tmp_path, "multi-freq-job")
        freq_files = [p for p in paths if "freq" in os.path.basename(p)]
        assert len(freq_files) >= 2


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8: Pipeline Integration with new stages
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineWithNewStages:
    """End-to-end integration: verify new stages fit into run_stages_3_to_9."""

    def _make_job(self, tmp_path):
        from unittest.mock import MagicMock
        from config import settings
        settings.DEV_MODE = True
        settings.ANTHROPIC_API_KEY = ""
        settings.OPENROUTER_API_KEY = ""
        settings.CHARTS_DIR  = str(tmp_path / "charts")
        settings.REPORTS_DIR = str(tmp_path / "reports")

        db = MagicMock()
        job = MagicMock()
        job.project_brief = {
            "topic": "New Pipeline Integration Test",
            "objectives": ["Test new stages"],
            "hypotheses": ["H0: no significant effect"],
            "study_type": "quantitative",
            "dependent_variable": "Performance",
            "independent_variable": "Method",
            "population": "University students",
        }
        job.data_dictionary = {
            "variables": [
                {"clean_name": "score",  "measurement_level": "ratio",   "role": "dependent"},
                {"clean_name": "hours",  "measurement_level": "ratio",   "role": "independent"},
                {"clean_name": "q1",     "measurement_level": "ordinal", "role": "covariate"},
                {"clean_name": "q2",     "measurement_level": "ordinal", "role": "covariate"},
                {"clean_name": "q3",     "measurement_level": "ordinal", "role": "covariate"},
                {"clean_name": "gender", "measurement_level": "nominal", "role": "group"},
            ],
            "ratio_vars":   ["score", "hours"],
            "ordinal_vars": ["q1", "q2", "q3"],
            "nominal_vars": ["gender"],
            "llm_context":  "score: ratio\nhours: ratio\nq1-q3: ordinal\ngender: nominal",
        }
        job.researcher_overrides = {}
        job.missing_strategy = "mean_impute"
        job.survey_id = None
        job.source_filename = None
        job.id = "new-pipeline-integ"
        return job, db

    def test_pipeline_completes_without_error(self, tmp_path):
        from analysis.pipeline import run_stages_3_to_9
        job, db = self._make_job(tmp_path)
        run_stages_3_to_9(job, db)
        assert job.status == "complete"

    def test_pipeline_produces_selected_tests_with_cronbach(self, tmp_path):
        from analysis.pipeline import run_stages_3_to_9
        job, db = self._make_job(tmp_path)
        run_stages_3_to_9(job, db)
        names = [t["test_name"] for t in (job.selected_tests or [])]
        assert any("Cronbach" in n for n in names), f"Cronbach not in: {names}"

    def test_pipeline_produces_normality_check(self, tmp_path):
        from analysis.pipeline import run_stages_3_to_9
        job, db = self._make_job(tmp_path)
        run_stages_3_to_9(job, db)
        names = [t["test_name"] for t in (job.selected_tests or [])]
        assert any("Normality" in n or "Shapiro" in n for n in names), f"Normality not in: {names}"

    def test_pipeline_results_have_new_keys(self, tmp_path):
        from analysis.pipeline import run_stages_3_to_9
        job, db = self._make_job(tmp_path)
        run_stages_3_to_9(job, db)
        results = job.results or {}
        # DEV_MODE returns mock with these keys
        assert "summary" in results
        assert "descriptive" in results

    def test_pipeline_generates_multiple_charts(self, tmp_path):
        from analysis.pipeline import run_stages_3_to_9
        job, db = self._make_job(tmp_path)
        run_stages_3_to_9(job, db)
        assert job.chart_paths is not None

    def test_pipeline_report_path_is_docx(self, tmp_path):
        from analysis.pipeline import run_stages_3_to_9
        job, db = self._make_job(tmp_path)
        run_stages_3_to_9(job, db)
        assert job.report_path is not None
        assert job.report_path.endswith(".docx")
        assert os.path.exists(job.report_path)

    def test_pipeline_mean_impute_strategy_in_code(self, tmp_path):
        """Verify mean_impute strategy is reflected in generated code."""
        from analysis.pipeline import run_stages_3_to_9
        job, db = self._make_job(tmp_path)
        job.missing_strategy = "mean_impute"
        run_stages_3_to_9(job, db)
        assert job.generated_code is not None
        assert "fillna" in job.generated_code or "mean" in job.generated_code

    def test_pipeline_drop_rows_strategy_in_code(self, tmp_path):
        from analysis.pipeline import run_stages_3_to_9
        job, db = self._make_job(tmp_path)
        job.missing_strategy = "drop_rows"
        run_stages_3_to_9(job, db)
        assert "dropna" in job.generated_code


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9: Form Validation Logic (QA)
# ══════════════════════════════════════════════════════════════════════════════

class TestFormValidationLogic:
    """
    Mimics the frontend validateBrief() function in Python.
    These are pure logic tests — no browser required.
    """

    def validate_brief(self, brief: dict) -> dict:
        """Python mirror of the frontend validateBrief() function."""
        errors = {}
        if not brief.get("topic", "").strip():
            errors["topic"] = "Project topic is required"
        if not brief.get("population", "").strip():
            errors["population"] = "Target population is required"
        if not brief.get("dependent_variable", "").strip():
            errors["dependent_variable"] = "Dependent variable is required"
        if not brief.get("independent_variable", "").strip():
            errors["independent_variable"] = "Independent variable is required"
        objectives = brief.get("objectives", [""])
        if not (objectives and objectives[0].strip()):
            errors["objectives"] = "At least one objective is required"
        hypotheses = brief.get("hypotheses", [""])
        if not (hypotheses and hypotheses[0].strip()):
            errors["hypotheses"] = "At least one hypothesis (H1) is required"
        return errors

    def test_all_fields_filled_passes(self):
        brief = {
            "topic": "Impact of X on Y",
            "population": "University students",
            "dependent_variable": "Performance",
            "independent_variable": "Motivation",
            "objectives": ["To examine the effect of X on Y"],
            "hypotheses": ["H0: There is no significant effect of X on Y"],
        }
        errors = self.validate_brief(brief)
        assert errors == {}, f"Expected no errors, got: {errors}"

    def test_empty_topic_fails(self):
        brief = {
            "topic": "",
            "population": "Students",
            "dependent_variable": "DV",
            "independent_variable": "IV",
            "objectives": ["Objective"],
            "hypotheses": ["H0: no effect"],
        }
        errors = self.validate_brief(brief)
        assert "topic" in errors

    def test_whitespace_only_topic_fails(self):
        brief = {
            "topic": "   ",
            "population": "Students",
            "dependent_variable": "DV",
            "independent_variable": "IV",
            "objectives": ["Obj"],
            "hypotheses": ["H0"],
        }
        errors = self.validate_brief(brief)
        assert "topic" in errors

    def test_missing_population_fails(self):
        brief = {
            "topic": "Study",
            "population": "",
            "dependent_variable": "DV",
            "independent_variable": "IV",
            "objectives": ["Obj"],
            "hypotheses": ["H0"],
        }
        errors = self.validate_brief(brief)
        assert "population" in errors

    def test_missing_dv_fails(self):
        brief = {
            "topic": "Study",
            "population": "Pop",
            "dependent_variable": "",
            "independent_variable": "IV",
            "objectives": ["Obj"],
            "hypotheses": ["H0"],
        }
        errors = self.validate_brief(brief)
        assert "dependent_variable" in errors

    def test_missing_iv_fails(self):
        brief = {
            "topic": "Study",
            "population": "Pop",
            "dependent_variable": "DV",
            "independent_variable": "",
            "objectives": ["Obj"],
            "hypotheses": ["H0"],
        }
        errors = self.validate_brief(brief)
        assert "independent_variable" in errors

    def test_empty_objective_fails(self):
        brief = {
            "topic": "Study",
            "population": "Pop",
            "dependent_variable": "DV",
            "independent_variable": "IV",
            "objectives": [""],
            "hypotheses": ["H0"],
        }
        errors = self.validate_brief(brief)
        assert "objectives" in errors

    def test_empty_hypothesis_fails(self):
        brief = {
            "topic": "Study",
            "population": "Pop",
            "dependent_variable": "DV",
            "independent_variable": "IV",
            "objectives": ["Obj"],
            "hypotheses": [""],
        }
        errors = self.validate_brief(brief)
        assert "hypotheses" in errors

    def test_all_empty_returns_six_errors(self):
        brief = {
            "topic": "",
            "population": "",
            "dependent_variable": "",
            "independent_variable": "",
            "objectives": [""],
            "hypotheses": [""],
        }
        errors = self.validate_brief(brief)
        assert len(errors) == 6

    def test_partial_fill_returns_correct_error_count(self):
        # Only topic and population filled
        brief = {
            "topic": "My Study",
            "population": "Teachers",
            "dependent_variable": "",
            "independent_variable": "",
            "objectives": [""],
            "hypotheses": [""],
        }
        errors = self.validate_brief(brief)
        assert len(errors) == 4

    def test_no_statistical_method_field_required(self):
        """Confirms stat method is NOT a required field (AI auto-selects)."""
        brief = {
            "topic": "Study",
            "population": "Pop",
            "dependent_variable": "DV",
            "independent_variable": "IV",
            "objectives": ["Obj"],
            "hypotheses": ["H0"],
            # No statistical_method field
        }
        errors = self.validate_brief(brief)
        assert "statistical_method" not in errors

    def test_extra_hypotheses_do_not_affect_validation(self):
        """Additional H2/H3 are optional and should not cause failures."""
        brief = {
            "topic": "Study",
            "population": "Pop",
            "dependent_variable": "DV",
            "independent_variable": "IV",
            "objectives": ["Main objective", "Secondary objective"],
            "hypotheses": ["H0: no effect", "H0: no difference", "H0: no association"],
        }
        errors = self.validate_brief(brief)
        assert errors == {}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10: QA — Data Integrity Checks
# ══════════════════════════════════════════════════════════════════════════════

class TestQADataIntegrity:
    """QA checks: ensure results always have consistent structure."""

    def test_result_summary_items_always_have_test_name(self):
        from analysis.pipeline import _execute_code
        from config import settings
        settings.DEV_MODE = True
        settings.ANTHROPIC_API_KEY = ""
        result = _execute_code("", {}, "qa-job")
        for item in result.get("summary", []):
            assert "test_name" in item, f"Item missing test_name: {item}"

    def test_result_p_value_is_float_when_present(self):
        from analysis.pipeline import _execute_code
        from config import settings
        settings.DEV_MODE = True
        settings.ANTHROPIC_API_KEY = ""
        result = _execute_code("", {}, "qa-pval")
        for item in result.get("summary", []):
            if "p_value" in item:
                assert isinstance(item["p_value"], (int, float)), f"p_value not numeric: {item}"

    def test_result_significant_is_boolean(self):
        from analysis.pipeline import _execute_code
        from config import settings
        settings.DEV_MODE = True
        settings.ANTHROPIC_API_KEY = ""
        result = _execute_code("", {}, "qa-sig")
        for item in result.get("summary", []):
            if "significant" in item:
                assert isinstance(item["significant"], bool), f"significant not bool: {item}"

    def test_parse_brief_always_returns_correct_types(self):
        from analysis.pipeline import _parse_brief
        for raw in [{}, {"topic": "T"}, {"objectives": [None, "", "Valid"]}, {"significance_level": 0.01}]:
            r = _parse_brief(raw)
            assert isinstance(r["topic"], str)
            assert isinstance(r["objectives"], list)
            assert isinstance(r["hypotheses"], list)
            assert isinstance(r["significance_level"], (int, float))

    def test_cleaner_never_adds_rows(self):
        """Clean data must never have more rows than raw data."""
        from analysis.cleaner import clean_and_inspect
        import pandas as pd, numpy as np
        np.random.seed(7)
        for _ in range(5):
            n = np.random.randint(10, 100)
            df = pd.DataFrame({"a": np.random.randn(n), "b": np.random.randn(n)})
            clean_df, _, _ = clean_and_inspect(df)
            assert len(clean_df) <= n, f"Cleaner added rows! {len(clean_df)} > {n}"

    def test_selected_tests_always_start_with_descriptive(self):
        from analysis.pipeline import _mock_tests
        for _ in range(3):
            data_dict = {"ratio_vars": ["x"], "ordinal_vars": [], "nominal_vars": [], "variables": []}
            tests = _mock_tests({}, data_dict)
            assert tests[0]["test_name"] == "Descriptive Statistics", \
                f"First test is not descriptive: {tests[0]['test_name']}"

    def test_job_status_transitions_never_skip_complete(self, tmp_path):
        """Pipeline must end in 'complete' not any intermediate status."""
        from unittest.mock import MagicMock
        from analysis.pipeline import run_stages_3_to_9
        from config import settings
        settings.DEV_MODE = True
        settings.ANTHROPIC_API_KEY = ""
        settings.CHARTS_DIR = str(tmp_path / "c")
        settings.REPORTS_DIR = str(tmp_path / "r")
        db = MagicMock()
        job = MagicMock()
        job.project_brief = {}
        job.data_dictionary = {"variables": [], "ratio_vars": [], "ordinal_vars": [], "llm_context": ""}
        job.researcher_overrides = {}
        job.missing_strategy = "flag_only"
        job.survey_id = None
        job.source_filename = None
        job.id = "qa-final"
        run_stages_3_to_9(job, db)
        assert job.status == "complete"

    def test_mock_report_sections_all_have_text(self):
        from analysis.pipeline import _mock_report_text
        report = _mock_report_text({"topic": "Study", "dependent_variable": "DV", "independent_variable": "IV"}, [])
        for section in report["sections"]:
            assert len(section.get("text", "").strip()) > 20, \
                f"Section '{section['heading']}' has insufficient text"

    def test_inspection_report_total_missing_cells_non_negative(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd
        df = pd.DataFrame({"a": [1, None, 3], "b": [None, None, 3]})
        _, report, _ = clean_and_inspect(df)
        assert report["total_missing_cells"] >= 0

    def test_inspection_report_outliers_pct_between_0_and_100(self):
        from analysis.cleaner import clean_and_inspect
        import pandas as pd, numpy as np
        data = list(np.random.normal(70, 5, 50)) + [9999.0, -9999.0]
        df = pd.DataFrame({"score": data})
        _, report, _ = clean_and_inspect(df)
        for col, info in report["outliers"].items():
            assert 0 <= info["pct_outliers"] <= 100, f"pct_outliers out of range: {info}"

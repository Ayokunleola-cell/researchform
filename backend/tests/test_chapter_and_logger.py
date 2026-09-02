"""
Tests for the chapter extractor and training data logger.
"""
import json
import os
import tempfile
import pytest


# ─── Extractor tests ───────────────────────────────────────────────────────────

class TestExtractor:
    def test_extract_txt_file(self):
        from analysis.extractor import extract_text_from_file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("This is chapter one. " * 50)
            path = f.name
        try:
            text = extract_text_from_file(path)
            assert len(text) > 0
            assert "chapter one" in text
        finally:
            os.unlink(path)

    def test_extract_txt_truncates_at_max_chars(self):
        from analysis.extractor import extract_text_from_file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("A" * 20000)
            path = f.name
        try:
            text = extract_text_from_file(path, max_chars=8000)
            assert len(text) == 8000
        finally:
            os.unlink(path)

    def test_unsupported_extension_returns_empty(self):
        from analysis.extractor import extract_text_from_file
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"some bytes")
            path = f.name
        try:
            text = extract_text_from_file(path)
            assert text == ""
        finally:
            os.unlink(path)

    def test_missing_file_returns_empty(self):
        from analysis.extractor import extract_text_from_file
        text = extract_text_from_file("/nonexistent/path/file.txt")
        assert text == ""

    def test_extract_docx(self):
        """Test Word document extraction using python-docx."""
        from docx import Document
        from analysis.extractor import extract_text_from_file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            path = f.name
        try:
            doc = Document()
            doc.add_paragraph("Background of the study.")
            doc.add_paragraph("This research examines the relationship between variables.")
            doc.save(path)
            text = extract_text_from_file(path)
            assert "Background of the study" in text
            assert "relationship between variables" in text
        finally:
            os.unlink(path)

    def test_extract_chapters_dict(self):
        from analysis.extractor import extract_chapters
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Literature review content.")
            path = f.name
        try:
            result = extract_chapters({"chapter2": path, "chapter1": "", "chapter3": "/nonexistent.docx"})
            assert "chapter2" in result
            assert "Literature review" in result["chapter2"]
            assert result.get("chapter3", "") == "" or "[Could not" in result.get("chapter3", "")
        finally:
            os.unlink(path)


# ─── Training Data Logger tests ────────────────────────────────────────────────

class FakeJob:
    """Minimal mock of AnalysisJob for testing the logger."""
    def __init__(self):
        self.id = "test-job-001"
        self.data_dictionary = {
            "variables": [{"clean_name": "gender"}, {"clean_name": "gpa"}],
            "ordinal_vars": ["q1", "q2", "q3"],
            "ratio_vars": ["gpa", "hours_studied"],
        }
        self.selected_tests = [
            {"test_name": "Pearson Correlation", "variables": ["gpa", "hours_studied"]}
        ]
        self.generated_code = "import pandas as pd\nresults = {}\nprint(results)"
        self.missing_strategy = "mean_impute"
        self.chapter_texts = {"chapter2": "Bandura (1977) posited that..."}


class TestTrainingLogger:
    def test_saves_three_examples_per_job(self, tmp_path, monkeypatch):
        """Logger should produce exactly 3 JSONL lines per job (one per task)."""
        import analysis.pipeline as pipeline
        monkeypatch.setattr(pipeline.settings, "STORAGE_DIR", str(tmp_path))

        brief = {
            "topic": "Effect of social media on academic performance",
            "dependent_variable": "GPA",
            "independent_variable": "Social media hours",
            "population": "200-level students, UNILAG",
            "objectives": ["To examine the relationship between social media and GPA"],
            "hypotheses": ["H01: There is no significant relationship..."],
        }
        results = {
            "summary": [{"test_name": "Pearson Correlation", "statistic": 0.45, "p_value": 0.012}],
            "descriptive": {"gpa": {"mean": 3.2, "std": 0.6}},
        }
        chapter_texts = {"chapter2": "Bandura (1977) social learning theory..."}
        report_text = {"chapter_title": "CHAPTER FOUR", "sections": [{"heading": "4.1", "text": "Introduction..."}]}

        job = FakeJob()
        pipeline._save_training_example(job, brief, results, chapter_texts, report_text)

        # Check individual job file
        job_file = tmp_path / "training_data" / "test-job-001.jsonl"
        assert job_file.exists(), "Individual job JSONL file not created"
        lines = job_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3, f"Expected 3 training examples, got {len(lines)}"

        # Verify task types
        tasks = [json.loads(l)["task"] for l in lines]
        assert "test_selection" in tasks
        assert "code_generation" in tasks
        assert "report_writing" in tasks

    def test_master_file_appends(self, tmp_path, monkeypatch):
        """Each call should append 3 lines to the master JSONL file."""
        import analysis.pipeline as pipeline
        monkeypatch.setattr(pipeline.settings, "STORAGE_DIR", str(tmp_path))

        brief = {"topic": "Test", "dependent_variable": "DV", "independent_variable": "IV",
                 "population": "Students", "objectives": [], "hypotheses": []}
        results = {"summary": [], "descriptive": {}}
        report_text = {"sections": []}

        job1 = FakeJob()
        job1.id = "job-001"
        job2 = FakeJob()
        job2.id = "job-002"

        pipeline._save_training_example(job1, brief, results, {}, report_text)
        pipeline._save_training_example(job2, brief, results, {}, report_text)

        master = tmp_path / "training_data" / "researchform_training.jsonl"
        lines = master.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 6, f"Expected 6 lines (2 jobs × 3), got {len(lines)}"

    def test_stats_file_updated(self, tmp_path, monkeypatch):
        """Stats file should track job count and chapter usage."""
        import analysis.pipeline as pipeline
        monkeypatch.setattr(pipeline.settings, "STORAGE_DIR", str(tmp_path))

        brief = {"topic": "Test", "dependent_variable": "DV", "independent_variable": "IV",
                 "population": "", "objectives": [], "hypotheses": []}
        job = FakeJob()
        pipeline._save_training_example(job, brief, {}, {"chapter2": "some text"}, {})

        stats_file = tmp_path / "training_data" / "stats.json"
        assert stats_file.exists()
        stats = json.loads(stats_file.read_text())
        assert stats["total_jobs"] == 1
        assert stats["total_examples"] == 3
        assert stats["jobs_with_chapters"] == 1

    def test_skips_logging_when_no_real_data(self, tmp_path, monkeypatch):
        """Logger should silently skip if no selected_tests (DEV_MODE mock run)."""
        import analysis.pipeline as pipeline
        monkeypatch.setattr(pipeline.settings, "STORAGE_DIR", str(tmp_path))

        job = FakeJob()
        job.selected_tests = []
        job.generated_code = ""

        pipeline._save_training_example(job, {}, {}, {}, {})

        training_dir = tmp_path / "training_data"
        assert not training_dir.exists() or not any(training_dir.glob("*.jsonl"))

    def test_never_raises_on_bad_data(self):
        """_save_training_example must never raise — it's wrapped in try/except in pipeline."""
        import analysis.pipeline as pipeline
        # None job → guard returns early, no exception
        pipeline._save_training_example(None, None, None, None, None)
        # Empty selected_tests + generated_code → skips logging silently
        job = FakeJob()
        job.selected_tests = []
        job.generated_code = ""
        pipeline._save_training_example(job, {}, {}, {}, {})


# backend/analysis/decode/__init__.py
"""
Stage 2 — Data Decode Module
Entry points: decode_file(path), decode_from_db(survey_id, db)
Returns: {data_dictionary, warnings, n_rows, n_columns, n_complete_rows, dataframe_pkl}
"""
from .orchestrator import decode_file, decode_from_db

__all__ = ["decode_file", "decode_from_db"]

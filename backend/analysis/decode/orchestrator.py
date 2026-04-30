# backend/analysis/decode/orchestrator.py
"""
Runs the 8 decode responsibilities in fixed sequence:
2.1 Format detection & parsing
2.2 Sheet & structure normalisation
2.3 Column name sanitisation
2.4 Value label resolution
2.5 Measurement level inference
2.6 Missing value handling
2.7 Data dictionary construction
2.8 Decode report & warnings
"""
import os
import pickle
import tempfile
from datetime import datetime
from typing import Optional
try:
    import pandas as pd
except ImportError:
    pd = None

from .parsers.spss_parser import parse_spss
from .parsers.excel_parser import parse_excel
from .parsers.csv_parser import parse_csv
from .parsers.db_parser import parse_from_db
from .transforms.column_cleaner import clean_columns
from .transforms.label_resolver import resolve_labels
from .transforms.level_inferrer import infer_levels
from .transforms.missing_handler import handle_missing
from .dictionary.builder import build_dictionary


def decode_file(file_path: str) -> dict:
    """Decode an uploaded file (xlsx, csv, sav)."""
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")

    # 2.1 Parse
    if ext == "sav":
        df, meta = parse_spss(file_path)
        source_type = "spss"
    elif ext in ("xlsx", "xls"):
        df, meta = parse_excel(file_path)
        source_type = "excel"
    elif ext == "csv":
        df, meta = parse_csv(file_path)
        source_type = "csv"
    else:
        raise ValueError(f"Unsupported file type: .{ext}")

    return _run_decode(df, meta, source_type, source_filename=os.path.basename(file_path))


def decode_from_db(survey_id: str, db) -> dict:
    """Decode responses stored in the database."""
    from config import settings
    if getattr(settings, "DEV_MODE", False) and not settings.ANTHROPIC_API_KEY:
        return {
            "data_dictionary": {
                "variables": [
                    {"clean_name": "gender", "measurement_level": "nominal", "role": "independent"},
                    {"clean_name": "age", "measurement_level": "ordinal", "role": "independent"},
                    {"clean_name": "rating", "measurement_level": "ordinal", "role": "dependent"}
                ],
                "ratio_vars": [],
                "interval_vars": [],
                "ordinal_vars": ["rating"],
                "nominal_vars": ["gender", "age"]
            },
            "warnings": [],
            "n_rows": 3,
            "n_columns": 3,
            "n_complete_rows": 3,
            "dataframe_pkl": None
        }
        
    df, meta = parse_from_db(survey_id, db)
    return _run_decode(df, meta, "survey_db", survey_id=survey_id)


def _run_decode(df: pd.DataFrame, meta: dict, source_type: str,
                source_filename: str = None, survey_id: str = None) -> dict:
    warnings = []

    # 2.3 Column name sanitisation
    df, col_map = clean_columns(df, meta)

    # 2.4 Value label resolution
    df, value_labels = resolve_labels(df, meta, col_map)

    # 2.5 Measurement level inference
    levels = infer_levels(df, meta, col_map, warnings)

    # 2.6 Missing value handling
    df, missing_stats = handle_missing(df, warnings)

    # 2.7 Build data dictionary
    data_dict = build_dictionary(
        df=df,
        col_map=col_map,
        value_labels=value_labels,
        levels=levels,
        missing_stats=missing_stats,
        meta=meta,
        source_type=source_type,
        source_filename=source_filename,
        survey_id=survey_id,
        warnings=warnings,
    )

    # Pickle dataframe for pipeline stages 4-7
    pkl_dir = "storage/dataframes"
    os.makedirs(pkl_dir, exist_ok=True)
    pkl_path = None
    if survey_id:
        pkl_path = os.path.join(pkl_dir, f"{survey_id}.pkl")
    elif source_filename:
        pkl_path = os.path.join(pkl_dir, f"{source_filename}.pkl")
    if pkl_path:
        df.to_pickle(pkl_path)

    return {
        "data_dictionary": data_dict,
        "warnings": [w if isinstance(w, dict) else w.dict() for w in warnings],
        "n_rows": len(df),
        "n_columns": len(df.columns),
        "n_complete_rows": int(df.dropna().shape[0]),
        "dataframe_pkl": pkl_path,
    }

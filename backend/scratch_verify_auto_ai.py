# backend/scratch_verify_auto_ai.py
import os
import shutil
import pandas as pd
import numpy as np
from analysis.pipeline import _select_tests, run_all_tests
from analysis.charts import create_visualisations

def test_auto_ai_pipeline():
    print("--- TESTING AI AUTO SELECTION PIPELINE ---")
    
    # 1. Synthetic dataset
    np.random.seed(42)
    n = 50
    df = pd.DataFrame({
        "age": np.random.randint(18, 65, size=n),
        "satisfaction_score": np.random.normal(70, 15, size=n),
        "income": np.random.normal(50000, 12000, size=n),
        "department": np.random.choice(["Sales", "Engineering", "HR", "Marketing"], size=n),
        "employment_type": np.random.choice(["Full-time", "Part-time"], size=n)
    })
    
    data_dict = {
        "variables": [
            {"clean_name": "age", "measurement_level": "ratio", "role": "independent"},
            {"clean_name": "satisfaction_score", "measurement_level": "ratio", "role": "dependent"},
            {"clean_name": "income", "measurement_level": "ratio", "role": "covariate"},
            {"clean_name": "department", "measurement_level": "nominal", "role": "independent"},
            {"clean_name": "employment_type", "measurement_level": "nominal", "role": "independent"},
        ],
        "ordinal_vars": [],
        "ratio_vars": ["age", "satisfaction_score", "income"],
        "nominal_vars": ["department", "employment_type"],
        "measurement_levels": {
            "age": "ratio", "satisfaction_score": "ratio", "income": "ratio",
            "department": "nominal", "employment_type": "nominal"
        }
    }
    
    brief = {
        "dependent_variable": "satisfaction_score",
        "independent_variable": "department",
        "hypotheses": ["Department affects satisfaction score"],
        "demographic_columns": ["employment_type"]
    }
    
    # 2. Test AI Auto Test Selection (auto_select=True)
    print("\n1. Testing AI Auto Technique Selection (auto_select=True)...")
    tests = _select_tests(brief, data_dict, {}, auto_select=True, user_techniques=[])
    print(f"   -> AI Selected Tests ({len(tests)} tests): {tests}")
    assert len(tests) > 0, "AI Auto test selection returned empty!"
    
    # 3. Run Statistical Engine
    print("\n2. Executing Statistical Engine...")
    results = run_all_tests(
        tests=tests,
        df=df,
        brief=brief,
        data_dict=data_dict,
        missing_strategy="flag_only"
    )
    print(f"   -> Results generated keys: {list(results.keys())}")
    
    # 4. Test AI Auto Charts & Tables Selection (auto_viz=True, auto_tables=True)
    print("\n3. Testing AI Auto Charts & Tables Generation (auto_viz=True, auto_tables=True)...")
    test_chart_dir = os.path.join(os.getcwd(), "scratch_test_charts")
    if os.path.exists(test_chart_dir):
        shutil.rmtree(test_chart_dir)
        
    chart_paths = create_visualisations(
        results=results,
        df=df,
        brief=brief,
        job_id="test_job_123",
        chart_dir=test_chart_dir,
        tests=tests,
        auto_viz=True,
        selected_viz=[],
        auto_tables=True,
        selected_tables=[]
    )
    
    print(f"   -> Total Generated Auto Artifacts: {len(chart_paths)} files")
    for p in chart_paths:
        print(f"      - {os.path.basename(p)}")
        
    assert len(chart_paths) > 0, "No charts/tables generated in auto mode!"
    
    # Cleanup test output dir
    if os.path.exists(test_chart_dir):
        shutil.rmtree(test_chart_dir)
        
    print("\n SUCCESS: All AI Auto selection modules (tests, tables, charts) verified runtime execution!")

if __name__ == "__main__":
    test_auto_ai_pipeline()

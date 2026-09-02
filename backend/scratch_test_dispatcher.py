import json
from analysis.engine.dispatcher import run_all_tests
import pandas as pd
import numpy as np

df = pd.DataFrame({
    'group': ['A', 'A', 'B', 'B', 'A', 'B'] * 5,
    'score': np.random.randn(30),
})
brief = {
    "dependent_variable": "score",
    "independent_variable": "group",
    "research_questions": ["Test?"],
    "hypotheses": ["Test!"],
    "significance_level": 0.05
}
tests = [
    {"test_function": "independent_t", "variables": ["group", "score"]}, 
    {"test_function": "simple_linear_regression", "variables": ["score", "group"]}
]
data_dict = {}

try:
    results = run_all_tests(tests=tests, df=df, brief=brief, data_dict=data_dict)
    print("Summary length:", len(results.get("summary", [])))
    print("Summary:", json.dumps(results.get("summary"), indent=2))
except Exception as e:
    import traceback
    traceback.print_exc()

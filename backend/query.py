import sys
sys.path.append('.')
from analysis.pipeline import _mock_tests

hypotheses = [
    "H1: The probability of turnover intent can be predicted from salary and emotional burnout (Logistic Regression)",
    "H2: The underlying factors of burnout can be identified via Principal Component Analysis (PCA)",
    "H3: There is a significant difference between pre-test performance and post-test performance (Paired T-test)",
    "H4: There is a significant association between department and whether an employee was promoted (Chi-Square)",
    "H5: The median emotional burnout differs between employees who were promoted and those who were not (Mann-Whitney)",
    "H6: Median performance differs significantly across various departments (Kruskal-Wallis)",
    "H7: There is a non-parametric correlation between satisfaction with manager and satisfaction with pay (Spearman)"
]
data_dict = {
    "ratio_vars": ["salary", "performance", "pre_test", "post_test"],
    "ordinal_vars": ["burnout_emotional", "burnout_usedup", "burnout_fatigue", "sat_manager", "sat_pay"],
    "nominal_vars": ["turnover_intent", "promoted", "department", "gender"]
}

tests = _mock_tests({"hypotheses": hypotheses}, data_dict)
for t in tests:
    print(t["test_function"], t["variables"])


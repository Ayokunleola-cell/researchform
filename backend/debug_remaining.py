"""Debug script for ICC and Poisson remaining failures."""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd, numpy as np

# === ICC Debug ===
rng = np.random.default_rng(42); n = 120
binary = np.where(rng.random(n) > 0.5, 1, 0)
df = pd.DataFrame({
    'likert1': rng.integers(1, 6, n),
    'likert2': rng.integers(1, 6, n),
    'likert3': rng.integers(1, 6, n),
})

from analysis.engine.tests.reliability import run_icc
r = run_icc(df, ['likert1', 'likert2', 'likert3'], {'significance_level': 0.05})
status = 'PASS' if not r.get('error') else f'FAIL: {r.get("reason")}'
print('ICC result:', status)

# Check what pingouin returns
import pingouin as pg
data_reset = df.copy()
data_reset['targets'] = range(len(data_reset))
melted = data_reset.melt(id_vars='targets', var_name='raters', value_name='ratings')
icc_res = pg.intraclass_corr(data=melted, targets='targets', raters='raters', ratings='ratings')
print('ICC columns:', list(icc_res.columns))
print('ICC types:', list(icc_res['Type']))
row = icc_res.iloc[0]
ci_col = next((c for c in ['CI95%', 'CI95'] if c in row.index), None)
print('CI column found:', ci_col)
print('row.index:', list(row.index))

# === Poisson Debug ===
print()
rng3 = np.random.default_rng(42); n = 120
groups = np.tile(['A','B','C'], n // 3 + 1)[:n]
binary = np.where(rng3.random(n) > 0.5, 1, 0)
age = rng3.normal(35, 10, n).clip(18, 80)
income = rng3.lognormal(10, 1, n)
s1 = rng3.normal(65, 12, n).clip(0, 100)
s2 = rng3.normal(70, 10, n).clip(0, 100)
s3 = rng3.normal(55, 15, n).clip(0, 100)
l1 = rng3.integers(1, 6, n); l2 = rng3.integers(1, 6, n)
l3 = rng3.integers(1, 6, n); l4 = rng3.integers(1, 6, n); l5 = rng3.integers(1, 6, n)
bi1 = rng3.integers(0, 2, n); bi2 = rng3.integers(0, 2, n)
bi3 = rng3.integers(0, 2, n); bi4 = rng3.integers(0, 2, n)
count_var = rng3.poisson(lam=5, size=n)
df2 = pd.DataFrame({'count_var': count_var, 'age': age, 'income': income})
print('count_var min:', df2.count_var.min(), 'max:', df2.count_var.max())

from analysis.engine.tests.regression import run_poisson_regression, run_negative_binomial
r2 = run_poisson_regression(df2, ['count_var', 'age', 'income'], {'significance_level': 0.05})
status2 = 'PASS' if not r2.get('error') else f'FAIL: {r2.get("reason")}'
print('Poisson result:', status2)

r3 = run_negative_binomial(df2, ['count_var', 'age', 'income'], {'significance_level': 0.05})
status3 = 'PASS' if not r3.get('error') else f'FAIL: {r3.get("reason")}'
print('NegBin result:', status3)

# backend/analysis/engine/tests/timeseries.py
"""Time series analysis — stationarity, decomposition, ARIMA, autocorrelation, forecasting."""
from __future__ import annotations
import pandas as pd
import numpy as np
from scipy import stats
from analysis.engine.schema import build_result, build_error

try:
    from statsmodels.tsa.stattools import (
        adfuller, kpss, acf, pacf, ccf, grangercausalitytests
    )
    from statsmodels.tsa.seasonal import seasonal_decompose
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    from statsmodels.stats.diagnostic import acorr_ljungbox
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.vector_ar.var_model import VAR
    _sm = True
except ImportError:
    _sm = False


def _get_series(df, variables):
    col = next((c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])), None)
    if col is None:
        return None, None
    s = df[col].dropna()
    return s, col


def run_adf_test(df, variables, brief, alpha=0.05):
    """Augmented Dickey-Fuller unit root test."""
    try:
        if not _sm:
            return build_error("ADF Test", "adf_test", "statsmodels not installed.", "pip install statsmodels")
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("ADF Test", "adf_test", "No numeric column found.", "Select a time series column.")
        result = adfuller(s, autolag="AIC")
        adf_stat, p_val, n_lags, n_obs = result[0], result[1], result[2], result[3]
        critical_vals = result[4]
        stationary = bool(p_val < alpha)
        return build_result("Augmented Dickey-Fuller Test", "adf_test",
                            "ADF", adf_stat, p_value=p_val, n=n_obs,
                            significant=stationary,
                            conclusion=f"Series is {'stationary' if stationary else 'non-stationary (unit root present)'}. ADF = {adf_stat:.4f}, p = {p_val:.4f}.",
                            additional_stats={
                                "adf_statistic": round(float(adf_stat), 4),
                                "p_value": round(float(p_val), 4),
                                "n_lags_used": n_lags,
                                "critical_values": {k: round(float(v), 4) for k, v in critical_vals.items()},
                                "is_stationary": stationary,
                            })
    except Exception as e:
        return build_error("ADF Test", "adf_test", str(e), "Check time series column.")


def run_kpss_test(df, variables, brief, alpha=0.05):
    """KPSS stationarity test (null = stationary)."""
    try:
        if not _sm:
            return build_error("KPSS Test", "kpss_test", "statsmodels not installed.", "pip install statsmodels")
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("KPSS Test", "kpss_test", "No numeric column found.", "Select a time series column.")
        stat, p_val, n_lags, critical_vals = kpss(s, regression="c", nlags="auto")
        # KPSS: reject H0 (stationary) if p < alpha => non-stationary
        non_stationary = bool(p_val < alpha)
        return build_result("KPSS Stationarity Test", "kpss_test",
                            "KPSS", stat, p_value=p_val, n=len(s),
                            significant=non_stationary,
                            conclusion=f"Series is {'non-stationary' if non_stationary else 'stationary'}. KPSS = {stat:.4f}, p = {p_val:.4f}.",
                            additional_stats={
                                "kpss_statistic": round(float(stat), 4),
                                "p_value": round(float(p_val), 4),
                                "n_lags": n_lags,
                                "critical_values": {k: round(float(v), 4) for k, v in critical_vals.items()},
                                "is_stationary": not non_stationary,
                            })
    except Exception as e:
        return build_error("KPSS Test", "kpss_test", str(e), "Check time series column.")


def run_autocorrelation(df, variables, brief, alpha=0.05):
    """Autocorrelation Function (ACF) and significance analysis."""
    try:
        if not _sm:
            return build_error("ACF", "autocorrelation", "statsmodels not installed.", "pip install statsmodels")
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("ACF", "autocorrelation", "No numeric column found.", "Select a numeric time series column.")
        n_lags = min(40, len(s) // 4)
        acf_values, conf_int = acf(s, nlags=n_lags, alpha=alpha)
        pacf_values, pacf_ci = pacf(s, nlags=min(n_lags, len(s)//2 - 1), alpha=alpha)
        ci_bound = 1.96 / np.sqrt(len(s))
        # Significant lags
        sig_acf = [i for i, v in enumerate(acf_values) if i > 0 and abs(v) > ci_bound]
        sig_pacf = [i for i, v in enumerate(pacf_values) if i > 0 and abs(v) > ci_bound]
        acf_table = [{"lag": i, "acf": round(float(v), 4), "ci_lower": round(float(conf_int[i, 0] - v), 4),
                      "ci_upper": round(float(conf_int[i, 1] - v), 4), "significant": bool(abs(v) > ci_bound)}
                     for i, v in enumerate(acf_values)]
        return build_result("Autocorrelation Function (ACF)", "autocorrelation",
                            "Max ACF", float(np.max(np.abs(acf_values[1:]))), n=len(s),
                            additional_stats={
                                "acf_values": acf_table,
                                "pacf_values": [{"lag": i, "pacf": round(float(v), 4)}
                                                for i, v in enumerate(pacf_values)],
                                "significant_acf_lags": sig_acf,
                                "significant_pacf_lags": sig_pacf,
                                "ci_bound": round(float(ci_bound), 4),
                                "suggestion": f"ACF cuts off at lag {sig_acf[-1] if sig_acf else 0}, PACF at {sig_pacf[-1] if sig_pacf else 0}.",
                            }, table=acf_table[:20])
    except Exception as e:
        return build_error("ACF", "autocorrelation", str(e), "Check numeric time series column.")


def run_partial_autocorrelation(df, variables, brief, alpha=0.05):
    """Partial Autocorrelation Function (PACF) analysis."""
    try:
        if not _sm:
            return build_error("PACF", "partial_autocorrelation", "statsmodels not installed.", "pip install statsmodels")
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("PACF", "partial_autocorrelation", "No numeric column found.", "Select a time series column.")
        n_lags = min(20, len(s) // 4)
        pacf_values, conf_int = pacf(s, nlags=n_lags, alpha=alpha)
        ci_bound = 1.96 / np.sqrt(len(s))
        pacf_table = [{"lag": i, "pacf": round(float(v), 4),
                       "significant": bool(i > 0 and abs(v) > ci_bound)}
                      for i, v in enumerate(pacf_values)]
        return build_result("Partial Autocorrelation Function (PACF)", "partial_autocorrelation",
                            "Max PACF", float(np.max(np.abs(pacf_values[1:]))), n=len(s),
                            additional_stats={"pacf_values": pacf_table,
                                             "ci_bound": round(float(ci_bound), 4)},
                            table=pacf_table)
    except Exception as e:
        return build_error("PACF", "partial_autocorrelation", str(e), "Check time series column.")


def run_ljung_box(df, variables, brief, alpha=0.05):
    """Ljung-Box Q-test for residual autocorrelation."""
    try:
        if not _sm:
            return build_error("Ljung-Box Test", "ljung_box", "statsmodels not installed.", "pip install statsmodels")
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("Ljung-Box Test", "ljung_box", "No numeric column found.", "Select a time series column.")
        lags = min(20, len(s) // 5)
        result = acorr_ljungbox(s, lags=[lags], return_df=True)
        stat = float(result["lb_stat"].iloc[0])
        p = float(result["lb_pvalue"].iloc[0])
        significant = bool(p < alpha)
        return build_result("Ljung-Box Q-Test", "ljung_box",
                            "Q", stat, p_value=p, n=len(s), df_val=lags,
                            significant=significant,
                            conclusion=f"Q({lags}) = {stat:.3f}, p = {p:.4f}. {'Significant autocorrelation detected.' if significant else 'No significant autocorrelation.'}",
                            additional_stats={"Q_stat": round(stat, 4), "p_value": round(p, 4),
                                             "lags": lags, "white_noise": not significant})
    except Exception as e:
        return build_error("Ljung-Box Test", "ljung_box", str(e), "Check time series column.")


def run_seasonal_decompose(df, variables, brief, alpha=0.05):
    """Classical seasonal decomposition (trend + seasonal + residual)."""
    try:
        if not _sm:
            return build_error("Seasonal Decomposition", "seasonal_decompose",
                               "statsmodels not installed.", "pip install statsmodels")
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("Seasonal Decomposition", "seasonal_decompose",
                               "No numeric column found.", "Select a time series column.")
        period = int(brief.get("period", 12) or 12)
        if len(s) < 2 * period:
            return build_error("Seasonal Decomposition", "seasonal_decompose",
                               f"Series too short (n={len(s)}) for period={period}. Need >= {2*period} observations.",
                               "Reduce period or use more data.")
        model_type = str(brief.get("decompose_model", "additive") or "additive")
        decomp = seasonal_decompose(s, model=model_type, period=period)
        trend = [round(float(v), 4) if not np.isnan(v) else None for v in decomp.trend.values]
        seasonal = [round(float(v), 4) for v in decomp.seasonal.values]
        residual = [round(float(v), 4) if not np.isnan(v) else None for v in decomp.resid.values]
        # Variance attributed to components
        obs_var = float(s.var())
        resid_notna = decomp.resid.dropna()
        resid_var = float(resid_notna.var()) if len(resid_notna) > 0 else 0
        return build_result("Seasonal Decomposition", "seasonal_decompose",
                            "Period", period, n=len(s),
                            additional_stats={
                                "model": model_type,
                                "period": period,
                                "trend": trend,
                                "seasonal": seasonal,
                                "residual": residual,
                                "obs_variance": round(obs_var, 4),
                                "resid_variance": round(resid_var, 4),
                                "signal_to_noise": round(obs_var / (resid_var + 1e-10), 4),
                            })
    except Exception as e:
        return build_error("Seasonal Decomposition", "seasonal_decompose", str(e),
                           "Check time series column and period parameter.")


def run_arima(df, variables, brief, alpha=0.05):
    """ARIMA(p,d,q) modeling and forecasting."""
    try:
        if not _sm:
            return build_error("ARIMA", "arima_model", "statsmodels not installed.", "pip install statsmodels")
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("ARIMA", "arima_model", "No numeric column found.", "Select a time series column.")
        p = int(brief.get("arima_p", 1) or 1)
        d = int(brief.get("arima_d", 1) or 1)
        q = int(brief.get("arima_q", 1) or 1)
        n_forecast = int(brief.get("n_forecast", 12) or 12)
        model = ARIMA(s.values, order=(p, d, q))
        fitted = model.fit()
        forecast_result = fitted.get_forecast(steps=n_forecast)
        forecast_mean = [round(float(v), 4) for v in forecast_result.predicted_mean]
        ci = forecast_result.conf_int()
        # conf_int() may return DataFrame or ndarray depending on ARIMA input type
        try:
            ci_arr = ci.values if hasattr(ci, "values") else np.array(ci)
        except Exception:
            ci_arr = np.array(ci)
        forecast_ci = [{"lower": round(float(ci_arr[i, 0]), 4), "upper": round(float(ci_arr[i, 1]), 4)}
                       for i in range(len(ci_arr))]
        # In-sample fit metrics
        residuals = fitted.resid
        n = len(s)
        mse = float(np.mean(residuals**2))
        mae = float(np.mean(np.abs(residuals)))
        # Ljung-Box on residuals
        lb_result = acorr_ljungbox(residuals, lags=[min(10, n//5)], return_df=True)
        lb_p = float(lb_result["lb_pvalue"].iloc[0])
        return build_result(f"ARIMA({p},{d},{q}) Model", "arima_model",
                            "AIC", fitted.aic, n=n,
                            additional_stats={
                                "order": {"p": p, "d": d, "q": q},
                                "AIC": round(float(fitted.aic), 4),
                                "BIC": round(float(fitted.bic), 4),
                                "log_likelihood": round(float(fitted.llf), 4),
                                "mse": round(mse, 4), "mae": round(mae, 4),
                                "rmse": round(float(np.sqrt(mse)), 4),
                                "ljung_box_p_residuals": round(lb_p, 4),
                                "residuals_white_noise": bool(lb_p >= alpha),
                                "forecast": forecast_mean,
                                "forecast_ci": forecast_ci,
                                "params": ({k: round(float(v), 4) for k, v in fitted.params.items()}
                                           if hasattr(fitted.params, "items")
                                           else {f"param_{i}": round(float(v), 4)
                                                 for i, v in enumerate(fitted.params)}),
                            })
    except Exception as e:
        return build_error("ARIMA", "arima_model", str(e), "Check time series column and ARIMA orders (p,d,q in brief).")


def run_sarima(df, variables, brief, alpha=0.05):
    """SARIMA(p,d,q)(P,D,Q,s) seasonal ARIMA."""
    try:
        if not _sm:
            return build_error("SARIMA", "sarima_model", "statsmodels not installed.", "pip install statsmodels")
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("SARIMA", "sarima_model", "No numeric column found.", "Select a time series column.")
        p, d, q = int(brief.get("arima_p", 1)), int(brief.get("arima_d", 1)), int(brief.get("arima_q", 1))
        P = int(brief.get("sarima_P", 1) or 1)
        D = int(brief.get("sarima_D", 1) or 1)
        Q = int(brief.get("sarima_Q", 1) or 1)
        s_period = int(brief.get("period", 12) or 12)
        n_forecast = int(brief.get("n_forecast", 12) or 12)
        if len(s) < s_period * 2:
            return build_error("SARIMA", "sarima_model",
                               f"Series too short (n={len(s)}) for seasonal period {s_period}.",
                               "Use more data or reduce period.")
        model = SARIMAX(s.values, order=(p, d, q), seasonal_order=(P, D, Q, s_period))
        fitted = model.fit(disp=False)
        forecast_result = fitted.get_forecast(steps=n_forecast)
        forecast_mean = [round(float(v), 4) for v in forecast_result.predicted_mean]
        return build_result(f"SARIMA({p},{d},{q})×({P},{D},{Q},{s_period}) Model", "sarima_model",
                            "AIC", fitted.aic, n=len(s),
                            additional_stats={
                                "AIC": round(float(fitted.aic), 4),
                                "BIC": round(float(fitted.bic), 4),
                                "forecast": forecast_mean,
                                "seasonal_period": s_period,
                            })
    except Exception as e:
        return build_error("SARIMA", "sarima_model", str(e), "Check series and SARIMA orders in brief.")


def run_ets(df, variables, brief, alpha=0.05):
    """Exponential Smoothing (ETS / Holt-Winters) forecasting."""
    try:
        if not _sm:
            return build_error("ETS", "exponential_smoothing", "statsmodels not installed.", "pip install statsmodels")
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("ETS", "exponential_smoothing", "No numeric column found.", "Select a numeric column.")
        period = int(brief.get("period", 12) or 12)
        n_forecast = int(brief.get("n_forecast", 12) or 12)
        trend_type = str(brief.get("trend", "add") or "add")
        seasonal_type = str(brief.get("seasonal", "add") or "add") if len(s) >= 2 * period else None
        model = ExponentialSmoothing(s.values, trend=trend_type,
                                     seasonal=seasonal_type,
                                     seasonal_periods=period if seasonal_type else None)
        fitted = model.fit(optimized=True)
        forecast = fitted.forecast(n_forecast)
        sse = float(np.sum(fitted.resid**2))
        n = len(s)
        return build_result("Exponential Smoothing (ETS)", "exponential_smoothing",
                            "AIC", fitted.aic, n=n,
                            additional_stats={
                                "AIC": round(float(fitted.aic), 4),
                                "SSE": round(sse, 4),
                                "RMSE": round(float(np.sqrt(sse / n)), 4),
                                "alpha": round(float(fitted.params["smoothing_level"]), 4),
                                "forecast": [round(float(f), 4) for f in forecast],
                                "trend_type": trend_type,
                                "seasonal_type": seasonal_type,
                            })
    except Exception as e:
        return build_error("ETS", "exponential_smoothing", str(e), "Check time series column and period.")


def run_granger_causality(df, variables, brief, alpha=0.05):
    """Granger causality test (X does not Granger-cause Y)."""
    try:
        if not _sm:
            return build_error("Granger Causality", "granger_causality",
                               "statsmodels not installed.", "pip install statsmodels")
        if len(variables) < 2:
            return build_error("Granger Causality", "granger_causality",
                               "Need y_col and x_col.", "Select 2 numeric time series columns.")
        y_col, x_col = variables[0], variables[1]
        data = df[[y_col, x_col]].dropna().astype(float)
        if len(data) < 20:
            return build_error("Granger Causality", "granger_causality",
                               f"Too few observations (n={len(data)}). Need >= 20.", "Use longer series.")
        max_lag = int(brief.get("max_lag", 4) or 4)
        results = grangercausalitytests(data[[y_col, x_col]], maxlag=max_lag, verbose=False)
        table = []
        for lag, res in results.items():
            F_val = float(res[0]["ssr_ftest"][0])
            p_val = float(res[0]["ssr_ftest"][1])
            table.append({"lag": lag, "F": round(F_val, 4), "p": round(p_val, 4),
                          "granger_causes": bool(p_val < alpha)})
        min_p = min(r["p"] for r in table)
        any_sig = any(r["granger_causes"] for r in table)
        return build_result("Granger Causality Test", "granger_causality",
                            "Min p", min_p, n=len(data),
                            significant=any_sig,
                            conclusion=f"{x_col} {'Granger-causes' if any_sig else 'does not Granger-cause'} {y_col}.",
                            additional_stats={"lags_tested": table,
                                             "min_p_value": round(min_p, 4),
                                             "any_significant": any_sig},
                            table=table)
    except Exception as e:
        return build_error("Granger Causality", "granger_causality", str(e), "Check two numeric time series columns.")


def run_var_model(df, variables, brief, alpha=0.05):
    """Vector Autoregression (VAR) model for multiple time series."""
    try:
        if not _sm:
            return build_error("VAR", "var_model", "statsmodels not installed.", "pip install statsmodels")
        cols = [c for c in variables if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(cols) < 2:
            return build_error("VAR", "var_model", "Need >= 2 numeric time series columns.", "Select multiple columns.")
        data = df[cols].dropna().astype(float)
        if len(data) < 20:
            return build_error("VAR", "var_model", f"Too few observations (n={len(data)}). Need >= 20.", "Use longer series.")
        max_lags = int(brief.get("max_lag", 8) or 8)
        model = VAR(data.values)
        lag_order = model.select_order(maxlags=min(max_lags, len(data)//5))
        optimal_lag = int(lag_order.aic)
        if optimal_lag == 0:
            optimal_lag = 1
        fitted = model.fit(optimal_lag)
        n_forecast = int(brief.get("n_forecast", 6) or 6)
        forecast = fitted.forecast(data.values[-optimal_lag:], steps=n_forecast)
        return build_result(f"VAR({optimal_lag}) Model", "var_model",
                            "Optimal lag", optimal_lag, n=len(data),
                            additional_stats={
                                "optimal_lag_aic": optimal_lag,
                                "AIC": round(float(fitted.aic), 4),
                                "variables": cols,
                                "forecast": [[round(float(v), 4) for v in row] for row in forecast],
                                "forecast_variables": cols,
                            })
    except Exception as e:
        return build_error("VAR", "var_model", str(e), "Check multiple numeric time series columns.")


def run_mann_kendall(df, variables, brief, alpha=0.05):
    """Mann-Kendall trend test for monotonic trend in time series."""
    try:
        s, col = _get_series(df, variables)
        if s is None:
            return build_error("Mann-Kendall", "mann_kendall", "No numeric column found.", "Select a time series column.")
        x = s.values
        n = len(x)
        if n < 8:
            return build_error("Mann-Kendall", "mann_kendall", f"Series too short (n={n}). Need >= 8.", "Use longer series.")
        # Vectorized Mann-Kendall S statistic
        try:
            import pymannkendall as mk
            result_mk = mk.original_test(s)
            S = result_mk.s
            tau = result_mk.Tau
            p = result_mk.p
            var_S = result_mk.var_s
            Z = result_mk.z
            use_pymannkendall = True
        except ImportError:
            use_pymannkendall = False
            # Vectorized numpy implementation O(n log n)
            arr = np.array(s)
            # Use outer subtraction sign approach
            diff_signs = np.sign(np.subtract.outer(arr, arr))
            S = float(np.sum(np.triu(diff_signs, k=1)))
            n_val = len(arr)
            counts = np.unique(arr, return_counts=True)[1]
            tau_factor = sum(t * (t - 1) * (2 * t + 5) for t in counts if t > 1)
            var_S = float((n_val * (n_val - 1) * (2 * n_val + 5) - tau_factor) / 18)
            if var_S > 0:
                if S > 0:
                    Z = (S - 1) / np.sqrt(var_S)
                elif S < 0:
                    Z = (S + 1) / np.sqrt(var_S)
                else:
                    Z = 0.0
                p = float(2 * stats.norm.sf(abs(Z)))
            else:
                Z = 0.0
                p = 1.0
            tau = float(S / (n_val * (n_val - 1) / 2)) if n_val > 1 else 0.0

        if var_S <= 0:
            return build_error("Mann-Kendall", "mann_kendall", "Cannot compute variance (all values tied).", "Check data.")
        trend = "upward" if S > 0 else ("downward" if S < 0 else "no trend")
        # Sen's slope
        slopes = []
        for i in range(n - 1):
            for j in range(i + 1, n):
                if j != i:
                    slopes.append((x[j] - x[i]) / (j - i))
        sen_slope = float(np.median(slopes))
        return build_result("Mann-Kendall Trend Test", "mann_kendall",
                            "Z", Z, p_value=p, n=n,
                            significant=bool(p < alpha),
                            conclusion=f"{'Significant' if p<alpha else 'Non-significant'} {trend} trend. Z = {Z:.3f}, p = {p:.4f}. Sen's slope = {sen_slope:.4f}.",
                            additional_stats={
                                "S": int(S), "Z": round(Z, 4), "p": round(p, 4),
                                "tau": round(tau, 4), "sen_slope": round(sen_slope, 4),
                                "trend_direction": trend,
                            })
    except Exception as e:
        return build_error("Mann-Kendall", "mann_kendall", str(e), "Check numeric time series column.")

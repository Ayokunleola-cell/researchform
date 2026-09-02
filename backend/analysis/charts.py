"""
charts.py  Beautiful, publication-quality chart & table generation using Plotly.

Every chart is saved as a high-resolution PNG (1400800 px, scale=2).
Design principles:
   Plotly with 'plotly_white' template  clean, modern, professional look
   One variable / one topic = one image file (no crammed multi-panel grids)
   Rich colour palette consistent with frontend brand
   Full result tables generated as images alongside every chart
   Gradient fills, drop-shadow annotations, proper axis labels everywhere
"""
from __future__ import annotations
import os, traceback

#  Plotly imports (beautiful charts) 
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio

# Prevent Kaleido from hanging on Windows by disabling MathJax
try:
    pio.kaleido.scope.mathjax = None
except Exception:
    pass

from plotly.subplots import make_subplots

#  Brand palette 
BRAND   = "#6366f1"
SUCCESS = "#10b981"
WARN    = "#f59e0b"
DANGER  = "#ef4444"
PINK    = "#ec4899"
BLUE    = "#3b82f6"
PURPLE  = "#8b5cf6"
CYAN    = "#06b6d4"

PALETTE = [BRAND, PINK, WARN, SUCCESS, BLUE, DANGER, PURPLE, CYAN,
           "#f97316", "#14b8a6", "#a855f7", "#eab308"]

# Plotly template & layout defaults
_TEMPLATE  = "plotly_white"
_FONT      = dict(family="Inter, Arial, sans-serif", size=13, color="#111827")
_TITLE_FONT = dict(family="Inter, Arial, sans-serif", size=16, color="#111827")
_MARGIN    = dict(l=70, r=50, t=80, b=80)
_BG        = "#ffffff"
_PAPER_BG  = "#f9fafb"

# Export size
_W, _H, _SCALE = 1400, 750, 2


#  Helpers 
import unicodedata, re

def _sanitize_text(s) -> str:
    """Safely sanitize text strings against invalid unicode, punctuation, HTML, or control characters."""
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    return s.strip()

def _trunc(s: str, n: int = 24) -> str:
    st = _sanitize_text(s)
    return (st[:n] + "...") if len(st) > n else st

def _safe_col(col: str, maxlen: int = 18) -> str:
    """Return a filesystem-safe, ASCII-only version of a column name for use in filenames."""
    s = _sanitize_text(str(col))
    # Keep only alphanumeric + underscore, collapse runs
    s = re.sub(r'[^a-zA-Z0-9]+', '_', s).strip('_')
    return s[:maxlen] if s else "col"


def _layout(**kw):
    """Return a base Layout dict merged with caller overrides."""
    base = dict(
        template=_TEMPLATE,
        font=_FONT,
        title_font=_TITLE_FONT,
        paper_bgcolor=_PAPER_BG,
        plot_bgcolor=_BG,
        margin=_MARGIN,
        legend=dict(
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#e5e7eb",
            borderwidth=1,
            font=dict(size=12),
        ),
        hoverlabel=dict(bgcolor="white", font_size=12, bordercolor="#d1d5db"),
    )
    base.update(kw)
    return base


import re

def _save(fig: go.Figure, path: str, chart_paths: list,
          w: int = _W, h: int = _H):
    try:
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        filename = os.path.basename(path)
        # Sanitize filename: only keep ASCII alphanumeric, underscore, hyphen, dot
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        # Collapse multiple underscores
        safe_filename = re.sub(r'_+', '_', safe_filename).strip('_')
        safe_path = os.path.join(dirname, safe_filename)

        # Windows: normalize to forward slashes for kaleido (avoids Errno 22)
        abs_path = os.path.abspath(safe_path)
        clean_target = abs_path.replace("\\", "/")

        saved = False
        try:
            fig.write_image(clean_target, width=w, height=h, scale=_SCALE)
            saved = True
        except Exception as ke:
            print(f"[Chart Export Warning] kaleido write_image failed: {ke}")
            # Fallback 1: Try without scale parameter
            try:
                fig.write_image(clean_target, width=w, height=h)
                saved = True
            except Exception as ke2:
                print(f"[Chart Export Warning] Fallback write_image failed: {ke2}")

        # Fallback 2: Save as interactive HTML if PNG export fails
        if not saved:
            html_path = abs_path.replace(".png", ".html")
            try:
                fig.write_html(html_path)
                chart_paths.append(html_path)
                print(f"[Chart Export] Saved as HTML fallback: {html_path}")
                return
            except Exception as he:
                print(f"[Chart Export Warning] HTML fallback also failed: {he}")
                return

        if os.path.exists(abs_path):
            chart_paths.append(abs_path)
        elif os.path.exists(safe_path):
            chart_paths.append(safe_path)
    except Exception as e:
        print(f"[Chart Export Warning] Could not save chart to {path}: {e}")


def _axis(title: str, **kw):
    return dict(
        title=dict(text=title, font=dict(size=13, color="#374151")),
        gridcolor="#e5e7eb",
        linecolor="#d1d5db",
        zerolinecolor="#d1d5db",
        tickfont=dict(size=11, color="#6b7280"),
        **kw,
    )


#  Beautiful table image 
def _table_fig(header_cols: list[str], rows: list[list],
               title: str, col_widths: list[int] | None = None) -> go.Figure:
    """Create a styled plotly Table figure."""
    n_rows = len(rows)
    # Zebra-stripe row colours
    fill_colors = []
    for i in range(n_rows):
        fill_colors.append("#f0f0ff" if i % 2 == 0 else "#ffffff")

    fig = go.Figure(go.Table(
        columnwidth=col_widths or [200] * len(header_cols),
        header=dict(
            values=[f"<b>{c}</b>" for c in header_cols],
            fill_color=BRAND,
            align="center",
            font=dict(color="white", size=13, family="Inter, Arial, sans-serif"),
            line_color="white",
            height=36,
        ),
        cells=dict(
            values=[[row[i] for row in rows] for i in range(len(header_cols))],
            fill_color=[fill_colors],
            align=["left"] + ["center"] * (len(header_cols) - 1),
            font=dict(color="#111827", size=12, family="Inter, Arial, sans-serif"),
            line_color="#e5e7eb",
            height=30,
        ),
    ))
    fig.update_layout(
        title=dict(text=title, font=_TITLE_FONT, x=0.5, xanchor="center"),
        paper_bgcolor=_PAPER_BG,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


# 
# MAIN ENTRY POINT
# 
def create_visualisations(results: dict, df, brief: dict, job_id: str,
                           chart_dir: str,
                           tests: list = None,
                           auto_viz: bool = True,
                           selected_viz: list = None,
                           auto_tables: bool = True,
                           selected_tables: list = None,
                           label_map: dict = None) -> list:
    """Return list of saved chart file paths."""
    os.makedirs(chart_dir, exist_ok=True)
    chart_paths: list[str] = []
    _lmap = label_map or {}

    def lbl(col: str, max_words: int = 6) -> str:
        """Return the human-readable display label for a column."""
        if col in _lmap:
            words = _lmap[col].split()
            return " ".join(words[:max_words])
        # Auto-format fallback: strip q{n}_ prefix, title-case
        import re as _re
        clean = _re.sub(r'^q\d+_?', '', str(col))
        clean = _re.sub(r'[_\-]+', ' ', clean).strip()
        return clean.title() if clean else str(col)

    # Normalize selections
    _sel_tables: set = set(selected_tables or [])
    _sel_viz: set = set(selected_viz or [])

    def save(fig, name, w=_W, h=_H):
        _save(fig, os.path.join(chart_dir, name), chart_paths, w=w, h=h)

    def _want_table(table_id: str) -> bool:
        """Return True if this table should be generated."""
        return auto_tables or table_id in _sel_tables

    def _want_viz(viz_id: str) -> bool:
        """Return True if this chart/visualization should be generated."""
        if auto_viz:
            return True
        aliases = {
            "correlation": {"correlation", "heatmap", "corr"},
            "means": {"means", "bar", "means_comparison"},
            "bar": {"bar", "means", "distribution", "frequency"},
            "pie": {"pie", "donut"},
            "distribution": {"distribution", "histogram"},
            "boxplot": {"boxplot", "box"},
            "scatter": {"scatter", "regression"},
            "violin": {"violin"},
            "qqplot": {"qqplot", "qq"}
        }
        allowed = aliases.get(viz_id, {viz_id})
        return bool(_sel_viz.intersection(allowed))

    #  TABLE 1: Descriptive Statistics 
    try:
        import pandas as pd
        raw_desc = results.get("descriptive", {})
        add_desc = (raw_desc.get("descriptive_stats", {})
                    .get("additional_stats", {}))
        desc = add_desc.get("columns") or add_desc or raw_desc

        stat_rows = []
        for col, v in desc.items():
            if not isinstance(v, dict):
                continue
            stat_rows.append([
                col,
                f"{v.get('n', v.get('count', ''))}",
                f"{v.get('mean', ''):.4f}" if isinstance(v.get('mean'), (int, float)) else "",
                f"{v.get('std', v.get('sd', '')):.4f}" if isinstance(v.get('std', v.get('sd')), (int, float)) else "",
                f"{v.get('min', ''):.4f}" if isinstance(v.get('min'), (int, float)) else "",
                f"{v.get('max', ''):.4f}" if isinstance(v.get('max'), (int, float)) else "",
                f"{v.get('median', ''):.4f}" if isinstance(v.get('median'), (int, float)) else "",
                f"{v.get('skewness', v.get('skew', '')):.4f}" if isinstance(v.get('skewness', v.get('skew')), (int, float)) else "",
                f"{v.get('kurtosis', ''):.4f}" if isinstance(v.get('kurtosis'), (int, float)) else "",
            ])

        if stat_rows and _want_table('descriptive'):
            hcols = ["Variable", "N", "Mean", "SD", "Min", "Max", "Median", "Skewness", "Kurtosis"]
            # Apply human-readable labels to the Variable column
            for row in stat_rows:
                row[0] = lbl(row[0])
            fig = _table_fig(hcols, stat_rows, "Descriptive Statistics Summary",
                             col_widths=[220, 60, 90, 90, 90, 90, 90, 100, 100])
            h = max(500, 60 + len(stat_rows) * 32)
            save(fig, "table_descriptive.png", w=_W, h=h)
    except Exception:
        traceback.print_exc()

    #  TABLE 2: Statistical Test Results 
    try:
        summary = results.get("summary", [])
        if not summary:
            # Gather from all result buckets
            buckets = ["inferential", "multivariate", "survival",
                       "causal", "timeseries", "multilevel"]
            for bk in buckets:
                bk_data = results.get(bk, {})
                for tkey, tval in bk_data.items():
                    if isinstance(tval, dict) and "test_name" in tval:
                        summary.append(tval)

        test_rows = []
        for s in summary:
            if not isinstance(s, dict):
                continue
            stat = s.get("statistic", {})
            stat_val = stat.get("value", "") if isinstance(stat, dict) else stat
            pval = s.get("p_value")
            ef   = s.get("effect_size", {})
            ef_v = ef.get("value", "") if isinstance(ef, dict) else ""
            ef_n = ef.get("name", "")   if isinstance(ef, dict) else ""
            sig  = s.get("significant")
            test_rows.append([
                s.get("test_name", ""),
                f"{stat_val:.4f}" if isinstance(stat_val, (int, float)) else str(stat_val),
                f"{pval:.4f}" if isinstance(pval, (int, float)) else "",
                " Yes" if sig is True else " No" if sig is False else "",
                f"{ef_v:.4f} ({ef_n})" if isinstance(ef_v, (int, float)) and ef_n else (
                    f"{ef_v:.4f}" if isinstance(ef_v, (int, float)) else ""),
                s.get("fitness", ""),
            ])

        if test_rows and _want_table('test_results'):
            hcols = ["Test Name", "Statistic", "p-value", "Significant",
                     "Effect Size", "Fitness"]
            fig = _table_fig(hcols, test_rows,
                             "Statistical Test Results Summary",
                             col_widths=[280, 110, 100, 100, 170, 100])
            h = max(500, 60 + len(test_rows) * 32)
            save(fig, "table_test_results.png", w=_W, h=h)
    except Exception:
        traceback.print_exc()

    #  CHART 1 + TABLE: Frequency bar & pie  one pair per column 
    try:
        raw_freq   = results.get("frequencies", {})
        add_stats  = raw_freq.get("frequencies", {}).get("additional_stats", {})
        frequencies = add_stats.get("columns") or add_stats or raw_freq
        if not frequencies:
            raw_desc2 = results.get("descriptive", {})
            dcols = (raw_desc2.get("descriptive_stats", {})
                     .get("additional_stats", {}).get("columns", {}))
            frequencies = {k: v.get("value_counts")
                           for k, v in dcols.items() if "value_counts" in v}

        for i, col in enumerate(list(frequencies.keys())[:6]):
            freq = frequencies[col]
            if not freq or not isinstance(freq, dict):
                continue
            keys   = list(freq.keys())[:14]
            values = [freq[k] for k in keys]
            labels = [_trunc(str(k)) for k in keys]
            total  = sum(values) or 1
            pcts   = [v / total * 100 for v in values]

            #  Bar chart 
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=labels, y=values,
                marker=dict(
                    color=values,
                    colorscale=[[0, "#a5b4fc"], [1, BRAND]],
                    showscale=False,
                    line=dict(color="white", width=1.5),
                ),
                text=[f"{v:,}<br>({p:.1f}%)" for v, p in zip(values, pcts)],
                textposition="outside",
                textfont=dict(size=11, color="#374151"),
                hovertemplate="<b>%{x}</b><br>Count: %{y:,}<extra></extra>",
            ))
            fig.update_layout(**_layout(
                title=dict(text=f"Frequency Distribution — <b>{lbl(col)}</b>",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis(lbl(col), tickangle=-30),
                yaxis=_axis("Count"),
                bargap=0.25,
            ))
            if _want_viz('bar'):
                save(fig, f"chart_freq_{i+1}_{_safe_col(col)}_bar.png", w=900, h=600)

            # Pie Chart
            if _want_viz('pie'):
                colors = [PALETTE[idx % len(PALETTE)] for idx in range(len(keys))]
                fig2 = go.Figure(go.Pie(
                    labels=[_trunc(str(k), 22) for k in keys],
                    values=values,
                    hole=0.4,
                    marker=dict(colors=colors, line=dict(color="white", width=2)),
                    textinfo="percent+label",
                    textfont=dict(size=12),
                    hovertemplate="<b>%{label}</b><br>Count: %{value:,}<br>Share: %{percent}<extra></extra>",
                ))
                fig2.update_layout(**_layout(
                    title=dict(text=f"Distribution Share — <b>{lbl(col)}</b>",
                               font=_TITLE_FONT, x=0.5, xanchor="center"),
                    showlegend=True,
                    legend=dict(orientation="v", y=0.5, x=1.02),
                ))
                save(fig2, f"chart_freq_{i+1}_{_safe_col(col)}_pie.png", w=900, h=700)


            #  Frequency Table 
            if _want_table('frequency'):
                trows = [[str(k), f"{v:,}", f"{v/total*100:.1f}%"]
                         for k, v in zip(keys, values)]
                trows.append(["Total", f"{total:,}", "100%"])
                fig3 = _table_fig(["Category", "Count", "Percentage"],
                                   trows, f"Frequency Table — {lbl(col)}",
                                   col_widths=[250, 120, 120])
                h = max(300, 60 + len(trows) * 32)
                save(fig3, f"table_freq_{i+1}_{_safe_col(col)}.png", w=600, h=h)

    except Exception:
        traceback.print_exc()

    #  CHART 2: Variable means  sorted gradient bar 
    try:
        import pandas as pd
        raw_desc  = results.get("descriptive", {})
        add_d     = (raw_desc.get("descriptive_stats", {})
                     .get("additional_stats", {}))
        desc      = add_d.get("columns") or add_d or raw_desc
        means     = {col: v["mean"] for col, v in desc.items()
                     if isinstance(v, dict) and isinstance(v.get("mean"), (int, float))}
        sds       = {col: v.get("std", v.get("sd", 0)) for col, v in desc.items()
                     if isinstance(v, dict) and "mean" in v}

        if means:
            items   = sorted(means.items(), key=lambda x: x[1], reverse=True)[:14]
            cols_m, vals_m = zip(*items)
            errs    = [sds.get(c, 0) for c in cols_m]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[lbl(c, 4) for c in cols_m],
                y=list(vals_m),
                error_y=dict(type="data", array=errs, visible=True,
                             color="#9ca3af", thickness=1.5),
                marker=dict(
                    color=list(vals_m),
                    colorscale=[[0, "#c7d2fe"], [0.5, BRAND], [1, "#4338ca"]],
                    showscale=True,
                    colorbar=dict(title="Mean", thickness=14, len=0.7),
                    line=dict(color="white", width=1.5),
                ),
                text=[f"{v:.2f}" for v in vals_m],
                textposition="outside",
                textfont=dict(size=11),
                hovertemplate="<b>%{x}</b><br>Mean: %{y:.4f}<extra></extra>",
            ))
            fig.update_layout(**_layout(
                title=dict(text="Variable Means Comparison (sorted, +/-1 SD error bars)",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis("Variable", tickangle=-35),
                yaxis=_axis("Mean Score"),
                bargap=0.3,
            ))
            if _want_viz('means') or _want_viz('bar'):
                save(fig, "chart_means.png")
    except Exception:
        traceback.print_exc()

    #  CHART 3 + TABLE: Correlation heatmap 
    try:
        import pandas as pd
        df_num = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
        ncols  = df_num.select_dtypes(include="number").columns.tolist()[:12]
        if len(ncols) >= 2:
            corr = df_num[ncols].corr().round(4)
            cols_short = [_trunc(c, 16) for c in ncols]

            fig = go.Figure(go.Heatmap(
                z=corr.values.tolist(),
                x=[lbl(c, 4) for c in ncols],
                y=[lbl(c, 4) for c in ncols],
                colorscale=[
                    [0.0, "#dc2626"], [0.25, "#f87171"],
                    [0.5, "#f9fafb"],
                    [0.75, "#818cf8"], [1.0, "#4338ca"],
                ],
                zmid=0, zmin=-1, zmax=1,
                text=[[f"{v:.2f}" for v in row] for row in corr.values.tolist()],
                texttemplate="%{text}",
                textfont=dict(size=11),
                colorbar=dict(title="r", thickness=16, len=0.8),
                hoverongaps=False,
                hovertemplate="<b>%{y}</b>  <b>%{x}</b><br>r = %{z:.4f}<extra></extra>",
            ))
            fig.update_layout(**_layout(
                title=dict(text="Correlation Matrix (Pearson r)",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=dict(tickangle=-40, tickfont=dict(size=11)),
                yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
            ))
            sz = max(700, len(ncols) * 70)
            if _want_viz('correlation') or _want_viz('heatmap'):
                save(fig, "chart_correlation.png", w=sz, h=sz)

            #  Correlation Table 
            trows = []
            for r_col in ncols:
                row = [lbl(r_col)]
                for c_col in ncols:
                    v = corr.loc[r_col, c_col]
                    row.append(f"{v:.3f}")
                trows.append(row)
            if _want_table('correlation'):
                fig2 = _table_fig(
                    ["Variable"] + [lbl(c, 2) for c in ncols],
                    trows,
                    "Correlation Matrix Table",
                    col_widths=[200] + [90] * len(ncols),
                )
                sz2 = max(500, 60 + len(ncols) * 32)
                save(fig2, "table_correlation.png", w=max(900, len(ncols) * 100), h=sz2)
    except Exception:
        traceback.print_exc()

    #  CHART 4: Histograms  one per variable 
    try:
        import pandas as pd, numpy as np
        from scipy.stats import norm as _norm
        df_num = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
        for ci, col in enumerate(df_num.select_dtypes(include="number").columns.tolist()[:8]):
            data = df_num[col].dropna()
            if len(data) < 4:
                continue
            mu, sigma = float(data.mean()), float(data.std())

            fig = go.Figure()
            # Histogram
            fig.add_trace(go.Histogram(
                x=data.tolist(), nbinsx=28,
                name="Observed",
                marker=dict(
                    color=BRAND, opacity=0.8,
                    line=dict(color="white", width=0.8),
                ),
                histnorm="probability density",
                hovertemplate="Range: %{x}<br>Density: %{y:.4f}<extra></extra>",
            ))
            # Normal curve overlay
            if sigma > 0:
                x_line = np.linspace(float(data.min()) - sigma,
                                     float(data.max()) + sigma, 300)
                y_line = _norm.pdf(x_line, mu, sigma)
                fig.add_trace(go.Scatter(
                    x=x_line.tolist(), y=y_line.tolist(),
                    mode="lines", name=f"Normal curve (={mu:.2f}, ={sigma:.2f})",
                    line=dict(color=DANGER, width=2.5, dash="solid"),
                ))
            # Mean line
            fig.add_vline(x=mu, line=dict(color=WARN, width=2, dash="dash"),
                          annotation_text=f"Mean = {mu:.2f}",
                          annotation_position="top right",
                          annotation_font=dict(size=12, color=WARN))
            fig.update_layout(**_layout(
                title=dict(text=f"Distribution of '<b>{lbl(col)}</b>'",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis(lbl(col)),
                yaxis=_axis("Density"),
                barmode="overlay",
            ))
            if _want_viz('distribution') or _want_viz('histogram'):
                save(fig, f"chart_dist_{ci+1}_{_safe_col(col)}.png")
    except Exception:
        traceback.print_exc()

    #  CHART 5: Boxplots  all numeric vars 
    try:
        import pandas as pd
        df_num    = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
        box_cols  = df_num.select_dtypes(include="number").columns.tolist()[:10]
        if box_cols:
            fig = go.Figure()
            for ci, col in enumerate(box_cols):
                data = df_num[col].dropna().tolist()
                clr  = PALETTE[ci % len(PALETTE)]
                fig.add_trace(go.Box(
                    y=data, name=lbl(col, 4),
                    marker=dict(color=clr, size=4, opacity=0.6,
                                outliercolor=DANGER,
                                line=dict(outliercolor=DANGER, outlierwidth=1.5)),
                    line=dict(color=clr, width=2),
                    fillcolor=f"rgba({int(clr[1:3], 16)}, {int(clr[3:5], 16)}, {int(clr[5:7], 16)}, 0.2)",
                    boxmean="sd",
                    hovertemplate=(
                        f"<b>{lbl(col)}</b><br>"
                        "Value: %{y:.4f}<extra></extra>"
                    ),
                ))
            fig.update_layout(**_layout(
                title=dict(text="Boxplot - Distribution Comparison Across Variables",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis("Variable", tickangle=-30),
                yaxis=_axis("Value"),
                boxmode="group",
            ))
            if _want_viz('boxplot'):
                save(fig, "chart_boxplots.png", w=max(1000, len(box_cols) * 120), h=700)
    except Exception:
        traceback.print_exc()

    #  CHART 6: Scatter plot + regression line 
    try:
        import pandas as pd, numpy as np
        df_num   = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
        sc_cols  = df_num.select_dtypes(include="number").columns.tolist()[:4]
        if len(sc_cols) >= 2:
            xcol, ycol = sc_cols[0], sc_cols[1]
            valid = df_num[[xcol, ycol]].dropna()
            fig   = go.Figure()
            fig.add_trace(go.Scatter(
                x=valid[xcol].tolist(), y=valid[ycol].tolist(),
                mode="markers",
                name="Observations",
                marker=dict(
                    color=BRAND, size=7, opacity=0.6,
                    line=dict(color="white", width=0.8),
                ),
                hovertemplate=(f"<b>{lbl(xcol)}</b>: %{{x:.3f}}<br>"
                               f"<b>{lbl(ycol)}</b>: %{{y:.3f}}<extra></extra>"),
            ))
            if len(valid) > 2:
                m, b = np.polyfit(valid[xcol], valid[ycol], 1)
                xs   = np.linspace(float(valid[xcol].min()), float(valid[xcol].max()), 200)
                fig.add_trace(go.Scatter(
                    x=xs.tolist(), y=(m * xs + b).tolist(),
                    mode="lines", name=f"Trend line (slope={m:.3f})",
                    line=dict(color=DANGER, width=2.5),
                ))
            fig.update_layout(**_layout(
                title=dict(text=f"Scatter Plot: <b>{lbl(xcol)}</b> vs <b>{lbl(ycol)}</b>",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis(lbl(xcol)),
                yaxis=_axis(lbl(ycol)),
            ))
            if _want_viz('scatter'):
                save(fig, "chart_scatter.png")
    except Exception:
        traceback.print_exc()

    #  CHART 7: Violin plots  one per variable 
    try:
        import pandas as pd
        df_num   = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
        vio_cols = df_num.select_dtypes(include="number").columns.tolist()[:6]
        for vi, col in enumerate(vio_cols):
            data = df_num[col].dropna().tolist()
            clr  = PALETTE[vi % len(PALETTE)]
            fig  = go.Figure()
            fig.add_trace(go.Violin(
                y=data, name=lbl(col, 4),
                box_visible=True,
                meanline_visible=True,
                line_color=clr,
                fillcolor=f"rgba({int(clr[1:3], 16)}, {int(clr[3:5], 16)}, {int(clr[5:7], 16)}, 0.25)",
                opacity=0.85,
                points="outliers",
                marker=dict(color=DANGER, size=4, opacity=0.5),
            ))
            fig.update_layout(**_layout(
                title=dict(text=f"Violin Plot Distribution of '<b>{lbl(col)}</b>'",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis(""),
                yaxis=_axis(lbl(col)),
                showlegend=False,
            ))
            if _want_viz('violin'):
                save(fig, f"chart_violin_{vi+1}_{_safe_col(col)}.png", w=800, h=700)
    except Exception:
        traceback.print_exc()

    #  CHART 8: Q-Q plots  one per variable 
    try:
        import pandas as pd, numpy as np
        from scipy import stats as _stats
        df_num  = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
        qq_cols = df_num.select_dtypes(include="number").columns.tolist()[:6]
        for qi, col in enumerate(qq_cols):
            data = df_num[col].dropna()
            if len(data) < 4:
                continue
            (osm, osr), (slope, intercept, r) = _stats.probplot(data, dist="norm")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=osm.tolist(), y=osr.tolist(),
                mode="markers",
                name="Data quantiles",
                marker=dict(color=BRAND, size=7, opacity=0.65,
                            line=dict(color="white", width=0.8)),
                hovertemplate="Theoretical: %{x:.3f}<br>Sample: %{y:.3f}<extra></extra>",
            ))
            line_x = np.array([float(min(osm)), float(max(osm))])
            fig.add_trace(go.Scatter(
                x=line_x.tolist(),
                y=(slope * line_x + intercept).tolist(),
                mode="lines",
                name=f"Reference line  (r = {r:.3f})",
                line=dict(color=DANGER, width=2.5, dash="solid"),
            ))
            fig.update_layout(**_layout(
                title=dict(text=f"Q-Q Plot (Normality Check) - '<b>{lbl(col)}</b>'",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis("Theoretical Quantiles"),
                yaxis=_axis("Sample Quantiles"),
            ))
            if _want_viz('qqplot'):
                save(fig, f"chart_qq_{qi+1}_{_safe_col(col)}.png", w=800, h=700)
    except Exception:
        traceback.print_exc()

    #  CHART 9 + TABLE: Skewness & Kurtosis 
    try:
        sk_data  = results.get("skewness_kurtosis", {})
        cols_sk  = [k for k in sk_data
                    if isinstance(sk_data[k], dict) and "skewness" in sk_data[k]][:12]
        if cols_sk:
            skews    = [sk_data[c]["skewness"] for c in cols_sk]
            kurts    = [sk_data[c]["kurtosis"] for c in cols_sk]
            sk_cols  = [lbl(c, 4) for c in cols_sk]

            def _sk_color(v):
                return DANGER if abs(v) > 1 else WARN if abs(v) > 0.5 else SUCCESS

            # Skewness chart
            fig = go.Figure(go.Bar(
                x=sk_cols, y=skews,
                marker=dict(
                    color=[_sk_color(s) for s in skews],
                    line=dict(color="white", width=1.5),
                    opacity=0.85,
                ),
                text=[f"{s:.3f}" for s in skews],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Skewness: %{y:.4f}<extra></extra>",
            ))
            fig.add_hline(y=1,  line=dict(color=DANGER, dash="dash", width=1.5),
                          annotation_text="+1 threshold")
            fig.add_hline(y=-1, line=dict(color=DANGER, dash="dash", width=1.5),
                          annotation_text="-1 threshold")
            fig.add_hline(y=0,  line=dict(color="#374151", width=1))
            fig.update_layout(**_layout(
                title=dict(
                    text="Skewness by Variable<br>"
                         "<sup> |skew|>1   |skew|>0.5   symmetric</sup>",
                    font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis("Variable", tickangle=-35),
                yaxis=_axis("Skewness Coefficient"),
                bargap=0.3,
            ))
            save(fig, "chart_skewness.png")

            # Kurtosis chart
            fig2 = go.Figure(go.Bar(
                x=sk_cols, y=kurts,
                marker=dict(
                    color=[_sk_color(k) for k in kurts],
                    line=dict(color="white", width=1.5),
                    opacity=0.85,
                ),
                text=[f"{k:.3f}" for k in kurts],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Kurtosis: %{y:.4f}<extra></extra>",
            ))
            fig2.add_hline(y=0, line=dict(color="#374151", width=1))
            fig2.update_layout(**_layout(
                title=dict(
                    text="Excess Kurtosis by Variable<br>"
                         "<sup> |kurt|>1   |kurt|>0.5   near-normal</sup>",
                    font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis("Variable", tickangle=-35),
                yaxis=_axis("Excess Kurtosis"),
                bargap=0.3,
            ))
            save(fig2, "chart_kurtosis.png")

            # Skewness/Kurtosis Table
            sk_rows = [[lbl(c), f"{s:.4f}",
                        "High" if abs(s) > 1 else "Moderate" if abs(s) > 0.5 else "Symmetric",
                        f"{k:.4f}",
                        "Leptokurtic" if k > 1 else "Platykurtic" if k < -1 else "Near-normal"]
                       for c, s, k in zip(cols_sk, skews, kurts)]
            if _want_table('skewness_kurtosis'):
                fig3 = _table_fig(
                    ["Variable", "Skewness", "Skew Interpretation",
                     "Excess Kurtosis", "Kurtosis Interpretation"],
                    sk_rows,
                    "Skewness & Kurtosis Summary Table",
                    col_widths=[220, 110, 180, 130, 200],
                )
                h = max(400, 60 + len(sk_rows) * 32)
                save(fig3, "table_skewness_kurtosis.png", w=1000, h=h)
    except Exception:
        traceback.print_exc()

    #  CHART 10: Z-Score distributions  one per variable 
    try:
        import pandas as pd, numpy as np
        from scipy import stats as _stats
        z_data  = results.get("z_scores", {})
        df_num  = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
        z_cols  = [c for c in df_num.select_dtypes(include="number").columns.tolist()[:5]
                   if c in z_data]
        for zi, col in enumerate(z_cols):
            data   = df_num[col].dropna()
            z_vals = _stats.zscore(data).tolist()
            x_norm = list(range(-45, 46))
            x_norm_f = [x / 10 for x in x_norm]
            y_norm = _stats.norm.pdf(x_norm_f)
            pct    = z_data[col].get("area_within_1sd", "")

            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=z_vals, nbinsx=30,
                name="Observed z-scores",
                marker=dict(color=BRAND, opacity=0.78,
                            line=dict(color="white", width=0.8)),
                histnorm="probability density",
            ))
            fig.add_trace(go.Scatter(
                x=x_norm_f, y=y_norm.tolist(),
                mode="lines", name="Standard normal",
                line=dict(color=DANGER, width=2.5),
            ))
            fig.add_vline(x=-3, line=dict(color=WARN, dash="dash", width=1.8),
                          annotation_text="3")
            fig.add_vline(x=3,  line=dict(color=WARN, dash="dash", width=1.8),
                          annotation_text="+3")
            subtitle = f"    {pct:.1f}% of values within 1" if pct else ""
            fig.update_layout(**_layout(
                title=dict(
                    text=f"Z-Score Distribution  '<b>{col}</b>'{subtitle}",
                    font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis("Z-Score"),
                yaxis=_axis("Density"),
                barmode="overlay",
            ))
            save(fig, f"chart_zscore_{zi+1}_{_safe_col(col)}.png")
    except Exception:
        traceback.print_exc()

    #  CHART 11 + TABLE: Outlier summary 
    try:
        outlier_data = results.get("outliers", {})
        col_entries  = {k: v for k, v in outlier_data.items()
                        if isinstance(v, dict) and "iqr_method" in v}
        if col_entries:
            cols_o   = list(col_entries.keys())[:10]
            iqr_cnts = [col_entries[c]["iqr_method"]["count"] for c in cols_o]
            z_cnts   = [col_entries[c].get("zscore_method", {}).get("count", 0)
                        for c in cols_o]
            total_n  = max(len(df), 1)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[_trunc(c, 18) for c in cols_o], y=iqr_cnts,
                name="IQR method",
                marker=dict(color=BRAND, opacity=0.85,
                            line=dict(color="white", width=1.5)),
                text=[f"{v} ({v/total_n*100:.1f}%)" if v > 0 else "" for v in iqr_cnts],
                textposition="outside",
            ))
            fig.add_trace(go.Bar(
                x=[_trunc(c, 18) for c in cols_o], y=z_cnts,
                name="|z| > 3 method",
                marker=dict(color=DANGER, opacity=0.80,
                            line=dict(color="white", width=1.5)),
                text=[f"{v} ({v/total_n*100:.1f}%)" if v > 0 else "" for v in z_cnts],
                textposition="outside",
            ))
            fig.update_layout(**_layout(
                title=dict(text="Outlier Count by Variable & Detection Method",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis("Variable", tickangle=-35),
                yaxis=_axis("Number of Outliers"),
                barmode="group",
                bargap=0.25,
            ))
            save(fig, "chart_outliers.png")

            # Outlier Table
            o_rows = [[_trunc(c, 24),
                       f"{iq} ({iq/total_n*100:.1f}%)",
                       f"{z} ({z/total_n*100:.1f}%)",
                       str(col_entries[c]["iqr_method"].get("lower_bound", "")),
                       str(col_entries[c]["iqr_method"].get("upper_bound", ""))]
                      for c, iq, z in zip(cols_o, iqr_cnts, z_cnts)]
            if _want_table('outliers'):
                fig2 = _table_fig(
                    ["Variable", "IQR Outliers", "|z|>3 Outliers",
                     "IQR Lower", "IQR Upper"],
                    o_rows, "Outlier Detection Summary Table",
                    col_widths=[220, 130, 130, 110, 110],
                )
                h = max(400, 60 + len(o_rows) * 32)
                save(fig2, "table_outliers.png", w=800, h=h)
    except Exception:
        traceback.print_exc()

    #  CHART 12 + TABLE: Post-hoc Tukey HSD 
    try:
        posthoc    = results.get("posthoc", {})
        tukey_rows = posthoc.get("tukey_hsd", [])
        if tukey_rows and isinstance(tukey_rows, list) and tukey_rows:
            pairs   = [f"{r.get('group1','?')} vs {r.get('group2','?')}"
                       for r in tukey_rows[:20]]
            pvals   = [float(r.get("p-adj", r.get("pvalue", 1)))
                       for r in tukey_rows[:20]]
            reject  = [bool(r.get("reject", False)) for r in tukey_rows[:20]]
            colors  = [SUCCESS if r else DANGER for r in reject]
            diffs   = [r.get("meandiff", r.get("diff", "")) for r in tukey_rows[:20]]

            fig = go.Figure(go.Bar(
                x=pvals, y=pairs,
                orientation="h",
                marker=dict(color=colors, opacity=0.82,
                            line=dict(color="white", width=1.5)),
                text=[f"p={p:.4f}" for p in pvals],
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>p-adj: %{x:.4f}<extra></extra>",
            ))
            fig.add_vline(x=0.05, line=dict(color="#111827", dash="dash", width=2),
                          annotation_text=" = 0.05",
                          annotation_position="top right")
            fig.update_layout(**_layout(
                title=dict(text="Post-Hoc Pairwise Comparisons - Tukey HSD<br>"
                               "<sup> Significant   Not significant</sup>",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=_axis("Adjusted p-value"),
                yaxis=_axis("Comparison Pair", autorange="reversed"),
                height=max(500, len(pairs) * 38 + 120),
            ))
            save(fig, "chart_posthoc_tukey.png",
                 w=_W, h=max(500, len(pairs) * 38 + 120))

            if _want_table('posthoc'):
                ph_rows = [[pr,
                            f"{diff:.4f}" if isinstance(diff, (int, float)) else str(diff),
                            f"{pv:.4f}",
                            " Reject H" if rej else " Retain H"]
                           for pr, diff, pv, rej in zip(pairs, diffs, pvals, reject)]
                fig2 = _table_fig(
                    ["Comparison Pair", "Mean Difference", "Adj. p-value", "Decision"],
                    ph_rows, "Post-Hoc Tukey HSD Results Table",
                    col_widths=[280, 150, 120, 160],
                )
                h = max(400, 60 + len(ph_rows) * 32)
                save(fig2, "table_posthoc_tukey.png", w=800, h=h)
    except Exception:
        traceback.print_exc()

    #  TABLE + CHART 13: Normality summary 
    try:
        norm_ext  = results.get("normality_extended", {})
        norm_cols = [c for c in norm_ext if isinstance(norm_ext[c], dict)][:10]
        if norm_cols:
            test_labels = ["Shapiro-Wilk", "Anderson-Darling",
                           "Jarque-Bera", "D'Agostino"]
            test_keys   = ["shapiro_wilk", "anderson_darling",
                           "jarque_bera", "dagostino_pearson"]
            import numpy as np

            matrix, n_rows_tbl = [], []
            for col in norm_cols:
                row_vals, tbl_row = [], [_trunc(col, 24)]
                for tk in test_keys:
                    entry = norm_ext[col].get(tk)
                    if entry:
                        is_n = bool(entry.get("normal", False))
                        row_vals.append(1 if is_n else 0)
                        tbl_row.append(" Normal" if is_n else " Non-normal")
                    else:
                        row_vals.append(-1)
                        tbl_row.append("N/A")
                matrix.append(row_vals)
                n_rows_tbl.append(tbl_row)

            # Heatmap
            mat    = np.array(matrix, dtype=float)
            labels = [[" Normal" if v == 1 else " Non-normal" if v == 0 else "N/A"
                       for v in row] for row in matrix]
            fig = go.Figure(go.Heatmap(
                z=mat, x=test_labels,
                y=[_trunc(c, 20) for c in norm_cols],
                colorscale=[
                    [0.0, "#f9fafb"],
                    [0.5, "#fca5a5"],
                    [1.0, "#10b981"],
                ],
                zmin=-1, zmax=1,
                text=labels, texttemplate="%{text}",
                textfont=dict(size=12, color="#111827"),
                showscale=True,
                colorbar=dict(
                    title="Result",
                    tickvals=[-1, 0, 1],
                    ticktext=["N/A", "Non-normal", "Normal"],
                    thickness=16,
                ),
                hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
            ))
            fig.update_layout(**_layout(
                title=dict(text="Normality Test Results - Multi-test Summary",
                           font=_TITLE_FONT, x=0.5, xanchor="center"),
                xaxis=dict(tickfont=dict(size=12)),
                yaxis=dict(tickfont=dict(size=11), autorange="reversed"),
            ))
            h = max(500, len(norm_cols) * 55 + 150)
            save(fig, "chart_normality_summary.png", w=900, h=h)

            if _want_table('normality'):
                # Normality Table
                fig2 = _table_fig(
                    ["Variable"] + test_labels,
                    n_rows_tbl,
                    "Normality Test Results Table",
                    col_widths=[220, 150, 170, 140, 150],
                )
                h2 = max(400, 60 + len(n_rows_tbl) * 32)
                save(fig2, "table_normality.png", w=900, h=h2)
    except Exception:
        traceback.print_exc()

    #  CHART 14: Regression scatter 
    try:
        import pandas as pd, numpy as np
        summary = results.get("summary", [])
        for s in summary:
            if any(k in s.get("test_name", "").lower()
                   for k in ("correlation", "regression")):
                df_num  = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
                rc      = df_num.select_dtypes(include="number").columns.tolist()[:2]
                if len(rc) >= 2:
                    xcol, ycol = rc[0], rc[1]
                    valid = df_num[[xcol, ycol]].dropna()
                    fig   = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=valid[xcol].tolist(), y=valid[ycol].tolist(),
                        mode="markers",
                        name="Observations",
                        marker=dict(color=BRAND, size=7, opacity=0.6,
                                    line=dict(color="white", width=0.8)),
                        hovertemplate=(f"<b>{xcol}</b>: %{{x:.3f}}<br>"
                                       f"<b>{ycol}</b>: %{{y:.3f}}<extra></extra>"),
                    ))
                    if len(valid) > 2:
                        m, b = np.polyfit(valid[xcol], valid[ycol], 1)
                        xs   = np.linspace(float(valid[xcol].min()),
                                           float(valid[xcol].max()), 200)
                        fig.add_trace(go.Scatter(
                            x=xs.tolist(), y=(m * xs + b).tolist(),
                            mode="lines", name=f"Regression line (slope={m:.3f})",
                            line=dict(color=DANGER, width=2.5),
                        ))
                    fig.update_layout(**_layout(
                        title=dict(
                            text=f"Regression / Correlation Scatter<br>"
                                 f"<b>{xcol}</b> vs <b>{ycol}</b>",
                            font=_TITLE_FONT, x=0.5, xanchor="center"),
                        xaxis=_axis(xcol),
                        yaxis=_axis(ycol),
                    ))
                    save(fig, "chart_regression.png")
                break
    except Exception:
        traceback.print_exc()

    return chart_paths


# ─── HTML Table Generator ──────────────────────────────────────────────────────

def generate_html_tables(results: dict, df, brief: dict, label_map: dict = None) -> dict:
    """
    Generate APA-formatted HTML tables from analysis results.
    Returns dict of { section_key: html_string }.
    Tables use APA 7th style: no vertical lines, bold header, horizontal lines only.
    Each cell has a data-value attribute for clean copy-paste.
    """
    _lmap = label_map or {}

    def _lbl(col):
        if col in _lmap:
            return _lmap[col]
        import re
        clean = re.sub(r'^q\d+_?', '', str(col))
        clean = re.sub(r'[_\-]+', ' ', clean).strip().title()
        return clean or col

    def _sig(p):
        if p is None:
            return ""
        try:
            p = float(p)
            if p < 0.001: return "***"
            if p < 0.01:  return "**"
            if p < 0.05:  return "*"
        except Exception:
            pass
        return ""

    def _fmt(v, decimals=3):
        if v is None:
            return "—"
        try:
            f = float(v)
            if f != f:  # nan
                return "—"
            return f"{f:.{decimals}f}"
        except Exception:
            return str(v)

    _CSS = """
<style>
.rf-wrap{overflow-x:auto;border-radius:12px;box-shadow:0 2px 20px rgba(99,102,241,0.12);margin-bottom:28px;background:#fff}
.rf-table{border-collapse:collapse;width:100%;min-width:720px;font-family:'Inter',Arial,sans-serif;font-size:13px;color:#1e293b}
.rf-table caption{text-align:left;font-weight:700;font-size:15px;padding:14px 18px 6px;color:#0f172a;letter-spacing:-0.01em}
.rf-table thead tr{background:linear-gradient(135deg,#6366f1,#4f46e5);border-top:none}
.rf-table th{font-weight:700;padding:11px 18px;text-align:center;color:#fff;white-space:nowrap;font-size:12px;letter-spacing:0.03em}
.rf-table th:first-child{text-align:left;min-width:170px}
.rf-table td{padding:9px 18px;text-align:center;border:none;min-width:90px}
.rf-table td:first-child{text-align:left;font-weight:600;color:#0f172a;border-right:1px solid rgba(99,102,241,0.10)}
.rf-table tbody tr:nth-child(even){background:rgba(99,102,241,0.035)}
.rf-table tbody tr:nth-child(odd){background:#fff}
.rf-table tbody tr:last-child{border-bottom:2.5px solid #6366f1}
.rf-table tbody tr:hover{background:rgba(99,102,241,0.08);transition:background 0.15s}
.rf-table .sig{color:#6366f1;font-weight:800;font-size:11px;margin-left:2px}
.rf-note{font-size:11px;color:#64748b;padding:4px 18px 12px;font-style:italic;border-top:1px solid rgba(99,102,241,0.08)}
</style>"""

    def _table(caption, headers, rows, note=""):
        """Build one APA HTML table with brand-themed styling and full width."""
        head_html = "".join(f"<th>{h}</th>" for h in headers)
        body_html  = ""
        for row in rows:
            cells = "".join(
                f'<td data-value="{str(v)}">{v}</td>' for v in row
            )
            body_html += f"<tr>{cells}</tr>"
        note_html = f'<p class="rf-note">Note. {note}</p>' if note else ""
        return (
            f'{_CSS}<div class="rf-wrap">'
            f'<table class="rf-table">'
            f'<caption>{caption}</caption>'
            f'<thead><tr>{head_html}</tr></thead>'
            f'<tbody>{body_html}</tbody>'
            f'</table>{note_html}</div>'
        )

    tables = {}

    # ── Normalize: flatten nested bucket structure so all look-ups work with
    #    both dispatcher nested format {"family": {"test": result}}
    #    and any legacy flat format {"test": result}.
    _NON_BUCKET = {"summary", "meta", "health_report", "not_applicable",
                   "warnings", "fallbacks_applied"}
    _flat: dict = {}
    for _bk, _bv in results.items():
        if _bk not in _NON_BUCKET and isinstance(_bv, dict):
            _flat.update(_bv)          # merge all test_name→result pairs
        else:
            _flat[_bk] = _bv           # keep summary list, meta dict, etc.
    # Reliability section iterates the entire bucket, so preserve it separately
    _rel_bucket = results.get("reliability", {})

    # ── Descriptive Statistics ────────────────────────────────────────────────
    try:
        desc_data = _flat.get("descriptive_stats", {}) or {}
        stats = (desc_data.get("additional_stats") or {}).get("columns") or desc_data
        rows = []
        for col, s in stats.items():
            if not isinstance(s, dict):
                continue
            rows.append([
                _lbl(col),
                s.get("n", "—"),
                _fmt(s.get("mean")),
                _fmt(s.get("std")),
                _fmt(s.get("min")),
                _fmt(s.get("max")),
                _fmt(s.get("skewness") or s.get("skew")),
                _fmt(s.get("kurtosis")),
            ])
        if rows:
            tables["descriptive"] = _table(
                "Descriptive Statistics",
                ["Variable", "N", "M", "SD", "Min", "Max", "Skew", "Kurt"],
                rows,
                note="M = Mean; SD = Standard Deviation. *p < .05. **p < .01. ***p < .001."
            )
    except Exception:
        pass

    # ── Reliability ───────────────────────────────────────────────────────────
    try:
        rel = _rel_bucket
        rel_rows = []
        for test_key, val in rel.items():
            if not isinstance(val, dict):
                continue
            stats = val.get("additional_stats") or {}
            alpha_val = stats.get("alpha") or stats.get("cronbach_alpha") or val.get("statistic")
            n_items   = stats.get("n_items") or "—"
            rel_rows.append([test_key.replace("_", " ").title(),
                              _fmt(alpha_val), str(n_items),
                              "Acceptable" if alpha_val and float(alpha_val) >= 0.70 else "Low"])
        if rel_rows:
            tables["reliability"] = _table(
                "Reliability Statistics",
                ["Scale", "Cronbach's α", "N Items", "Interpretation"],
                rel_rows,
                note="α ≥ 0.70 = acceptable; α ≥ 0.80 = good; α ≥ 0.90 = excellent."
            )
    except Exception:
        pass

    # ── Correlation Matrix ────────────────────────────────────────────────────
    try:
        corr_result = _flat.get("correlation_matrix") or _flat.get("pearson_correlation") or {}
        corr_stats  = (corr_result.get("additional_stats") or {})
        matrix = corr_stats.get("matrix") or corr_stats.get("columns")
        if isinstance(matrix, dict):
            cols = list(matrix.keys())
            labels = [_lbl(c) for c in cols]
            headers = ["Variable"] + [f"{i+1}. {l}" for i, l in enumerate(labels)]
            rows = []
            for i, col in enumerate(cols):
                row = [f"{i+1}. {_lbl(col)}"]
                for j, col2 in enumerate(cols):
                    if j < i:
                        row.append("—")
                    elif j == i:
                        row.append("1.000")
                    else:
                        r_val = matrix[col].get(col2) or matrix[col2].get(col) if col2 in matrix else "—"
                        row.append(_fmt(r_val))
                rows.append(row)
            if rows:
                tables["correlation"] = _table(
                    "Correlation Matrix",
                    headers, rows,
                    note="* p < .05. ** p < .01. *** p < .001."
                )
    except Exception:
        pass

    # ── Test Results (parametric / non-parametric) ────────────────────────────
    try:
        test_rows = []
        for val in _flat.get("summary", []):
            if val.get("error"):
                continue  # Errors go in Key Findings, not APA tables
            
            stat_obj = val.get("statistic") or {}
            stat_val = stat_obj.get("value") if isinstance(stat_obj, dict) else None
            p_val = val.get("p_value")
            sig = _sig(p_val)
            test_rows.append([
                val.get("test_name", "Test").title(),
                _fmt(stat_val),
                _fmt(p_val, 4),
                sig,
                val.get("conclusion", "")[:60],
            ])
        if test_rows:
            tables["test_results"] = _table(
                "Statistical Test Results",
                ["Test", "Statistic", "p", "Sig.", "Conclusion"],
                test_rows,
                note="* p < .05. ** p < .01. *** p < .001."
            )
    except Exception:
        pass

    # ── CFA Fit Indices ───────────────────────────────────────────────────────
    try:
        cfa_result = _flat.get("confirmatory_fa") or {}
        cfa_stats  = (cfa_result.get("additional_stats") or {}) if cfa_result else {}
        if cfa_stats:
            fit_rows = [
                ["CFI", _fmt(cfa_stats.get("CFI")), "≥ 0.95",
                 "✓" if (cfa_stats.get("CFI") or 0) >= 0.95 else "✗"],
                ["TLI", _fmt(cfa_stats.get("TLI")), "≥ 0.95",
                 "✓" if (cfa_stats.get("TLI") or 0) >= 0.95 else "✗"],
                ["RMSEA", f'{_fmt(cfa_stats.get("RMSEA"))} [{_fmt(cfa_stats.get("RMSEA_lo90"))}, {_fmt(cfa_stats.get("RMSEA_hi90"))}]',
                 "≤ 0.06", "✓" if (cfa_stats.get("RMSEA") or 1) <= 0.06 else "✗"],
                ["SRMR", _fmt(cfa_stats.get("SRMR")), "≤ 0.08",
                 "✓" if (cfa_stats.get("SRMR") or 1) <= 0.08 else "✗"],
                ["χ²", f'{_fmt(cfa_stats.get("chi2"), 2)} (df={cfa_stats.get("df","—")})', "—", "—"],
                ["AIC", _fmt(cfa_stats.get("AIC"), 1), "Lower = better", "—"],
                ["BIC", _fmt(cfa_stats.get("BIC"), 1), "Lower = better", "—"],
            ]
            tables["cfa_fit"] = _table(
                "CFA Model Fit Indices",
                ["Index", "Value", "Criterion", "Status"],
                fit_rows,
                note="CFI = Comparative Fit Index; TLI = Tucker-Lewis Index; "
                     "RMSEA = Root Mean Square Error of Approximation [90% CI]; "
                     "SRMR = Standardized Root Mean Square Residual."
            )
    except Exception:
        pass

    # ── Regression Summary ────────────────────────────────────────────────────
    try:
        reg = (_flat.get("multiple_regression") or _flat.get("simple_linear_regression")
               or _flat.get("hierarchical_regression") or {})
        reg_stats = (reg.get("additional_stats") or {}) if reg else {}
        coefs = reg_stats.get("coefficients") or reg_stats.get("betas") or []
        if coefs:
            rows = []
            for c in coefs:
                rows.append([
                    c.get("predictor", c.get("variable", "")),
                    _fmt(c.get("b") or c.get("B") or c.get("coef")),
                    _fmt(c.get("SE") or c.get("std_err")),
                    _fmt(c.get("beta_std") or c.get("beta") or c.get("std_coef")),
                    _fmt(c.get("t") or c.get("z")),
                    _fmt(c.get("p") or c.get("p_value"), 4) + _sig(c.get("p") or c.get("p_value")),
                    f'[{_fmt(c.get("CI_lower"))}, {_fmt(c.get("CI_upper"))}]',
                ])
            tables["regression"] = _table(
                "Regression Coefficients",
                ["Predictor", "B", "SE", "β", "t", "p", "95% CI"],
                rows,
                note=f'R² = {_fmt(reg_stats.get("r_squared"))}, '
                     f'Adjusted R² = {_fmt(reg_stats.get("adj_r_squared"))}, '
                     f'F = {_fmt(reg_stats.get("f_statistic") or reg_stats.get("F"))}, '
                     f'p = {_fmt(reg_stats.get("f_pvalue") or reg_stats.get("p_value"),4)}. '
                     f'* p < .05. ** p < .01. *** p < .001.'
            )
    except Exception:
        pass

    # -- Robust Regression Coefficients (HC3) ---------------------------------
    try:
        reg_r = (_flat.get('multiple_regression') or _flat.get('simple_linear_regression')
                 or _flat.get('hierarchical_regression') or {})
        reg_rs = (reg_r.get('additional_stats') or {}) if reg_r else {}
        robust_coefs = reg_rs.get('robust_coefficients') or []
        if robust_coefs:
            rows = []
            for c in robust_coefs:
                rows.append([
                    c.get('predictor', ''),
                    _fmt(c.get('b')),
                    _fmt(c.get('SE_robust') or c.get('SE')),
                    _fmt(c.get('beta_std')),
                    _fmt(c.get('t')),
                    _fmt(c.get('p'), 4) + _sig(c.get('p')),
                    f'[{_fmt(c.get("CI_lower"))}, {_fmt(c.get("CI_upper"))}]',
                ])
            tables['regression_robust'] = _table(
                'Regression Coefficients (HC3 Robust Standard Errors)',
                ['Predictor', 'B', 'SE_HC3', 'β', 't', 'p', '95% CI'],
                rows,
                note='HC3 heteroscedasticity-consistent SEs (White, 1980). Use these when the Breusch-Pagan test is significant. * p < .05. ** p < .01. *** p < .001.'
            )
    except Exception:
        pass

    # -- Hierarchical Linear Model (HLM) / MixedLM ----------------------------
    try:
        lmm = _flat.get('linear_mixed_model') or {}
        lmm_stats = lmm.get('additional_stats') or {}
        if lmm_stats.get('fixed_effects') and lmm_stats.get('variance_components'):
            fe_rows = []
            for c in lmm_stats.get('fixed_effects', []):
                fe_rows.append([
                    c.get('predictor', ''),
                    _fmt(c.get('estimate')),
                    _fmt(c.get('SE')),
                    _fmt(c.get('z')),
                    _fmt(c.get('p'), 4) + _sig(c.get('p')),
                    f'[{_fmt(c.get("CI_lower"))}, {_fmt(c.get("CI_upper"))}]',
                ])
            tables['lmm_fixed'] = _table(
                'HLM Fixed Effects',
                ['Predictor', 'Estimate', 'SE', 'z', 'p', '95% CI'],
                fe_rows,
                note=f'Log-Likelihood = {_fmt(lmm_stats.get("log_likelihood"))}, AIC = {_fmt(lmm_stats.get("AIC"))}. * p < .05. ** p < .01. *** p < .001.'
            )
            re_rows = []
            for vc in lmm_stats.get('variance_components', []):
                icc_fmt = f"{vc.get('icc', 0) * 100:.2f}%" if vc.get('level') != 'Residual' else '-'
                re_rows.append([
                    vc.get('level', ''),
                    _fmt(vc.get('variance')),
                    icc_fmt
                ])
            tables['lmm_random'] = _table(
                'HLM Random Effects (Variance Components)',
                ['Level', 'Variance', 'ICC (%)'],
                re_rows,
                note=f'Total ICC (Variance explained by grouping structure) = {lmm_stats.get("total_icc", 0) * 100:.2f}%.'
            )
    except Exception:
        pass

    # -- Planned Contrasts ----------------------------------------------------
    try:
        pc = _flat.get('planned_contrasts') or {}
        pc_stats = (pc.get('additional_stats') or {}) if pc else {}
        contrasts = pc_stats.get('contrasts') or []
        if contrasts:
            rows = [
                [
                    c['contrast'],
                    _fmt(c['L']),
                    _fmt(c['SE']),
                    _fmt(c['t']),
                    str(c['df']),
                    _fmt(c['p'], 4) + _sig(c['p']),
                    _fmt(c['cohens_d']),
                    'Yes' if c['significant'] else 'No',
                ]
                for c in contrasts
            ]
            tables['planned_contrasts'] = _table(
                'Planned Contrasts',
                ['Contrast', 'L', 'SE', 't', 'df', 'p', 'Cohen\'s d', 'Sig.'],
                rows,
                note="L = contrast estimate. Cohen's d computed against pooled within-group SD. Helmert contrasts used unless custom weights provided in brief. * p < .05. ** p < .01. *** p < .001."
            )
    except Exception:
        pass
    return tables

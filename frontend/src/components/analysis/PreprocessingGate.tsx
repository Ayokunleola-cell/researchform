// src/components/analysis/PreprocessingGate.tsx
import React, { useState, useMemo } from 'react';
import {
  RiBrainFill,
  RiSettings3Fill,
  RiCheckboxCircleFill,
  RiArrowRightSFill,
  RiArrowLeftSFill,
  RiBarChart2Fill,
  RiAlertFill,
  RiLineChartFill,
  RiRefreshLine,
  RiShieldCheckFill,
  RiLoader4Line,
  RiDatabase2Fill,
  RiPercentFill,
  RiStackFill,
  RiFlashlightFill,
  RiErrorWarningFill,
  RiFilter3Fill,
  RiSparklingFill,
} from 'react-icons/ri';
import { analysisApi } from '@/lib/api';
import toast from 'react-hot-toast';

// ─── Types ───────────────────────────────────────────────────────────────────
interface ColumnProfile {
  dtype: string;
  inferred_type: string;
  n_missing: number;
  pct_missing: number;
  n_unique: number;
  issues: string[];
  recommended_missing_strategy?: string;
  n_outliers_iqr?: number;
  skewness?: number;
  skew_severity?: string;
}

interface InspectionReport {
  data_quality_score?: number;
  quality_label?: string;
  shape_before?: { rows: number; columns: number };
  completeness_pct?: number;
  pct_complete_rows?: number;
  n_duplicates_found?: number;
  column_profiles?: Record<string, ColumnProfile>;
  missing_per_column?: Record<string, { pct_missing: number; recommended_strategy: string }>;
  outliers?: Record<string, { pct_outliers: number }>;
  inconsistencies?: Record<string, object>;
  skewed_columns?: string[];
}

interface PreprocessingGateProps {
  jobId: string;
  inspectionReport: InspectionReport;
  onComplete: () => void;
}

// ─── Strategy option banks ────────────────────────────────────────────────────
const IMPUTE_OPTIONS = [
  { value: 'keep',          label: 'Keep as-is' },
  { value: 'median_impute', label: 'Median imputation' },
  { value: 'mean_impute',   label: 'Mean imputation' },
  { value: 'mode_impute',   label: 'Mode imputation' },
  { value: 'knn_impute',    label: 'KNN imputation' },
  { value: 'mice_impute',   label: 'MICE imputation' },
  { value: 'drop_column',   label: 'Drop column' },
];
const OUTLIER_OPTIONS = [
  { value: 'keep',            label: 'Keep as-is' },
  { value: 'winsorize',       label: 'Winsorize (1st–99th %)' },
  { value: 'remove_outliers', label: 'Remove outlier rows' },
];
const SKEW_OPTIONS = [
  { value: 'keep',          label: 'Keep as-is' },
  { value: 'log_transform', label: 'Log1p transform' },
];
const INCONSISTENCY_OPTIONS = [
  { value: 'keep',              label: 'Keep as-is' },
  { value: 'standardise_case', label: 'Standardise case (Title Case)' },
];

// ─── Score ring ───────────────────────────────────────────────────────────────
function QualityRing({ score }: { score: number }) {
  const r = 38;
  const circ = 2 * Math.PI * r;
  const color = score >= 90 ? 'var(--success)' : score >= 70 ? 'var(--brand)' : score >= 50 ? 'var(--warning)' : 'var(--danger)';
  return (
    <svg width={96} height={96} viewBox="0 0 96 96" style={{ overflow: 'visible' }}>
      <circle cx={48} cy={48} r={r} fill="none" stroke="var(--border)" strokeWidth={7} />
      <circle
        cx={48} cy={48} r={r} fill="none"
        stroke={color} strokeWidth={7}
        strokeDasharray={`${(score / 100) * circ} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-90 48 48)"
        style={{ transition: 'stroke-dasharray 1s cubic-bezier(0.4,0,0.2,1)' }}
      />
      <text x={48} y={44} textAnchor="middle" fill={color} fontSize={18} fontWeight={700} fontFamily="Syne, sans-serif">{score}</text>
      <text x={48} y={60} textAnchor="middle" fill="var(--text-3)" fontSize={10} fontWeight={500}>/100</text>
    </svg>
  );
}

// ─── Stat pill ────────────────────────────────────────────────────────────────
function StatPill({ icon: Icon, label, value, color }: { icon: any; label: string; value: string; color?: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      background: 'var(--surface-2)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', padding: '10px 16px', minWidth: 130,
    }}>
      <Icon size={18} style={{ color: color || 'var(--brand)', flexShrink: 0 }} />
      <div>
        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', lineHeight: 1.2 }}>{value}</div>
        <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 1 }}>{label}</div>
      </div>
    </div>
  );
}

// ─── Issue type config ────────────────────────────────────────────────────────
const ISSUE_CONFIG = {
  missing:       { icon: RiAlertFill,        color: 'var(--warning)', bg: 'rgba(234,88,12,0.1)',   label: 'Missing' },
  outlier:       { icon: RiErrorWarningFill, color: 'var(--danger)',  bg: 'rgba(220,38,38,0.1)',   label: 'Outlier' },
  skew:          { icon: RiLineChartFill,    color: 'var(--brand)',   bg: 'rgba(99,102,241,0.12)', label: 'Skewed' },
  inconsistency: { icon: RiRefreshLine,      color: 'var(--success)', bg: 'rgba(5,150,105,0.1)',   label: 'Inconsistent' },
} as const;

type IssueType = keyof typeof ISSUE_CONFIG;

// ─── Main Component ───────────────────────────────────────────────────────────
export default function PreprocessingGate({ jobId, inspectionReport: report, onComplete }: PreprocessingGateProps) {
  const [mode, setMode] = useState<'auto' | 'manual' | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [manualChoices, setManualChoices] = useState<Record<string, string>>({});

  const score   = report?.data_quality_score ?? 0;
  const label   = report?.quality_label ?? 'Unknown';
  const rows    = report?.shape_before?.rows ?? 0;
  const cols    = report?.shape_before?.columns ?? 0;
  const missing = report?.missing_per_column ?? {};
  const outliers = report?.outliers ?? {};
  const skewed   = report?.skewed_columns ?? [];
  const incons   = report?.inconsistencies ?? {};

  // Build unified issue list
  const issueRows = useMemo(() => {
    const out: Array<{
      col: string;
      issueType: IssueType;
      issueLabel: string;
      recommended: string;
      options: Array<{ value: string; label: string }>;
    }> = [];

    Object.entries(missing).forEach(([col, info]) => {
      if (info.pct_missing > 0) {
        out.push({ col, issueType: 'missing', issueLabel: `${info.pct_missing}% missing`, recommended: info.recommended_strategy || 'median_impute', options: IMPUTE_OPTIONS });
      }
    });
    Object.entries(outliers).forEach(([col, info]) => {
      out.push({ col, issueType: 'outlier', issueLabel: `${info.pct_outliers}% outliers`, recommended: info.pct_outliers < 2 ? 'remove_outliers' : 'winsorize', options: OUTLIER_OPTIONS });
    });
    skewed.forEach(col => {
      if (!out.find(r => r.col === col && r.issueType === 'skew')) {
        const sk = report?.column_profiles?.[col]?.skewness;
        out.push({ col, issueType: 'skew', issueLabel: sk ? `Skew: ${sk.toFixed(2)}` : 'Highly skewed', recommended: 'log_transform', options: SKEW_OPTIONS });
      }
    });
    Object.keys(incons).forEach(col => {
      out.push({ col, issueType: 'inconsistency', issueLabel: 'Case variants', recommended: 'standardise_case', options: INCONSISTENCY_OPTIONS });
    });
    return out;
  }, [report]);

  const initChoices = () => {
    const d: Record<string, string> = {};
    issueRows.forEach(r => { d[r.col] = r.recommended; });
    setManualChoices(d);
  };

  const handleMode = (m: 'auto' | 'manual') => {
    setMode(m);
    if (m === 'manual') initChoices();
  };

  const handleSubmit = async () => {
    if (!mode) return;
    setSubmitting(true);
    try {
      await analysisApi.submitPreprocessingChoice(jobId, {
        mode,
        manual_choices: mode === 'manual' ? manualChoices : {},
      });
      toast.success(mode === 'auto' ? 'AI preprocessing applied — pipeline continuing…' : 'Manual choices submitted — pipeline continuing…');
      onComplete();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Could not submit preprocessing choice');
    } finally {
      setSubmitting(false);
    }
  };

  // ─── Quality score colour helper
  const scoreColor = score >= 90 ? 'var(--success)' : score >= 70 ? 'var(--brand)' : score >= 50 ? 'var(--warning)' : 'var(--danger)';

  return (
    <div className="animate-slide-up" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Header banner ── */}
      <div className="card" style={{ padding: '20px 24px', borderLeft: '3px solid var(--brand)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10, flexShrink: 0,
            background: 'rgba(99,102,241,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <RiFilter3Fill size={20} style={{ color: 'var(--brand)' }} />
          </div>
          <div>
            <p style={{ margin: 0, fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>
              Stage 1 — Inspection Complete
            </p>
            <p style={{ margin: '2px 0 0', fontSize: 13, color: 'var(--text-3)' }}>
              Your dataset has been profiled. Choose how to preprocess it before analysis continues.
            </p>
          </div>
        </div>
      </div>

      {/* ── Quality snapshot ── */}
      <div className="card" style={{ padding: '20px 24px' }}>
        <p style={{ margin: '0 0 16px', fontSize: 12, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Data Quality Report
        </p>
        <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Score ring */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0 }}>
            <QualityRing score={score} />
            <div>
              <div style={{ fontSize: 20, fontWeight: 800, color: scoreColor, fontFamily: 'Syne, sans-serif', lineHeight: 1 }}>{label}</div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>{rows.toLocaleString()} rows · {cols} columns</div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{issueRows.length} issue{issueRows.length !== 1 ? 's' : ''} detected</div>
            </div>
          </div>

          <div style={{ width: '1px', height: 64, background: 'var(--border)', flexShrink: 0 }} />

          {/* Stats */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <StatPill icon={RiPercentFill}       label="Completeness"   value={`${report?.completeness_pct ?? 0}%`} />
            <StatPill icon={RiStackFill}          label="Complete rows"  value={`${report?.pct_complete_rows ?? 0}%`} />
            <StatPill icon={RiDatabase2Fill}      label="Issues found"   value={`${issueRows.length}`} color="var(--warning)" />
            <StatPill icon={RiRefreshLine}        label="Duplicates"     value={`${report?.n_duplicates_found ?? 0}`} color="var(--danger)" />
          </div>
        </div>
      </div>

      {/* ── Mode selector ── */}
      {!mode && (
        <div>
          <p style={{ margin: '0 0 14px', fontSize: 12, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Choose Preprocessing Strategy
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {/* Auto card */}
            <button
              onClick={() => handleMode('auto')}
              className="card"
              style={{
                padding: '28px 24px', cursor: 'pointer', textAlign: 'left',
                border: '1px solid var(--border)', background: 'var(--surface)',
                transition: 'all 0.18s', color: 'inherit',
                display: 'flex', flexDirection: 'column', gap: 14,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'var(--brand)';
                e.currentTarget.style.boxShadow = 'var(--glow)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.boxShadow = 'var(--shadow)';
                e.currentTarget.style.transform = 'none';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 12, flexShrink: 0,
                  background: 'linear-gradient(135deg, var(--brand-dark), var(--brand-light))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: '0 4px 12px rgba(99,102,241,0.35)',
                }}>
                  <RiBrainFill size={22} color="var(--brand-text)" />
                </div>
                <span className="badge badge-brand" style={{ fontSize: 11 }}>Recommended</span>
              </div>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', fontFamily: 'Syne, sans-serif', marginBottom: 6 }}>
                  AI Auto Preprocessing
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.7 }}>
                  The AI analyses your dataset structure and selects the optimal cleaning strategy for each column automatically.
                </div>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {['Smart imputation', 'Outlier handling', 'Skew correction', 'Deduplication'].map(t => (
                  <span key={t} className="badge badge-brand" style={{ fontSize: 11 }}>{t}</span>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--brand)', fontSize: 13, fontWeight: 600, marginTop: 4 }}>
                <RiSparklingFill size={14} /> Select AI Preprocessing <RiArrowRightSFill size={16} />
              </div>
            </button>

            {/* Manual card */}
            <button
              onClick={() => handleMode('manual')}
              className="card"
              style={{
                padding: '28px 24px', cursor: 'pointer', textAlign: 'left',
                border: '1px solid var(--border)', background: 'var(--surface)',
                transition: 'all 0.18s', color: 'inherit',
                display: 'flex', flexDirection: 'column', gap: 14,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'var(--success)';
                e.currentTarget.style.boxShadow = '0 0 24px rgba(5,150,105,0.2)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.boxShadow = 'var(--shadow)';
                e.currentTarget.style.transform = 'none';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 12, flexShrink: 0,
                  background: 'linear-gradient(135deg, #059669, #34d399)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: '0 4px 12px rgba(5,150,105,0.35)',
                }}>
                  <RiSettings3Fill size={22} color="#fff" />
                </div>
                <span className="badge badge-success" style={{ fontSize: 11 }}>Full control</span>
              </div>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', fontFamily: 'Syne, sans-serif', marginBottom: 6 }}>
                  Manual Preprocessing
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.7 }}>
                  Review each detected issue column by column and select exactly how it should be handled. Recommendations pre-filled.
                </div>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {['Per-column control', 'Pre-filled recommendations', `${issueRows.length} decision${issueRows.length !== 1 ? 's' : ''}`].map(t => (
                  <span key={t} className="badge badge-success" style={{ fontSize: 11, color: 'var(--success)', background: 'rgba(5,150,105,0.1)' }}>{t}</span>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--success)', fontSize: 13, fontWeight: 600, marginTop: 4 }}>
                <RiShieldCheckFill size={14} /> Configure manually <RiArrowRightSFill size={16} />
              </div>
            </button>
          </div>
        </div>
      )}

      {/* ── Auto confirmation ── */}
      {mode === 'auto' && (
        <div className="card animate-slide-up" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <button
              onClick={() => setMode(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}
            >
              <RiArrowLeftSFill size={18} /> Back
            </button>
          </div>

          <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
            <div style={{
              width: 44, height: 44, borderRadius: 11, flexShrink: 0,
              background: 'linear-gradient(135deg, var(--brand-dark), var(--brand-light))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <RiBrainFill size={20} color="var(--brand-text)" />
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ margin: '0 0 4px', fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>
                AI will handle {issueRows.length} issue{issueRows.length !== 1 ? 's' : ''} automatically
              </p>
              <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--text-3)' }}>
                The optimal strategy is selected based on column type, missingness pattern and distribution.
              </p>

              {issueRows.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {issueRows.slice(0, 6).map(r => {
                    const cfg = ISSUE_CONFIG[r.issueType];
                    return (
                      <div key={`${r.col}-${r.issueType}`} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '8px 12px', borderRadius: 'var(--radius-sm)',
                        background: 'var(--surface-2)', border: '1px solid var(--border)',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <cfg.icon size={14} style={{ color: cfg.color }} />
                          <span style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500 }}>{r.col}</span>
                          <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{r.issueLabel}</span>
                        </div>
                        <span style={{ fontSize: 12, color: 'var(--brand)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <RiFlashlightFill size={12} />
                          {r.options.find(o => o.value === r.recommended)?.label}
                        </span>
                      </div>
                    );
                  })}
                  {issueRows.length > 6 && (
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--text-3)', paddingLeft: 12 }}>
                      + {issueRows.length - 6} more column{issueRows.length - 6 !== 1 ? 's' : ''} handled automatically
                    </p>
                  )}
                </div>
              )}
              {issueRows.length === 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--success)', fontSize: 13 }}>
                  <RiCheckboxCircleFill size={16} />
                  Dataset looks clean — no issues to fix.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Manual choices table ── */}
      {mode === 'manual' && (
        <div className="card animate-slide-up" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button
                onClick={() => setMode(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}
              >
                <RiArrowLeftSFill size={18} /> Back
              </button>
              <span style={{ color: 'var(--border)' }}>|</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <RiSettings3Fill size={16} style={{ color: 'var(--success)' }} />
                <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>Column-by-Column Settings</span>
              </div>
            </div>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
              {issueRows.length} issue{issueRows.length !== 1 ? 's' : ''} · pre-filled with recommendations
            </span>
          </div>

          {issueRows.length === 0 ? (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px',
              background: 'rgba(5,150,105,0.06)', border: '1px solid rgba(5,150,105,0.2)',
              borderRadius: 'var(--radius)', color: 'var(--success)', fontSize: 13,
            }}>
              <RiCheckboxCircleFill size={18} />
              No issues detected — dataset is clean and ready.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Column', 'Issue type', 'Details', 'Strategy'].map(h => (
                      <th key={h} style={{
                        padding: '8px 12px', textAlign: 'left',
                        fontSize: 11, fontWeight: 700, color: 'var(--text-3)',
                        textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {issueRows.map((row, i) => {
                    const cfg = ISSUE_CONFIG[row.issueType];
                    return (
                      <tr
                        key={`${row.col}-${row.issueType}`}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          background: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-2)',
                          transition: 'background 0.12s',
                        }}
                      >
                        {/* Column name */}
                        <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', fontFamily: 'JetBrains Mono, monospace' }}>
                            {row.col}
                          </span>
                        </td>
                        {/* Issue type badge */}
                        <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: 5,
                            padding: '3px 10px', borderRadius: 20,
                            background: cfg.bg, color: cfg.color,
                            fontSize: 11, fontWeight: 600,
                          }}>
                            <cfg.icon size={11} />
                            {cfg.label}
                          </span>
                        </td>
                        {/* Issue detail */}
                        <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--text-3)' }}>
                          {row.issueLabel}
                        </td>
                        {/* Strategy select */}
                        <td style={{ padding: '10px 12px' }}>
                          <select
                            className="input"
                            value={manualChoices[row.col] ?? row.recommended}
                            onChange={e => setManualChoices(prev => ({ ...prev, [row.col]: e.target.value }))}
                            style={{ fontSize: 12, padding: '6px 10px', minWidth: 190, height: 'auto' }}
                          >
                            {row.options.map(opt => (
                              <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Submit bar (appears when a mode is selected) ── */}
      {mode && (
        <div className="card animate-slide-up" style={{ padding: '16px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {mode === 'auto'
                ? <RiBrainFill size={18} style={{ color: 'var(--brand)' }} />
                : <RiSettings3Fill size={18} style={{ color: 'var(--success)' }} />
              }
              <span style={{ fontSize: 14, color: 'var(--text-2)', fontWeight: 500 }}>
                {mode === 'auto'
                  ? 'AI will automatically apply the best strategy for each column.'
                  : `${issueRows.length} manual strateg${issueRows.length !== 1 ? 'ies' : 'y'} configured.`
                }
              </span>
            </div>
            <button
              className="btn btn-primary"
              onClick={handleSubmit}
              disabled={submitting}
              style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 200, justifyContent: 'center' }}
            >
              {submitting
                ? <><RiLoader4Line size={16} className="animate-spin" /> Applying…</>
                : mode === 'auto'
                  ? <><RiSparklingFill size={16} /> Apply AI Preprocessing</>
                  : <><RiCheckboxCircleFill size={16} /> Apply My Choices</>
              }
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

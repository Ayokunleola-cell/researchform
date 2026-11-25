// src/pages/analysis/[id].tsx
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/router';
import AppLayout from '../../components/layout/AppLayout';
import ResearchWorkflow from '../../components/ui/ResearchWorkflow';
import { analysisApi, api, downloadBlob } from '../../lib/api';
import ReportDownloadPanel from '../../components/analysis/ReportDownloadPanel';
import ChatPanel from '../../components/analysis/ChatPanel';
import PreprocessingGate from '../../components/analysis/PreprocessingGate';
import DataTransformPanel from '../../components/analysis/DataTransformPanel';
import ResultsTable from '../../components/analysis/ResultsTable';
import { RiArrowLeftSFill, RiArrowUpSFill, RiFlaskFill, RiDownload2Fill, RiCloseFill, RiCodeBoxFill, RiLineChartFill, RiLayoutMasonryFill, RiBookOpenFill, RiFileTextFill, RiLoader4Line, RiPulseFill, RiShieldFill, RiEyeFill, RiCheckboxCircleFill, RiCheckLine, RiDatabase2Fill, RiArrowDownSFill, RiErrorWarningFill, RiBarChart2Fill, RiDeleteBinFill, RiRefreshLine, RiBrainFill, RiSettings3Fill, RiSparklingFill, RiSearchLine, RiAlertFill, RiInformationFill, RiFilterLine, RiArrowRightSFill, RiCodeSSlashFill, RiListCheck2, RiEqualizer2Fill, RiTableFill, RiMagicFill, RiImageFill } from 'react-icons/ri';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import { useAnalysisStore } from '../../lib/analysisStore';


// ──────────────────────────────────────── 7-Stage pipeline definition ────────────────────────────────────────
type Stage = { n: number; label: string; keys: string[]; star?: boolean; };

const STAGES: Stage[] = [
  { n: 1, label: 'Inspection & Cleaning', keys: ['assembling', 'cleaning', 'inspecting', 'awaiting_preprocessing_choice'] },
  { n: 2, label: 'Data Decode',           keys: ['decoding', 'decode_review'] },
  { n: 3, label: 'Context Analysis',      keys: ['parsing'] },
  { n: 4, label: 'Descriptive Stats',     keys: ['selecting'] },
  { n: 5, label: 'Inferential Stats',     keys: ['generating', 'executing'] },
  { n: 6, label: 'Visualisation',         keys: ['visualising'] },
  { n: 7, label: 'Report & Document',     keys: ['writing', 'building'] },
];

const STAGE_ORDER: Record<string, number> = {
  pending: 0,
  assembling: 1, cleaning: 1, inspecting: 1, awaiting_preprocessing_choice: 1,
  decoding: 2, decode_review: 2,
  parsing: 3,
  selecting: 4,
  generating: 5, executing: 5,
  visualising: 6,
  writing: 7, building: 7,
  complete: 8, failed: -1,
};

const RUNNING_MESSAGES: Record<string, string> = {
  assembling:  'Assembling data from source...',
  cleaning:    'Applying your preprocessing strategy — cleaning data...',
  inspecting:  'Profiling dataset structure and detecting issues...',
  awaiting_preprocessing_choice: 'Inspection complete — waiting for your preprocessing choice...',
  decoding:    'Decoding column headers, value labels, and measurement levels...',
  parsing:     'AI is analysing research context and mapping variables...',
  selecting:   'AI is selecting appropriate statistical tests...',
  generating:  'Generating Python analysis code for all tests...',
  executing:   'Running statistical analysis (Descriptive + Inferential)...',
  visualising: 'Creating publication-ready charts and figures...',
  writing:     'AI is writing Chapter 4 academic narrative...',
  building:    'Building formatted Word document...',
};

const STAGE_SUBTEXTS: Record<string, string> = {
  assembling:  'Gathering files...',
  cleaning:    'Organizing dataset...',
  inspecting:  'Analyzing structure...',
  awaiting_preprocessing_choice: 'User action required',
  decoding:    'Reading variables...',
  parsing:     'Reviewing brief...',
  selecting:   'Picking methods...',
  generating:  'Writing code...',
  executing:   'Crunching numbers...',
  visualising: 'Plotting charts...',
  writing:     'Drafting text...',
  building:    'Finalizing document...',
};

// ──────────────────────────────────────── Stage Bar ────────────────────────────────────────
function StageBar({ status }: { status: string }) {
  const current = STAGE_ORDER[status] ?? 0;
  const isComplete = status === 'complete';
  const isFailed = status === 'failed';
  
  // Current active or final stage
  const activeStage = STAGES.find(s => s.n === current) || (isComplete ? STAGES[STAGES.length - 1] : STAGES[0]);
  const activeStageNum = isComplete ? 7 : Math.min(Math.max(current, 1), 7);
  const percentComplete = isComplete ? 100 : Math.round((Math.max(current - 1, 0) / 7) * 100);

  return (
    <div className="w-full">
      {/* Mobile Stage Summary Banner (Visible on smaller mobile screens) */}
      <div className="flex md:hidden items-center justify-between gap-3 mb-3 pb-3 border-b border-border">
        <div className="flex items-center gap-2.5 min-w-0">
          <div 
            className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold text-xs shadow-sm"
            style={{
              background: isFailed
                ? '#ef4444'
                : isComplete
                ? '#10b981'
                : 'linear-gradient(135deg, #6366f1, #4f46e5)',
            }}
          >
            {isComplete ? (
              <RiCheckboxCircleFill size={15} />
            ) : isFailed ? (
              <RiCloseFill size={15} />
            ) : (
              <RiLoader4Line size={15} className="animate-spin" />
            )}
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wider leading-none" style={{ color: 'var(--text-3)', margin: '0 0 2px' }}>
              {isComplete ? 'Pipeline Status' : isFailed ? 'Failed' : `Stage ${activeStageNum} of 7`}
            </p>
            <p className="text-xs font-bold truncate leading-tight" style={{ color: 'var(--text)', margin: 0 }}>
              {isComplete ? 'All 7 Analysis Stages Complete' : activeStage?.label}
            </p>
          </div>
        </div>

        <span 
          className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-full flex-shrink-0" 
          style={{ 
            background: isComplete ? 'rgba(16,185,129,0.12)' : 'var(--surface-2)', 
            color: isComplete ? '#10b981' : 'var(--brand-text)',
            border: '1px solid var(--border)' 
          }}
        >
          {isComplete ? '✓ Complete' : `${percentComplete}%`}
        </span>
      </div>

      {/* Responsive Horizontal Scroll Strip */}
      <div className="w-full overflow-x-auto no-scrollbar py-1">
        <div className="flex items-start justify-between min-w-[580px] md:min-w-full gap-0 px-1">
          {STAGES.map((stage, idx) => {
            const done   = current > stage.n || isComplete;
            const active = (current === stage.n || (status === 'decode_review' && stage.n === 2)) && !isComplete;
            const failed = isFailed && active;

            return (
              <React.Fragment key={stage.n}>
                <div 
                  className="flex flex-col items-center gap-1.5 flex-1 text-center"
                  style={{ minWidth: 70, maxWidth: 96, padding: '0 2px' }}
                >
                  {/* Step Circle */}
                  <div 
                    style={{
                      width: 34, 
                      height: 34, 
                      borderRadius: '50%',
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center',
                      background: failed
                        ? 'linear-gradient(135deg,#ef4444,#dc2626)'
                        : done
                        ? 'linear-gradient(135deg,#10b981,#059669)'
                        : active
                        ? 'linear-gradient(135deg,#6366f1,#4f46e5)'
                        : 'var(--surface-2)',
                      border: failed
                        ? '2px solid rgba(239,68,68,0.5)'
                        : active
                        ? '2px solid rgba(99,102,241,0.5)'
                        : done 
                        ? '2px solid rgba(16,185,129,0.4)'
                        : '2px solid var(--border)',
                      boxShadow: failed
                        ? '0 0 0 4px rgba(239,68,68,0.12),0 2px 8px rgba(239,68,68,0.25)'
                        : active
                        ? '0 0 0 4px rgba(99,102,241,0.15),0 2px 8px rgba(99,102,241,0.25)'
                        : done 
                        ? '0 2px 6px rgba(16,185,129,0.18)' 
                        : 'none',
                      color: done || active || failed ? '#ffffff' : 'var(--text-3)',
                      transition: 'all 0.25s ease',
                      transform: active ? 'scale(1.08)' : 'scale(1)',
                      fontWeight: 700, 
                      fontSize: 12,
                      flexShrink: 0,
                    }}
                  >
                    {done ? (
                      <RiCheckboxCircleFill size={16} />
                    ) : failed ? (
                      <RiCloseFill size={16} />
                    ) : active ? (
                      <RiLoader4Line size={16} className="animate-spin" />
                    ) : (
                      stage.n
                    )}
                  </div>

                  {/* Step Label — cleanly formatted with word wrapping, never overlaps */}
                  <p 
                    style={{
                      fontSize: 10, 
                      fontWeight: active ? 700 : done ? 600 : 500, 
                      margin: 0,
                      color: failed 
                        ? 'var(--danger)' 
                        : active 
                        ? 'var(--brand)' 
                        : done 
                        ? 'var(--success)' 
                        : 'var(--text-3)',
                      lineHeight: 1.25, 
                      textAlign: 'center',
                      wordBreak: 'break-word',
                      maxWidth: '100%',
                    }}
                  >
                    {stage.label}
                  </p>
                </div>

                {/* Connecting Line between steps */}
                {idx < STAGES.length - 1 && (
                  <div 
                    className="flex-1 mt-4 rounded-full"
                    style={{
                      height: 2, 
                      minWidth: 8,
                      background: done
                        ? 'linear-gradient(90deg,#10b981,#059669)'
                        : active
                        ? 'linear-gradient(90deg,#6366f1 0%,var(--border) 100%)'
                        : 'var(--border)',
                      transition: 'background 0.4s ease',
                    }} 
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────── Inspection Report Panel ────────────────────────────────────────
function InspectionPanel({ report, cleaning }: { report: any; cleaning: any }) {
  const [open, setOpen] = useState(true);
  if (!report || Object.keys(report).length === 0) return null;

  const actions = cleaning?.actions_taken || [];
  const outliers = report.outliers || {};
  const outlierCols = Object.keys(outliers);
  const rowsBefore = report.shape_before?.rows ?? 0;
  const rowsAfter  = report.shape_after?.rows ?? 0;
  const colsBefore = report.shape_before?.columns ?? 0;
  const colsAfter  = report.shape_after?.columns ?? 0;

  return (
    <div className="card overflow-hidden" style={{ border: '1px solid rgba(99,102,241,0.2)' }}>
      <button
        className="w-full flex items-center justify-between p-4"
        style={{ background: 'rgba(99,102,241,0.04)' }}
        onClick={() => setOpen(!open)}
      >
        <span className="flex items-center gap-2 font-semibold text-sm" style={{ color: 'var(--text)' }}>
          <RiShieldFill size={16} style={{ color: 'var(--brand)' }} />
          Stage 1: Data Inspection & Cleaning Report
          {actions.length > 0 && (
            <span className="badge badge-brand text-xs">{actions.length} action{actions.length > 1 ? 's' : ''} taken</span>
          )}
        </span>
        {open ? <RiArrowUpSFill size={16} style={{ color: 'var(--text-3)' }} /> : <RiArrowDownSFill size={16} style={{ color: 'var(--text-3)' }} />}
      </button>

      {open && (
        <div className="p-4 space-y-4">
          {/* Shape summary */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Rows (raw)',    value: rowsBefore, icon: <RiDatabase2Fill size={14} /> },
              { label: 'Rows (clean)',  value: rowsAfter,  icon: <RiDatabase2Fill size={14} />, highlight: rowsBefore !== rowsAfter },
              { label: 'Columns (raw)',  value: colsBefore, icon: <RiPulseFill size={14} /> },
              { label: 'Columns (clean)',value: colsAfter, icon: <RiPulseFill size={14} />, highlight: colsBefore !== colsAfter },
            ].map(({ label, value, icon, highlight }) => (
              <div key={label} className="card p-3 text-center">
                <div className="flex justify-center mb-1" style={{ color: highlight ? 'var(--warning)' : 'var(--brand)' }}>{icon}</div>
                <p className="font-display font-bold text-xl" style={{ color: highlight ? 'var(--warning)' : 'var(--text)' }}>{value ?? '—'}</p>
                <p className="text-xs" style={{ color: 'var(--text-3)' }}>{label}</p>
              </div>
            ))}
          </div>

          {/* Cleaning actions */}
          {actions.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold" style={{ color: 'var(--text-2)' }}>Cleaning Actions Performed</p>
              {actions.map((a: any, i: number) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg" style={{ background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)' }}>
                  <RiCheckboxCircleFill size={15} style={{ color: 'var(--success)', flexShrink: 0, marginTop: 1 }} />
                  <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>{a.description}</p>
                    {a.columns && <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>Affected: {a.columns.join(', ')}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* No actions */}
          {actions.length === 0 && (
            <div className="flex items-center gap-2 p-3 rounded-lg" style={{ background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.15)' }}>
              <RiCheckboxCircleFill size={15} style={{ color: 'var(--success)' }} />
              <p className="text-sm" style={{ color: 'var(--text-2)' }}>No cleaning actions needed — data is already clean</p>
            </div>
          )}

          {/* Outlier warnings */}
          {outlierCols.length > 0 && (
            <div>
              <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-2)' }}>
                Outliers Detected (IQR method) — flagged for awareness, not removed
              </p>
              <div className="grid grid-cols-2 gap-2">
                {outlierCols.slice(0, 6).map(col => (
                  <div key={col} className="p-3 rounded-lg" style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)' }}>
                    <p className="text-xs font-semibold" style={{ color: 'var(--warning)' }}>{col}</p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-2)' }}>
                      {outliers[col].n_outliers} outlier{outliers[col].n_outliers > 1 ? 's' : ''} ({outliers[col].pct_outliers}%) · Fence: [{outliers[col].lower_fence}, {outliers[col].upper_fence}]
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Complete rows */}
          <div className="flex items-center justify-between text-xs p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
            <span style={{ color: 'var(--text-2)' }}>Complete rows (no missing values)</span>
            <span className="font-semibold" style={{ color: 'var(--text)' }}>
              {report.pct_complete_rows?.toFixed(1)}% ({Math.round((report.pct_complete_rows / 100) * rowsAfter)} rows)
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────── Decode Review Component ────────────────────────────────────────
function DecodeReview({ job, onApprove }: { job: any; onApprove: () => void }) {
  const [overrides, setOverrides]         = useState<Record<string, any>>({});
  const [approving, setApproving]         = useState(false);
  const [mode, setMode]                   = useState<'summary' | 'review'>('summary');
  const [search, setSearch]               = useState('');
  const [filterFlag, setFilterFlag]       = useState(false);
  const [weightColumn, setWeightColumn]   = useState<string>('');
  const [imputationMethod, setImputation] = useState<'none' | 'mice' | 'knn'>('none');
  const [showAdvanced, setShowAdvanced]   = useState(false);
  // Per-variable imputation: { varName: 'none' | 'mean' | 'median' | 'knn' | 'mice' | 'exclude' }
  const [perVarImputation, setPerVarImputation] = useState<Record<string, string>>({});

  const dict = job.data_dictionary || {};
  const variables: any[] = dict.variables || [];
  // Numeric columns available as weight candidates
  const numericCols: string[] = variables
    .filter((v: any) => ['interval','ratio'].includes(v.level) || v.dtype === 'float64' || v.dtype === 'int64')
    .map((v: any) => v.clean_name)
    .filter(Boolean);

  // ──────────────────────────────────────── Compute per-variable confidence ────────────────────────────────────────
  const withConfidence = variables.map(v => {
    let score = 100;
    const flags: string[] = [];
    if (v.level_uncertain) { score -= 30; flags.push('Level uncertain'); }
    if (v.high_missing)    { score -= 20; flags.push('High missing values'); }
    if (v.inferred_by === 'heuristic') { score -= 10; flags.push('Heuristic decode'); }
    if (!v.label || v.label === v.clean_name) { score -= 5; flags.push('No label'); }
    return { ...v, confidence: Math.max(score, 0), flags };
  });

  const uncertain    = withConfidence.filter(v => v.confidence < 70);
  const highConf     = withConfidence.filter(v => v.confidence >= 70);
  const overallScore = Math.round(withConfidence.reduce((s, v) => s + v.confidence, 0) / Math.max(withConfidence.length, 1));
  const overallLabel = overallScore >= 90 ? 'Excellent' : overallScore >= 75 ? 'Good' : overallScore >= 60 ? 'Fair' : 'Needs Review';
  const overallColor = overallScore >= 90 ? 'var(--success)' : overallScore >= 75 ? 'var(--brand)' : overallScore >= 60 ? 'var(--warning)' : 'var(--danger)';

  // ──────────────────────────────────────── Filtered variable list ────────────────────────────────────────
  const filtered = withConfidence.filter(v => {
    const matchSearch = !search || v.clean_name.toLowerCase().includes(search.toLowerCase()) || (v.label || '').toLowerCase().includes(search.toLowerCase());
    const matchFlag   = !filterFlag || v.confidence < 70;
    return matchSearch && matchFlag;
  });

  const setOverride = (colName: string, key: string, val: string) => {
    setOverrides(o => ({ ...o, [colName]: { ...o[colName], [key]: val } }));
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      await analysisApi.approveDecoded(job.id, {
        variable_overrides:  overrides,
        missing_strategy:    'preprocessed',
        weight_column:       weightColumn || null,
        imputation_method:   imputationMethod !== 'none' ? imputationMethod : null,
        manual_choices:      Object.keys(perVarImputation).length > 0
          ? { per_var_imputation: perVarImputation }
          : undefined,
      });
      toast.success('Analysis settings saved — running full pipeline!');
      onApprove();
    } catch {
      toast.error('Failed to approve decode');
    } finally {
      setApproving(false);
    }
  };

  // ──────────────────────────────────────── Confidence ring SVG ────────────────────────────────────────
  const r = 32; const circ = 2 * Math.PI * r;
  const ConfRing = ({ score, size = 72 }: { score: number; size?: number }) => {
    const c = score >= 90 ? 'var(--success)' : score >= 70 ? 'var(--brand)' : score >= 50 ? 'var(--warning)' : 'var(--danger)';
    const rr = size * 0.44; const cc = 2 * Math.PI * rr;
    return (
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={rr} fill="none" stroke="var(--border)" strokeWidth={5} />
        <circle cx={size/2} cy={size/2} r={rr} fill="none" stroke={c} strokeWidth={5}
          strokeDasharray={`${(score/100)*cc} ${cc}`} strokeLinecap="round"
          transform={`rotate(-90 ${size/2} ${size/2})`}
          style={{ transition: 'stroke-dasharray 0.8s cubic-bezier(0.4,0,0.2,1)' }} />
        <text x={size/2} y={size/2+2} textAnchor="middle" fill={c} fontSize={size*0.22} fontWeight={700} fontFamily="Syne, sans-serif">{score}</text>
      </svg>
    );
  };

  // ──────────────────────────────────────── Level / Role colour badges ────────────────────────────────────────
  const levelColor: Record<string, string> = {
    nominal: 'rgba(99,102,241,0.12)', ordinal: 'rgba(234,88,12,0.1)',
    interval: 'rgba(5,150,105,0.1)', ratio: 'rgba(37,99,235,0.1)',
  };
  const levelText: Record<string, string> = {
    nominal: 'var(--brand)', ordinal: 'var(--warning)',
    interval: 'var(--success)', ratio: 'var(--info)',
  };
  const roleColor: Record<string, string> = {
    dependent: 'rgba(220,38,38,0.1)', independent: 'rgba(5,150,105,0.1)',
    covariate: 'rgba(99,102,241,0.08)', group: 'rgba(234,88,12,0.1)', exclude: 'rgba(0,0,0,0.06)',
  };
  const roleText: Record<string, string> = {
    dependent: 'var(--danger)', independent: 'var(--success)',
    covariate: 'var(--brand)', group: 'var(--warning)', exclude: 'var(--text-3)',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ──────────────────────────────────────── Inspection Report (collapsible) ──────────────────────────────────────── */}
      <InspectionPanel report={job.inspection_report} cleaning={job.cleaning_summary} />

      {/* ──────────────────────────────────────── AI Decode Confidence Banner ──────────────────────────────────────── */}
      <div className="card" style={{ padding: '20px 24px', borderLeft: `3px solid ${overallColor}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          <ConfRing score={overallScore} size={72} />
          <div style={{ flex: 1, minWidth: 200 }}>
            <p style={{ margin: 0, fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: 18, color: overallColor }}>
              {overallLabel} Decode Quality
            </p>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-3)' }}>
              AI decoded <strong style={{ color: 'var(--text)' }}>{variables.length} variables</strong> —&nbsp;
              <span style={{ color: 'var(--success)' }}>{highConf.length} high confidence</span>,&nbsp;
              <span style={{ color: uncertain.length > 0 ? 'var(--warning)' : 'var(--text-3)' }}>{uncertain.length} need attention</span>
            </p>
          </div>
          {/* Stat chips */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {([
              { label: 'Variables',   value: variables.length,            color: 'var(--brand)' },
              { label: 'Respondents', value: dict.n_rows,                 color: 'var(--text-2)' },
              { label: 'Complete rows', value: dict.n_complete_rows,      color: 'var(--success)' },
              { label: 'Flagged',     value: uncertain.length,            color: uncertain.length > 0 ? 'var(--warning)' : 'var(--text-3)' },
            ] as const).map(({ label, value, color }) => (
              <div key={label} style={{ textAlign: 'center', padding: '8px 14px', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', minWidth: 70 }}>
                <div style={{ fontSize: 18, fontWeight: 800, color, fontFamily: 'Syne, sans-serif' }}>{value ?? '—'}</div>
                <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2 }}>{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Decode warnings inline */}
        {job.decode_warnings?.length > 0 && (
          <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.2)' }}>
            <p style={{ margin: '0 0 6px', fontSize: 12, fontWeight: 700, color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <RiAlertFill size={13} /> {job.decode_warnings.length} Decode Warning{job.decode_warnings.length > 1 ? 's' : ''}
            </p>
            {job.decode_warnings.slice(0, 3).map((w: any, i: number) => (
              <p key={i} style={{ margin: '2px 0', fontSize: 12, color: 'var(--text-2)' }}>
                <strong>{w.severity?.toUpperCase()}</strong>{w.variable ? ` [${w.variable}]` : ''}: {w.message}
                {w.suggestion && <span style={{ color: 'var(--text-3)' }}> â†’ {w.suggestion}</span>}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* ──────────────────────────────────────── Mode selector ──────────────────────────────────────── */}
      {mode === 'summary' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {/* Quick Approve */}
          <div className="card" style={{ padding: '22px 22px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 44, height: 44, borderRadius: 11, background: 'linear-gradient(135deg, var(--brand-dark), var(--brand-light))', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 12px rgba(99,102,241,0.3)' }}>
                <RiSparklingFill size={20} color="var(--brand-text)" />
              </div>
              <div>
                <p style={{ margin: 0, fontWeight: 700, fontSize: 15, fontFamily: 'Syne, sans-serif', color: 'var(--text)' }}>Quick Approve</p>
                <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text-3)' }}>Trust the AI — one click</p>
              </div>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-3)', lineHeight: 1.7 }}>
              Accept AI's variable classifications as-is. Best when decode quality is <strong style={{ color: overallColor }}>{overallLabel}</strong> and you trust the column naming.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {['Nominal', 'Ordinal', 'Interval', 'Ratio'].map(l => {
                const count = variables.filter(v => v.measurement_level === l.toLowerCase()).length;
                return count > 0 ? (
                  <span key={l} style={{ padding: '2px 8px', borderRadius: 20, background: levelColor[l.toLowerCase()], color: levelText[l.toLowerCase()], fontSize: 11, fontWeight: 600 }}>
                    {count} {l}
                  </span>
                ) : null;
              })}
            </div>

            <button
              className="btn btn-primary"
              onClick={handleApprove}
              disabled={approving}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 4 }}
            >
              {approving ? <RiLoader4Line size={15} className="animate-spin" /> : <RiSparklingFill size={15} />}
              {approving ? 'Starting analysis…' : 'Approve & Run Analysis'}
            </button>
          </div>

          {/* Review & Configure */}
          <button
            className="card"
            onClick={() => setMode('review')}
            style={{ padding: '22px 22px', display: 'flex', flexDirection: 'column', gap: 12, textAlign: 'left', cursor: 'pointer', color: 'inherit', transition: 'all 0.18s', border: '1px solid var(--border)' }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--success)'; e.currentTarget.style.boxShadow = '0 0 20px rgba(5,150,105,0.15)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'var(--shadow)'; }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 44, height: 44, borderRadius: 11, background: 'linear-gradient(135deg, #059669, #34d399)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 12px rgba(5,150,105,0.3)' }}>
                <RiEqualizer2Fill size={20} color="#fff" />
              </div>
              <div>
                <p style={{ margin: 0, fontWeight: 700, fontSize: 15, fontFamily: 'Syne, sans-serif', color: 'var(--text)' }}>Review & Configure</p>
                <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text-3)' }}>Full variable-by-variable control</p>
              </div>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-3)', lineHeight: 1.7 }}>
              Inspect each variable's measurement level, role, sample values, and value labels. Correct anything before running analysis.
            </p>
            {uncertain.length > 0 && (
              <div style={{ padding: '8px 12px', borderRadius: 'var(--radius-sm)', background: 'rgba(234,88,12,0.07)', border: '1px solid rgba(234,88,12,0.2)' }}>
                <p style={{ margin: 0, fontSize: 12, color: 'var(--warning)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <RiAlertFill size={12} />
                  {uncertain.length} variable{uncertain.length > 1 ? 's' : ''} flagged for review
                </p>
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--success)', fontSize: 13, fontWeight: 600, marginTop: 4 }}>
              <RiEqualizer2Fill size={14} /> Open Variable Editor <RiArrowRightSFill size={16} />
            </div>
          </button>
        </div>
      )}

      {/* ──────────────────────────────────────── Full Review Mode ──────────────────────────────────────── */}
      {mode === 'review' && (
        <div className="animate-slide-up" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* ──────────────────────────────────────── Analysis Settings ──────────────────────────────────────── */}
          <div className="card" style={{ border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
            <button
              onClick={() => setShowAdvanced(a => !a)}
              style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'var(--surface-2)', border: 'none', cursor: 'pointer', color: 'var(--text-2)' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
                <RiEqualizer2Fill size={15} style={{ color: 'var(--brand)' }} />
                Analysis Settings
                {weightColumn && (
                  <span style={{ padding: '1px 8px', borderRadius: 20, background: 'rgba(99,102,241,0.15)', color: 'var(--brand)', fontSize: 11 }}>
                    Weighted
                  </span>
                )}
              </span>
              {showAdvanced ? <RiArrowUpSFill size={16} /> : <RiArrowDownSFill size={16} />}
            </button>
            {showAdvanced && (
              <div style={{ padding: '20px 18px', background: 'var(--surface)' }}>
                <p style={{ margin: '0 0 4px', fontSize: 12, fontWeight: 700, color: 'var(--text-2)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Survey Case Weighting</p>
                <p style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--text-3)', lineHeight: 1.6 }}>
                  Select a numeric column whose values represent case weights. All analyses will be run on the weighted dataset.
                </p>
                <select
                  value={weightColumn}
                  onChange={e => setWeightColumn(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', fontSize: 13 }}
                >
                  <option value="">No weighting (default)</option>
                  {numericCols.map(col => <option key={col} value={col} style={{ background: 'var(--surface)', color: 'var(--text)' }}>{col}</option>)}
                </select>
              </div>
            )}
          </div>

          {/* Toolbar */}
          <div className="card" style={{ padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <button onClick={() => setMode('summary')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4, padding: 0 }}>
                ← Back
              </button>
              <div style={{ width: 1, height: 20, background: 'var(--border)' }} />
              <div style={{ flex: 1, position: 'relative', maxWidth: 280 }}>
                <RiSearchLine size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-3)' }} />
                <input
                  className="input"
                  placeholder="Search variables…"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  style={{ paddingLeft: 32, fontSize: 13, height: 36 }}
                />
              </div>
              <button
                onClick={() => setFilterFlag(f => !f)}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: `1px solid ${filterFlag ? 'var(--warning)' : 'var(--border)'}`, background: filterFlag ? 'rgba(234,88,12,0.08)' : 'var(--surface-2)', color: filterFlag ? 'var(--warning)' : 'var(--text-3)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
              >
                <RiFilterLine size={13} /> {filterFlag ? 'Flagged only' : 'All variables'}
              </button>
              <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-3)' }}>
                {filtered.length} of {variables.length} shown
              </span>
            </div>
          </div>

          {/* Variable cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {filtered.length === 0 && (
              <div className="card" style={{ padding: 32, textAlign: 'center' }}>
                <RiSearchLine size={28} style={{ color: 'var(--text-3)', margin: '0 auto 8px' }} />
                <p style={{ color: 'var(--text-3)', fontSize: 13 }}>No variables match your filter</p>
              </div>
            )}
            {filtered.map((v, idx) => {
              const override = overrides[v.clean_name] || {};
              const level    = override.measurement_level || v.measurement_level;
              const role     = override.role || 'covariate';
              const confColor = v.confidence >= 90 ? 'var(--success)' : v.confidence >= 70 ? 'var(--brand)' : v.confidence >= 50 ? 'var(--warning)' : 'var(--danger)';
              return (
                <div key={v.clean_name} className="card" style={{ padding: '14px 18px', border: v.confidence < 70 ? '1px solid rgba(234,88,12,0.3)' : '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap' }}>

                    {/* Confidence ring + name */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 200 }}>
                      <ConfRing score={v.confidence} size={48} />
                      <div>
                        <p style={{ margin: 0, fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, fontSize: 13, color: 'var(--text)' }}>{v.clean_name}</p>
                        <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--text-3)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={v.label}>{v.label !== v.clean_name ? v.label : '—'}</p>
                        <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>{v.dtype}</span>
                          <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-3)' }}>{v.inferred_by}</span>
                        </div>
                      </div>
                    </div>

                    {/* Measurement level */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 140 }}>
                      <p style={{ margin: 0, fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Measurement Level</p>
                      <select
                        className="input"
                        value={level}
                        onChange={e => setOverride(v.clean_name, 'measurement_level', e.target.value)}
                        style={{ fontSize: 12, height: 34, padding: '0 8px', background: levelColor[level] || 'var(--surface-2)', color: levelText[level] || 'var(--text)', border: `1px solid ${levelText[level] || 'var(--border)'}`, fontWeight: 600 }}
                      >
                        {['nominal', 'ordinal', 'interval', 'ratio'].map(l => <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>)}
                      </select>
                      {v.level_uncertain && <p style={{ margin: 0, fontSize: 10, color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 3 }}><RiAlertFill size={10} /> Uncertain</p>}
                    </div>

                    {/* Role */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 130 }}>
                      <p style={{ margin: 0, fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Variable Role</p>
                      <select
                        className="input"
                        value={role}
                        onChange={e => setOverride(v.clean_name, 'role', e.target.value)}
                        style={{ fontSize: 12, height: 34, padding: '0 8px', background: roleColor[role] || 'var(--surface-2)', color: 'var(--text)', border: `1px solid ${roleText[role] || 'var(--border)'}`, fontWeight: 600 }}
                      >
                        {['covariate', 'dependent', 'independent', 'group', 'moderator', 'mediator', 'control', 'exclude'].map(r => <option key={r} value={r} style={{ background: 'var(--surface)', color: 'var(--text)' }}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
                      </select>
                    </div>

                    {/* Missing + stats + per-variable imputation */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 160 }}>
                      <p style={{ margin: 0, fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Missing</p>
                      <div style={{ fontSize: 13, fontWeight: 700, color: v.high_missing ? 'var(--danger)' : 'var(--text)' }}>
                        {v.n_missing} <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-3)' }}>({v.pct_missing?.toFixed(0)}%)</span>
                      </div>
                      {v.value_min !== null && v.value_min !== undefined && (
                        <p style={{ margin: 0, fontSize: 10, color: 'var(--text-3)' }}>Range: {v.value_min?.toFixed(1)} – {v.value_max?.toFixed(1)}</p>
                      )}
                      {/* Per-variable imputation dropdown — only show if variable has missing values */}
                      {v.n_missing > 0 && (() => {
                        const pct = v.pct_missing ?? 0;
                        const recommended: string = pct < 5 ? 'mean' : pct < 20 ? 'knn' : 'mice';
                        const hint = pct < 5
                          ? 'Low missing (<5%) — Mean/Median is sufficient'
                          : pct < 20
                          ? 'Moderate missing (5–20%) — KNN recommended'
                          : 'High missing (>20%) — MICE or Exclude recommended';
                        const current = perVarImputation[v.clean_name] ?? recommended;
                        return (
                          <div style={{ marginTop: 4 }}>
                            <p style={{ margin: '0 0 3px', fontSize: 10, fontWeight: 600, color: 'var(--text-3)' }}
                               title={hint}>Imputation â“˜</p>
                            <select
                              value={current}
                              onChange={e => setPerVarImputation(prev => ({ ...prev, [v.clean_name]: e.target.value }))}
                              style={{
                                fontSize: 11, padding: '3px 6px', borderRadius: 6,
                                border: `1px solid ${current !== recommended ? 'var(--brand)' : 'var(--border)'}`,
                                background: 'var(--surface-2)', color: 'var(--text)', width: '100%',
                              }}
                            >
                              <option value="mean">Mean {recommended === 'mean' ? 'â˜…' : ''}</option>
                              <option value="median">Median {recommended === 'median' ? 'â˜…' : ''}</option>
                              <option value="knn">KNN (k=5) {recommended === 'knn' ? 'â˜…' : ''}</option>
                              <option value="mice">MICE {recommended === 'mice' ? 'â˜…' : ''}</option>
                              <option value="exclude">Exclude variable</option>
                            </select>
                          </div>
                        );
                      })()}
                    </div>

                    {/* Flags */}
                    {v.flags.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
                        <p style={{ margin: 0, fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Flags</p>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {v.flags.map((f: string) => (
                            <span key={f} style={{ fontSize: 10, padding: '2px 7px', borderRadius: 10, background: 'rgba(234,88,12,0.08)', color: 'var(--warning)', border: '1px solid rgba(234,88,12,0.2)', fontWeight: 600 }}>{f}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Sample values + value labels row */}
                  {(v.sample_values?.length > 0 || v.value_labels) && (
                    <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                      {v.sample_values?.length > 0 && (
                        <div>
                          <p style={{ margin: '0 0 4px', fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Sample Values</p>
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {v.sample_values.slice(0, 6).map((s: any, i: number) => (
                              <span key={i} style={{ fontSize: 11, padding: '1px 8px', borderRadius: 10, background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-2)', fontFamily: 'JetBrains Mono, monospace' }}>{String(s)}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {v.value_labels && (
                        <div>
                          <p style={{ margin: '0 0 4px', fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Value Labels</p>
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {Object.entries(v.value_labels).slice(0, 5).map(([k, lbl]) => (
                              <span key={k} style={{ fontSize: 11, padding: '1px 8px', borderRadius: 10, background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)', color: 'var(--brand)', fontFamily: 'JetBrains Mono, monospace' }}>{k} = {String(lbl)}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Approve bar */}
          <div className="card" style={{ padding: '14px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
              <button
                onClick={() => setMode('summary')}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text-2)', fontSize: 13, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}
              >
                ← Back to AI Summary
              </button>
              <div style={{ fontSize: 13, color: 'var(--text-3)', textAlign: 'center' }}>
                {Object.keys(overrides).length > 0
                  ? <span style={{ color: 'var(--brand)' }}>{Object.keys(overrides).length} variable{Object.keys(overrides).length > 1 ? 's' : ''} customised</span>
                  : 'No changes — using AI defaults'}
              </div>
              <button
                className="btn btn-primary"
                onClick={handleApprove}
                disabled={approving}
                style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 220, justifyContent: 'center' }}
              >
                {approving ? <RiLoader4Line size={16} className="animate-spin" /> : <RiCheckboxCircleFill size={16} />}
                {approving ? 'Starting Analysis…' : 'Approve & Run Analysis'}
              </button>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────── Chart Image Component ────────────────────────────────────────
function ChartImage({ url, index, isPaid, onPreview, isHtml }: { url: string, index: number, isPaid: boolean, onPreview?: () => void, isHtml?: boolean }) {
  const [error, setError] = useState(false);
  const [retries, setRetries] = useState(0);

  // Interactive HTML chart (Plotly fallback — e.g. correlation heatmap)
  if (isHtml) {
    return (
      <div className="relative group/img w-full h-full flex flex-col items-stretch" style={{ minHeight: 320 }}>
        <iframe
          src={url}
          title={`Interactive Chart ${index + 1}`}
          style={{ width: '100%', height: 340, border: 'none', borderRadius: 4, background: '#fff', pointerEvents: isPaid ? 'auto' : 'none' }}
          sandbox="allow-scripts allow-same-origin"
        />
        {onPreview && (
          <button
            onClick={onPreview}
            className="absolute opacity-0 group-hover/img:opacity-100 transition-all duration-200"
            style={{ top: '50%', left: '50%', transform: 'translate(-50%,-50%)', background: 'rgba(0,0,0,0.75)', border: 'none', borderRadius: 24, padding: '10px 20px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, color: '#fff', fontSize: 13, fontWeight: 600, backdropFilter: 'blur(8px)', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}
            title="Preview full size"
          >
            <RiEyeFill size={16} />
            Preview
          </button>
        )}
      </div>
    );
  }

  if (error && retries > 3) {
    return (
      <div className="flex flex-col items-center justify-center p-8 space-y-2">
        <RiLineChartFill size={24} style={{ color: 'var(--text-3)' }} />
        <p style={{ color: 'var(--text-3)', fontSize: '12px' }}>Chart {index + 1} unavailable</p>
        <button onClick={() => { setError(false); setRetries(0); }} className="text-xs text-brand hover:underline mt-2">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="relative group/img w-full h-full flex items-center justify-center">
      <img
        src={error ? `${url}&retry=${retries}` : url}
        alt={`Chart ${index + 1}`}
        style={{ maxWidth: '100%', maxHeight: 350, objectFit: 'contain', pointerEvents: isPaid ? 'auto' : 'none', display: error && retries > 3 ? 'none' : 'block' }}
        onError={() => {
          setRetries(r => r + 1);
          setError(true);
        }}
        onLoad={() => setError(false)}
      />
      {onPreview && !error && (
        <button
          onClick={onPreview}
          className="absolute opacity-0 group-hover/img:opacity-100 transition-all duration-200"
          style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)', background: 'rgba(0,0,0,0.75)', border: 'none', borderRadius: 24, padding: '10px 20px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, color: '#fff', fontSize: 13, fontWeight: 600, backdropFilter: 'blur(8px)', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}
          title="Preview full size"
        >
          <RiEyeFill size={16} />
          Preview
        </button>
      )}
    </div>
  );
}


// ──────────────────────────────────────── Image Preview Lightbox ────────────────────────────────────────
function ImagePreviewModal({ url, label, isHtml, onClose, onPrev, onNext, hasPrev, hasNext }: { url: string, label: string, isHtml?: boolean, onClose: () => void, onPrev?: () => void, onNext?: () => void, hasPrev?: boolean, hasNext?: boolean }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft' && hasPrev && onPrev) onPrev();
      if (e.key === 'ArrowRight' && hasNext && onNext) onNext();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, onPrev, onNext, hasPrev, hasNext]);

  if (!mounted) return null;

  return createPortal(
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 999999, background: 'rgba(0,0,0,0.88)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', backdropFilter: 'blur(8px)' }}
      onClick={onClose}
    >
      <div
        style={{ position: 'relative', background: '#fff', borderRadius: 16, overflow: 'hidden', boxShadow: '0 32px 80px rgba(0,0,0,0.5)', width: '100%', maxWidth: '1200px', height: '100%', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid #e5e7eb', background: '#f9fafb', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontWeight: 700, fontSize: 15, color: '#111827' }}>{label}</span>
            {isHtml && <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 8, background: 'rgba(99,102,241,0.1)', color: '#6366f1' }}>INTERACTIVE</span>}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {hasPrev && (
              <button onClick={onPrev} style={{ background: '#f3f4f6', border: '1px solid #e5e7eb', borderRadius: 8, padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, color: '#374151', fontWeight: 600, fontSize: 13 }}>
                Previous
              </button>
            )}
            {hasNext && (
              <button onClick={onNext} style={{ background: '#f3f4f6', border: '1px solid #e5e7eb', borderRadius: 8, padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, color: '#374151', fontWeight: 600, fontSize: 13 }}>
                Next
              </button>
            )}
            <button onClick={onClose} style={{ background: '#f3f4f6', border: 'none', borderRadius: 8, padding: '6px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, color: '#374151', fontWeight: 600, fontSize: 13, transition: 'all 0.2s' }} onMouseEnter={e => e.currentTarget.style.background = '#e5e7eb'} onMouseLeave={e => e.currentTarget.style.background = '#f3f4f6'}>
              <RiCloseFill size={16} /> Close
            </button>
          </div>
        </div>
        {/* Content: iframe for HTML charts, img for PNG */}
        <div style={{ flex: 1, padding: isHtml ? 0 : 24, overflow: 'auto', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f3f4f6', position: 'relative' }}>
          {hasPrev && (
            <button onClick={onPrev} style={{ position: 'absolute', left: 16, zIndex: 10, background: 'rgba(255,255,255,0.9)', border: 'none', borderRadius: '50%', width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
              <RiArrowLeftSFill size={28} color="#000" />
            </button>
          )}
          {isHtml ? (
            <iframe
              src={url}
              title={label}
              style={{ width: '100%', height: '100%', border: 'none', background: '#fff' }}
              sandbox="allow-scripts allow-same-origin"
            />
          ) : (
            <img src={url} alt={label} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: 8, boxShadow: '0 4px 24px rgba(0,0,0,0.08)', border: '1px solid #e5e7eb', background: '#fff' }} />
          )}
          {hasNext && (
            <button onClick={onNext} style={{ position: 'absolute', right: 16, zIndex: 10, background: 'rgba(255,255,255,0.9)', border: 'none', borderRadius: '50%', width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
              <RiArrowRightSFill size={28} color="#000" />
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}


// ──────────────────────────────────────── Stat Formatting Helpers ────────────────────────────────────────
function fmtP(p: any): string {
  if (p === undefined || p === null) return '—';
  const v = Number(p);
  if (isNaN(v)) return '—';
  if (v < 0.001) return '< .001';
  return `= ${v.toFixed(3).replace(/^0/, '')}`;
}
function sigStars(p: any): string {
  const v = Number(p);
  if (isNaN(v)) return '';
  if (v < 0.001) return '***';
  if (v < 0.01) return '**';
  if (v < 0.05) return '*';
  return '';
}
function fmtNum(val: any, d = 3): string {
  if (val === undefined || val === null) return '—';
  const n = typeof val === 'object' ? Number(val?.value ?? val) : Number(val);
  if (isNaN(n)) return '—';
  return n.toFixed(d);
}
function effectLabel(name: string, value: number): string {
  if (!name || value === undefined || value === null || isNaN(value)) return '';
  const n = (name || '').toLowerCase();
  const v = Math.abs(value);

  // Cohen's d / Hedges' g
  if (n.includes('d') || n.includes('cohen') || n.includes('delta') || n.includes("hedges")) {
    if (v >= 0.8) return 'Large'; if (v >= 0.5) return 'Medium'; if (v >= 0.2) return 'Small'; return 'Negligible';
  }
  // η² (eta squared) / ω² / partial η² / f² / ANOVA effect sizes
  if (n.includes('η') || n.includes('eta') || n.includes('omega') || n.includes('ω') || n === 'f2' || n.includes('f²')) {
    if (v >= 0.14) return 'Large'; if (v >= 0.06) return 'Medium'; if (v >= 0.01) return 'Small'; return 'Negligible';
  }
  // R² (regression) — Cohen's benchmarks for R²
  if (n === 'r²' || n === 'r2' || n === 'rsquared' || n.includes('r-sq') || n.includes('r sq')) {
    if (v >= 0.26) return 'Large'; if (v >= 0.13) return 'Medium'; if (v >= 0.02) return 'Small'; return 'Negligible';
  }
  // Pearson r / Spearman rho / Kendall tau / point-biserial r
  if (n === 'r' || n === 'rho' || n.includes('spearman') || n.includes('pearson') || n === 'tau' || n === 'τ' || n.includes('point') || n.includes('biserial')) {
    if (v >= 0.5) return 'Large'; if (v >= 0.3) return 'Medium'; if (v >= 0.1) return 'Small'; return 'Negligible';
  }
  // Cramér's V / phi coefficient / phi (chi-square family)
  if (n.includes('cram') || n === 'v' || n === 'φ' || n.includes('phi') || n.includes('cramers')) {
    if (v >= 0.5) return 'Large'; if (v >= 0.3) return 'Medium'; if (v >= 0.1) return 'Small'; return 'Negligible';
  }
  // Kendall's W (Friedman) — small effect for W is harder to define; use as-is
  if (n === 'w' || n.includes("kendall's w")) {
    if (v >= 0.7) return 'Large'; if (v >= 0.5) return 'Medium'; if (v >= 0.3) return 'Small'; return 'Negligible';
  }
  // Generic correlation fallback (if name suggests a correlation)
  if (n.includes('corr')) {
    if (v >= 0.5) return 'Large'; if (v >= 0.3) return 'Medium'; if (v >= 0.1) return 'Small'; return 'Negligible';
  }
  return '';
}

function alphaQuality(a: number) {
  if (a >= 0.90) return { label: 'Excellent',    color: '#10b981' };
  if (a >= 0.80) return { label: 'Good',         color: '#10b981' };
  if (a >= 0.70) return { label: 'Acceptable',   color: '#6366f1' };
  if (a >= 0.60) return { label: 'Questionable', color: '#f59e0b' };
  return            { label: 'Unacceptable', color: '#ef4444' };
}

// ──────────────────────────────────────── Results Display ────────────────────────────────────────
function ResultsDisplay({ job, onRefresh }: { job: any, onRefresh?: () => void }) {
  const [activeTab, setActiveTab] = useState<'findings' | 'descriptive' | 'assumptions' | 'reliability' | 'html_tables' | 'charts' | 'tables'>('findings');
  const [showTransform, setShowTransform] = useState(false);
  const [showAllFreqs, setShowAllFreqs] = useState(false);
  const [showApaTable4, setShowApaTable4] = useState(false);
  const [testFilter, setTestFilter] = useState<'all' | 'sig' | 'ns'>('all');

  const [userPrefs, setUserPrefs] = useState<{ font_type?: string, font_size?: string }>({});
  const [previewState, setPreviewState] = useState<{ type: 'chart' | 'table', index: number } | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem('rf_user');
    if (stored && stored !== 'undefined') {
      try {
        const u = JSON.parse(stored);
        if (u?.preferences) {
          setUserPrefs({ 
            font_type: u.preferences.font_type || 'Times New Roman',
            font_size: u.preferences.font_size || '14px',
          });
        }
      } catch (e) {}
    }
  }, []);

  const [downloading, setDownloading] = useState(false);

  const handleDownloadWord = async () => {
    setDownloading(true);
    try {
      const res = await analysisApi.getReport(job.id);
      downloadBlob(res.data, `Comprehensive_Report_${job.id.slice(0, 8)}.docx`);
      toast.success('Word Report downloaded');
    } catch (err: any) {
      toast.error('Failed to download Word report');
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      const res = await analysisApi.getReportPdf(job.id);
      downloadBlob(res.data, `Comprehensive_Report_${job.id.slice(0, 8)}.pdf`);
      toast.success('PDF Report downloaded');
    } catch (err: any) {
      toast.error('Failed to download PDF report');
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadRaw = async () => {
    setDownloading(true);
    try {
      const res = await analysisApi.getRawReport(job.id);
      downloadBlob(res.data, `Raw_Statistics_${job.id.slice(0, 8)}.docx`);
      toast.success('Raw Output downloaded');
    } catch (err: any) {
      toast.error('Failed to download raw output');
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadRawPdf = async () => {
    setDownloading(true);
    try {
      const res = await analysisApi.getRawReportPdf(job.id);
      downloadBlob(res.data, `Raw_Statistics_${job.id.slice(0, 8)}.pdf`);
      toast.success('Raw PDF downloaded');
    } catch (err: any) {
      toast.error('Failed to download raw PDF');
    } finally {
      setDownloading(false);
    }
  };



  const topic =
    job.project_brief?.topic || job.survey_title || job.source_filename || 'Analysis report';

  const results  = job.results || {};
  const tests    = job.selected_tests || [];
  // Normalize field names: backend may use different keys across versions
  // Harvest all inferential and statistical test results from summary and all family buckets
  const rawSummary: any[] = [...(results.summary || [])];
  const seenTestKeys = new Set(rawSummary.map((r: any) => `${(r.test_name || r.test_function || '').toLowerCase()}_${r.hypothesis_index ?? ''}`));

  const testBuckets = ['comparison', 'correlation', 'regression', 'causal', 'multivariate', 'survival', 'timeseries', 'multilevel', 'posthoc'];
  testBuckets.forEach(bKey => {
    const bucket = results[bKey];
    if (bucket && typeof bucket === 'object') {
      Object.entries(bucket).forEach(([tKey, tRes]: [string, any]) => {
        if (tRes && typeof tRes === 'object') {
          const tName = tRes.test_name || tKey.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
          const dedupeKey = `${(tName || tKey).toLowerCase()}_${tRes.hypothesis_index ?? ''}`;
          if (!seenTestKeys.has(dedupeKey) && (tRes.p_value !== undefined || tRes.statistic !== undefined || tRes.test_stat !== undefined || tRes.F !== undefined || tRes.t !== undefined || tRes.r !== undefined || tRes.chi2 !== undefined || tRes.error)) {
            seenTestKeys.add(dedupeKey);
            rawSummary.push({
              test_name: tName,
              test_function: tKey,
              ...tRes,
            });
          }
        }
      });
    }
  });

  if (Array.isArray(job.selected_tests)) {
    job.selected_tests.forEach((st: any) => {
      const tName = typeof st === 'string' ? st : st?.test_name || st?.test_function;
      if (tName) {
        const alreadyIn = rawSummary.some((r: any) => 
          (r.test_name && r.test_name.toLowerCase().includes(tName.toLowerCase())) ||
          (r.test_function && r.test_function.toLowerCase().includes(tName.toLowerCase()))
        );
        if (!alreadyIn) {
          rawSummary.push({
            test_name: tName,
            test_function: typeof st === 'string' ? st : st?.test_function || tName,
            hypothesis: st?.hypothesis || '',
            hypothesis_index: st?.hypothesis_index ?? -1,
            statistic: null,
            p_value: null,
            significant: null,
            conclusion: 'This test was included in the study research design.',
          });
        }
      }
    });
  }

  const summary = rawSummary.map((r: any) => {
    // ── statistic value (prefer new flat field, fall back to nested or old aliases) ──
    const statObj = r.statistic;
    const statValueRaw =
      r.statistic_value                               // new flat field
      ?? (typeof statObj === 'object' ? statObj?.value : statObj)  // nested or old flat
      ?? r.test_stat ?? r.stat ?? r.chi2 ?? r.F ?? r.t ?? r.r ?? r.beta ?? r.U ?? r.H ?? r.W ?? r.z;

    // ── statistic label ──────────────────────────────────────────────────────
    const rawStatName =
      r.statistic_name                                // new flat field
      ?? (typeof statObj === 'object' ? statObj?.label : null)     // nested
      ?? r.stat_name ?? r.test_statistic_name
      ?? (r.chi2 !== undefined ? 'χ²' : r.F !== undefined ? 'F' : r.t !== undefined ? 't'
        : r.r !== undefined ? 'r' : r.beta !== undefined ? 'β' : r.U !== undefined ? 'U' : r.H !== undefined ? 'H' : r.W !== undefined ? 'W'
        : r.z !== undefined ? 'z' : 'Stat');
    // Translate legacy 'interaction_b' label (old moderation results) → 't'
    const statName = rawStatName === 'interaction_b' ? 't' : rawStatName;

    // ── p-value ──────────────────────────────────────────────────────────────
    const pValue = r.p_value ?? r.p ?? r.pvalue ?? r.p_val;

    // ── effect size — normalise to { name, value } shape the card renderer uses ──
    const effObj = r.effect_size;
    let effValue: any =
      r.effect_size_value                             // new flat field
      ?? (typeof effObj === 'object' ? effObj?.value : effObj)
      ?? r.eta_sq ?? r.cohen_d ?? r.r ?? r.omega_sq ?? r.cramer_v ?? r.epsilon_sq;
    let effName: string | null =
      r.effect_size_name                              // new flat field
      ?? (typeof effObj === 'object' ? effObj?.name : null);
    let effInterp: string | null =
      r.effect_size_interpretation
      ?? (typeof effObj === 'object' ? effObj?.interpretation : null);

    // Recover R² from additional_stats for regression tests that are missing effect size
    if (!effName || effValue == null) {
      const as = r.additional_stats || {};
      const r2 = as.r2 ?? as.r_squared ?? as.R2 ?? as['R²'];
      if (r2 !== undefined && r2 !== null) { effName = 'R²'; effValue = r2; }
    }

    // Fallback interpretation: compute magnitude from effectLabel() when null or 'see guidelines'
    if (effName && effValue != null && (!effInterp || effInterp === 'see guidelines')) {
      const computed = effectLabel(effName, Number(effValue));
      if (computed) effInterp = computed.toLowerCase();
    }

    // ── significance ─────────────────────────────────────────────────────────
    const significant =
      r.significant ?? r.sig ?? r.is_significant
      ?? (pValue !== undefined && pValue !== null && Number(pValue) < 0.05);

    // ── CI ───────────────────────────────────────────────────────────────────
    const ci_95 = r.ci_95 ?? r.confidence_interval ?? r.ci ?? null;

    return {
      ...r,
      // Flat, normalised values used by the table and card renderers
      statistic:      statValueRaw,          // always a number (or null)
      statistic_name: statName,
      p_value:        pValue,
      effect_size:    { name: effName, value: effValue, interpretation: effInterp },
      significant,
      df:             r.df,
      ci_95:          Array.isArray(ci_95) ? ci_95 : null,
      post_hoc:       Array.isArray(r.post_hoc) ? r.post_hoc : [],
    };
  });
  
  // Handle both flat and nested JSON structures from backend
  const add_desc = results.descriptive?.descriptive_stats?.additional_stats;
  const desc     = add_desc?.columns || add_desc || results.descriptive || {};

  // Frequencies: frequency_analysis stores { additional_stats: { frequencies: { col: {...} } } }
  // Flatten all frequency_analysis results across all keys in the frequencies bucket
  const freqs: Record<string, any> = (() => {
    const bucket = results.frequencies || {};
    for (const key of Object.keys(bucket)) {
      const as = bucket[key]?.additional_stats;
      if (as?.frequencies) return as.frequencies;
      if (as?.columns) return as.columns;
    }
    // fallback: treat values directly as frequency data
    return bucket;
  })();

  // Normality: aggregate per-column results from all normality tests in results.normality
  const normality: Record<string, any> = (() => {
    const bucket = results.normality || {};
    // Try normality_check first (primary test)
    if (bucket.normality_check?.additional_stats?.columns)
      return bucket.normality_check.additional_stats.columns;
    // Aggregate first available columns across any normality test
    for (const key of Object.keys(bucket)) {
      const cols = bucket[key]?.additional_stats?.columns;
      if (cols && typeof cols === 'object') return cols;
    }
    // Fallback: old path (assumptions bucket)
    if (results.assumptions?.normality_check?.additional_stats?.columns)
      return results.assumptions.normality_check.additional_stats.columns;
    return {};
  })();

  const reliability = results.reliability || {};

  const allCharts = job.chart_paths || [];

  // Helper: derive human-readable caption from chart filename convention used by charts.py
  function captionFromPath(path: string): string {
    const fname = path.split(/[\\/]/).pop() || path;
    const base  = fname.replace(/\.(png|html)$/i, '');
    // Strip leading "chart_" or "table_"
    const core  = base.replace(/^(chart|table)_/, '');
    // Known prefixes → readable labels
    const knownPrefixes: Record<string, string> = {
      'dist_':      'Distribution',
      'violin_':    'Violin Plot',
      'qq_':        'Q-Q Plot',
      'boxplot':    'Box Plot',
      'boxplots':   'Box Plots',
      'scatter':    'Scatter Plot',
      'regression': 'Regression Plot',
      'means':      'Group Means',
      'correlation':'Correlation Heatmap',
      'freq_':      'Frequency Chart',
    };
    for (const [prefix, label] of Object.entries(knownPrefixes)) {
      const prefixClean = prefix.endsWith('_') ? prefix.slice(0, -1) : prefix;
      if (core.startsWith(prefix) || core === prefixClean) {
        const varPart = core.replace(new RegExp('^' + prefix), '').replace(/^\d+_/, '').replace(/_/g, ' ');
        return varPart ? `${label}: ${varPart}` : label;
      }
    }
    // Generic: replace underscores and title-case
    return core.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  const chartItems = allCharts
    .map((path: string, i: number) => ({
      path,
      originalIndex: i,
      isHtml: path.toLowerCase().endsWith('.html'),
      caption: captionFromPath(path),
    }))
    .filter((item: any) => !item.path.includes('table_'));

  const tableItems = allCharts
    .map((path: string, i: number) => ({
      path,
      originalIndex: i,
      isHtml: path.toLowerCase().endsWith('.html'),
      caption: captionFromPath(path),
    }))
    .filter((item: any) => item.path.includes('table_'));

  let currentPreviewUrl = '';
  let currentPreviewLabel = '';
  let currentPreviewIsHtml = false;
  let hasPrev = false;
  let hasNext = false;
  let handlePrev = () => {};
  let handleNext = () => {};

  if (previewState) {
    const list = previewState.type === 'chart' ? chartItems : tableItems;
    const labelPrefix = previewState.type === 'chart' ? 'Figure' : 'Table';
    if (previewState.index >= 0 && previewState.index < list.length) {
      const item = list[previewState.index];
      const i = item.originalIndex;
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
      const cleanBaseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
      currentPreviewUrl = `${cleanBaseUrl}/analysis/jobs/${job.id}/charts/${i}?v=${job.completed_at || job.id}`;
      currentPreviewLabel = `${labelPrefix} ${previewState.index + 1}${item.caption ? ` — ${item.caption}` : ''}`;
      currentPreviewIsHtml = !!item.isHtml;

      hasPrev = previewState.index > 0;
      hasNext = previewState.index < list.length - 1;

      handlePrev = () => setPreviewState({ type: previewState.type, index: previewState.index - 1 });
      handleNext = () => setPreviewState({ type: previewState.type, index: previewState.index + 1 });
    }
  }

  const htmlTables: Record<string, string> = job.html_tables || {};
  const htmlTableKeys = Object.keys(htmlTables);

  const TABLE_TITLES: Record<string, string> = {
    descriptive:         'Descriptive Statistics',
    reliability:         'Reliability Statistics',
    correlation:         'Correlation Matrix',
    test_results:        'Statistical Test Results',
    cfa_fit:             'CFA Model Fit Indices',
    regression:          'Regression Coefficients',
    regression_robust:   'Regression Coefficients (HC3 Robust SEs)',
    planned_contrasts:   'Planned Contrasts',
  };

  const sigCount   = summary.filter((r: any) => r.significant).length;
  const nsCount    = summary.filter((r: any) => !r.significant && !r.error).length;
  const sigRate    = summary.length > 0 ? Math.round((sigCount / summary.length) * 100) : 0;

  const TABS = [
    { id: 'findings',     label: 'Inferential Statistics', icon: RiFlaskFill,          count: summary.length },
    { id: 'descriptive',  label: 'Descriptive Statistics', icon: RiBarChart2Fill,      count: Object.keys(desc).length + Object.keys(freqs).length },
    { id: 'charts',       label: 'Visualizations',         icon: RiLineChartFill,      count: chartItems.length },
    { id: 'html_tables',  label: 'APA Tables',             icon: RiTableFill,          count: htmlTableKeys.length },
    { id: 'assumptions',  label: 'Assumptions',            icon: RiShieldFill,         count: Object.keys(normality).length },
    { id: 'reliability',  label: 'Reliability',            icon: RiCheckboxCircleFill, count: Object.keys(reliability).length },
    { id: 'tables',       label: 'Table Images',           icon: RiImageFill,          count: tableItems.length },
  ];

  // ──────────────────────────────────────── Levene / VIF / outlier data from results ────────────────────────────────────────
  const levene  = results.assumptions?.levene  || results.levene  || {};
  const vifData = results.assumptions?.vif     || results.vif     || {};
  const outliers= results.assumptions?.outliers|| results.outliers|| {};


  return (
    <div className="space-y-6">
      <ReportDownloadPanel jobId={job.id} jobTitle={topic} reportType={job.project_brief?.report_type} onUnlock={onRefresh} />

      {/* Wrapper for results content that enforces payment lock */}
      <div 
        className={clsx("space-y-6", !job.report_paid && "select-none")}
        onCopy={(e) => {
          if (!job.report_paid) {
            e.preventDefault();
            toast.error("Please unlock the analysis to copy content.");
          }
        }}
      >
        {/* Tests selected */}
      {tests.length > 0 && (
        <div className="card p-5">
          <p className="font-semibold text-sm mb-3" style={{ color: 'var(--text)' }}>
            Statistical Tests Run ({tests.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {tests.map((t: any, i: number) => (
              <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium"
                style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', color: 'var(--brand)' }}>
                <RiBarChart2Fill size={11} />
                {t.test_name}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Raw Report CTA — above tabs */}
      {job.report_paid && (
        <div className="card" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between gap-3 px-3 py-2">
            <div className="flex items-center gap-2">
              <RiDownload2Fill size={12} style={{ color: 'var(--brand)' }} />
              <p className="font-semibold text-xs m-0" style={{ color: 'var(--text)' }}>Statistical Raw Report</p>
              <span className="text-xs" style={{ color: 'var(--text-3)' }}>— Export all tables, frequencies, tests & charts</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {/* Word */}
              <button
                onClick={handleDownloadRaw}
                disabled={downloading}
                title="Download Word (.docx)"
                className="flex flex-col items-center gap-0.5"
                style={{ background: 'none', border: 'none', cursor: downloading ? 'not-allowed' : 'pointer', padding: 2 }}
              >
                <div className="flex items-center justify-center rounded" style={{ width: 28, height: 28, background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)', color: '#2563eb', opacity: downloading ? 0.5 : 1 }}>
                  {downloading ? <RiLoader4Line size={13} className="animate-spin" /> : <RiFileTextFill size={13} />}
                </div>
                <span style={{ fontSize: 9, fontWeight: 700, color: '#fff', letterSpacing: '0.04em' }}>WORD</span>
              </button>
              <div style={{ width: 1, height: 22, background: 'var(--border)' }} />
              {/* PDF */}
              <button
                onClick={handleDownloadRawPdf}
                disabled={downloading}
                title="Download PDF"
                className="flex flex-col items-center gap-0.5"
                style={{ background: 'none', border: 'none', cursor: downloading ? 'not-allowed' : 'pointer', padding: 2 }}
              >
                <div className="flex items-center justify-center rounded" style={{ width: 28, height: 28, background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.2)', color: '#dc2626', opacity: downloading ? 0.5 : 1 }}>
                  {downloading ? <RiLoader4Line size={13} className="animate-spin" /> : <RiDownload2Fill size={13} />}
                </div>
                <span style={{ fontSize: 9, fontWeight: 700, color: '#fff', letterSpacing: '0.04em' }}>PDF</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────
           Sidebar + Content layout
      ──────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row gap-4 items-start w-full">

        {/* LEFT: vertical tab sidebar on desktop, smooth horizontal scroll tabs on mobile */}
        <div className="w-full md:w-48 flex-shrink-0 flex md:flex-col gap-1.5 overflow-x-auto no-scrollbar py-1 md:py-0 md:sticky md:top-20">
          {TABS.map(tab => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap flex-shrink-0 md:w-full cursor-pointer"
                style={{
                  border: active ? '1px solid rgba(99,102,241,0.3)' : '1px solid transparent',
                  background: active ? 'rgba(99,102,241,0.12)' : 'var(--surface-2)',
                  color: active ? 'var(--brand)' : 'var(--text-2)',
                }}
              >
                <Icon size={14} style={{ flexShrink: 0 }} />
                <span className="flex-1 text-left">{tab.label}</span>
                {tab.count > 0 && (
                  <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, padding: '1px 6px', borderRadius: 6, background: active ? 'rgba(99,102,241,0.25)' : 'var(--surface-3)', color: active ? 'var(--brand)' : 'var(--text-3)', flexShrink: 0 }}>{tab.count}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* RIGHT: content panel */}
        <div className="w-full flex-1 min-w-0">

      {/* Transform Panel Drawer */}
      {showTransform && (
        <DataTransformPanel
          jobId={job.id}
          onClose={() => setShowTransform(false)}
          onApplied={() => { setShowTransform(false); onRefresh && onRefresh(); }}
        />
      )}

      {/* Tab: Hypothesis Tests */}

      {/* Tab: Inferential Statistics & Hypothesis Tests */}
      {activeTab === 'findings' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="font-bold text-base" style={{ color: 'var(--text)', margin: 0 }}>Inferential Statistics &amp; Hypothesis Tests</h3>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>Hypothesis decisions, test statistics (t, F, r, χ², β), exact p-values, and effect sizes</p>
            </div>
            {htmlTables.test_results && (
              <button
                onClick={() => setShowApaTable4(v => !v)}
                className="btn btn-ghost text-xs flex items-center gap-1.5"
                style={{ border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--brand)', fontWeight: 600, padding: '6px 12px', borderRadius: 8 }}
              >
                <RiTableFill size={13} />
                {showApaTable4 ? 'Hide APA Table 4.4' : 'View APA Table 4.4'}
              </button>
            )}
          </div>

          {showApaTable4 && htmlTables.test_results && (
            <div className="card p-4 overflow-hidden" style={{ border: '1px solid rgba(99,102,241,0.3)', background: 'var(--surface)' }}>
              <div className="flex items-center justify-between mb-2">
                <p className="font-bold text-xs" style={{ color: 'var(--brand)' }}>Table 4.4: Summary of Hypotheses Testing and Inferential Statistics</p>
                <button onClick={() => setShowApaTable4(false)} className="btn btn-ghost btn-icon p-1" style={{ width: 22, height: 22 }}><RiCloseFill size={13} /></button>
              </div>
              <div className="overflow-x-auto rf-table-embed" dangerouslySetInnerHTML={{ __html: htmlTables.test_results }} />
            </div>
          )}

          {summary.length === 0 ? (
            <div className="card p-10 text-center">
              <RiFlaskFill size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
              <p className="text-sm font-semibold" style={{ color: 'var(--text-2)' }}>No inferential statistical results available</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-3)' }}>Run an inferential analysis to see hypothesis findings here.</p>
            </div>
          ) : (
            <>
              {/* ──────────────────────────────────────── Summary bar ──────────────────────────────────────── */}
              <div className="card px-4 py-3" style={{ background: 'var(--surface-2)' }}>
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-6 flex-wrap">
                    {[
                      { label: 'Tests Run',      value: summary.length,                                        color: 'var(--brand)' },
                      { label: 'Significant',    value: sigCount,                                              color: '#10b981' },
                      { label: 'Not Significant',value: nsCount,                                              color: 'var(--text-3)' },
                      { label: 'Errors',         value: summary.filter((r: any) => r.error).length,           color: summary.filter((r: any) => r.error).length > 0 ? '#ef4444' : 'var(--text-3)' },
                    ].map((s: any) => (
                      <div key={s.label} className="flex items-center gap-2">
                        <span style={{ fontSize: 20, fontWeight: 800, color: s.color, fontFamily: 'Syne, sans-serif' }}>{s.value}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{s.label}</span>
                      </div>
                    ))}
                  </div>

                  {/* Filter pills */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {[
                      { id: 'all', label: `All (${summary.length})` },
                      { id: 'sig', label: `Significant (${sigCount})` },
                      { id: 'ns',  label: `Not Significant (${nsCount})` },
                    ].map(f => (
                      <button
                        key={f.id}
                        onClick={() => setTestFilter(f.id as any)}
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          padding: '3px 9px',
                          borderRadius: 6,
                          border: testFilter === f.id ? '1px solid var(--brand)' : '1px solid var(--border)',
                          background: testFilter === f.id ? 'rgba(99,102,241,0.12)' : 'var(--surface)',
                          color: testFilter === f.id ? 'var(--brand)' : 'var(--text-2)',
                          cursor: 'pointer',
                        }}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* ──────────────────────────────────────── Effect Size Summary Table ──────────────────────────────────────── */}
              {summary.filter((r: any) => !r.error && (r.effect_size !== undefined && r.effect_size !== null)).length > 0 && (
                <div className="card overflow-hidden">
                  <div style={{ padding: '10px 14px', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                    <p style={{ margin: 0, fontWeight: 700, fontSize: 12, color: 'var(--text)' }}>Effect Size Summary</p>
                    <p style={{ margin: '2px 0 0', fontSize: 10, color: 'var(--text-3)' }}>Practical magnitude of every finding — more important than p-value alone</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                      <thead>
                        <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                          {['Test', 'Statistic', 'p-value', 'Effect Size', 'Magnitude', 'Significant'].map(h => (
                            <th key={h} style={{ padding: '8px 12px', textAlign: h === 'Test' ? 'left' : 'center', fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {summary.filter((r: any) => !r.error).map((r: any, i: number) => {
                          const pV = r.p_value !== undefined && r.p_value !== null ? Number(r.p_value) : null;
                          const eR = typeof r.effect_size === 'object' ? r.effect_size?.value : r.effect_size;
                          const eN = typeof r.effect_size === 'object' ? r.effect_size?.name : (r.statistic_name || 'Effect');
                          const eLbl = eR != null ? effectLabel(String(eN), Number(eR)) : '—';
                          const eLblColor = eLbl === 'Large' ? '#ef4444' : eLbl === 'Medium' ? '#f59e0b' : eLbl === 'Small' ? '#6366f1' : 'var(--text-3)';
                          return (
                            <tr key={i} style={{ borderTop: '1px solid var(--border)', background: i % 2 ? 'var(--surface-2)' : 'transparent' }}>
                              <td style={{ padding: '8px 12px', fontWeight: 600, fontSize: 11, color: 'var(--text)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.test_name}>{r.test_name}</td>
                              <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--brand)', fontSize: 11 }}>{r.statistic_name || '—'} = {typeof r.statistic === 'object' ? fmtNum(r.statistic?.value) : fmtNum(r.statistic)}</td>
                              <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: pV !== null && pV < 0.05 ? '#059669' : 'var(--text-3)', fontSize: 11 }}>{pV !== null ? `p ${fmtP(pV)}` : '—'}</td>
                              <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-2)', fontSize: 11 }}>{eN} = {eR != null ? fmtNum(eR) : '—'}</td>
                              <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                                <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 10, color: eLblColor, background: `${eLblColor}15`, border: `1px solid ${eLblColor}30` }}>{eLbl}</span>
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                                <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 10, color: r.significant ? '#059669' : 'var(--text-3)', background: r.significant ? 'rgba(16,185,129,0.1)' : 'var(--surface-2)', border: `1px solid ${r.significant ? 'rgba(16,185,129,0.25)' : 'var(--border)'}` }}>{r.significant ? '✓ Yes' : '✗ No'}</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* ──────────────────────────────────────── Individual test cards ──────────────────────────────────────── */}
              {summary.filter((r: any) => testFilter === 'sig' ? r.significant : testFilter === 'ns' ? !r.significant : true).map((r: any, i: number) => {
                const pVal = r.p_value !== undefined && r.p_value !== null ? Number(r.p_value) : null;
                const statRaw = typeof r.statistic === 'object' ? r.statistic?.value : r.statistic;
                const statName = r.statistic_name || r.statistic?.label || 'Stat';
                const dfVal = r.df !== undefined ? r.df : (r.df1 !== undefined && r.df2 !== undefined ? `${r.df1}, ${r.df2}` : null);
                const effRaw = typeof r.effect_size === 'object' ? r.effect_size?.value : r.effect_size;
                const effName = typeof r.effect_size === 'object' ? r.effect_size?.name : 'Effect';
                const effLbl = effRaw !== undefined && effRaw !== null ? effectLabel(String(effName), Number(effRaw)) : '';
                const effColor = effLbl === 'Large' ? '#ef4444' : effLbl === 'Medium' ? '#f59e0b' : effLbl === 'Small' ? '#6366f1' : 'var(--text-3)';
                const ci = r.ci_95 || r.confidence_interval || r.ci || null;
                const postHoc: any[] = r.post_hoc || r.posthoc || r.tukey || r.pairwise || [];
                const sig = r.significant;
                if (r.error) return (
                  <div key={i} className="card p-4" style={{ borderLeft: '3px solid #ef4444' }}>
                    <div className="flex items-start gap-2">
                      <RiErrorWarningFill size={15} style={{ color: '#ef4444', flexShrink: 0, marginTop: 2 }} />
                      <div>
                        <p className="text-sm font-semibold" style={{ color: '#ef4444' }}>{r.test_name}</p>
                        <p className="text-xs mt-1" style={{ color: 'var(--text-3)' }}>{r.error}</p>
                      </div>
                    </div>
                  </div>
                );
                return (
                  <div key={i} className="card overflow-hidden" style={{ borderLeft: `3px solid ${sig ? '#10b981' : 'rgba(99,102,241,0.3)'}` }}>
                    {/* Header row */}
                    <div className="flex items-start gap-3 p-4 pb-2">
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: sig ? '#10b981' : 'var(--text-3)', marginTop: 6, flexShrink: 0 }} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="text-sm font-bold" style={{ color: 'var(--text)', margin: 0 }}>{r.test_name}</p>
                          <span className="text-xs px-2 py-0.5 rounded-full font-semibold"
                            style={{ background: sig ? 'rgba(16,185,129,0.12)' : 'rgba(0,0,0,0.06)', color: sig ? '#059669' : 'var(--text-3)', border: `1px solid ${sig ? 'rgba(16,185,129,0.25)' : 'var(--border)'}` }}>
                            {sig ? '✓ Significant' : '✗ Not Significant'}
                          </span>
                          {effLbl && <span style={{ fontSize: 11, fontWeight: 700, padding: '1px 8px', borderRadius: 10, color: effColor, background: `${effColor}15`, border: `1px solid ${effColor}30` }}>{effLbl} effect</span>}
                        </div>
                        {r.hypothesis && <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{r.hypothesis}</p>}
                      </div>
                    </div>

                    {/* Stat badges row */}
                    <div className="flex items-center gap-2 flex-wrap px-4 pb-2">
                      {statRaw !== undefined && statRaw !== null && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 6, background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', color: 'var(--brand)', fontSize: 12, fontWeight: 700, fontFamily: 'JetBrains Mono, monospace' }}>
                          {statName} = {fmtNum(statRaw)}{dfVal !== null ? <span style={{ fontWeight: 400, opacity: 0.7, marginLeft: 2 }}>({typeof dfVal === 'string' ? dfVal : fmtNum(dfVal, 0)})</span> : null}
                        </span>
                      )}
                      {pVal !== null && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 6, background: pVal < 0.05 ? 'rgba(16,185,129,0.08)' : 'rgba(0,0,0,0.05)', border: `1px solid ${pVal < 0.05 ? 'rgba(16,185,129,0.25)' : 'var(--border)'}`, color: pVal < 0.05 ? '#059669' : 'var(--text-3)', fontSize: 12, fontWeight: 700, fontFamily: 'JetBrains Mono, monospace' }}>
                          p {fmtP(pVal)}{sigStars(pVal) ? ` ${sigStars(pVal)}` : ''}
                        </span>
                      )}
                      {effRaw !== undefined && effRaw !== null && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 6, background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-2)', fontSize: 12, fontWeight: 700, fontFamily: 'JetBrains Mono, monospace' }}>
                          {effName} = {fmtNum(effRaw)}
                        </span>
                      )}
                      {/* 95% CI badge */}
                      {ci && Array.isArray(ci) && ci.length === 2 && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 6, background: 'rgba(14,165,233,0.08)', border: '1px solid rgba(14,165,233,0.25)', color: '#0ea5e9', fontSize: 12, fontWeight: 700, fontFamily: 'JetBrains Mono, monospace' }}>
                          95% CI [{fmtNum(ci[0])}, {fmtNum(ci[1])}]
                        </span>
                      )}
                      {r.n && <span style={{ display: 'inline-flex', padding: '3px 10px', borderRadius: 6, background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-3)', fontSize: 12, fontFamily: 'JetBrains Mono, monospace' }}>n = {r.n}</span>}
                    </div>

                    {/* Conclusion */}
                    {r.conclusion && (
                      <div className="mx-4 mb-3 p-3 rounded-lg" style={{ background: 'var(--surface-2)', borderLeft: '2px solid var(--border-2)' }}>
                        <p style={{ color: 'var(--text-2)', fontFamily: userPrefs.font_type ? `${userPrefs.font_type}, serif` : 'Times New Roman, serif', fontSize: userPrefs.font_size || '14px', lineHeight: 1.75, margin: 0 }}>
                          {r.conclusion}
                        </p>
                      </div>
                    )}

                    {/* Post-hoc table (ANOVA pairwise comparisons) */}
                    {postHoc && postHoc.length > 0 && (
                      <div className="mx-4 mb-4">
                        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>Post-hoc Pairwise Comparisons</p>
                        <div className="overflow-x-auto">
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                            <thead>
                              <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                                {['Group A', 'Group B', 'Difference', 'p-value', 'Significant'].map(h => (
                                  <th key={h} style={{ padding: '6px 10px', textAlign: h === 'Group A' || h === 'Group B' ? 'left' : 'center', fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {postHoc.map((ph: any, pi: number) => {
                                const phP = Number(ph.p_value ?? ph.p ?? ph.pvalue ?? 1);
                                const phSig = phP < 0.05;
                                return (
                                  <tr key={pi} style={{ borderTop: '1px solid var(--border)', background: pi % 2 ? 'var(--surface-2)' : 'transparent' }}>
                                    <td style={{ padding: '6px 10px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text)', fontWeight: 600, fontSize: 11 }}>{ph.group1 ?? ph.a ?? ph.group_a ?? '—'}</td>
                                    <td style={{ padding: '6px 10px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text)', fontWeight: 600, fontSize: 11 }}>{ph.group2 ?? ph.b ?? ph.group_b ?? '—'}</td>
                                    <td style={{ padding: '6px 10px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-2)', fontSize: 11 }}>{ph.mean_diff !== undefined ? fmtNum(ph.mean_diff) : ph.diff !== undefined ? fmtNum(ph.diff) : '—'}</td>
                                    <td style={{ padding: '6px 10px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: phSig ? '#059669' : 'var(--text-3)', fontSize: 11 }}>p {fmtP(phP)}{sigStars(phP) ? ` ${sigStars(phP)}` : ''}</td>
                                    <td style={{ padding: '6px 10px', textAlign: 'center' }}>
                                      <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 8px', borderRadius: 10, color: phSig ? '#059669' : 'var(--text-3)', background: phSig ? 'rgba(16,185,129,0.1)' : 'var(--surface-2)', border: `1px solid ${phSig ? 'rgba(16,185,129,0.25)' : 'var(--border)'}` }}>{phSig ? '✓' : '✗'}</span>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}

      {/* Tab: Descriptive & Frequencies */}
      {activeTab === 'descriptive' && (
        <div className="space-y-4">
          {Object.keys(desc).length > 0 && (
            <div className="card overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'var(--border)' }}>
                <div>
                  <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>Descriptive Statistics</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{Object.keys(desc).length} variables · N, Mean, SD, Skewness &amp; Kurtosis</p>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full" style={{ borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-2)', borderBottom: '2px solid var(--border)' }}>
                      {['Variable', 'N', 'Mean', 'Median', 'SD', 'Min', 'Max', 'Skewness', 'Kurtosis'].map(h => (
                        <th key={h} style={{ padding: '10px 12px', textAlign: h === 'Variable' ? 'left' : 'right', fontSize: 11, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(desc).map(([col, st]: [string, any], idx) => (
                      typeof st === 'object' && st.mean !== undefined ? (
                        <tr key={col} style={{ borderTop: '1px solid var(--border)', background: idx % 2 === 0 ? 'transparent' : 'var(--surface-2)' }}>
                          <td style={{ padding: '9px 12px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 600, color: 'var(--text)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={col}>{col}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>{st.count ?? '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', fontWeight: 600, color: 'var(--text)', fontFamily: 'JetBrains Mono, monospace' }}>{fmtNum(st.mean)}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: 'var(--text-2)', fontFamily: 'JetBrains Mono, monospace' }}>{st.median !== undefined ? fmtNum(st.median) : '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: 'var(--text-2)', fontFamily: 'JetBrains Mono, monospace' }}>{st.std !== undefined ? fmtNum(st.std) : '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>{st.min !== undefined ? fmtNum(st.min, 2) : '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>{st.max !== undefined ? fmtNum(st.max, 2) : '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>{st.skewness !== undefined ? fmtNum(st.skewness) : st.skew !== undefined ? fmtNum(st.skew) : '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'right', color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>{st.kurtosis !== undefined ? fmtNum(st.kurtosis) : '—'}</td>
                        </tr>
                      ) : null
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {Object.keys(freqs).length > 0 && (() => {
            // UUID-slug pattern: 8-4-4-4-12 hex segments separated by underscores or dashes
            const isUuidSlug = (name: string) =>
              /^[0-9a-f]{8}[_-][0-9a-f]{4}[_-][0-9a-f]{4}[_-][0-9a-f]{4}[_-][0-9a-f]{12}$/i.test(name);

            const validFreqs = Object.entries(freqs).filter(([col, freq]: [string, any]) => {
              // Skip UUID-named phantom columns
              if (isUuidSlug(col)) return false;
              const counts = freq?.counts ?? (typeof freq === 'object' && !Array.isArray(freq) ? freq : {});
              const keys = Object.keys(counts);
              const nCats = keys.length;
              const nValid = freq?.n_valid ?? nCats;
              // Skip if only category is empty string or whitespace
              if (nCats === 0) return false;
              if (nCats === 1 && String(keys[0]).trim() === '') return false;
              // Skip single-value (no distribution to show) unless it's meaningful
              if (nCats === 1) return false;
              // High-cardinality guard: skip if too many unique values relative to N
              return nCats <= 50 && nCats <= nValid * 0.6;
            });
            if (validFreqs.length === 0) return null;
            return (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>Frequency Distributions</p>
                  {validFreqs.length > 4 && (
                    <button onClick={() => setShowAllFreqs(f => !f)} style={{ fontSize: 12, color: 'var(--brand)', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
                      {showAllFreqs ? 'Show fewer' : `Show all ${validFreqs.length}`}
                    </button>
                  )}
                </div>
                <div className="space-y-4">
                  {validFreqs.slice(0, showAllFreqs ? undefined : 4).map(([col, freq]: [string, any]) => {
                    const rawCounts: Record<string, number> = freq?.counts ?? (typeof freq === 'object' && !Array.isArray(freq) ? freq : {});
                    const rawPct: Record<string, number>   = freq?.percent ?? {};
                    const rawCumPct: Record<string, number> = freq?.cumulative_pct ?? {};
                    const total: number  = freq?.n_valid  ?? Object.values(rawCounts).reduce((a: number, v: any) => a + Number(v), 0);
                    const missing: number = freq?.n_missing ?? 0;
                    // Sort by count descending
                    const sorted = Object.entries(rawCounts).sort(([, a], [, b]) => Number(b) - Number(a));
                    const maxCount = sorted.length > 0 ? Number(sorted[0][1]) : 1;

                    return (
                      <div key={col} className="card overflow-hidden">
                        {/* Table header */}
                        <div className="flex items-center justify-between px-4 py-2.5" style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                          <p className="font-bold text-sm" style={{ color: 'var(--text)', margin: 0 }}>{col}</p>
                          <div className="flex items-center gap-3">
                            {missing > 0 && <span style={{ fontSize: 10, color: '#f59e0b', fontFamily: 'JetBrains Mono, monospace' }}>{missing} missing</span>}
                            <span style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>N = {total}</span>
                          </div>
                        </div>
                        {/* Frequency table */}
                        <div className="overflow-x-auto">
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                            <thead>
                              <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                                {['Value', 'Frequency', '%', 'Cumulative %', ''].map(h => (
                                  <th key={h} style={{ padding: '7px 12px', textAlign: h === 'Value' ? 'left' : h === '' ? 'left' : 'center', fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {sorted.map(([val, count], ri) => {
                                const pct    = rawPct[val]    !== undefined ? Number(rawPct[val])    : total > 0 ? (Number(count) / total) * 100 : 0;
                                const cumPct = rawCumPct[val] !== undefined ? Number(rawCumPct[val]) : 0;
                                const barW   = maxCount > 0 ? (Number(count) / maxCount) * 100 : 0;
                                return (
                                  <tr key={val} style={{ borderTop: '1px solid var(--border)', background: ri % 2 === 0 ? 'transparent' : 'var(--surface-2)' }}>
                                    <td style={{ padding: '7px 12px', fontWeight: 600, color: 'var(--text)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={String(val)}>{String(val)}</td>
                                    <td style={{ padding: '7px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text)' }}>{Number(count)}</td>
                                    <td style={{ padding: '7px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: 'var(--brand)' }}>{pct.toFixed(1)}%</td>
                                    <td style={{ padding: '7px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-3)' }}>{cumPct > 0 ? `${cumPct.toFixed(1)}%` : '—'}</td>
                                    <td style={{ padding: '7px 12px', minWidth: 80 }}>
                                      <div style={{ height: 5, background: 'var(--surface-3)', borderRadius: 3, overflow: 'hidden' }}>
                                        <div style={{ height: '100%', borderRadius: 3, background: 'linear-gradient(90deg,#6366f1,#8b5cf6)', width: `${barW}%`, transition: 'width 0.5s ease' }} />
                                      </div>
                                    </td>
                                  </tr>
                                );
                              })}
                              {/* Total row */}
                              <tr style={{ borderTop: '2px solid var(--border)', background: 'var(--surface-2)' }}>
                                <td style={{ padding: '7px 12px', fontWeight: 700, color: 'var(--text)', fontSize: 11 }}>Total</td>
                                <td style={{ padding: '7px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: 'var(--text)' }}>{total}</td>
                                <td style={{ padding: '7px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: 'var(--text)' }}>100.0%</td>
                                <td colSpan={2} />
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()}


          {/* Descriptive Visualizations (Charts & Figures) */}
          {chartItems.length > 0 && (
            <div className="card p-4 space-y-3" style={{ border: '1px solid var(--border)' }}>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <p className="font-bold text-sm" style={{ color: 'var(--text)', margin: 0 }}>Descriptive Visualizations &amp; Charts</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>Frequency distributions, demographic bar charts, and data figures</p>
                </div>
                <button
                  onClick={() => setActiveTab('charts')}
                  className="btn btn-ghost text-xs flex items-center gap-1"
                  style={{ color: 'var(--brand)', fontWeight: 600 }}
                >
                  View All in Visualizations Tab ({chartItems.length}) <RiArrowRightSFill size={14} />
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12 }}>
                {chartItems.slice(0, 6).map((item: any, idx: number) => {
                  const caption = item.caption || `Figure ${idx + 1}`;
                  const baseUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/$/, '');
                  const mkUrl = `${baseUrl}/analysis/jobs/${job.id}/charts/${item.originalIndex}?v=${job.completed_at || job.id}`;
                  return (
                    <div key={item.originalIndex} className="card overflow-hidden" style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>
                      <div className="flex items-center justify-between px-3 py-1.5" style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-2)' }}>Figure {idx + 1}</span>
                        <button onClick={() => setPreviewState({ type: 'chart', index: idx })} className="btn btn-ghost btn-icon p-1" style={{ width: 22, height: 22 }} title="Full screen">
                          <RiEyeFill size={12} style={{ color: 'var(--brand)' }} />
                        </button>
                      </div>
                      <div style={{ background: '#fff', minHeight: 150, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 6, cursor: 'pointer' }} onClick={() => setPreviewState({ type: 'chart', index: idx })}>
                        <ChartImage url={mkUrl} index={item.originalIndex} isPaid={!!job.report_paid} isHtml={item.isHtml} onPreview={() => setPreviewState({ type: 'chart', index: idx })} />
                      </div>
                      <div style={{ padding: '6px 10px', borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}>
                        <p style={{ margin: 0, fontSize: 11, color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={caption}>
                          <strong>Figure {idx + 1}.</strong> {caption}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {Object.keys(desc).length === 0 && Object.keys(freqs).length === 0 && (
            <div className="card p-10 text-center">
              <RiDatabase2Fill size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
              <p className="text-sm font-semibold" style={{ color: 'var(--text-2)' }}>No descriptive statistics available</p>
            </div>
          )}
        </div>
      )}

      {/* Tab: Reliability & Normality */}
      {activeTab === 'reliability' && (
        <div className="space-y-4">
          {reliability.cronbach_alpha && (() => {
            const alphaVal = Number(
              reliability.cronbach_alpha.statistic?.value ??
              reliability.cronbach_alpha.additional_stats?.alpha ??
              reliability.cronbach_alpha.alpha ?? 0
            );
            const nItems = reliability.cronbach_alpha.additional_stats?.n_items ?? reliability.cronbach_alpha.n_items ?? '—';
            const nObs   = reliability.cronbach_alpha.n ?? '—';
            const alphaCI = reliability.cronbach_alpha.additional_stats?.ci_95 || reliability.cronbach_alpha.ci_95;
            const itemStats = reliability.cronbach_alpha.additional_stats?.item_stats;
            const q = alphaQuality(alphaVal);
            const circ = 2 * Math.PI * 40;
            return (
              <div className="card overflow-hidden">
                <div className="p-4 border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>Scale Reliability — Cronbach's Alpha (α)</p>
                </div>
                <div className="p-5">
                  <div className="flex items-center gap-6 flex-wrap">
                    <div style={{ position: 'relative', width: 100, height: 100, flexShrink: 0 }}>
                      <svg width={100} height={100} viewBox="0 0 100 100">
                        <circle cx={50} cy={50} r={40} fill="none" stroke="var(--border)" strokeWidth={8} />
                        <circle cx={50} cy={50} r={40} fill="none" stroke={q.color} strokeWidth={8}
                          strokeDasharray={`${Math.min(alphaVal, 1) * circ} ${circ}`} strokeLinecap="round"
                          transform="rotate(-90 50 50)"
                          style={{ transition: 'stroke-dasharray 1s cubic-bezier(0.4,0,0.2,1)' }} />
                        <text x={50} y={46} textAnchor="middle" fill={q.color} fontSize={16} fontWeight={800} fontFamily="Syne, sans-serif">α</text>
                        <text x={50} y={62} textAnchor="middle" fill={q.color} fontSize={12} fontWeight={700} fontFamily="JetBrains Mono, monospace">{alphaVal.toFixed(3)}</text>
                      </svg>
                    </div>
                    <div className="grid grid-cols-2 gap-3 flex-1" style={{ minWidth: 200 }}>
                      {([
                        { label: 'Alpha (α)',      value: alphaVal.toFixed(3), color: q.color,          mono: true },
                        { label: 'Reliability',    value: q.label,            color: q.color          },
                        { label: 'Scale Items',    value: String(nItems),     color: 'var(--text)'    },
                        { label: 'Observations',   value: String(nObs),       color: 'var(--text)'    },
                        ...(alphaCI ? [{ label: '95% CI', value: `[${fmtNum(alphaCI[0])}, ${fmtNum(alphaCI[1])}]`, color: 'var(--text-2)', mono: true }] : []),
                      ] as any[]).map((s: any) => (
                        <div key={s.label} style={{ padding: '10px 14px', borderRadius: 10, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                          <p style={{ margin: 0, fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>{s.label}</p>
                          <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: s.color, fontFamily: s.mono ? 'JetBrains Mono, monospace' : 'Syne, sans-serif' }}>{s.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  {(reliability.cronbach_alpha.conclusion || reliability.cronbach_alpha.additional_stats?.conclusion) && (
                    <div className="mt-4 p-3 rounded-lg" style={{ background: 'var(--surface-2)', borderLeft: '2px solid var(--border-2)' }}>
                      <p style={{ margin: 0, fontFamily: userPrefs.font_type ? `${userPrefs.font_type}, serif` : 'Times New Roman, serif', fontSize: userPrefs.font_size || '14px', color: 'var(--text-2)', lineHeight: 1.75 }}>
                        {reliability.cronbach_alpha.conclusion || reliability.cronbach_alpha.additional_stats?.conclusion}
                      </p>
                    </div>
                  )}
                  {itemStats && (
                    <div className="mt-4">
                      <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Item-Level Statistics</p>
                      <div className="overflow-x-auto">
                        <table className="w-full" style={{ borderCollapse: 'collapse', fontSize: 11 }}>
                          <thead>
                            <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                              {['Item', 'Mean', 'SD', 'Item-Total r', 'α if Deleted'].map(h => (
                                <th key={h} style={{ padding: '7px 10px', textAlign: h === 'Item' ? 'left' : 'right', fontWeight: 700, color: 'var(--text-3)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(itemStats as Record<string, any>).map(([item, s]: [string, any], idx) => (
                              <tr key={item} style={{ borderTop: '1px solid var(--border)', background: idx % 2 ? 'var(--surface-2)' : 'transparent' }}>
                                <td style={{ padding: '7px 10px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--text)', fontWeight: 600 }}>{item}</td>
                                <td style={{ padding: '7px 10px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-2)' }}>{fmtNum(s.mean)}</td>
                                <td style={{ padding: '7px 10px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-2)' }}>{fmtNum(s.std)}</td>
                                <td style={{ padding: '7px 10px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: Number(s.item_total_corr) >= 0.3 ? '#10b981' : '#f59e0b' }}>{fmtNum(s.item_total_corr)}</td>
                                <td style={{ padding: '7px 10px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-3)' }}>{fmtNum(s.alpha_if_deleted)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
          {Object.keys(normality).length > 0 && (
            <div className="card overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                <div>
                  <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>Normality Tests</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>H₀: data is normally distributed. Reject if p &lt; .05.</p>
                </div>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  <span className="flex items-center gap-1.5" style={{ color: '#10b981' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} /> Normal</span>
                  <span className="flex items-center gap-1.5" style={{ color: '#f59e0b' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} /> Non-normal</span>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full" style={{ borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                      {['Variable', 'Test', 'Statistic', 'p-value', 'N', 'Decision'].map(h => (
                        <th key={h} style={{ padding: '10px 12px', textAlign: h === 'Variable' ? 'left' : 'center', fontSize: 11, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(normality).map(([col, result]: [string, any], idx) => (
                      typeof result === 'object' && result !== null ? (
                        <tr key={col} style={{ borderTop: '1px solid var(--border)', background: idx % 2 ? 'var(--surface-2)' : 'transparent' }}>
                          <td style={{ padding: '9px 12px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 600, color: 'var(--text)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={col}>{col}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'center', color: 'var(--text-3)', fontSize: 11 }}>{result.test_name || result.test || 'Shapiro-Wilk'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text)' }}>{result.statistic !== undefined ? fmtNum(result.statistic, 4) : result.W !== undefined ? fmtNum(result.W, 4) : '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: Number(result.p_value) < 0.05 ? '#f59e0b' : '#10b981' }}>
                            {result.p_value !== undefined ? fmtP(result.p_value) : '—'}{sigStars(result.p_value) ? ` ${sigStars(result.p_value)}` : ''}
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'center', color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>{result.n ?? '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'center' }}>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, background: result.normal ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)', color: result.normal ? '#059669' : '#d97706', border: `1px solid ${result.normal ? 'rgba(16,185,129,0.25)' : 'rgba(245,158,11,0.25)'}` }}>
                              {result.normal ? '✓ Normal' : '✗ Non-normal'}
                            </span>
                          </td>
                        </tr>
                      ) : null
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {Object.entries(reliability).filter(([k]) => k !== 'cronbach_alpha').map(([k, v]: [string, any]) => {
            if (!v || typeof v !== 'object') return null;
            const statVal = v.statistic?.value ?? v.statistic ?? v.alpha ?? v.omega;
            return (
              <div key={k} className="card p-4">
                <div className="flex items-start gap-3">
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--brand)', marginTop: 6, flexShrink: 0 }} />
                  <div className="flex-1">
                    <p className="text-sm font-bold" style={{ color: 'var(--text)' }}>{v.test_name || k.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</p>
                    {statVal !== undefined && <p style={{ marginTop: 4, fontFamily: 'JetBrains Mono, monospace', fontSize: 13, color: 'var(--brand)', fontWeight: 700 }}>{fmtNum(statVal, 4)}</p>}
                    {(v.conclusion || v.additional_stats?.conclusion) && <p className="mt-2 text-xs" style={{ color: 'var(--text-2)', lineHeight: 1.6, fontFamily: userPrefs.font_type ? `${userPrefs.font_type}, serif` : 'Times New Roman, serif' }}>{v.conclusion || v.additional_stats?.conclusion}</p>}
                  </div>
                </div>
              </div>
            );
          })}
          {Object.keys(normality).length === 0 && Object.keys(reliability).length === 0 && (
            <div className="card p-10 text-center">
              <RiShieldFill size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
              <p className="text-sm font-semibold" style={{ color: 'var(--text-2)' }}>No reliability results</p>
            </div>
          )}
        </div>
      )}

      {/* ────────────────────────────────────────
           Tab: ASSUMPTIONS — normality, Levene's, VIF, outliers
      ──────────────────────────────────────── */}
      {activeTab === 'assumptions' && (
        <div className="space-y-4">

          {/* What are assumptions? */}
          <div className="card p-4" style={{ background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.2)' }}>
            <p style={{ margin: 0, fontSize: 12, fontWeight: 700, color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <RiAlertFill size={14} /> Why Assumptions Matter
            </p>
            <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--text-2)', lineHeight: 1.65 }}>
              Statistical tests are only valid when their assumptions are met. If normality fails, switch to non-parametric tests.
              If Levene's fails, use Welch's correction. Check VIF &gt; 10 in regression — it means two predictors are near-identical.
            </p>
          </div>

          {/* ──────────────────────────────────────── Normality Tests ──────────────────────────────────────── */}
          {Object.keys(normality).length > 0 ? (
            <div className="card overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                <div>
                  <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>Normality Tests (Shapiro-Wilk)</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>H₀: data is normally distributed — p &gt; .05 means normal. Use parametric tests only if normal.</p>
                </div>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  <span className="flex items-center gap-1.5" style={{ color: '#10b981' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} /> Normal</span>
                  <span className="flex items-center gap-1.5" style={{ color: '#f59e0b' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} /> Non-normal</span>
                </div>
              </div>
              {/* Assumption verdict banner */}
              {(() => {
                const nonNormal = Object.values(normality).filter((v: any) => typeof v === 'object' && v !== null && !v.normal);
                return nonNormal.length > 0 ? (
                  <div style={{ padding: '8px 16px', background: 'rgba(245,158,11,0.07)', borderBottom: '1px solid rgba(245,158,11,0.2)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <RiAlertFill size={13} style={{ color: 'var(--warning)', flexShrink: 0 }} />
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--warning)', fontWeight: 600 }}>
                      {nonNormal.length} variable{nonNormal.length !== 1 ? 's are' : ' is'} non-normally distributed — consider non-parametric alternatives (Mann-Whitney, Kruskal-Wallis, Spearman).
                    </p>
                  </div>
                ) : (
                  <div style={{ padding: '8px 16px', background: 'rgba(16,185,129,0.05)', borderBottom: '1px solid rgba(16,185,129,0.15)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <RiCheckboxCircleFill size={13} style={{ color: 'var(--success)', flexShrink: 0 }} />
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--success)', fontWeight: 600 }}>All variables are normally distributed — parametric tests are appropriate.</p>
                  </div>
                );
              })()}
              <div className="overflow-x-auto">
                <table className="w-full" style={{ borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                      {['Variable', 'Test', 'Statistic', 'p-value', 'N', 'Normal?', 'Recommended Test'].map(h => (
                        <th key={h} style={{ padding: '10px 12px', textAlign: h === 'Variable' ? 'left' : 'center', fontSize: 11, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(normality).map(([col, result]: [string, any], idx) => (
                      typeof result === 'object' && result !== null ? (
                        <tr key={col} style={{ borderTop: '1px solid var(--border)', background: idx % 2 ? 'var(--surface-2)' : 'transparent' }}>
                          <td style={{ padding: '9px 12px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 600, color: 'var(--text)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={col}>{col}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'center', color: 'var(--text-3)', fontSize: 11 }}>{result.test_name || result.test || 'Shapiro-Wilk'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text)' }}>{result.statistic !== undefined ? fmtNum(result.statistic, 4) : result.W !== undefined ? fmtNum(result.W, 4) : '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: Number(result.p_value) < 0.05 ? '#f59e0b' : '#10b981' }}>
                            {result.p_value !== undefined ? fmtP(result.p_value) : '—'}{sigStars(result.p_value) ? ` ${sigStars(result.p_value)}` : ''}
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'center', color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>{result.n ?? '—'}</td>
                          <td style={{ padding: '9px 12px', textAlign: 'center' }}>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, background: result.normal ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)', color: result.normal ? '#059669' : '#d97706', border: `1px solid ${result.normal ? 'rgba(16,185,129,0.25)' : 'rgba(245,158,11,0.25)'}` }}>
                              {result.normal ? '✓ Yes' : '✗ No'}
                            </span>
                          </td>
                          <td style={{ padding: '9px 12px', textAlign: 'center', fontSize: 11, color: 'var(--text-2)', fontStyle: 'italic' }}>
                            {result.normal ? 'Parametric (t-test / ANOVA)' : 'Non-parametric (Mann-Whitney / Kruskal-Wallis)'}
                          </td>
                        </tr>
                      ) : null
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="card p-6 text-center" style={{ border: '1px solid var(--border)' }}>
              <p style={{ color: 'var(--text-3)', fontSize: 13 }}>No normality test results available.</p>
            </div>
          )}

          {/* ──────────────────────────────────────── Levene's Test (Homogeneity of Variance) ──────────────────────────────────────── */}
          {Object.keys(levene).length > 0 && (
            <div className="card overflow-hidden">
              <div className="p-4 border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>Levene's Test — Homogeneity of Variance</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>p &gt; .05 = equal variances — ANOVA assumption is met. If p &lt; .05, use Welch's correction.</p>
              </div>
              <div className="overflow-x-auto">
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                      {['Variable / Group', 'F', 'df1', 'df2', 'p-value', 'Equal Variances?'].map(h => (
                        <th key={h} style={{ padding: '9px 12px', textAlign: h === 'Variable / Group' ? 'left' : 'center', fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(levene).map(([k, v]: [string, any], idx) => {
                      const lp = Number(v?.p_value ?? v?.p ?? 1);
                      const equalVar = lp >= 0.05;
                      return (
                        <tr key={k} style={{ borderTop: '1px solid var(--border)', background: idx % 2 ? 'var(--surface-2)' : 'transparent' }}>
                          <td style={{ padding: '8px 12px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 600, color: 'var(--text)' }}>{k}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-2)', fontSize: 11 }}>{fmtNum(v?.statistic ?? v?.F)}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-3)', fontSize: 11 }}>{v?.df1 ?? '—'}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-3)', fontSize: 11 }}>{v?.df2 ?? '—'}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: equalVar ? '#10b981' : '#f59e0b', fontSize: 11 }}>p {fmtP(lp)}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                            <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 10, color: equalVar ? '#059669' : '#d97706', background: equalVar ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)', border: `1px solid ${equalVar ? 'rgba(16,185,129,0.25)' : 'rgba(245,158,11,0.25)'}` }}>{equalVar ? '✓ Yes' : '✗ No — use Welch'}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ──────────────────────────────────────── VIF Multicollinearity ──────────────────────────────────────── */}
          {Object.keys(vifData).length > 0 && (
            <div className="card overflow-hidden">
              <div className="p-4 border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>Multicollinearity — VIF Scores</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>VIF &lt; 5 = acceptable. VIF 5–10 = moderate concern. VIF &gt; 10 = serious multicollinearity — consider removing or combining predictors.</p>
              </div>
              <div className="overflow-x-auto">
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                      {['Predictor', 'VIF', 'Tolerance', 'Assessment'].map(h => (
                        <th key={h} style={{ padding: '9px 12px', textAlign: h === 'Predictor' ? 'left' : 'center', fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(vifData).map(([k, v]: [string, any], idx) => {
                      const vifVal = typeof v === 'number' ? v : v?.vif ?? v?.value ?? 0;
                      const tol = vifVal > 0 ? (1 / vifVal).toFixed(3) : '—';
                      const assessment = vifVal > 10 ? { label: 'Serious', color: '#ef4444' } : vifVal > 5 ? { label: 'Moderate', color: '#f59e0b' } : { label: 'Acceptable', color: '#10b981' };
                      return (
                        <tr key={k} style={{ borderTop: '1px solid var(--border)', background: idx % 2 ? 'var(--surface-2)' : 'transparent' }}>
                          <td style={{ padding: '8px 12px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 600, color: 'var(--text)' }}>{k}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: assessment.color, fontSize: 12 }}>{fmtNum(vifVal, 2)}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-3)', fontSize: 11 }}>{tol}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                            <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 10, color: assessment.color, background: `${assessment.color}18`, border: `1px solid ${assessment.color}35` }}>{assessment.label}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ──────────────────────────────────────── Outlier Summary ──────────────────────────────────────── */}
          {Object.keys(outliers).length > 0 && (
            <div className="card overflow-hidden">
              <div className="p-4 border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>Outlier Detection</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>Values beyond ±3 SD or outside 1.5×IQR from quartiles. High outlier counts may distort means and inflate Type I errors.</p>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, padding: 16 }}>
                {Object.entries(outliers).map(([col, info]: [string, any]) => {
                  const cnt = typeof info === 'number' ? info : info?.count ?? info?.n ?? 0;
                  const pct = typeof info === 'object' ? info?.pct ?? info?.percent ?? null : null;
                  const bad = cnt > 5;
                  return (
                    <div key={col} style={{ padding: '10px 14px', borderRadius: 9, border: `1px solid ${bad ? 'rgba(239,68,68,0.25)' : 'var(--border)'}`, background: bad ? 'rgba(239,68,68,0.04)' : 'var(--surface-2)' }}>
                      <p style={{ margin: 0, fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, fontSize: 12, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={col}>{col}</p>
                      <p style={{ margin: '4px 0 0', fontSize: 18, fontWeight: 800, color: bad ? '#ef4444' : 'var(--text-2)', fontFamily: 'Syne, sans-serif' }}>{cnt} <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-3)' }}>outlier{cnt !== 1 ? 's' : ''}{pct !== null ? ` (${Number(pct).toFixed(1)}%)` : ''}</span></p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {Object.keys(normality).length === 0 && Object.keys(levene).length === 0 && Object.keys(vifData).length === 0 && (
            <div className="card p-10 text-center">
              <RiShieldFill size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
              <p className="text-sm font-semibold" style={{ color: 'var(--text-2)' }}>No assumption check results</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-3)' }}>Assumption checks run automatically during analysis.</p>
            </div>
          )}
        </div>
      )}
      {/* Tab: APA Tables */}
      {activeTab === 'html_tables' && (
        <div className="space-y-4">
          {htmlTableKeys.length === 0 ? (
            <div className="card p-10 text-center">
              <RiTableFill size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
              <p className="text-sm font-semibold" style={{ color: 'var(--text-2)' }}>No APA tables available</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-3)' }}>Tables are generated when analysis completes.</p>
            </div>
          ) : (
            <>
              {/* Quick-nav pills — jump to each table */}
              {htmlTableKeys.length > 1 && (
                <div className="flex items-center gap-1.5 flex-wrap" style={{ paddingBottom: 4 }}>
                  {htmlTableKeys.map(key => (
                    <button key={key} onClick={() => { const el = document.getElementById(`apa-${key}`); el?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }}
                      style={{ padding: '3px 10px', borderRadius: 6, border: '1px solid rgba(99,102,241,0.25)', background: 'rgba(99,102,241,0.08)', color: 'var(--brand)', fontSize: 11, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                      {TABLE_TITLES[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                    </button>
                  ))}
                </div>
              )}
              {htmlTableKeys.map(key => (
                <div key={key} id={`apa-${key}`}>
                  <ResultsTable
                    tableKey={key}
                    title={TABLE_TITLES[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                    htmlContent={htmlTables[key]}
                  />
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {/* Tab: Charts */}
      {activeTab === 'charts' && (() => {
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/$/, '');
        const mkUrl = (idx: number) => `${baseUrl}/analysis/jobs/${job.id}/charts/${idx}?v=${job.completed_at || job.id}`;
        const dlChart = async (origIdx: number, label: string) => {
          if (!job.report_paid) { toast.error('Please unlock the analysis to download.'); return; }
          try {
            const res = await api.get(`/analysis/jobs/${job.id}/charts/${origIdx}`, { responseType: 'blob' });
            const url = window.URL.createObjectURL(res.data);
            const a = document.createElement('a'); a.href = url; a.download = `${label}.png`;
            document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(url);
          } catch { toast.error('Failed to download'); }
        };
        return (
          <div>
            {chartItems.length > 0 ? (
              <>
                <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                  <div>
                    <h3 className="font-bold text-base" style={{ color: 'var(--text)', margin: 0 }}>Data Visualizations &amp; Figures</h3>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{chartItems.length} publication-ready figure{chartItems.length !== 1 ? 's' : ''} (descriptive distributions, regression plots &amp; charts)</p>
                  </div>
                  <button onClick={async () => { for (let i = 0; i < chartItems.length; i++) { await dlChart(chartItems[i].originalIndex, `Figure_${i+1}`); await new Promise(r => setTimeout(r, 150)); } toast.success(`${chartItems.length} charts downloaded`); }}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text-2)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                    <RiDownload2Fill size={13} /> Download All
                  </button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
                  {chartItems.map((item: any, idx: number) => {
                    const caption = item.caption || `Figure ${idx + 1}`;
                    return (
                    <div key={item.originalIndex} className="card overflow-hidden"
                      style={{ border: '1px solid var(--border)', transition: 'all 0.2s', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
                      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 6px 24px rgba(99,102,241,0.15)'; (e.currentTarget as HTMLElement).style.borderColor = 'rgba(99,102,241,0.3)'; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)'; (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'; }}>
                      <div className="flex items-center justify-between px-3 py-2" style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                        <div className="flex items-center gap-2">
                          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-2)' }}>Figure {idx + 1}</span>
                          {item.isHtml && (
                            <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 8, background: 'rgba(99,102,241,0.12)', color: 'var(--brand)', letterSpacing: '0.04em' }}>INTERACTIVE</span>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          <button onClick={() => setPreviewState({ type: 'chart', index: idx })} className="btn btn-ghost btn-icon p-1" style={{ width: 26, height: 26 }} title="Full screen"><RiEyeFill size={13} style={{ color: 'var(--brand)' }} /></button>
                          {!item.isHtml && (
                            <button onClick={() => dlChart(item.originalIndex, `Figure_${idx+1}`)} className="btn btn-ghost btn-icon p-1" style={{ width: 26, height: 26 }} title={job.report_paid ? 'Download' : 'Unlock to download'}><RiDownload2Fill size={13} style={{ color: job.report_paid ? 'var(--brand)' : 'var(--text-3)' }} /></button>
                          )}
                        </div>
                      </div>
                      <div style={{ background: '#fff', minHeight: item.isHtml ? 340 : 180, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: item.isHtml ? 0 : 8, cursor: 'pointer' }} onClick={() => !item.isHtml && setPreviewState({ type: 'chart', index: idx })}>
                        <ChartImage url={mkUrl(item.originalIndex)} index={item.originalIndex} isPaid={!!job.report_paid} isHtml={item.isHtml} onPreview={() => setPreviewState({ type: 'chart', index: idx })} />
                      </div>
                      {/* Caption */}
                      <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}>
                        <p style={{ margin: 0, fontSize: 11, fontStyle: 'italic', color: 'var(--text-2)' }}>
                          <strong>Figure {idx + 1}.</strong> {caption}
                        </p>
                      </div>
                    </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <div className="card p-12 text-center">
                <RiLineChartFill size={40} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
                <p className="text-sm font-semibold" style={{ color: 'var(--text-2)' }}>No charts generated</p>
                <p className="text-xs mt-1" style={{ color: 'var(--text-3)' }}>Charts appear here after visualisation completes.</p>
              </div>
            )}
          </div>
        );
      })()}

      {/* Tab: Figure Tables */}
      {activeTab === 'tables' && (() => {
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/$/, '');
        const mkUrl = (idx: number) => `${baseUrl}/analysis/jobs/${job.id}/charts/${idx}?v=${job.completed_at || job.id}`;
        const dlTable = async (origIdx: number, label: string) => {
          if (!job.report_paid) { toast.error('Please unlock the analysis to download.'); return; }
          try {
            const res = await api.get(`/analysis/jobs/${job.id}/charts/${origIdx}`, { responseType: 'blob' });
            const url = window.URL.createObjectURL(res.data);
            const a = document.createElement('a'); a.href = url; a.download = `${label}.png`;
            document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(url);
          } catch { toast.error('Failed to download'); }
        };
        return (
          <div>
            {tableItems.length > 0 ? (
              <>
                <div className="flex items-center justify-between mb-3">
                  <p style={{ fontSize: 12, color: 'var(--text-3)' }}>{tableItems.length} table image{tableItems.length !== 1 ? 's' : ''}</p>
                  <button onClick={async () => { for (let i = 0; i < tableItems.length; i++) { await dlTable(tableItems[i].originalIndex, `Table_${i+1}`); await new Promise(r => setTimeout(r, 150)); } toast.success(`${tableItems.length} tables downloaded`); }}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text-2)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                    <RiDownload2Fill size={13} /> Download All
                  </button>
                </div>
                <div className="space-y-4">
                  {tableItems.map((item: any, idx: number) => (
                    <div key={item.originalIndex} className="card overflow-hidden" style={{ border: '1px solid var(--border)', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                      <div className="flex items-center justify-between px-3 py-2" style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-2)' }}>Table {idx + 1}</span>
                        <div className="flex items-center gap-1">
                          <button onClick={() => setPreviewState({ type: 'table', index: idx })} className="btn btn-ghost btn-icon p-1" style={{ width: 26, height: 26 }} title="Full screen"><RiEyeFill size={13} style={{ color: 'var(--brand)' }} /></button>
                          <button onClick={() => dlTable(item.originalIndex, `Table_${idx+1}`)} className="btn btn-ghost btn-icon p-1" style={{ width: 26, height: 26 }} title={job.report_paid ? 'Download' : 'Unlock to download'}><RiDownload2Fill size={13} style={{ color: job.report_paid ? 'var(--brand)' : 'var(--text-3)' }} /></button>
                        </div>
                      </div>
                      <div style={{ background: '#fff', minHeight: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16, cursor: 'pointer' }} onClick={() => setPreviewState({ type: 'table', index: idx })}>
                        <ChartImage url={mkUrl(item.originalIndex)} index={item.originalIndex} isPaid={!!job.report_paid} onPreview={() => setPreviewState({ type: 'table', index: idx })} />
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="card p-12 text-center">
                <RiLayoutMasonryFill size={40} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
                <p className="text-sm font-semibold" style={{ color: 'var(--text-2)' }}>No figure tables generated</p>
              </div>
            )}
          </div>
        );
      })()}
      {/* Image Preview Modal */}
      {previewState && (
        <ImagePreviewModal
          url={currentPreviewUrl}
          label={currentPreviewLabel}
          isHtml={currentPreviewIsHtml}
          onClose={() => setPreviewState(null)}
          onPrev={handlePrev}
          onNext={handleNext}
          hasPrev={hasPrev}
          hasNext={hasNext}
        />
      )}

        </div>{/* end content panel */}
      </div>{/* end sidebar+content row */}
      </div>{/* end payment lock wrapper */}

    </div>
  );
}

// ──────────────────────────────────────── Main Page ────────────────────────────────────────
export default function AnalysisJobPage() {
  const router = useRouter();
  const { id } = router.query as { id: string };
  const [job, setJob] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [deletingJob, setDeletingJob] = useState(false);
  const [retryingJob, setRetryingJob] = useState(false);
  const [gateSubmitted, setGateSubmittedState] = useState(false);
  const gateSubmittedRef = useRef(false);
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  // Global analysis tracking — survives navigation
  const { watchJob, _updateJob } = useAnalysisStore();

  const setGateSubmitted = (val: boolean) => {
    gateSubmittedRef.current = val;
    setGateSubmittedState(val);
  };

  const startPolling = (intervalMs = 2000) => {
    clearInterval(pollRef.current);
    // Phase 3B: jitter prevents thundering-herd when many users poll simultaneously
    const jitter = Math.floor(Math.random() * 1000);
    pollRef.current = setInterval(() => fetchJobRef.current?.(), intervalMs + jitter);
  };

  const fetchJobRef = useRef<(() => Promise<void>) | null>(null);

  const fetchJob = async () => {
    try {
      const res = await analysisApi.getJob(id);
      setJob(res.data);
      const st = res.data.status;

      // Keep global store in sync so sidebar panel updates even on other pages
      _updateJob(id, { status: st as any });

      // If we submitted the gate and the backend has moved past awaiting_preprocessing_choice, clear flag
      if (gateSubmittedRef.current && st !== 'awaiting_preprocessing_choice') {
        setGateSubmitted(false);
      }
      const done = ['complete', 'failed'].includes(st);
      const needsAction = ['decode_review', 'awaiting_preprocessing_choice'].includes(st);
      if ((done || needsAction) && !gateSubmittedRef.current) {
        clearInterval(pollRef.current);
      }
    } catch {
      clearInterval(pollRef.current);
    }
  };

  // keep the ref in sync so startPolling's closure always calls the latest fetchJob
  fetchJobRef.current = fetchJob;

  useEffect(() => {
    if (!id) return;
    fetchJob().finally(() => setLoading(false));
    startPolling(2000);
    // Note: we do NOT unwatch on unmount — the global poller in analysisStore
    // keeps tracking this job via the lightweight /status endpoint across navigation.
    return () => clearInterval(pollRef.current);
  }, [id]);

  // Register job with global store so sidebar panel always shows it
  useEffect(() => {
    if (!id || !job) return;
    const title = job.project_brief?.topic || job.source_filename || 'Analysis Job';
    watchJob(id, title);
  }, [id, job?.id]);

  const handleRetryJob = async () => {
    setRetryingJob(true);
    try {
      await analysisApi.retryJob(id);
      toast.success('Restarting analysis pipeline...');
      fetchJobRef.current?.();
      startPolling(1500);
    } catch (err: any) {
      toast.error('Failed to restart analysis. Please try again.');
    } finally {
      setRetryingJob(false);
    }
  };

  const handleDeleteJob = async () => {
    if (!confirm('Delete this analysis job and all its files? This cannot be undone.')) return;
    setDeletingJob(true);
    try {
      await analysisApi.deleteJob(id);
      toast.success('Job deleted');
      router.push('/analysis');
    } catch {
      toast.error('Failed to delete job');
      setDeletingJob(false);
    }
  };

  if (loading) return (
    <AppLayout title="Analysis">
      <div className="flex items-center justify-center h-64">
        <RiLoader4Line className="animate-spin" size={32} style={{ color: 'var(--brand)' }} />
      </div>
    </AppLayout>
  );

  const isActive = !['complete', 'failed', 'decode_review', 'awaiting_preprocessing_choice'].includes(job?.status);
  const jobTitle = job?.project_brief?.topic || job?.source_filename || 'Analysis Job';

  return (
    <AppLayout
      title={jobTitle.length > 48 ? `${jobTitle.slice(0, 48)}…` : jobTitle}
      breadcrumbs={[
        { label: 'Dashboard', href: '/dashboard' },
        { label: 'Analysis', href: '/analysis' },
        { label: 'Job detail' },
      ]}
      headerActions={
        <div className="flex items-center gap-2">
            {isActive && (
              <span className="flex items-center gap-2 text-sm" style={{ color: 'var(--brand)' }}>
                <RiLoader4Line size={14} className="animate-spin" /> Processing...
              </span>
            )}
            <button
              className="btn btn-ghost btn-icon"
              onClick={handleDeleteJob}
              disabled={deletingJob}
              title="Delete job"
              style={{ color: 'var(--danger)' }}
            >
              {deletingJob ? <RiLoader4Line size={16} className="animate-spin" /> : <RiDeleteBinFill size={16} />}
            </button>
        </div>
      }
    >
      <div className="page-container page-stack">
        <ResearchWorkflow />
        <div className="card p-5 w-full">
          <StageBar status={job?.status || 'pending'} />
        </div>

        {/* Preprocessing gate — shows when pipeline pauses for mode choice */}
        {job?.status === 'awaiting_preprocessing_choice' && !gateSubmitted && job?.inspection_report && (
          <PreprocessingGate
            jobId={job.id}
            inspectionReport={job.inspection_report as any}
            onComplete={() => {
              // Optimistically hide gate immediately, then poll fast until status changes
              setGateSubmitted(true);
              fetchJobRef.current?.();
              startPolling(1500);
            }}
          />
        )}

        {/* Transition spinner: gate submitted but status not yet updated */}
        {gateSubmitted && job?.status === 'awaiting_preprocessing_choice' && (
          <div className="card p-8 text-center animate-slide-up">
            <RiLoader4Line size={40} className="animate-spin mx-auto mb-4" style={{ color: 'var(--brand)' }} />
            <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>Applying preprocessing strategy…</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-3)' }}>Pipeline is resuming — this usually takes a few seconds</p>
            <div className="mt-4 h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface-2)', maxWidth: 240, margin: '16px auto 0' }}>
              <div className="h-full rounded-full" style={{ width: '60%', background: 'var(--brand)', animation: 'pulse 1.5s ease-in-out infinite' }} />
            </div>
          </div>
        )}

        {/* Decode review gate */}
        {job?.status === 'decode_review' && (
          <div>
            <div className="flex items-center gap-3 p-4 rounded-xl mb-4"
              style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}>
              <RiErrorWarningFill size={20} style={{ color: 'var(--warning)' }} />
              <div>
                <p className="font-semibold text-sm" style={{ color: 'var(--warning)' }}>
                  Stage 2: Decode Review Required
                </p>
                <p className="text-xs" style={{ color: 'var(--text-2)' }}>
                  Review the inspection report and variable classifications below, then approve to run the full analysis.
                </p>
              </div>
            </div>
            <DecodeReview job={job} onApprove={() => {
              fetchJobRef.current?.();
              startPolling(1500);
            }} />
          </div>
        )}

        {/* Error Management Card */}
        {job?.status === 'failed' && (
          <div className="card p-6 md:p-8 animate-slide-up shadow-lg" style={{ border: '1px solid rgba(239, 68, 68, 0.3)', background: 'linear-gradient(180deg, rgba(239, 68, 68, 0.04) 0%, var(--surface) 100%)' }}>
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 shadow-sm" style={{ background: 'rgba(239, 68, 68, 0.12)', color: 'var(--danger)' }}>
                <RiErrorWarningFill size={26} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <h3 className="text-lg font-bold" style={{ color: 'var(--text)', fontFamily: 'Syne, sans-serif', margin: 0 }}>
                    Analysis Could Not Complete
                  </h3>
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider" style={{ background: 'rgba(239, 68, 68, 0.12)', color: 'var(--danger)' }}>
                    Failed
                  </span>
                </div>
                <p className="text-sm leading-relaxed mb-6" style={{ color: 'var(--text-2)', maxWidth: 720 }}>
                  {(() => {
                    const raw = job.error_message || '';
                    const lower = raw.toLowerCase();
                    if (!raw || lower.includes('session') || lower.includes('rollback') || lower.includes('flush') || lower.includes('keys must be str') || lower.includes('timestamp') || lower.includes('sqlite') || lower.includes('typeerror')) {
                      return 'The analysis encountered a data formatting issue while processing your dataset. Please click Retry to run the analysis again.';
                    }
                    if (lower.includes('timeout') || lower.includes('timed out')) {
                      return 'The analysis timed out due to extended processing time. Please click Retry to run the analysis again.';
                    }
                    return raw;
                  })()}
                </p>

                {/* Actions */}
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    className="btn btn-primary flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm shadow-md"
                    onClick={handleRetryJob}
                    disabled={retryingJob}
                  >
                    {retryingJob ? <RiLoader4Line size={16} className="animate-spin" /> : <RiRefreshLine size={16} />}
                    {retryingJob ? 'Restarting…' : 'Retry Analysis'}
                  </button>

                  <button
                    className="btn btn-ghost flex items-center gap-2 px-4 py-2 rounded-xl text-sm border"
                    onClick={() => router.push('/analysis')}
                    style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
                  >
                    Start New Analysis
                  </button>

                  <button
                    className="btn btn-ghost flex items-center gap-2 px-4 py-2 rounded-xl text-sm"
                    onClick={() => router.push('/dashboard')}
                    style={{ color: 'var(--text-3)' }}
                  >
                    Return to Dashboard
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Running progress */}
        {isActive && (
          <div className="card p-8 text-center">
            <div className="relative inline-block mb-6">
              <RiLoader4Line size={48} className="animate-spin mx-auto" style={{ color: 'var(--brand)' }} />
            </div>
            <p className="font-display font-semibold text-lg mb-2" style={{ color: 'var(--text)' }}>
              {RUNNING_MESSAGES[job?.status] || 'Processing...'}
            </p>
            <p className="text-sm" style={{ color: 'var(--text-3)' }}>
              Stage {STAGE_ORDER[job?.status] ?? '?'} of 7 · {STAGE_SUBTEXTS[job?.status] || 'Please wait...'}
            </p>
            <div className="mt-6 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface-2)' }}>
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{ width: `${((STAGE_ORDER[job?.status] ?? 0) / 7) * 100}%`, background: 'var(--brand)' }}
              />
            </div>
          </div>
        )}

        {job?.status === 'complete' && (
          <div className="flex flex-col md:flex-row gap-6">
            <div className="flex-1 min-w-0 pb-8">
              <ResultsDisplay job={job} onRefresh={() => fetchJobRef.current?.()} />
            </div>
            <div className="w-full md:w-[380px] md:flex-shrink-0" style={{ alignSelf: 'flex-start' }}>
              <ChatPanel jobId={job.id} />
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

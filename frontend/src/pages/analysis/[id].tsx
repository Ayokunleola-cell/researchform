// src/pages/analysis/[id].tsx
import React, { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/router';
import AppLayout from '../../components/layout/AppLayout';
import { analysisApi, downloadBlob } from '../../lib/api';
import {
  CheckCircle, AlertCircle, Loader2, Clock, Download,
  RefreshCw, Edit2, ChevronDown, ChevronUp, FileText,
  BarChart3, Code2, FlaskConical, BookOpen, Check, X
} from 'lucide-react';
import toast from 'react-hot-toast';
import clsx from 'clsx';

const STAGES = [
  { n: 1, label: 'Data Assembly',   key: 'assembling' },
  { n: 2, label: 'Data Decode',     key: 'decoding',       star: true },
  { n: 3, label: 'Brief Parsing',   key: 'parsing' },
  { n: 4, label: 'Test Selection',  key: 'selecting' },
  { n: 5, label: 'Code Generation', key: 'generating' },
  { n: 6, label: 'Code Execution',  key: 'executing' },
  { n: 7, label: 'Visualisation',   key: 'visualising' },
  { n: 8, label: 'Report Writing',  key: 'writing' },
  { n: 9, label: 'Document Build',  key: 'building' },
];

const STAGE_ORDER: Record<string, number> = {
  pending: 0, assembling: 1, decoding: 2, decode_review: 2,
  parsing: 3, selecting: 4, generating: 5, executing: 6,
  visualising: 7, writing: 8, building: 9, complete: 10, failed: -1,
};

function StageBar({ status }: { status: string }) {
  const current = STAGE_ORDER[status] ?? 0;
  return (
    <div className="flex items-center gap-0 overflow-x-auto pb-2">
      {STAGES.map((stage, i) => {
        const done   = current > stage.n;
        const active = current === stage.n || (status === 'decode_review' && stage.n === 2);
        const failed = status === 'failed' && active;
        return (
          <React.Fragment key={stage.n}>
            <div className="flex flex-col items-center min-w-[72px]">
              <div
                className="stage-dot mb-1 text-xs"
                style={{
                  width: 28, height: 28, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 700,
                  background: failed ? 'var(--danger)' : done ? 'var(--success)' : active ? 'var(--brand)' : 'var(--surface-2)',
                  color: done || active ? '#fff' : 'var(--text-3)',
                  border: `2px solid ${done ? 'var(--success)' : active ? 'var(--brand)' : 'var(--border)'}`,
                  boxShadow: active ? '0 0 12px rgba(99,102,241,0.3)' : 'none',
                }}
              >
                {done ? <Check size={14} /> : failed ? <X size={14} /> : active ? <Loader2 size={13} className="animate-spin" /> : stage.n}
              </div>
              <p className="text-center leading-tight" style={{ fontSize: 9, color: active ? 'var(--brand)' : done ? 'var(--success)' : 'var(--text-3)', fontWeight: active || done ? 700 : 400 }}>
                {stage.label}
                {stage.star ? ' ★' : ''}
              </p>
            </div>
            {i < STAGES.length - 1 && (
              <div className="flex-1 h-0.5 mx-0.5" style={{ minWidth: 8, background: done ? 'var(--success)' : 'var(--border)' }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ─── Decode Review Component ─────────────────────────────────────────
function DecodeReview({ job, onApprove }: { job: any; onApprove: () => void }) {
  const [overrides, setOverrides] = useState<Record<string, any>>({});
  const [missingStrategy, setMissingStrategy] = useState(job.missing_strategy || 'flag_only');
  const [approving, setApproving] = useState(false);
  const dict = job.data_dictionary || {};
  const variables = dict.variables || [];

  const handleApprove = async () => {
    setApproving(true);
    try {
      await analysisApi.approveDecoded(job.id, { variable_overrides: overrides, missing_strategy: missingStrategy });
      toast.success('Decode approved — analysis starting!');
      onApprove();
    } catch {
      toast.error('Failed to approve decode');
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Warnings */}
      {job.decode_warnings?.length > 0 && (
        <div className="card p-4 space-y-2" style={{ border: '1px solid rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.05)' }}>
          <p className="font-semibold text-sm flex items-center gap-2" style={{ color: 'var(--warning)' }}>
            <AlertCircle size={16} /> Decode Warnings ({job.decode_warnings.length})
          </p>
          {job.decode_warnings.map((w: any, i: number) => (
            <div key={i} className="text-sm pl-6" style={{ color: 'var(--text-2)' }}>
              <strong>{w.severity.toUpperCase()}</strong>{w.variable ? ` [${w.variable}]` : ''}: {w.message}
              {w.suggestion && <span style={{ color: 'var(--text-3)' }}> → {w.suggestion}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Variables', value: dict.n_columns },
          { label: 'Respondents', value: dict.n_rows },
          { label: 'Complete Rows', value: dict.n_complete_rows },
          { label: 'Source', value: job.source_type?.toUpperCase() },
        ].map(({ label, value }) => (
          <div key={label} className="card p-3 text-center">
            <p className="font-display font-bold text-xl" style={{ color: 'var(--text)' }}>{value ?? '—'}</p>
            <p className="text-xs" style={{ color: 'var(--text-3)' }}>{label}</p>
          </div>
        ))}
      </div>

      {/* Missing strategy */}
      <div className="card p-4">
        <label className="label mb-3">Missing Value Strategy</label>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {[
            { value: 'flag_only',    label: 'Flag Only' },
            { value: 'drop_rows',    label: 'Drop Rows' },
            { value: 'mean_impute',  label: 'Mean Impute' },
            { value: 'mode_impute',  label: 'Mode Impute' },
          ].map(opt => (
            <button
              key={opt.value}
              onClick={() => setMissingStrategy(opt.value)}
              className="py-2 px-3 rounded-lg text-sm font-medium transition-all"
              style={{
                background: missingStrategy === opt.value ? 'var(--brand)' : 'var(--surface-2)',
                color: missingStrategy === opt.value ? '#fff' : 'var(--text-2)',
                border: `1.5px solid ${missingStrategy === opt.value ? 'var(--brand)' : 'var(--border)'}`,
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Variable table */}
      <div className="card overflow-hidden">
        <div className="p-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <p className="font-semibold" style={{ color: 'var(--text)' }}>
            Variable Review — review and correct measurement levels before analysis
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead style={{ background: 'var(--surface-2)' }}>
              <tr>
                {['Variable', 'Label', 'Type', 'Measurement Level', 'Missing', 'Role', 'Flag'].map(h => (
                  <th key={h} className="p-3 text-left font-semibold" style={{ color: 'var(--text-2)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {variables.map((v: any) => {
                const override = overrides[v.clean_name] || {};
                const level = override.measurement_level || v.measurement_level;
                const role  = override.role || v.role || 'covariate';
                return (
                  <tr key={v.clean_name} style={{ borderTop: '1px solid var(--border)' }}>
                    <td className="p-3 font-mono text-xs" style={{ color: 'var(--text)' }}>{v.clean_name}</td>
                    <td className="p-3 text-xs max-w-[160px] truncate" style={{ color: 'var(--text-2)' }} title={v.label}>{v.label}</td>
                    <td className="p-3 text-xs font-mono" style={{ color: 'var(--text-3)' }}>{v.dtype}</td>
                    <td className="p-3">
                      <select
                        className="text-xs rounded-lg px-2 py-1"
                        style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }}
                        value={level}
                        onChange={e => setOverrides(o => ({ ...o, [v.clean_name]: { ...override, measurement_level: e.target.value } }))}
                      >
                        {['nominal', 'ordinal', 'interval', 'ratio'].map(l => (
                          <option key={l} value={l}>{l}</option>
                        ))}
                      </select>
                      {v.level_uncertain && <span className="ml-1 text-xs" style={{ color: 'var(--warning)' }}>?</span>}
                    </td>
                    <td className="p-3 text-xs" style={{ color: v.pct_missing > 20 ? 'var(--danger)' : 'var(--text-2)' }}>
                      {v.n_missing} ({v.pct_missing?.toFixed(0)}%)
                    </td>
                    <td className="p-3">
                      <select
                        className="text-xs rounded-lg px-2 py-1"
                        style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }}
                        value={role}
                        onChange={e => setOverrides(o => ({ ...o, [v.clean_name]: { ...override, role: e.target.value } }))}
                      >
                        {['covariate', 'dependent', 'independent', 'group', 'exclude'].map(r => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    </td>
                    <td className="p-3">
                      {v.high_missing && <span className="badge badge-danger text-xs">High missing</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <button
        className="btn btn-primary w-full btn-lg"
        onClick={handleApprove}
        disabled={approving}
      >
        {approving ? <Loader2 size={18} className="animate-spin" /> : <FlaskConical size={18} />}
        {approving ? 'Starting Analysis...' : 'Approve & Run Analysis'}
      </button>
    </div>
  );
}

// ─── Results Display ─────────────────────────────────────────────────
function ResultsDisplay({ job }: { job: any }) {
  const [reportLoading, setReportLoading] = useState(false);
  const [showCode, setShowCode] = useState(false);

  const handleDownloadReport = async () => {
    setReportLoading(true);
    try {
      const res = await analysisApi.getReport(job.id);
      downloadBlob(res.data, `Chapter4_${job.id}.docx`);
      toast.success('Report downloaded!');
    } catch {
      toast.error('Failed to download report');
    } finally {
      setReportLoading(false);
    }
  };

  const results = job.results || {};
  const tests = job.selected_tests || [];

  return (
    <div className="space-y-6">
      {/* Download Report */}
      <div className="card p-6 flex items-center gap-4" style={{ border: '2px solid var(--brand)', background: 'rgba(99,102,241,0.04)' }}>
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0" style={{ background: 'var(--brand)' }}>
          <BookOpen size={24} className="text-white" />
        </div>
        <div className="flex-1">
          <p className="font-display font-bold text-lg" style={{ color: 'var(--text)' }}>Chapter 4 Report Ready</p>
          <p className="text-sm" style={{ color: 'var(--text-2)' }}>
            Times New Roman · 12pt · Double-spaced · APA tables · Nigerian university format
          </p>
        </div>
        <button
          className="btn btn-primary btn-lg flex-shrink-0"
          onClick={handleDownloadReport}
          disabled={reportLoading}
        >
          {reportLoading ? <Loader2 size={18} className="animate-spin" /> : <Download size={18} />}
          Download .docx
        </button>
      </div>

      {/* Statistical tests used */}
      {tests.length > 0 && (
        <div className="card p-6">
          <h3 className="font-display font-semibold mb-4" style={{ color: 'var(--text)' }}>Statistical Tests Selected</h3>
          <div className="space-y-3">
            {tests.map((t: any, i: number) => (
              <div key={i} className="p-4 rounded-xl" style={{ background: 'var(--surface-2)' }}>
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'var(--brand)', opacity: 0.9 }}>
                    <BarChart3 size={16} className="text-white" />
                  </div>
                  <div>
                    <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{t.test_name}</p>
                    <p className="text-xs mt-1" style={{ color: 'var(--text-2)' }}>{t.rationale}</p>
                    {t.hypothesis && <p className="text-xs mt-1 font-mono" style={{ color: 'var(--text-3)' }}>→ {t.hypothesis}</p>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Key results */}
      {results.summary && (
        <div className="card p-6">
          <h3 className="font-display font-semibold mb-4" style={{ color: 'var(--text)' }}>Key Findings</h3>
          <div className="space-y-3">
            {results.summary.map((r: any, i: number) => (
              <div key={i} className="p-4 rounded-xl" style={{ background: 'var(--surface-2)' }}>
                <p className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>{r.hypothesis}</p>
                <div className="flex items-center gap-3 flex-wrap">
                  {r.statistic && <span className="badge badge-brand font-mono">{r.statistic_name} = {r.statistic.toFixed(3)}</span>}
                  {r.p_value !== undefined && (
                    <span className={`badge ${r.p_value < 0.05 ? 'badge-danger' : 'badge-neutral'} font-mono`}>
                      p = {r.p_value.toFixed(3)}
                    </span>
                  )}
                  {r.effect_size && <span className="badge badge-neutral font-mono">{r.effect_size_name} = {r.effect_size.toFixed(3)}</span>}
                </div>
                <p className="text-xs mt-2" style={{ color: 'var(--text-2)', fontFamily: 'Times New Roman' }}>
                  {r.conclusion}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Charts */}
      {job.chart_paths?.length > 0 && (
        <div className="card p-6">
          <h3 className="font-display font-semibold mb-4" style={{ color: 'var(--text)' }}>Charts Generated</h3>
          <div className="grid grid-cols-2 gap-3">
            {job.chart_paths.map((path: string, i: number) => (
              <div key={i} className="rounded-xl overflow-hidden border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)', aspectRatio: '4/3', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <img
                  src={`${process.env.NEXT_PUBLIC_API_URL}/analysis/jobs/${job.id}/charts/${i}`}
                  alt={`Chart ${i + 1}`}
                  className="max-w-full max-h-full object-contain"
                  onError={(e: any) => {
                    e.target.style.display = 'none';
                    e.target.parentElement.innerHTML = `<p style="color:var(--text-3);font-size:12px">Chart ${i+1}</p>`;
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Generated code */}
      {job.generated_code && (
        <div className="card overflow-hidden">
          <button
            className="w-full flex items-center justify-between p-4 border-b"
            style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}
            onClick={() => setShowCode(!showCode)}
          >
            <span className="flex items-center gap-2 font-semibold text-sm" style={{ color: 'var(--text)' }}>
              <Code2 size={16} style={{ color: 'var(--brand)' }} /> Generated Python Code
            </span>
            {showCode ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {showCode && (
            <div className="code-block text-xs" style={{ maxHeight: 400, overflow: 'auto' }}>
              <pre>{job.generated_code}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────
export default function AnalysisJobPage() {
  const router = useRouter();
  const { id } = router.query as { id: string };
  const [job, setJob] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  const fetchJob = async () => {
    try {
      const res = await analysisApi.getJob(id);
      setJob(res.data);
      if (['complete', 'failed', 'decode_review'].includes(res.data.status)) {
        clearInterval(pollRef.current);
      }
    } catch {
      clearInterval(pollRef.current);
    }
  };

  useEffect(() => {
    if (!id) return;
    fetchJob().finally(() => setLoading(false));
    pollRef.current = setInterval(fetchJob, 3000);
    return () => clearInterval(pollRef.current);
  }, [id]);

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin" size={32} style={{ color: 'var(--brand)' }} />
      </div>
    </AppLayout>
  );

  const isActive = !['complete', 'failed', 'decode_review'].includes(job?.status);

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text)' }}>
              Analysis Job
            </h1>
            <p className="text-xs font-mono mt-1" style={{ color: 'var(--text-3)' }}>{id}</p>
          </div>
          <div className="flex items-center gap-3">
            {isActive && (
              <span className="flex items-center gap-2 text-sm" style={{ color: 'var(--brand)' }}>
                <Loader2 size={14} className="animate-spin" /> Processing...
              </span>
            )}
            <button className="btn btn-ghost btn-icon" onClick={fetchJob} title="Refresh">
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        {/* Stage bar */}
        <div className="card p-5">
          <StageBar status={job?.status || 'pending'} />
        </div>

        {/* Decode review gate */}
        {job?.status === 'decode_review' && (
          <div>
            <div className="flex items-center gap-3 p-4 rounded-xl mb-4" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}>
              <AlertCircle size={20} style={{ color: 'var(--warning)' }} />
              <div>
                <p className="font-semibold text-sm" style={{ color: 'var(--warning)' }}>Decode Review Required</p>
                <p className="text-xs" style={{ color: 'var(--text-2)' }}>
                  Review the variable classifications below, correct any errors, then approve to start analysis.
                </p>
              </div>
            </div>
            <DecodeReview job={job} onApprove={() => {
              pollRef.current = setInterval(fetchJob, 3000);
              fetchJob();
            }} />
          </div>
        )}

        {/* Error */}
        {job?.status === 'failed' && (
          <div className="card p-6" style={{ border: '1px solid var(--danger)', background: 'rgba(239,68,68,0.05)' }}>
            <div className="flex items-center gap-3 mb-2">
              <AlertCircle size={20} style={{ color: 'var(--danger)' }} />
              <p className="font-semibold" style={{ color: 'var(--danger)' }}>Analysis Failed</p>
            </div>
            <p className="text-sm" style={{ color: 'var(--text-2)' }}>
              {job.error_message || 'An unexpected error occurred during analysis.'}
            </p>
          </div>
        )}

        {/* Running status */}
        {isActive && job?.status !== 'decode_review' && (
          <div className="card p-6 text-center">
            <Loader2 size={40} className="animate-spin mx-auto mb-4" style={{ color: 'var(--brand)' }} />
            <p className="font-display font-semibold" style={{ color: 'var(--text)' }}>
              {job?.status === 'decoding' ? 'Decoding your data...' :
               job?.status === 'selecting' ? 'AI is selecting statistical tests...' :
               job?.status === 'generating' ? 'Generating Python analysis code...' :
               job?.status === 'executing' ? 'Running statistical analysis...' :
               job?.status === 'visualising' ? 'Creating charts...' :
               job?.status === 'writing' ? 'Writing Chapter 4 narrative...' :
               job?.status === 'building' ? 'Building Word document...' :
               'Processing...'}
            </p>
            <p className="text-sm mt-2" style={{ color: 'var(--text-3)' }}>This may take 1–3 minutes</p>
          </div>
        )}

        {/* Complete results */}
        {job?.status === 'complete' && <ResultsDisplay job={job} />}
      </div>
    </AppLayout>
  );
}

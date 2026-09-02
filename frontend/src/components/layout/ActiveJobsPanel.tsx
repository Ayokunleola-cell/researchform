// src/components/layout/ActiveJobsPanel.tsx
/**
 * Persistent sidebar panel showing all running analysis jobs.
 * Rendered inside AppLayout — survives page navigation.
 * Clicking a job navigates to its analysis page.
 */
import React from 'react';
import Link from 'next/link';
import { useAnalysisStore, TrackedJob } from '../../lib/analysisStore';
import { RiBarChart2Fill, RiCheckboxCircleFill, RiErrorWarningFill, RiLoader4Line, RiTimeLine, RiEyeFill } from 'react-icons/ri';

const STAGE_LABELS: Record<number, string> = {
  1: 'Inspecting',
  2: 'Decoding',
  3: 'Configuring',
  4: 'Running tests',
  5: 'Writing report',
  6: 'Generating charts',
  7: 'Complete',
};

function JobRow({ job, collapsed }: { job: TrackedJob; collapsed: boolean }) {
  const isComplete = job.status === 'complete';
  const isFailed = job.status === 'failed';
  const isActive = !isComplete && !isFailed;

  const color = isComplete
    ? 'var(--success)'
    : isFailed
    ? 'var(--danger)'
    : 'var(--brand)';

  const pct = Math.round((job.stage / job.totalStages) * 100);
  const elapsed = Math.round((Date.now() - job.startedAt) / 1000);
  const elapsedStr = elapsed < 60 ? `${elapsed}s` : `${Math.round(elapsed / 60)}m`;

  if (collapsed) {
    // Compact dot indicator in collapsed sidebar
    return (
      <Link href={`/analysis/${job.id}`} title={job.title}>
        <div
          style={{
            width: 8, height: 8, borderRadius: '50%',
            background: color,
            margin: '4px auto',
            boxShadow: isActive ? `0 0 6px ${color}` : 'none',
            animation: isActive ? 'pulse 2s infinite' : 'none',
          }}
        />
      </Link>
    );
  }

  return (
    <Link href={`/analysis/${job.id}`} style={{ textDecoration: 'none' }}>
      <div
        style={{
          padding: '8px 10px',
          borderRadius: 8,
          background: 'var(--surface-3)',
          border: `1px solid ${isActive ? 'rgba(99,102,241,0.2)' : 'var(--border)'}`,
          cursor: 'pointer',
          transition: 'all 0.15s',
          marginBottom: 6,
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = color; e.currentTarget.style.background = 'var(--surface-2)'; }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = isActive ? 'rgba(99,102,241,0.2)' : 'var(--border)'; e.currentTarget.style.background = 'var(--surface-3)'; }}
      >
        {/* Title row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
          {isComplete ? (
            <RiCheckboxCircleFill size={12} color="var(--success)" />
          ) : isFailed ? (
            <RiErrorWarningFill size={12} color="var(--danger)" />
          ) : (
            <RiLoader4Line
              size={12}
              color="var(--brand)"
              style={{ animation: 'spin 1s linear infinite' }}
            />
          )}
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flex: 1,
            }}
            title={job.title}
          >
            {job.title}
          </span>
          <span style={{ fontSize: 10, color: 'var(--text-3)', flexShrink: 0 }}>
            {elapsedStr}
          </span>
        </div>

        {/* Progress bar */}
        {!isFailed && (
          <div style={{ height: 3, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${pct}%`,
                background: `linear-gradient(90deg, ${color}, ${color}cc)`,
                borderRadius: 2,
                transition: 'width 0.5s ease',
              }}
            />
          </div>
        )}

        {/* Stage label */}
        <div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-3)', display: 'flex', justifyContent: 'space-between' }}>
          <span>{isFailed ? 'Failed — click to view' : STAGE_LABELS[job.stage] || job.status}</span>
          {!isFailed && <span style={{ color }}>{pct}%</span>}
        </div>
      </div>
    </Link>
  );
}

interface ActiveJobsPanelProps {
  collapsed: boolean;
}

export default function ActiveJobsPanel({ collapsed }: ActiveJobsPanelProps) {
  const { trackedJobs, clearFinished } = useAnalysisStore();
  const jobs = Object.values(trackedJobs);

  if (jobs.length === 0) return null;

  const activeCount = jobs.filter(j => j.status !== 'complete' && j.status !== 'failed').length;

  if (collapsed) {
    return (
      <div style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
        {jobs.slice(0, 3).map(job => (
          <JobRow key={job.id} job={job} collapsed />
        ))}
      </div>
    );
  }

  return (
    <div
      style={{
        padding: '10px 12px',
        borderTop: '1px solid var(--border)',
        marginTop: 8,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <RiBarChart2Fill size={12} color={activeCount > 0 ? 'var(--brand)' : 'var(--text-3)'} />
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            {activeCount > 0 ? `${activeCount} Running` : 'Analysis Jobs'}
          </span>
        </div>
        {jobs.some(j => j.status === 'complete' || j.status === 'failed') && (
          <button
            onClick={clearFinished}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 10, color: 'var(--text-3)', padding: 0,
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Job rows */}
      <div>
        {jobs.map(job => (
          <JobRow key={job.id} job={job} collapsed={false} />
        ))}
      </div>
    </div>
  );
}

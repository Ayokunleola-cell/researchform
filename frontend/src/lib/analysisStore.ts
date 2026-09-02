// src/lib/analysisStore.ts
/**
 * Global analysis job tracking store.
 * Lives at the app root — survives page navigation.
 * The [id].tsx page registers/unregisters jobs here.
 * AppLayout reads this to show the persistent sidebar panel.
 */
import { create } from 'zustand';
import { analysisApi } from './api';

export type TrackedJobStatus =
  | 'pending'
  | 'preprocessing'
  | 'preprocessing_review'
  | 'decode_review'
  | 'running'
  | 'complete'
  | 'failed'
  | 'queued';

export interface TrackedJob {
  id: string;
  title: string;          // e.g. filename or survey name
  status: TrackedJobStatus;
  stage: number;          // 1-7 for progress bar
  totalStages: number;
  startedAt: number;      // Date.now()
  updatedAt: number;
}

interface AnalysisStore {
  trackedJobs: Record<string, TrackedJob>;
  /** Call when user starts an analysis or navigates to an existing one */
  watchJob: (id: string, title: string) => void;
  /** Call when job reaches terminal state (complete/failed) */
  unwatchJob: (id: string) => void;
  /** Internal: update a job's live status */
  _updateJob: (id: string, patch: Partial<TrackedJob>) => void;
  /** Clear all terminal jobs (housekeeping) */
  clearFinished: () => void;
}

/** Map backend status → wizard stage number */
function statusToStage(status: string): number {
  const map: Record<string, number> = {
    pending: 1,
    preprocessing: 1,
    preprocessing_review: 1,
    decode_review: 2,
    running: 4,
    complete: 7,
    failed: 0,
    queued: 1,
  };
  return map[status] ?? 1;
}

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  trackedJobs: {},

  watchJob: (id, title) => {
    const existing = get().trackedJobs[id];
    if (existing) return; // already tracked
    set(s => ({
      trackedJobs: {
        ...s.trackedJobs,
        [id]: {
          id,
          title,
          status: 'pending',
          stage: 1,
          totalStages: 7,
          startedAt: Date.now(),
          updatedAt: Date.now(),
        },
      },
    }));
  },

  unwatchJob: (id) => {
    set(s => {
      const next = { ...s.trackedJobs };
      delete next[id];
      return { trackedJobs: next };
    });
  },

  _updateJob: (id, patch) => {
    set(s => {
      if (!s.trackedJobs[id]) return s;
      return {
        trackedJobs: {
          ...s.trackedJobs,
          [id]: { ...s.trackedJobs[id], ...patch, updatedAt: Date.now() },
        },
      };
    });
  },

  clearFinished: () => {
    set(s => {
      const next = { ...s.trackedJobs };
      for (const [id, job] of Object.entries(next)) {
        if (job.status === 'complete' || job.status === 'failed') {
          delete next[id];
        }
      }
      return { trackedJobs: next };
    });
  },
}));

// ─── Global Polling Singleton ─────────────────────────────────────────────────
// Runs outside React component lifecycle so navigation doesn't stop it.
let _pollTimer: ReturnType<typeof setInterval> | null = null;

export function startGlobalPoller() {
  if (_pollTimer) return; // already running

  _pollTimer = setInterval(async () => {
    const { trackedJobs, _updateJob, unwatchJob } = useAnalysisStore.getState();
    const active = Object.values(trackedJobs).filter(
      j => j.status !== 'complete' && j.status !== 'failed'
    );
    if (active.length === 0) return;

    await Promise.allSettled(
      active.map(async job => {
        try {
          // Use lightweight status endpoint — tiny payload, fast response
          const res = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/analysis/jobs/${job.id}/status`,
            {
              headers: {
                Authorization: `Bearer ${
                  typeof window !== 'undefined'
                    ? localStorage.getItem('rf_token') || ''
                    : ''
                }`,
              },
            }
          );
          if (!res.ok) return;
          const data = await res.json();
          const status = data.status as TrackedJobStatus;
          _updateJob(job.id, { status, stage: statusToStage(status) });

          // Fire browser notification on completion
          if (status === 'complete' || status === 'failed') {
            if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
              new Notification(status === 'complete' ? '✅ Analysis Complete' : '❌ Analysis Failed', {
                body: `${job.title} — ${status === 'complete' ? 'results ready' : 'check for errors'}`,
                icon: '/favicon.ico',
              });
            }
          }
        } catch {
          // Network error — keep tracking, don't remove job
        }
      })
    );
  }, 3000 + Math.random() * 1000); // 3-4s with jitter to spread load
}

export function stopGlobalPoller() {
  if (_pollTimer) {
    clearInterval(_pollTimer);
    _pollTimer = null;
  }
}

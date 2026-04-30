// src/pages/reports/index.tsx
import React, { useEffect, useState } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { analysisApi, downloadBlob } from '../../lib/api';
import { BookOpen, Download, Clock, CheckCircle, Loader2, BarChart3 } from 'lucide-react';
import Link from 'next/link';
import toast from 'react-hot-toast';

export default function ReportsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    analysisApi.listJobs().then(r => setJobs((r.data || []).filter((j: any) => j.status === 'complete'))).finally(() => setLoading(false));
  }, []);

  const handleDownload = async (jobId: string) => {
    setDownloading(jobId);
    try {
      const res = await analysisApi.getReport(jobId);
      downloadBlob(res.data, `Chapter4_${jobId.slice(0,8)}.docx`);
      toast.success('Report downloaded!');
    } catch { toast.error('Download failed'); }
    finally { setDownloading(null); }
  };

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--text)' }}>Reports</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-2)' }}>Download Chapter 4 Word documents from completed analyses</p>
        </div>

        {loading ? (
          <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-20 rounded-2xl" />)}</div>
        ) : jobs.length === 0 ? (
          <div className="card p-16 text-center">
            <BookOpen size={48} className="mx-auto mb-4" style={{ color: 'var(--text-3)' }} />
            <p className="font-display font-bold text-lg mb-2" style={{ color: 'var(--text)' }}>No reports yet</p>
            <p className="text-sm mb-6" style={{ color: 'var(--text-2)' }}>Complete an analysis to generate your Chapter 4 report</p>
            <Link href="/analysis"><button className="btn btn-primary"><BarChart3 size={16} /> Go to Analysis</button></Link>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job: any) => (
              <div key={job.id} className="card p-5 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(16,185,129,0.1)' }}>
                  <BookOpen size={22} style={{ color: 'var(--success)' }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold" style={{ color: 'var(--text)' }}>
                    {job.survey_title || job.source_filename || 'Analysis Report'}
                  </p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-3)' }}>
                    <span className="badge badge-success text-xs mr-2">Complete</span>
                    {job.n_rows} rows · {job.n_columns} variables ·
                    Completed {job.completed_at ? new Date(job.completed_at).toLocaleDateString() : '—'}
                  </p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <Link href={`/analysis/${job.id}`}>
                    <button className="btn btn-secondary btn-sm">View Results</button>
                  </Link>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => handleDownload(job.id)}
                    disabled={downloading === job.id}
                  >
                    {downloading === job.id ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                    Download .docx
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="card p-5" style={{ background: 'rgba(99,102,241,0.04)', border: '1px solid rgba(99,102,241,0.2)' }}>
          <p className="font-semibold text-sm mb-1" style={{ color: 'var(--text)' }}>Report Format</p>
          <p className="text-sm" style={{ color: 'var(--text-2)' }}>
            All reports are formatted in <strong>Times New Roman 12pt, double-spaced</strong> following
            Nigerian university academic standards. Hypothesis conclusions use the standard
            "yielded t(df) = X.XX, p = 0.XXX" format with formal accept/reject language.
          </p>
        </div>
      </div>
    </AppLayout>
  );
}

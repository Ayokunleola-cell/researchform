// src/pages/reports/index.tsx
import React, { useEffect, useState } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import PageHeader from '../../components/ui/PageHeader';
import ResearchWorkflow from '../../components/ui/ResearchWorkflow';
import EmptyState from '../../components/ui/EmptyState';
import { analysisApi, downloadBlob } from '../../lib/api';
import { RiBarChart2Fill, RiCoinsFill, RiDownload2Fill, RiLoader4Line, RiBookOpenFill } from 'react-icons/ri';
import Link from 'next/link';
import toast from 'react-hot-toast';
import DownloadDropdown from '../../components/ui/DownloadDropdown';

/** When responseType='blob', axios delivers error payloads as Blobs — parse them back to JSON. */
async function parseBlobError(err: any): Promise<any> {
  try {
    const data = err.response?.data;
    if (data instanceof Blob) {
      const text = await data.text();
      return JSON.parse(text);
    }
    return data;
  } catch {
    return null;
  }
}

export default function ReportsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [billingMap, setBillingMap] = useState<Record<string, { cost: number; paid: boolean; can: boolean }>>({});

  useEffect(() => {
    analysisApi
      .listJobs()
      .then(async (r) => {
        const complete = (r.data || []).filter((j: any) => j.status === 'complete');
        setJobs(complete);
        const map: Record<string, { cost: number; paid: boolean; can: boolean }> = {};
        await Promise.all(
          complete.map(async (j: any) => {
            try {
              const b = await analysisApi.getJobBilling(j.id);
              map[j.id] = {
                cost: b.data.credits_required,
                paid: b.data.report_paid,
                can: b.data.can_download,
              };
            } catch {
              map[j.id] = { cost: 0, paid: false, can: false };
            }
          })
        );
        setBillingMap(map);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleDownload = async (jobId: string) => {
    setDownloading(jobId);
    try {
      const res = await analysisApi.getReport(jobId);
      downloadBlob(res.data, `Report_${jobId.slice(0,8)}.docx`);
      toast.success('Report downloaded!');
    } catch (err: any) {
      const parsed = await parseBlobError(err);
      const d = parsed?.detail;
      if (err.response?.status === 402 && d && typeof d === 'object' && d.required != null) {
        toast.error(`Need ${Number(d.required).toFixed(2)} credits (balance: ${Number(d.balance).toFixed(2)})`);
      } else if (err.response?.status === 402) {
        toast.error('Please unlock the analysis to download the report.');
      } else {
        toast.error('Download failed. Please try again.');
      }
    }
    finally { setDownloading(null); }
  };

  const handleDownloadPdf = async (jobId: string) => {
    setDownloading(jobId);
    try {
      const res = await analysisApi.getReportPdf(jobId);
      downloadBlob(res.data, `Report_${jobId.slice(0,8)}.pdf`);
      toast.success('PDF Report downloaded!');
    } catch (err: any) {
      const parsed = await parseBlobError(err);
      const d = parsed?.detail;
      if (err.response?.status === 402 && d && typeof d === 'object' && d.required != null) {
        toast.error(`Need ${Number(d.required).toFixed(2)} credits (balance: ${Number(d.balance).toFixed(2)})`);
      } else if (err.response?.status === 402) {
        toast.error('Please unlock the analysis to download the report.');
      } else {
        toast.error('PDF download failed. Please try again.');
      }
    }
    finally { setDownloading(null); }
  };

  return (
    <AppLayout
      title="Reports"
      breadcrumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Reports' }]}
    >
      <div className="page-container page-stack">
        <ResearchWorkflow />
        <PageHeader
          title="Reports"
          description="Download Word documents from completed analysis jobs. Credits are charged on first download based on AI usage."
          actions={
            <Link href="/settings/credits">
              <button type="button" className="btn btn-secondary btn-sm">
                <RiCoinsFill size={14} /> Buy credits
              </button>
            </Link>
          }
        />

        {loading ? (
          <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-20 rounded-2xl" />)}</div>
        ) : jobs.length === 0 ? (
          <EmptyState
            icon={RiBookOpenFill}
            title="No reports yet"
            action={
              <Link href="/analysis">
                <button type="button" className="btn btn-primary"><RiBarChart2Fill size={16} /> Go to Analysis</button>
              </Link>
            }
          />
        ) : (
          <div className="space-y-3">
            {jobs.map((job: any) => (
              <div key={job.id} className="card p-5 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(16,185,129,0.1)' }}>
                  <RiBookOpenFill size={22} style={{ color: 'var(--success)' }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold" style={{ color: 'var(--text)' }}>
                    {job.project_brief?.topic || job.survey_title || job.source_filename || 'Analysis Report'}
                  </p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-3)' }}>
                    <span className="badge badge-success text-xs mr-2">Complete</span>
                    {job.n_rows} rows · {job.n_columns} variables
                    {job.selected_tests?.length > 0 && ` · ${job.selected_tests.length} tests run`}
                    {' · '}Completed {job.completed_at ? new Date(job.completed_at).toLocaleDateString() : '—'}
                  </p>
                </div>

                  <div className="flex gap-2 flex-shrink-0 relative">
                  <Link href={`/analysis/${job.id}`}>
                    <button className="btn btn-secondary btn-sm">View Results</button>
                  </Link>
                  <DownloadDropdown 
                    onDownloadWord={() => handleDownload(job.id)}
                    onDownloadPdf={() => handleDownloadPdf(job.id)}
                    downloading={downloading === job.id}
                  />
                  </div>
              </div>
            ))}
          </div>
        )}

      </div>
    </AppLayout>
  );
}

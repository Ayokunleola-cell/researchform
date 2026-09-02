import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { analysisApi, downloadBlob, type JobBilling } from '../../lib/api';
import { RiEyeFill, RiHardDriveFill, RiErrorWarningFill, RiCoinsFill, RiProjectorFill as PresentationIcon, RiFileTextFill, RiDownload2Fill, RiCloseFill, RiCheckboxCircleFill, RiLoader4Line, RiBookOpenFill } from 'react-icons/ri';
import toast from 'react-hot-toast';

/** When responseType='blob', axios error payloads arrive as Blobs — parse them back to JSON. */
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

type ReportDownloadPanelProps = {
  jobId: string;
  jobTitle?: string;
  reportType?: string;
  onUnlock?: () => void;
};

type ConfirmModalConfig = {
  title: string;
  message: React.ReactNode;
  confirmText: string;
  cancelText: string;
  isError?: boolean;
  onConfirm: () => void;
};

const REPORT_LABELS: Record<string, string> = {
  chapter4: 'Report',
  academic_report: 'Academic Report',
  research_paper: 'Research Paper',
  business_report: 'Business Report',
  executive_summary: 'Executive Summary',
  technical_report: 'Technical Report',
  slide_deck: 'Slide Deck Briefing'
};

export default function ReportDownloadPanel({ jobId, jobTitle, reportType, onUnlock }: ReportDownloadPanelProps) {
  const [billing, setBilling] = useState<JobBilling | null>(null);
  const [loadingBilling, setLoadingBilling] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [exportingDrive, setExportingDrive] = useState(false);

  const [generatingPresentation, setGeneratingPresentation] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [confirmModal, setConfirmModal] = useState<ConfirmModalConfig | null>(null);

  const loadBilling = () => {
    setLoadingBilling(true);
    analysisApi
      .getJobBilling(jobId)
      .then((res) => setBilling(res.data))
      .catch(() => setBilling(null))
      .finally(() => setLoadingBilling(false));
  };

  useEffect(() => {
    loadBilling();
  }, [jobId]);

  const handleUnlock = async () => {
    setDownloading(true);
    try {
      await analysisApi.unlockAnalysis(jobId);
      toast.success('Analysis unlocked successfully!');
      loadBilling();
      onUnlock?.();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 402 && detail) {
        const msg = typeof detail === 'object' ? `Need ${detail.required?.toFixed(2)} credits (you have ${detail.balance?.toFixed(2)})` : String(detail);
        toast.error(msg);
      } else {
        toast.error('Failed to unlock analysis');
      }
    } finally {
      setDownloading(false);
    }
  };

  const handleGeneratePresentation = async () => {
    setGeneratingPresentation(true);
    try {
      await analysisApi.generatePresentation(jobId);
      toast.success('Presentation generated!');
      loadBilling();
    } catch (err) {
      toast.error('Failed to generate presentation');
    } finally {
      setGeneratingPresentation(false);
    }
  };

  const handleUnlockPresentation = async () => {
    const cost = billing?.presentation_credits_required || 0;
    setConfirmModal({
      title: 'Unlock AI Presentation',
      message: `Unlocking the custom AI presentation will cost ${cost.toFixed(2)} credits. Proceed?`,
      confirmText: 'Unlock',
      cancelText: 'Cancel',
      onConfirm: async () => {
        setConfirmModal(null);
        setDownloading(true);
        try {
          await analysisApi.unlockPresentation(jobId);
          toast.success('Presentation unlocked!');
          loadBilling();
          onUnlock?.();
        } catch (err: any) {
          toast.error('Failed to unlock presentation. Insufficient credits?');
        } finally {
          setDownloading(false);
        }
      }
    });
  };

  const handleDownloadPresentation = async () => {
    setDownloading(true);
    try {
      const res = await analysisApi.getPresentation(jobId);
      downloadBlob(res.data, `Presentation_${jobId.slice(0, 8)}.pptx`);
      toast.success('Presentation downloaded!');
    } catch (err) {
      toast.error('Failed to download presentation');
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadWord = async () => {
    setDownloading(true);
    try {
      const res = await analysisApi.getReport(jobId);
      downloadBlob(res.data, `Report_${jobId.slice(0, 8)}.docx`);
      toast.success('Word Report downloaded');
    } catch (err: any) {
      const parsed = await parseBlobError(err);
      const d = parsed?.detail;
      if (err.response?.status === 402 && d && typeof d === 'object' && d.required != null) {
        toast.error(`Need ${Number(d.required).toFixed(2)} credits (balance: ${Number(d.balance).toFixed(2)})`);
      } else if (err.response?.status === 402) {
        toast.error('Please unlock the analysis to download the report.');
      } else {
        toast.error('Failed to download Word report');
      }
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      const res = await analysisApi.getReportPdf(jobId);
      downloadBlob(res.data, `Report_${jobId.slice(0, 8)}.pdf`);
      toast.success('PDF Report downloaded');
    } catch (err: any) {
      const parsed = await parseBlobError(err);
      const d = parsed?.detail;
      if (err.response?.status === 402 && d && typeof d === 'object' && d.required != null) {
        toast.error(`Need ${Number(d.required).toFixed(2)} credits (balance: ${Number(d.balance).toFixed(2)})`);
      } else if (err.response?.status === 402) {
        toast.error('Please unlock the analysis to download the report.');
      } else {
        toast.error('Failed to download PDF report');
      }
    } finally {
      setDownloading(false);
    }
  };

  const handleExportDrive = async () => {
    setExportingDrive(true);
    toast.loading("Exporting to Google Drive...", { id: "export-drive" });
    try {
      const exportRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/integrations/google/export-drive`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({ resource_type: 'report', resource_id: jobId })
      });
      if (!exportRes.ok) {
        toast.dismiss("export-drive");
        const errData = await exportRes.json();
        return toast.error(errData.detail || 'Failed to export to Google Drive');
      }
      toast.dismiss("export-drive");
      toast.success("Successfully exported to Google Drive!");
    } catch (e) {
      toast.dismiss("export-drive");
      toast.error('Failed to export to Google Drive');
    } finally {
      setExportingDrive(false);
    }
  };

  const handlePreview = async () => {
    setShowPreview(true);
    if (!previewContent) {
      setLoadingPreview(true);
      try {
        const res = await analysisApi.getJobPreview(jobId);
        const text = res.data.text;
        if (text) {
          setPreviewContent(text);
        } else {
          setPreviewContent("Document preview is not available for this analysis.");
        }
      } catch (err) {
        toast.error("Failed to load document preview");
        setShowPreview(false);
      } finally {
        setLoadingPreview(false);
      }
    }
  };

  if (loadingBilling) {
    return (
      <div className="card p-6 flex items-center justify-center gap-3">
        <RiLoader4Line size={20} className="animate-spin text-brand" />
        <span className="text-sm text-secondary">Loading billing…</span>
      </div>
    );
  }

  if (!billing?.report_ready) {
    return null;
  }

  const paid = billing.report_paid;
  const canDownload = billing.can_download;
  const cost = billing.credits_required;
  const reportLabel = reportType ? (REPORT_LABELS[reportType] || 'Analysis') : 'Report';

  return (
    <>
      {paid ? (
        <div className="card mb-4" style={{ border: '1px solid var(--border)', background: 'var(--surface-2)' }}>

          {/* ── Header row ── */}
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b" style={{ borderColor: 'var(--border)' }}>
            <div className="flex flex-wrap items-center gap-2 min-w-0">
              <RiCheckboxCircleFill size={14} style={{ color: 'var(--success, #22c55e)' }} />
              <span className="font-semibold text-xs" style={{ color: 'var(--text)' }}>{reportLabel} Unlocked</span>
              <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', color: '#22c55e', background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.25)', borderRadius: 4, padding: '1px 5px' }}>PAID</span>
              {jobTitle && <span className="text-xs truncate max-w-[140px] sm:max-w-xs" style={{ color: 'var(--text-3)' }}>— {jobTitle}</span>}
            </div>
            <button
              onClick={handlePreview}
              className="flex items-center gap-1.5 ml-auto"
              style={{ fontSize: 11, fontWeight: 600, color: 'var(--brand)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            >
              <RiEyeFill size={12} /> Preview
            </button>
          </div>

          {/* ── Two sub-cards ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x" style={{ '--tw-divide-opacity': 1 } as any}>

            {/* Document Export */}
            <div>
              <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b" style={{ borderColor: 'var(--border)' }}>
                <div className="flex items-center gap-2">
                  <RiFileTextFill size={12} style={{ color: 'var(--brand)' }} />
                  <span className="font-semibold text-xs" style={{ color: 'var(--text)' }}>Document Export</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {/* WORD */}
                  <button onClick={handleDownloadWord} disabled={downloading} title="Download Word (.docx)"
                    className="flex flex-col items-center gap-0.5"
                    style={{ background: 'none', border: 'none', cursor: downloading ? 'not-allowed' : 'pointer', padding: 2 }}>
                    <div className="flex items-center justify-center rounded"
                      style={{ width: 28, height: 28, background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)', color: '#2563eb', opacity: downloading ? 0.5 : 1 }}>
                      {downloading ? <RiLoader4Line size={13} className="animate-spin" /> : <RiFileTextFill size={13} />}
                    </div>
                    <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-2)', letterSpacing: '0.04em' }}>WORD</span>
                  </button>
                  <div style={{ width: 1, height: 22, background: 'var(--border)' }} />
                  {/* PDF */}
                  <button onClick={handleDownloadPdf} disabled={downloading} title="Download PDF"
                    className="flex flex-col items-center gap-0.5"
                    style={{ background: 'none', border: 'none', cursor: downloading ? 'not-allowed' : 'pointer', padding: 2 }}>
                    <div className="flex items-center justify-center rounded"
                      style={{ width: 28, height: 28, background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.2)', color: '#dc2626', opacity: downloading ? 0.5 : 1 }}>
                      {downloading ? <RiLoader4Line size={13} className="animate-spin" /> : <RiDownload2Fill size={13} />}
                    </div>
                    <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-2)', letterSpacing: '0.04em' }}>PDF</span>
                  </button>
                </div>
              </div>
              <div className="px-4 py-2.5">
                <button onClick={handleExportDrive} disabled={exportingDrive}
                  className="flex items-center gap-2 w-full text-xs font-medium"
                  style={{ background: 'none', border: 'none', cursor: exportingDrive ? 'not-allowed' : 'pointer', color: 'var(--text-2)', padding: 0, opacity: exportingDrive ? 0.5 : 1 }}>
                  {exportingDrive ? <RiLoader4Line size={13} className="animate-spin" /> : <RiHardDriveFill size={13} style={{ color: 'var(--text-3)' }} />}
                  Save to Google Drive
                </button>
              </div>
            </div>

            {/* Presentation */}
            <div>
              <div className="flex items-center gap-2 px-4 py-2.5 border-b" style={{ borderColor: 'var(--border)' }}>
                <PresentationIcon size={11} style={{ color: '#ec4899' }} />
                <span className="font-semibold text-xs" style={{ color: 'var(--text)' }}>Presentation</span>
                {billing.presentation_paid && (
                  <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', color: '#22c55e', background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.25)', borderRadius: 4, padding: '1px 5px' }}>UNLOCKED</span>
                )}
              </div>
              <div className="px-4 py-2.5">
                {!billing.presentation_generated ? (
                  <button onClick={handleGeneratePresentation} disabled={generatingPresentation}
                    className="flex items-center gap-2 w-full text-xs font-medium"
                    style={{ background: 'none', border: 'none', cursor: generatingPresentation ? 'not-allowed' : 'pointer', color: 'var(--text-2)', padding: 0, opacity: generatingPresentation ? 0.5 : 1 }}>
                    {generatingPresentation ? <RiLoader4Line size={13} className="animate-spin" /> : <PresentationIcon size={13} style={{ color: '#ec4899' }} />}
                    {generatingPresentation ? 'Generating slides…' : 'Generate AI slides (.pptx)'}
                  </button>
                ) : !billing.presentation_paid ? (
                  <button onClick={handleUnlockPresentation} disabled={downloading}
                    className="btn btn-primary btn-sm w-full" style={{ fontSize: 11 }}>
                    <RiCoinsFill size={12} /> Unlock Slides ({(billing.presentation_credits_required || 0).toFixed(2)} cr)
                  </button>
                ) : (
                  <button onClick={handleDownloadPresentation} disabled={downloading}
                    className="flex items-center gap-2 w-full text-xs font-medium"
                    style={{ background: 'none', border: 'none', cursor: downloading ? 'not-allowed' : 'pointer', color: 'var(--text-2)', padding: 0, opacity: downloading ? 0.5 : 1 }}>
                    {downloading ? <RiLoader4Line size={13} className="animate-spin" /> : <RiDownload2Fill size={13} style={{ color: '#ec4899' }} />}
                    Download .pptx
                  </button>
                )}
              </div>
            </div>

          </div>
        </div>
      ) : (
        <div
          className="mb-6 rounded-2xl overflow-hidden"
          style={{
            border: '1px solid rgba(99,102,241,0.25)',
            background: 'linear-gradient(135deg, rgba(99,102,241,0.04) 0%, rgba(99,102,241,0.01) 100%)',
          }}
        >
          {/* Header strip */}
          <div style={{ background: 'rgba(99,102,241,0.07)', borderBottom: '1px solid rgba(99,102,241,0.15)', padding: '12px 20px' }}
            className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <RiBookOpenFill size={14} style={{ color: 'var(--brand)' }} />
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--brand)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {reportLabel} Ready
              </span>
            </div>
            <button onClick={handlePreview} className="flex items-center gap-1.5"
              style={{ fontSize: 12, color: 'var(--brand)', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
              <RiEyeFill size={12} /> Preview
            </button>
          </div>

          {/* Body */}
          <div className="flex flex-wrap items-center justify-between gap-4" style={{ padding: '16px 20px' }}>
            <div className="flex-1 min-w-0">
              {jobTitle && (
                <p className="text-sm font-semibold truncate" style={{ color: 'var(--text)', marginBottom: 6 }}>{jobTitle}</p>
              )}
              <div className="flex items-center gap-3 flex-wrap">
                <span style={{ fontSize: 13, color: 'var(--text-2)' }}>
                  <span style={{ color: 'var(--brand)', fontWeight: 700, fontSize: 15 }}>{cost.toFixed(2)}</span>
                  {' '}credits
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                  Balance: <strong style={{ color: canDownload ? 'var(--text-2)' : 'var(--danger)' }}>{billing.wallet_balance.toFixed(2)}</strong>
                </span>
                {!canDownload && (
                  <Link href="/settings/credits"
                    style={{ fontSize: 11, color: 'var(--brand)', fontWeight: 600, textDecoration: 'underline' }}>
                    Top up
                  </Link>
                )}
              </div>
            </div>

            <button
              type="button"
              className="btn btn-primary btn-sm flex-shrink-0"
              onClick={() => {
                if (!canDownload) {
                  setConfirmModal({
                    title: 'Insufficient Credits',
                    message: (
                      <>
                        Need <strong>{cost.toFixed(2)}</strong> credits but your balance is <strong>{billing.wallet_balance.toFixed(2)}</strong>.<br/><br/>
                        Go to the credits page to top up?
                      </>
                    ),
                    confirmText: 'Go to Credits',
                    cancelText: 'Cancel',
                    isError: true,
                    onConfirm: () => {
                      window.location.href = '/settings/credits';
                    }
                  });
                } else {
                  setConfirmModal({
                    title: 'Unlock Analysis',
                    message: `Deduct ${cost.toFixed(2)} credits to unlock this analysis?`,
                    confirmText: 'Unlock',
                    cancelText: 'Cancel',
                    onConfirm: () => {
                      setConfirmModal(null);
                      handleUnlock();
                    }
                  });
                }
              }}
              disabled={downloading}
            >
              {downloading ? <RiLoader4Line size={14} className="animate-spin" /> : null}
              {downloading ? 'Unlocking…' : 'Unlock Analysis'}
            </button>
          </div>
        </div>
      )}

      {showPreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm lg:pl-[260px]">
          <div className="bg-surface rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
            <div className="p-4 border-b border-border flex items-center justify-between bg-background">
              <h3 className="font-semibold flex items-center gap-2 m-0">
                <RiEyeFill size={18} className="text-brand" /> Document Preview
              </h3>
              <button 
                className="btn btn-ghost p-1 h-auto min-h-0"
                onClick={() => setShowPreview(false)}
              >
                <RiCloseFill size={20} />
              </button>
            </div>
            <div 
              className="p-6 overflow-y-auto flex-1 select-none"
              onCopy={(e) => {
                e.preventDefault();
                toast.error("Copying is disabled until the report is unlocked.");
              }}
              onContextMenu={(e) => {
                e.preventDefault();
              }}
            >
              {!paid && (
                <div className="mb-4 p-3 bg-brand/10 border border-brand/20 rounded-lg text-sm text-brand flex items-start gap-2">
                  <RiErrorWarningFill size={16} className="mt-0.5 shrink-0" />
                  <p className="m-0">You are viewing a protected preview. Copying and downloading are disabled until the report is unlocked.</p>
                </div>
              )}
              
              {loadingPreview ? (
                <div className="py-20 flex flex-col items-center justify-center gap-4">
                  <RiLoader4Line size={32} className="animate-spin text-brand" />
                  <p className="text-secondary">Loading document text...</p>
                </div>
              ) : (
                <div className="prose prose-sm max-w-none text-primary whitespace-pre-wrap">
                  {previewContent}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Custom Confirmation Modal */}
      {confirmModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm lg:pl-[260px] animate-fade-in">
          <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden animate-slide-up" style={{ border: '1px solid var(--border)' }}>
            <div className="p-5 flex flex-col items-center text-center">
              <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4" style={{ background: confirmModal.isError ? 'rgba(239,68,68,0.1)' : 'rgba(99,102,241,0.1)', color: confirmModal.isError ? '#ef4444' : 'var(--brand)' }}>
                {confirmModal.isError ? <RiErrorWarningFill size={24} /> : <RiCoinsFill size={24} />}
              </div>
              <h3 className="font-bold text-lg mb-2" style={{ color: 'var(--text)', fontFamily: "'Syne', sans-serif" }}>
                {confirmModal.title}
              </h3>
              <p className="text-sm mb-6" style={{ color: 'var(--text-2)', lineHeight: 1.5 }}>
                {confirmModal.message}
              </p>
              <div className="flex gap-3 w-full">
                <button 
                  className="btn btn-secondary flex-1 py-2.5 rounded-xl font-semibold text-sm"
                  onClick={() => setConfirmModal(null)}
                >
                  {confirmModal.cancelText}
                </button>
                <button 
                  className="btn flex-1 py-2.5 rounded-xl font-semibold text-sm"
                  style={{ 
                    background: confirmModal.isError ? '#ef4444' : 'var(--brand)', 
                    color: confirmModal.isError ? '#fff' : 'var(--brand-text)',
                    border: 'none', 
                    boxShadow: confirmModal.isError ? '0 4px 12px rgba(239,68,68,0.2)' : '0 4px 12px rgba(99,102,241,0.2)' 
                  }}
                  onClick={confirmModal.onConfirm}
                >
                  {confirmModal.confirmText}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

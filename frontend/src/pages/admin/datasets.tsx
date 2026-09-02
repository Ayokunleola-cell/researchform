import React, { useEffect, useState, useMemo } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { adminApi, downloadBlob } from '../../lib/api';
import { marketplaceDownloadUrl } from '../../lib/marketplaceAnalysis';
import toast from 'react-hot-toast';
import { RiPriceTag3Fill, RiExternalLinkFill, RiCloseCircleFill, RiCalendarEventFill, RiErrorWarningFill, RiFileTextFill, RiCloseFill, RiFilter3Fill, RiTimeFill, RiCheckboxCircleFill, RiLoader4Line, RiDatabase2Fill, RiSearchEyeFill, RiUserFill, RiDownload2Fill } from 'react-icons/ri';

const STATUS_OPTS = ['pending', 'verified', 'rejected'];

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: 'bg-amber-100 text-amber-700 border-amber-200',
    verified: 'bg-green-100 text-green-700 border-green-200',
    rejected: 'bg-red-100 text-red-700 border-red-200',
  };
  const icons: Record<string, React.ReactNode> = {
    pending: <RiTimeFill size={10} />,
    verified: <RiCheckboxCircleFill size={10} />,
    rejected: <RiCloseCircleFill size={10} />,
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${map[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {icons[status]} {status}
    </span>
  );
}

import AdminGuard from '../../components/admin/AdminGuard';

export default function AdminDatasetsPage() {
  return (
    <AdminGuard>
      <AdminDatasetsPageContent />
    </AdminGuard>
  );
}

function AdminDatasetsPageContent() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewingDataset, setReviewingDataset] = useState<any>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [search, setSearch] = useState('');
  const [domainFilter, setDomainFilter] = useState('all');
  const [view, setView] = useState<'cards' | 'table'>('cards');

  const loadData = async () => {
    try {
      const res = await adminApi.pendingDatasets();
      setDatasets(res.data);
    } catch (err: any) {
      toast.error(err.response?.status === 403 ? "You don't have admin privileges" : 'Failed to load pending datasets');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const domains = useMemo(() => ['all', ...Array.from(new Set(datasets.map((d: any) => d.domain).filter(Boolean)))], [datasets]);

  const filtered = useMemo(() => datasets.filter(d => {
    const matchSearch = search === '' ||
      d.title?.toLowerCase().includes(search.toLowerCase()) ||
      d.seller_name?.toLowerCase().includes(search.toLowerCase()) ||
      d.seller_email?.toLowerCase().includes(search.toLowerCase());
    const matchDomain = domainFilter === 'all' || d.domain === domainFilter;
    return matchSearch && matchDomain;
  }), [datasets, search, domainFilter]);

  const handleReview = async (status: 'verified' | 'rejected') => {
    if (!reviewingDataset) return;
    if (status === 'rejected' && !rejectionReason.trim()) {
      toast.error('Please provide a reason for rejection.');
      return;
    }
    setIsSubmitting(true);
    try {
      await adminApi.reviewDataset(reviewingDataset.id, status, status === 'rejected' ? rejectionReason : undefined);
      toast.success(`Dataset ${status === 'verified' ? 'approved ✓' : 'rejected'} successfully.`);
      setReviewingDataset(null);
      setRejectionReason('');
      await loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to review dataset');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppLayout title="Review Datasets" breadcrumbs={[{ label: 'Admin', href: '/admin/users' }, { label: 'Datasets' }]}>
      <div style={{ padding: '24px', maxWidth: 1300, margin: '0 auto' }}>

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold" style={{ fontFamily: 'Syne, sans-serif', color: 'var(--text)', margin: 0 }}>
              Pending Datasets
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
              Review and approve or reject marketplace dataset submissions
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-3 py-1.5 rounded-full text-sm font-bold" style={{
              background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)'
            }}>
              <RiTimeFill size={13} className="inline mr-1 -mt-0.5" />
              {filtered.length} pending review
            </span>
          </div>
        </div>

        {/* Filters */}
        <div className="card p-4 mb-5 flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[200px]">
            <RiSearchEyeFill size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-3)' }} />
            <input type="text" className="input w-full pl-9" placeholder="Search by title or seller…"
              value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            <RiFilter3Fill size={15} style={{ color: 'var(--text-3)' }} />
            <select className="input" value={domainFilter} onChange={e => setDomainFilter(e.target.value)}>
              {domains.map(d => <option key={d} value={d}>{d === 'all' ? 'All Domains' : d}</option>)}
            </select>
          </div>
          <p className="text-xs ml-auto" style={{ color: 'var(--text-3)' }}>{filtered.length} of {datasets.length} datasets</p>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex justify-center p-20"><RiLoader4Line className="animate-spin text-brand" size={32} /></div>
        ) : filtered.length === 0 ? (
          <div className="card p-16 text-center">
            <RiDatabase2Fill size={40} className="mx-auto mb-4" style={{ color: 'var(--text-3)' }} />
            <p className="font-semibold mb-1" style={{ color: 'var(--text)' }}>No datasets to review</p>
            <p className="text-sm" style={{ color: 'var(--text-3)' }}>All submissions have been processed or no datasets match your filters.</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {filtered.map(dataset => (
              <div key={dataset.id} className="card p-5 hover:shadow-lg transition-all group"
                style={{ borderLeft: '4px solid var(--brand)' }}>
                <div className="flex flex-col md:flex-row justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start gap-3 flex-wrap mb-2">
                      <h3 className="font-bold text-lg leading-tight" style={{ color: 'var(--text)', margin: 0 }}>
                        {dataset.title}
                      </h3>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold flex items-center gap-1"
                        style={{ background: 'rgba(99,102,241,0.1)', color: '#6366f1', border: '1px solid rgba(99,102,241,0.2)', whiteSpace: 'nowrap' }}>
                        <RiPriceTag3Fill size={10} /> {dataset.domain}
                      </span>
                    </div>

                    {dataset.description && (
                      <p className="text-sm mb-3 line-clamp-2" style={{ color: 'var(--text-2)' }}>
                        {dataset.description}
                      </p>
                    )}

                    <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs" style={{ color: 'var(--text-3)' }}>
                      <span className="flex items-center gap-1">
                        <RiUserFill size={12} />
                        <strong style={{ color: 'var(--text-2)' }}>{dataset.seller_name}</strong>
                        <span>({dataset.seller_email})</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <RiCalendarEventFill size={12} />
                        {new Date(dataset.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </span>
                      {dataset.price_naira !== undefined && dataset.price_naira !== null && (
                        <span className="font-semibold" style={{ color: '#10b981' }}>
                          ₦{Number(dataset.price_naira).toLocaleString()}
                        </span>
                      )}
                      {dataset.proof_document_path && (
                        <a href={dataset.proof_document_path} target="_blank" rel="noreferrer"
                          className="flex items-center gap-1 hover:underline" style={{ color: 'var(--brand)' }}>
                          <RiFileTextFill size={12} /> View ID Document <RiExternalLinkFill size={11} />
                        </a>
                      )}
                    </div>
                  </div>

                  <div className="flex md:flex-col gap-2 min-w-[150px] items-center md:items-stretch">
                    <button
                      className="btn flex-1 flex items-center justify-center gap-2 text-sm font-semibold"
                      style={{ background: '#10b981', color: 'white', border: 'none' }}
                      onClick={() => { setReviewingDataset(dataset); setRejectionReason(''); }}
                    >
                      <RiCheckboxCircleFill size={16} /> Review
                    </button>
                    <button
                      className="btn flex-1 flex items-center justify-center gap-2 text-sm font-semibold"
                      style={{ background: 'var(--surface-2)', color: 'var(--text-2)', border: '1px solid var(--border)' }}
                      onClick={() => { setReviewingDataset(dataset); setRejectionReason(''); }}
                    >
                      <RiCloseCircleFill size={16} /> Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Review Modal */}
        {reviewingDataset && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
            <div className="card p-0 max-w-2xl w-full shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
              {/* Modal header */}
              <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-2)' }}>
                <div>
                  <h3 className="text-lg font-bold" style={{ color: 'var(--text)', margin: 0, fontFamily: 'Syne,sans-serif' }}>
                    Dataset Review
                  </h3>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)', margin: 0 }}>
                    Make a decision for this submission
                  </p>
                </div>
                <button type="button" onClick={() => { setReviewingDataset(null); setRejectionReason(''); }} className="btn btn-ghost btn-icon">
                  <RiCloseFill size={16} />
                </button>
              </div>

              {/* Modal body */}
              <div className="p-6 overflow-y-auto flex-1 space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Title</p>
                    <p className="font-medium" style={{ color: 'var(--text)' }}>{reviewingDataset.title}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Domain</p>
                    <p className="font-medium" style={{ color: 'var(--text)' }}>{reviewingDataset.domain}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Seller</p>
                    <p className="font-medium" style={{ color: 'var(--text)' }}>{reviewingDataset.seller_name}</p>
                    <p className="text-xs" style={{ color: 'var(--text-3)' }}>{reviewingDataset.seller_email}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Submitted</p>
                    <p className="font-medium" style={{ color: 'var(--text)' }}>{new Date(reviewingDataset.created_at).toLocaleString()}</p>
                  </div>
                </div>

                {reviewingDataset.description && (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Description</p>
                    <p className="text-sm leading-relaxed p-3 rounded-lg" style={{ color: 'var(--text-2)', background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                      {reviewingDataset.description}
                    </p>
                  </div>
                )}

                {reviewingDataset.proof_document_path && (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Identity / Proof Document</p>
                    <a href={reviewingDataset.proof_document_path} target="_blank" rel="noreferrer"
                      className="flex items-center gap-2 text-sm hover:underline" style={{ color: 'var(--brand)' }}>
                      <RiFileTextFill size={16} /> View Document <RiExternalLinkFill size={14} />
                    </a>
                  </div>
                )}

                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Dataset File</p>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const res = await adminApi.downloadDataset(reviewingDataset.id);
                        if (res.data.download_url) {
                          window.open(res.data.download_url, '_blank');
                        } else if (res.data.download_token) {
                          window.open(marketplaceDownloadUrl(res.data.download_token), '_blank');
                        }
                      } catch (err: any) {
                        toast.error('Failed to download dataset');
                      }
                    }}
                    className="flex items-center gap-2 text-sm hover:underline" style={{ color: 'var(--brand)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}>
                    <RiDownload2Fill size={16} /> Download Dataset File
                  </button>
                </div>

                <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
                  <label className="block text-sm font-semibold mb-1" style={{ color: 'var(--text)' }}>
                    Rejection Reason <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>(required only for rejection)</span>
                  </label>
                  <textarea
                    className="input w-full"
                    style={{ minHeight: 80 }}
                    placeholder="Explain why this dataset is being rejected…"
                    value={rejectionReason}
                    onChange={e => setRejectionReason(e.target.value)}
                  />
                </div>
              </div>

              {/* Modal footer */}
              <div className="p-5 flex justify-end gap-3" style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}>
                <button type="button" className="btn btn-ghost" onClick={() => { setReviewingDataset(null); setRejectionReason(''); }}>
                  Cancel
                </button>
                <button type="button" disabled={isSubmitting}
                  className="btn flex items-center gap-2 text-sm font-semibold"
                  style={{ background: '#ef4444', color: 'white', border: 'none' }}
                  onClick={() => handleReview('rejected')}>
                  {isSubmitting ? <RiLoader4Line size={16} className="animate-spin" /> : <RiCloseCircleFill size={16} />}
                  Reject Dataset
                </button>
                <button type="button" disabled={isSubmitting}
                  className="btn btn-primary flex items-center gap-2 text-sm font-semibold"
                  onClick={() => handleReview('verified')}>
                  {isSubmitting ? <RiLoader4Line size={16} className="animate-spin" /> : <RiCheckboxCircleFill size={16} />}
                  Approve Dataset
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

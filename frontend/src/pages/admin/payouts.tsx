import React, { useEffect, useState, useMemo } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { adminApi } from '../../lib/api';
import { RiCloseCircleFill, RiCloseFill, RiSearchEyeFill, RiBankFill, RiFileTextFill, RiShieldCheckFill, RiTimeFill, RiLoader4Line, RiBuilding4Fill, RiEyeFill, RiBankCardFill, RiFilter3Fill, RiCheckboxCircleFill, RiCheckLine, RiUserFill, RiExternalLinkFill, RiErrorWarningFill, RiRefreshLine, RiCalendarEventFill } from 'react-icons/ri';
import toast from 'react-hot-toast';
import { useCurrencyStore } from '../../lib/store';

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string; border: string; label: string }> = {
    in_process: { bg: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: 'rgba(245,158,11,0.3)', label: 'Pending Review' },
    approved:   { bg: 'rgba(16,185,129,0.15)', color: '#10b981', border: 'rgba(16,185,129,0.3)', label: 'Approved' },
    denied:     { bg: 'rgba(239,68,68,0.12)',  color: '#ef4444', border: 'rgba(239,68,68,0.3)',  label: 'Denied' },
    pending:    { bg: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: 'rgba(245,158,11,0.3)', label: 'Pending' },
    paid:       { bg: 'rgba(16,185,129,0.15)', color: '#10b981', border: 'rgba(16,185,129,0.3)', label: 'Paid' },
    rejected:   { bg: 'rgba(239,68,68,0.12)',  color: '#ef4444', border: 'rgba(239,68,68,0.3)',  label: 'Rejected' },
  };
  const s = map[status] ?? { bg: 'rgba(100,100,100,0.12)', color: 'var(--text-2)', border: 'var(--border)', label: status };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 10px', borderRadius: 999,
      fontSize: 12, fontWeight: 600,
      background: s.bg, color: s.color,
      border: `1px solid ${s.border}`,
    }}>
      {s.label}
    </span>
  );
}

function ReasonModal({ onConfirm, onCancel, title, placeholder }: any) {
  const [reason, setReason] = useState('');
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-[60] backdrop-blur-sm">
      <div className="card p-6 max-w-md w-full shadow-2xl">
        <h3 className="text-lg font-bold mb-3" style={{ fontFamily: 'Syne,sans-serif', color: 'var(--text)' }}>{title}</h3>
        <textarea className="input w-full mb-4" style={{ minHeight: 90 }} placeholder={placeholder}
          value={reason} onChange={e => setReason(e.target.value)} autoFocus />
        <div className="flex justify-end gap-2">
          <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={() => onConfirm(reason)} disabled={!reason.trim()}>Confirm</button>
        </div>
      </div>
    </div>
  );
}

function ConfirmModal({ message, onConfirm, onCancel }: any) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-[60] backdrop-blur-sm">
      <div className="card p-6 max-w-sm w-full shadow-2xl">
        <h3 className="text-lg font-bold mb-3" style={{ fontFamily: 'Syne,sans-serif', color: 'var(--text)' }}>Confirm Action</h3>
        <p className="text-sm mb-5" style={{ color: 'var(--text-2)' }}>{message}</p>
        <div className="flex justify-end gap-2">
          <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={onConfirm}>Confirm</button>
        </div>
      </div>
    </div>
  );
}

import AdminGuard from '../../components/admin/AdminGuard';

export default function AdminPayoutsPage() {
  return (
    <AdminGuard>
      <AdminPayoutsPageContent />
    </AdminGuard>
  );
}

function AdminPayoutsPageContent() {
  const { formatPrice } = useCurrencyStore();
  const [kycRequests, setKycRequests] = useState<any[]>([]);
  const [withdrawals, setWithdrawals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'kyc' | 'withdrawals'>('kyc');

  const [kycSearch, setKycSearch] = useState('');
  const [kycStatusFilter, setKycStatusFilter] = useState('all');
  const [wSearch, setWSearch] = useState('');
  const [wStatusFilter, setWStatusFilter] = useState('all');

  const [reasonModal, setReasonModal] = useState<any>(null);
  const [confirmModal, setConfirmModal] = useState<any>(null);
  const [viewingKyc, setViewingKyc] = useState<any>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [kRes, wRes] = await Promise.all([adminApi.kycRequests(), adminApi.withdrawals()]);
      setKycRequests(kRes.data);
      setWithdrawals(wRes.data);
    } catch {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const filteredKyc = useMemo(() => kycRequests.filter(r => {
    const matchSearch = kycSearch === '' ||
      r.user_name?.toLowerCase().includes(kycSearch.toLowerCase()) ||
      r.user_email?.toLowerCase().includes(kycSearch.toLowerCase());
    const matchStatus = kycStatusFilter === 'all' || r.status === kycStatusFilter;
    return matchSearch && matchStatus;
  }), [kycRequests, kycSearch, kycStatusFilter]);

  const filteredWithdrawals = useMemo(() => withdrawals.filter(r => {
    const matchSearch = wSearch === '' ||
      r.user_name?.toLowerCase().includes(wSearch.toLowerCase()) ||
      r.user_email?.toLowerCase().includes(wSearch.toLowerCase());
    const matchStatus = wStatusFilter === 'all' || r.status === wStatusFilter;
    return matchSearch && matchStatus;
  }), [withdrawals, wSearch, wStatusFilter]);

  const pendingKyc = kycRequests.filter(r => r.status === 'in_process').length;
  const pendingW = withdrawals.filter(r => r.status === 'pending').length;

  const handleKycReview = async (id: string, status: 'approved' | 'denied') => {
    if (status === 'denied') {
      setReasonModal({
        title: 'Reason for Denial',
        placeholder: 'Explain why this KYC is being denied…',
        onConfirm: async (reason: string) => {
          setReasonModal(null);
          try {
            await adminApi.reviewKyc(id, status, reason);
            toast.success('KYC denied and user notified');
            loadData();
          } catch (err: any) { toast.error(err.response?.data?.detail || 'Failed'); }
        },
        onCancel: () => setReasonModal(null),
      });
    } else {
      setConfirmModal({
        message: 'Approve this KYC verification? The user will be notified and can now access seller features.',
        onConfirm: async () => {
          setConfirmModal(null);
          try {
            await adminApi.reviewKyc(id, status);
            toast.success('KYC approved ✓');
            loadData();
          } catch (err: any) { toast.error(err.response?.data?.detail || 'Failed'); }
        },
        onCancel: () => setConfirmModal(null),
      });
    }
  };

  const handleWithdrawalReview = async (id: string, status: 'paid' | 'rejected') => {
    if (status === 'rejected') {
      setReasonModal({
        title: 'Reason for Rejection',
        placeholder: 'Explain why this withdrawal is being rejected. Funds will be returned to the seller wallet.',
        onConfirm: async (reason: string) => {
          setReasonModal(null);
          try {
            await adminApi.reviewWithdrawal(id, status, reason);
            toast.success('Withdrawal rejected and funds refunded');
            loadData();
          } catch (err: any) { toast.error(err.response?.data?.detail || 'Failed'); }
        },
        onCancel: () => setReasonModal(null),
      });
    } else {
      setConfirmModal({
        message: 'Confirm that you have manually transferred the funds to the user\'s bank account. This action cannot be undone.',
        onConfirm: async () => {
          setConfirmModal(null);
          try {
            await adminApi.reviewWithdrawal(id, status);
            toast.success('Withdrawal marked as Paid ✓');
            loadData();
          } catch (err: any) { toast.error(err.response?.data?.detail || 'Failed'); }
        },
        onCancel: () => setConfirmModal(null),
      });
    }
  };

  const tabs = [
    { id: 'kyc', label: 'KYC Verification', icon: RiShieldCheckFill, badge: pendingKyc },
    { id: 'withdrawals', label: 'Withdrawals', icon: RiBankFill, badge: pendingW },
  ];

  return (
    <AppLayout title="Payouts & KYC" breadcrumbs={[{ label: 'Admin' }, { label: 'Payouts & KYC' }]}>
      <div style={{ padding: '24px', maxWidth: 1300, margin: '0 auto' }}>

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold" style={{ fontFamily: 'Syne, sans-serif', color: 'var(--text)', margin: 0 }}>
              Payouts & KYC
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
              Verify seller identities and process withdrawal requests
            </p>
          </div>
          <button onClick={loadData} className="btn btn-ghost flex items-center gap-2 text-sm">
            <RiRefreshLine size={15} /> Refresh
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Pending KYC', value: pendingKyc, color: '#f59e0b', icon: RiShieldCheckFill},
            { label: 'Approved KYC', value: kycRequests.filter(r => r.status === 'approved').length, color: '#10b981', icon: RiCheckboxCircleFill},
            { label: 'Pending Payouts', value: pendingW, color: '#6366f1', icon: RiBankFill},
            { label: 'Total Paid Out', value: withdrawals.filter(r => r.status === 'paid').length, color: '#10b981', icon: RiBankCardFill},
          ].map(({ label, value, color, icon: Icon }) => (
            <div key={label} className="card p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: `${color}18` }}>
                <Icon size={18} style={{ color }} />
              </div>
              <div>
                <p className="text-xl font-bold" style={{ color: 'var(--text)', margin: 0 }}>{value}</p>
                <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>{label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-1.5 mb-6 p-1.5 rounded-2xl w-fit shadow-sm" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
          {tabs.map(tab => {
            const isActive = activeTab === tab.id;
            return (
              <button key={tab.id} onClick={() => setActiveTab(tab.id as any)}
                className="flex items-center gap-2.5 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all cursor-pointer"
                style={{
                  background: isActive ? 'var(--brand)' : 'transparent',
                  color: isActive ? 'var(--brand-text)' : 'var(--text-2)',
                  border: 'none',
                  boxShadow: isActive ? '0 2px 8px rgba(0,0,0,0.15)' : 'none',
                }}>
                <tab.icon size={16} style={{ color: isActive ? 'var(--brand-text)' : 'var(--text-3)' }} />
                <span>{tab.label}</span>
                {tab.badge > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-bold transition-all"
                    style={{
                      background: isActive ? 'rgba(128, 128, 128, 0.25)' : 'rgba(245,158,11,0.18)',
                      color: isActive ? 'var(--brand-text)' : '#f59e0b',
                      border: isActive ? 'none' : '1px solid rgba(245,158,11,0.3)',
                    }}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {loading ? (
          <div className="flex justify-center p-20"><RiLoader4Line className="animate-spin text-brand" size={32} /></div>
        ) : activeTab === 'kyc' ? (
          <div>
            {/* KYC Filters */}
            <div className="card p-3 mb-4 flex flex-wrap gap-3 items-center">
              <div className="relative flex-1 min-w-[200px]">
                <RiSearchEyeFill size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-3)' }} />
                <input type="text" className="input w-full pl-9 py-2" placeholder="Search by name or email…"
                  value={kycSearch} onChange={e => setKycSearch(e.target.value)} />
              </div>
              <select className="input py-2" value={kycStatusFilter} onChange={e => setKycStatusFilter(e.target.value)}>
                <option value="all">All Status</option>
                <option value="in_process">Pending Review</option>
                <option value="approved">Approved</option>
                <option value="denied">Denied</option>
              </select>
              <p className="text-xs ml-auto" style={{ color: 'var(--text-3)' }}>{filteredKyc.length} requests</p>
            </div>

            {filteredKyc.length === 0 ? (
              <div className="card p-12 text-center">
                <RiShieldCheckFill size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
                <p style={{ color: 'var(--text-2)', fontWeight: 600 }}>No KYC requests found</p>
              </div>
            ) : (
              <div className="space-y-4">
                {filteredKyc.map(req => (
                  <div key={req.id} className="card p-0 overflow-hidden">
                    {/* Card top bar */}
                    <div className="flex items-center justify-between px-5 py-3"
                      style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                          style={{ background: `hsl(${(req.user_name?.charCodeAt(0) ?? 65) * 5 % 360}, 55%, 50%)` }}>
                          {req.user_name?.charAt(0)}
                        </div>
                        <div>
                          <p className="font-semibold text-sm" style={{ color: 'var(--text)', margin: 0 }}>{req.user_name}</p>
                          <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>{req.user_email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusBadge status={req.status} />
                        {req.verified_at && (
                          <span className="text-xs" style={{ color: 'var(--text-3)' }}>
                            {new Date(req.verified_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Card body */}
                    <div className="p-5 grid md:grid-cols-3 gap-5">
                      <div className="md:col-span-2 grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>ID Document</p>
                          <p className="font-medium" style={{ color: 'var(--text)' }}>{req.id_document_type ?? 'N/A'}</p>
                          {req.id_document_path && (
                            <a href={req.id_document_path} target="_blank" rel="noreferrer"
                              className="flex items-center gap-1 text-xs hover:underline mt-1" style={{ color: 'var(--brand)' }}>
                              <RiEyeFill size={11} /> View Document <RiExternalLinkFill size={10} />
                            </a>
                          )}
                        </div>
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Bank</p>
                          <p className="font-medium" style={{ color: 'var(--text)' }}>{req.bank_name ?? '—'}</p>
                        </div>
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Account Number</p>
                          <p className="font-medium font-mono" style={{ color: 'var(--text)' }}>{req.account_number ?? '—'}</p>
                        </div>
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Account Name</p>
                          <p className="font-medium" style={{ color: 'var(--text)' }}>{req.account_name ?? '—'}</p>
                        </div>
                        {req.rejection_reason && (
                          <div className="col-span-2">
                            <div className="p-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.2)', color: '#dc2626' }}>
                              <strong>Denial Reason:</strong> {req.rejection_reason}
                            </div>
                          </div>
                        )}
                      </div>

                      {req.status === 'in_process' && (
                        <div className="flex flex-col gap-2 justify-center">
                          <button onClick={() => handleKycReview(req.id, 'approved')}
                            className="btn flex items-center justify-center gap-2 font-semibold"
                            style={{ background: '#10b981', color: 'white', border: 'none' }}>
                            <RiCheckLine size={16} /> Approve KYC
                          </button>
                          <button onClick={() => handleKycReview(req.id, 'denied')}
                            className="btn flex items-center justify-center gap-2 font-semibold"
                            style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.3)' }}>
                            <RiCloseFill size={16} /> Deny KYC
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div>
            {/* Withdrawal Filters */}
            <div className="card p-3 mb-4 flex flex-wrap gap-3 items-center">
              <div className="relative flex-1 min-w-[200px]">
                <RiSearchEyeFill size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-3)' }} />
                <input type="text" className="input w-full pl-9 py-2" placeholder="Search by name or email…"
                  value={wSearch} onChange={e => setWSearch(e.target.value)} />
              </div>
              <select className="input py-2" value={wStatusFilter} onChange={e => setWStatusFilter(e.target.value)}>
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="paid">Paid</option>
                <option value="rejected">Rejected</option>
              </select>
              <p className="text-xs ml-auto" style={{ color: 'var(--text-3)' }}>{filteredWithdrawals.length} requests</p>
            </div>

            {filteredWithdrawals.length === 0 ? (
              <div className="card p-12 text-center">
                <RiBankFill size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
                <p style={{ color: 'var(--text-2)', fontWeight: 600 }}>No withdrawal requests found</p>
              </div>
            ) : (
              <div className="space-y-4">
                {filteredWithdrawals.map(req => (
                  <div key={req.id} className="card p-0 overflow-hidden"
                    style={{ borderLeft: `4px solid ${req.status === 'pending' ? '#f59e0b' : req.status === 'paid' ? '#10b981' : '#ef4444'}` }}>
                    <div className="flex items-center justify-between px-5 py-3"
                      style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-3">
                        <p className="text-2xl font-black" style={{ color: 'var(--text)', fontFamily: 'Syne,sans-serif', margin: 0 }}>
                          ₦{Number(req.amount).toLocaleString()}
                        </p>
                        <StatusBadge status={req.status} />
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold" style={{ color: 'var(--text)', margin: 0 }}>{req.user_name}</p>
                        <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>{req.user_email}</p>
                      </div>
                    </div>

                    <div className="p-5 grid md:grid-cols-3 gap-5">
                      <div className="md:col-span-2">
                        <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-3)' }}>
                          Bank Transfer Details
                        </p>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <p className="text-xs" style={{ color: 'var(--text-3)', marginBottom: 2 }}>Bank</p>
                            <p className="font-medium flex items-center gap-1" style={{ color: 'var(--text)' }}>
                              <RiBuilding4Fill size={13} /> {req.bank_name ?? '—'}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs" style={{ color: 'var(--text-3)', marginBottom: 2 }}>Account Name</p>
                            <p className="font-medium" style={{ color: 'var(--text)' }}>{req.account_name ?? '—'}</p>
                          </div>
                          <div>
                            <p className="text-xs" style={{ color: 'var(--text-3)', marginBottom: 2 }}>Account Number</p>
                            <p className="font-medium font-mono" style={{ color: 'var(--text)' }}>{req.account_number ?? '—'}</p>
                          </div>
                          <div>
                            <p className="text-xs" style={{ color: 'var(--text-3)', marginBottom: 2 }}>Requested</p>
                            <p className="font-medium" style={{ color: 'var(--text)' }}>
                              {req.created_at ? new Date(req.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                            </p>
                          </div>
                        </div>

                        {req.rejection_reason && (
                          <div className="mt-3 p-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.2)', color: '#dc2626' }}>
                            <strong>Rejection Reason:</strong> {req.rejection_reason}
                          </div>
                        )}
                      </div>

                      {req.status === 'pending' && (
                        <div className="flex flex-col gap-2 justify-center">
                          <button onClick={() => handleWithdrawalReview(req.id, 'paid')}
                            className="btn flex items-center justify-center gap-2 font-semibold"
                            style={{ background: '#10b981', color: 'white', border: 'none' }}>
                            <RiCheckLine size={16} /> Mark as Paid
                          </button>
                          <button onClick={() => handleWithdrawalReview(req.id, 'rejected')}
                            className="btn flex items-center justify-center gap-2 font-semibold"
                            style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.3)' }}>
                            <RiCloseFill size={16} /> Reject & Refund
                          </button>
                          <p className="text-xs text-center" style={{ color: 'var(--text-3)' }}>
                            Transfer funds before clicking "Mark as Paid"
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Reason Modal */}
      {reasonModal && <ReasonModal {...reasonModal} />}
      {/* Confirm Modal */}
      {confirmModal && <ConfirmModal {...confirmModal} />}
    </AppLayout>
  );
}

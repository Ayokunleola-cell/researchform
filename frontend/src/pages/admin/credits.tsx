import React, { useState, useMemo } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { adminApi } from '../../lib/api';
import toast from 'react-hot-toast';
import useSWR from 'swr';
import { RiGroupFill, RiCoinsFill, RiArrowRightUpLine, RiBankCardFill, RiDownload2Fill, RiCloseFill, RiFilter3Fill, RiStarFill, RiRefreshLine, RiLoader4Line, RiSearchEyeFill, RiLineChartFill } from 'react-icons/ri';
import AdminGuard from '../../components/admin/AdminGuard';

export default function AdminCreditsPage() {
  return (
    <AdminGuard>
      <AdminCreditsPageContent />
    </AdminGuard>
  );
}

function AdminCreditsPageContent() {
  const { data: walletsData, error: walletsError, mutate: mutateWallets, isLoading } = useSWR('/admin/credits/wallets', { refreshInterval: 30000 });
  const wallets: any[] = walletsData || [];
  const loading = isLoading;

  if (walletsError && walletsError.response?.status === 403) {
    toast.error("You don't have admin privileges", { id: 'admin-403' });
  }

  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'balance_desc' | 'balance_asc' | 'updated'>('balance_desc');
  const [balanceFilter, setBalanceFilter] = useState<'all' | 'zero' | 'low' | 'high'>('all');

  const [grantModal, setGrantModal] = useState<any>(null);
  const [grantAmount, setGrantAmount] = useState<number | ''>('');
  const [grantDesc, setGrantDesc] = useState('');
  const [isGranting, setIsGranting] = useState(false);

  const stats = useMemo(() => {
    const total = wallets.reduce((sum, w) => sum + (w.balance ?? 0), 0);
    const nonZero = wallets.filter(w => (w.balance ?? 0) > 0).length;
    return {
      totalCredits: total,
      nonZeroWallets: nonZero,
      avgBalance: wallets.length > 0 ? total / wallets.length : 0,
      maxBalance: wallets.length > 0 ? Math.max(...wallets.map(w => w.balance ?? 0)) : 0,
    };
  }, [wallets]);

  const filteredWallets = useMemo(() => {
    let result = wallets.filter(w => {
      const matchSearch = search === '' ||
        w.full_name?.toLowerCase().includes(search.toLowerCase()) ||
        w.email?.toLowerCase().includes(search.toLowerCase());
      const bal = w.balance ?? 0;
      const matchBalance =
        balanceFilter === 'all' ||
        (balanceFilter === 'zero' && bal === 0) ||
        (balanceFilter === 'low' && bal > 0 && bal < 10) ||
        (balanceFilter === 'high' && bal >= 10);
      return matchSearch && matchBalance;
    });
    if (sortBy === 'balance_desc') result = result.sort((a, b) => (b.balance ?? 0) - (a.balance ?? 0));
    else if (sortBy === 'balance_asc') result = result.sort((a, b) => (a.balance ?? 0) - (b.balance ?? 0));
    else result = result.sort((a, b) => new Date(b.updated_at ?? 0).getTime() - new Date(a.updated_at ?? 0).getTime());
    return result;
  }, [wallets, search, sortBy, balanceFilter]);

  const handleGrant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!grantModal || !grantAmount || !grantDesc) return;
    setIsGranting(true);
    try {
      const res = await adminApi.grantCredits(grantModal.user_id, Number(grantAmount), grantDesc);
      toast.success(`Credits updated. New balance: ${res.data.balance}`);
      setGrantModal(null);
      setGrantAmount('');
      setGrantDesc('');
      await mutateWallets();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update credits');
    } finally {
      setIsGranting(false);
    }
  };

  const exportCSV = () => {
    const rows = [
      ['Name', 'Email', 'Balance', 'Last Updated'],
      ...wallets.map(w => [w.full_name, w.email, w.balance?.toFixed(2), w.updated_at]),
    ];
    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'credit_wallets.csv'; a.click();
  };

  return (
    <AppLayout title="Credit Wallets" breadcrumbs={[{ label: 'Admin', href: '/admin/users' }, { label: 'Credits' }]}>
      <div style={{ padding: '24px', maxWidth: 1300, margin: '0 auto' }}>

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold" style={{ fontFamily: 'Syne, sans-serif', color: 'var(--text)', margin: 0 }}>
              Credit Wallets
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
              View and manage user credit balances across the platform
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => mutateWallets()} className="btn btn-ghost flex items-center gap-2 text-sm">
              <RiRefreshLine size={15} />
            </button>
            <button onClick={exportCSV} className="btn btn-secondary flex items-center gap-2 text-sm">
              <RiDownload2Fill size={15} /> Export CSV
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total Credits in Circulation', value: stats.totalCredits.toFixed(1), icon: RiCoinsFill, color: '#6366f1', suffix: 'cr' },
            { label: 'Wallets with Credits', value: stats.nonZeroWallets, icon: RiGroupFill, color: '#10b981', suffix: '' },
            { label: 'Average Balance', value: stats.avgBalance.toFixed(2), icon: RiLineChartFill, color: '#f59e0b', suffix: 'cr' },
            { label: 'Highest Balance', value: stats.maxBalance.toFixed(2), icon: RiStarFill, color: '#8b5cf6', suffix: 'cr' },
          ].map(({ label, value, icon: Icon, color, suffix }) => (
            <div key={label} className="card p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}18` }}>
                <Icon size={18} style={{ color }} />
              </div>
              <div>
                <p className="text-xl font-bold" style={{ color: 'var(--text)', margin: 0 }}>
                  {value}<span className="text-xs font-normal ml-0.5" style={{ color: 'var(--text-3)' }}>{suffix}</span>
                </p>
                <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>{label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="card p-4 mb-4 flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[200px]">
            <RiSearchEyeFill size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-3)' }} />
            <input type="text" className="input w-full pl-9" placeholder="Search by name or email…"
              value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="input" value={balanceFilter} onChange={e => setBalanceFilter(e.target.value as any)}>
            <option value="all">All Balances</option>
            <option value="zero">Zero Balance</option>
            <option value="low">Low (&lt; 10 cr)</option>
            <option value="high">High (≥ 10 cr)</option>
          </select>
          <select className="input" value={sortBy} onChange={e => setSortBy(e.target.value as any)}>
            <option value="balance_desc">Highest Balance First</option>
            <option value="balance_asc">Lowest Balance First</option>
            <option value="updated">Recently Updated</option>
          </select>
          <p className="text-xs ml-auto" style={{ color: 'var(--text-3)' }}>
            {filteredWallets.length} of {wallets.length} wallets
          </p>
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex justify-center p-20"><RiLoader4Line className="animate-spin text-brand" size={32} /></div>
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full text-left text-sm" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                  {['User', 'Email', 'Balance', 'Last Updated', 'Actions'].map(h => (
                    <th key={h} className="px-4 py-3 font-semibold text-xs uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredWallets.map((wallet, i) => {
                  const bal = wallet.balance ?? 0;
                  const isHigh = bal >= 10;
                  return (
                    <tr key={wallet.user_id} className="border-b border-border hover:bg-surface-alt transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                            style={{ background: `hsl(${(wallet.full_name?.charCodeAt(0) ?? 65) * 5 % 360}, 60%, 55%)` }}>
                            {wallet.full_name?.charAt(0) ?? '?'}
                          </div>
                          <span className="font-semibold" style={{ color: 'var(--text)' }}>{wallet.full_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-2)' }}>{wallet.email}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-base" style={{ color: isHigh ? '#10b981' : 'var(--text)' }}>
                            {bal.toFixed(2)}
                          </span>
                          <span className="text-xs" style={{ color: 'var(--text-3)' }}>cr</span>
                          {isHigh && <RiStarFill size={12} style={{ color: '#f59e0b' }} />}
                        </div>
                        <div className="mt-1 h-1.5 rounded-full overflow-hidden w-28" style={{ background: 'var(--border)' }}>
                          <div className="h-full rounded-full transition-all" style={{
                            width: `${Math.min((bal / (stats.maxBalance || 1)) * 100, 100)}%`,
                            background: isHigh ? '#10b981' : '#6366f1'
                          }} />
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-3)' }}>
                        {wallet.updated_at ? new Date(wallet.updated_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          className="btn btn-secondary btn-sm flex items-center gap-1"
                          onClick={() => setGrantModal(wallet)}
                        >
                          <RiCoinsFill size={13} /> Adjust
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {filteredWallets.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-12 text-center" style={{ color: 'var(--text-3)' }}>
                    No wallets match your filters.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Grant Modal */}
        {grantModal && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
            <div className="card p-6 max-w-md w-full shadow-2xl">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold" style={{ color: 'var(--text)', fontFamily: 'Syne,sans-serif' }}>
                  <RiBankCardFill size={20} className="inline mr-2 -mt-0.5" style={{ color: 'var(--brand)' }} />
                  Adjust Credits
                </h3>
                <button type="button" onClick={() => setGrantModal(null)} className="btn btn-ghost btn-icon"><RiCloseFill size={16} /></button>
              </div>
              <div className="p-3 rounded-xl mb-5 flex items-center gap-3" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                <div className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold"
                  style={{ background: `hsl(${(grantModal.full_name?.charCodeAt(0) ?? 65) * 5 % 360}, 60%, 55%)` }}>
                  {grantModal.full_name?.charAt(0)}
                </div>
                <div>
                  <p className="font-semibold text-sm" style={{ color: 'var(--text)', margin: 0 }}>{grantModal.full_name}</p>
                  <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>
                    Current balance: <strong style={{ color: 'var(--brand)' }}>{(grantModal.balance ?? 0).toFixed(2)} cr</strong>
                  </p>
                </div>
              </div>
              <form onSubmit={handleGrant} className="flex flex-col gap-4">
                <div>
                  <label className="block text-sm font-semibold mb-1">Amount (use negative to deduct)</label>
                  <input type="number" step="0.01" className="input w-full" placeholder="e.g. 50 or -10"
                    value={grantAmount} onChange={e => setGrantAmount(e.target.value ? Number(e.target.value) : '')} required />
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-1">Reason / Description</label>
                  <input type="text" className="input w-full" placeholder="e.g. Compensation for failed analysis"
                    value={grantDesc} onChange={e => setGrantDesc(e.target.value)} required />
                </div>
                <div className="flex justify-end gap-2 mt-2">
                  <button type="button" className="btn btn-ghost" onClick={() => setGrantModal(null)}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={isGranting}>
                    {isGranting ? <RiLoader4Line size={16} className="animate-spin" /> : 'Confirm'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

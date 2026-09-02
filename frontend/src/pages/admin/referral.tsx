// src/pages/admin/referral.tsx
import React, { useEffect, useState } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { adminReferralApi, adminApi } from '../../lib/api';
import { RiArrowUpSFill, RiGroupFill, RiArrowDownSFill, RiFlashlightFill, RiGiftFill, RiDownload2Fill, RiSettings3Fill, RiAwardFill } from 'react-icons/ri';
import toast from 'react-hot-toast';

interface ReferralStats {
  enabled: boolean;
  commission_pct: number;
  min_credits_threshold: number;
  total_referral_events: number;
  total_credits_paid_out: number;
  total_active_referrers: number;
  total_referred_users: number;
}

interface ReferralEvent {
  id: string;
  referrer_name: string;
  referrer_email: string;
  referee_name: string;
  referee_email: string;
  package_id: string;
  credits_purchased: number;
  amount_naira: number;
  commission_pct: number;
  credits_earned: number;
  created_at: string;
}

import AdminGuard from '../../components/admin/AdminGuard';

export default function AdminReferralPage() {
  return (
    <AdminGuard>
      <AdminReferralPageContent />
    </AdminGuard>
  );
}

function AdminReferralPageContent() {
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [events, setEvents] = useState<ReferralEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [commissionPct, setCommissionPct] = useState('');
  const [minThreshold, setMinThreshold] = useState('0');
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    Promise.all([
      adminReferralApi.stats(),
      adminReferralApi.events(50, 0),
    ]).then(([statsRes, eventsRes]) => {
      setStats(statsRes.data);
      setCommissionPct(String(statsRes.data.commission_pct));
      setMinThreshold(String(statsRes.data.min_credits_threshold ?? 0));
      setEnabled(statsRes.data.enabled);
      setEvents(eventsRes.data.events || []);
      setTotal(eventsRes.data.total || 0);
    }).catch(() => toast.error('Failed to load referral admin data'))
      .finally(() => setLoading(false));
  }, []);

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await Promise.all([
        adminApi.updateSetting('referral_commission_pct', commissionPct),
        adminApi.updateSetting('referral_enabled', enabled ? 'true' : 'false'),
        adminApi.updateSetting('referral_min_credits_threshold', minThreshold),
      ]);
      toast.success('Referral settings saved!');
    } catch {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const exportCSV = () => {
    const rows = [
      ['Referrer', 'Referrer Email', 'Referee', 'Referee Email', 'Package', 'Credits Purchased', 'Amount (₦)', 'Commission %', 'Credits Earned', 'Date'],
      ...events.map(e => [
        e.referrer_name, e.referrer_email,
        e.referee_name, e.referee_email,
        e.package_id, e.credits_purchased,
        e.amount_naira, e.commission_pct,
        e.credits_earned, e.created_at,
      ]),
    ];
    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'referral_events.csv'; a.click();
  };

  return (
    <AppLayout title="Referral Management" description="Admin panel for referral program management">
      <div style={{ padding: '24px', maxWidth: 1100, margin: '0 auto' }}>

        {/* Stats row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total Referral Events', value: stats?.total_referral_events ?? '—', icon: RiFlashlightFill, color: '#6366f1' },
            { label: 'Credits Paid Out', value: stats ? `${stats.total_credits_paid_out.toFixed(1)} cr` : '—', icon: RiAwardFill, color: '#f59e0b' },
            { label: 'Active Referrers', value: stats?.total_active_referrers ?? '—', icon: RiGroupFill, color: '#10b981' },
            { label: 'Referred Users', value: stats?.total_referred_users ?? '—', icon: RiGiftFill, color: '#8b5cf6' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="card p-5 flex items-center gap-4">
              <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}18` }}>
                <Icon size={20} style={{ color }} />
              </div>
              <div>
                <p style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', margin: 0 }}>{value}</p>
                <p style={{ fontSize: 12, color: 'var(--text-3)', margin: 0 }}>{label}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* Settings */}
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-5">
              <RiSettings3Fill size={18} style={{ color: 'var(--brand)' }} />
              <h2 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 15, color: 'var(--text)', margin: 0 }}>
                Referral Settings
              </h2>
            </div>

            <div className="mb-4">
              <label className="label mb-1">Commission % per referral</label>
              <p style={{ fontSize: 12, color: 'var(--text-3)', margin: '0 0 8px' }}>
                Percentage of credits bought by referee awarded to referrer
              </p>
              <div className="flex items-center gap-2">
                <input
                  type="number" min="0" max="100" step="0.5"
                  value={commissionPct}
                  onChange={e => setCommissionPct(e.target.value)}
                  className="input flex-1"
                  style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 18 }}
                />
                <span style={{ fontWeight: 700, color: 'var(--text-2)' }}>%</span>
              </div>
            </div>

            <div className="mb-4">
              <label className="label mb-1">Minimum credits threshold</label>
              <p style={{ fontSize: 12, color: 'var(--text-3)', margin: '0 0 8px' }}>
                Referred user must purchase at least this many credits for commission to fire. Set 0 for any purchase.
              </p>
              <div className="flex items-center gap-2">
                <input
                  type="number" min="0" step="1"
                  value={minThreshold}
                  onChange={e => setMinThreshold(e.target.value)}
                  className="input flex-1"
                  style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 18 }}
                />
                <span style={{ fontWeight: 700, color: 'var(--text-2)' }}>credits</span>
              </div>
            </div>

            <div className="mb-5 flex items-center gap-3">
              <label className="label mb-0">Program Enabled</label>
              <button
                onClick={() => setEnabled(e => !e)}
                className="rounded-full transition-all"
                style={{
                  width: 44, height: 24, background: enabled ? 'var(--brand)' : 'var(--border)',
                  border: 'none', cursor: 'pointer', position: 'relative',
                }}
              >
                <span style={{
                  position: 'absolute', top: 2, left: enabled ? 22 : 2, width: 20, height: 20,
                  borderRadius: '50%', background: '#fff', transition: 'left 0.2s',
                }} />
              </button>
              <span style={{ fontSize: 12, color: enabled ? 'var(--success)' : 'var(--text-3)' }}>
                {enabled ? 'Active' : 'Disabled'}
              </span>
            </div>

            <button onClick={handleSaveSettings} disabled={saving} className="btn btn-primary w-full btn-sm">
              {saving ? 'Saving…' : 'Save Settings'}
            </button>
          </div>

          {/* Summary */}
          <div className="lg:col-span-2 card p-6">
            <h2 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 15, color: 'var(--text)', margin: '0 0 16px' }}>
              How the system works
            </h2>
            <div className="grid grid-cols-2 gap-4 text-sm" style={{ color: 'var(--text-2)', lineHeight: 1.7 }}>
              <div>
                <p><strong>Signup:</strong> When a new user registers using a referral link (<code>?ref=CODE</code>), their account is linked to the referrer.</p>
                <p><strong>Commission:</strong> When the referred user purchases any credit package, the referrer automatically earns {commissionPct}% of the purchased credits.</p>
              </div>
              <div>
                <p><strong>Idempotent:</strong> Each payment reference can only trigger one commission — no double-crediting possible.</p>
                <p><strong>Self-referral:</strong> Blocked at registration — users cannot refer themselves.</p>
                <p><strong>Rate snapshot:</strong> The commission % at time of purchase is stored — changing the rate doesn't affect past events.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Events Table */}
        <div className="card p-0 overflow-hidden">
          <div className="flex items-center justify-between p-5" style={{ borderBottom: '1px solid var(--border)' }}>
            <div>
              <h2 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 15, color: 'var(--text)', margin: 0 }}>
                Referral Events
              </h2>
              <p style={{ fontSize: 12, color: 'var(--text-3)', margin: 0 }}>
                {total} total commission events recorded
              </p>
            </div>
            <button onClick={exportCSV} className="btn btn-secondary btn-sm flex items-center gap-2">
              <RiDownload2Fill size={14} /> Export CSV
            </button>
          </div>

          {loading ? (
            <div className="p-10 text-center" style={{ color: 'var(--text-3)' }}>Loading…</div>
          ) : events.length === 0 ? (
            <div className="p-10 text-center" style={{ color: 'var(--text-3)' }}>
              No referral events yet. Events appear here when referred users purchase credits.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: 'var(--surface-2)' }}>
                    {['Referrer', 'Referee', 'Package', 'Paid (₦)', 'Credits Bought', 'Comm %', 'Credits Earned', 'Date'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: 'var(--text-2)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5, whiteSpace: 'nowrap' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev, i) => (
                    <tr key={ev.id} style={{ borderTop: '1px solid var(--border)', background: i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.01)' }}>
                      <td style={{ padding: '10px 14px', color: 'var(--text)', fontWeight: 600 }}>
                        {ev.referrer_name}
                        <span style={{ display: 'block', fontSize: 11, color: 'var(--text-3)', fontWeight: 400 }}>{ev.referrer_email}</span>
                      </td>
                      <td style={{ padding: '10px 14px', color: 'var(--text)' }}>
                        {ev.referee_name}
                        <span style={{ display: 'block', fontSize: 11, color: 'var(--text-3)' }}>{ev.referee_email}</span>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span className="px-2 py-0.5 rounded-full text-xs font-bold" style={{ background: 'rgba(99,102,241,0.1)', color: '#6366f1' }}>
                          {ev.package_id}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px', color: 'var(--text-2)' }}>₦{ev.amount_naira?.toLocaleString()}</td>
                      <td style={{ padding: '10px 14px', color: 'var(--text-2)' }}>{ev.credits_purchased} cr</td>
                      <td style={{ padding: '10px 14px', color: 'var(--text-2)' }}>{ev.commission_pct}%</td>
                      <td style={{ padding: '10px 14px', fontWeight: 700, color: '#10b981' }}>+{ev.credits_earned.toFixed(2)} cr</td>
                      <td style={{ padding: '10px 14px', color: 'var(--text-3)', fontSize: 12, whiteSpace: 'nowrap' }}>
                        {new Date(ev.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </AppLayout>
  );
}

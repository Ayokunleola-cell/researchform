import React from 'react';
import Link from 'next/link';
import AppLayout from '../../components/layout/AppLayout';
import useSWR from 'swr';
import {
  RiGroupFill, RiCoinsFill, RiDatabase2Fill, RiBarChartBoxFill,
  RiShieldFlashFill, RiUserFollowFill, RiLoader4Line, RiArrowRightLine,
  RiAlertFill, RiCheckboxCircleFill, RiSettings4Fill, RiMoneyDollarCircleFill,
  RiRefreshLine, RiFilePaperFill, RiIdCardFill, RiBankFill,
} from 'react-icons/ri';

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({
  icon: Icon, label, value, sub, color, href,
}: {
  icon: React.ElementType; label: string; value: string | number; sub?: string;
  color: string; href?: string;
}) {
  const inner = (
    <div
      className="card p-5 flex items-start gap-4 transition-all"
      style={{ cursor: href ? 'pointer' : 'default' }}
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: `${color}22` }}
      >
        <Icon size={22} style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-2xl font-bold" style={{ color: 'var(--text)', margin: 0, fontFamily: 'Syne, sans-serif' }}>
          {value}
        </p>
        <p className="text-sm font-medium mt-0.5" style={{ color: 'var(--text-2)', margin: 0 }}>{label}</p>
        {sub && <p className="text-xs mt-1" style={{ color: 'var(--text-3)', margin: 0 }}>{sub}</p>}
      </div>
      {href && <RiArrowRightLine size={16} style={{ color: 'var(--text-3)', flexShrink: 0, marginTop: 4 }} />}
    </div>
  );

  return href ? <Link href={href} style={{ textDecoration: 'none' }}>{inner}</Link> : inner;
}

// ─── Action Alert ─────────────────────────────────────────────────────────────
function ActionAlert({ count, label, href, icon: Icon }: { count: number; label: string; href: string; icon: React.ElementType }) {
  if (count === 0) return null;
  return (
    <Link href={href} style={{ textDecoration: 'none' }}>
      <div
        className="flex items-center gap-3 p-3 rounded-xl border transition-all"
        style={{
          borderColor: '#f59e0b44',
          background: '#f59e0b0a',
          color: 'var(--text)',
        }}
      >
        <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: '#f59e0b22' }}>
          <Icon size={16} style={{ color: '#f59e0b' }} />
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold" style={{ margin: 0, color: 'var(--text)' }}>
            {count} {label}
          </p>
          <p className="text-xs" style={{ margin: 0, color: 'var(--text-3)' }}>Requires review</p>
        </div>
        <div
          className="px-2 py-0.5 rounded-full text-xs font-bold"
          style={{ background: '#f59e0b', color: '#fff', minWidth: 24, textAlign: 'center' }}
        >
          {count}
        </div>
      </div>
    </Link>
  );
}

// ─── Quick Link ───────────────────────────────────────────────────────────────
function QuickLink({ href, icon: Icon, label, description, color }: {
  href: string; icon: React.ElementType; label: string; description: string; color: string;
}) {
  return (
    <Link href={href} style={{ textDecoration: 'none' }}>
      <div className="card p-4 flex items-center gap-3 transition-all" style={{ cursor: 'pointer' }}>
        <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}22` }}>
          <Icon size={18} style={{ color }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm" style={{ margin: 0, color: 'var(--text)' }}>{label}</p>
          <p className="text-xs" style={{ margin: 0, color: 'var(--text-3)' }}>{description}</p>
        </div>
        <RiArrowRightLine size={14} style={{ color: 'var(--text-3)', flexShrink: 0 }} />
      </div>
    </Link>
  );
}

// ─── Role Badge ───────────────────────────────────────────────────────────────
const ROLE_COLORS: Record<string, string> = {
  admin: '#ef4444', researcher: '#6366f1', student: '#64748b',
  seller: '#8b5cf6', enterprise: '#0ea5e9',
};

import AdminGuard from '../../components/admin/AdminGuard';

export default function AdminDashboard() {
  return (
    <AdminGuard>
      <AdminDashboardContent />
    </AdminGuard>
  );
}

function AdminDashboardContent() {
  const { data: stats, error, isLoading, mutate } = useSWR('/admin/stats', {
    refreshInterval: 30000,
  });

  const loading = isLoading;
  const s = stats as any;

  return (
    <AppLayout
      title="Admin Dashboard"
      breadcrumbs={[{ label: 'Admin', href: '/admin' }, { label: 'Dashboard' }]}
    >
      <div style={{ padding: '24px', maxWidth: 1300, margin: '0 auto' }}>

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold" style={{ fontFamily: 'Syne, sans-serif', color: 'var(--text)', margin: 0 }}>
              Platform Overview
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
              Real-time platform health and activity metrics
            </p>
          </div>
          <button
            onClick={() => mutate()}
            className="btn btn-ghost flex items-center gap-2 text-sm"
            disabled={loading}
          >
            <RiRefreshLine size={15} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center p-20">
            <RiLoader4Line className="animate-spin" size={36} style={{ color: 'var(--brand)' }} />
          </div>
        ) : error ? (
          <div className="card p-8 text-center">
            <RiAlertFill size={32} style={{ color: '#ef4444', margin: '0 auto 12px' }} />
            <p style={{ color: 'var(--text-2)' }}>Failed to load platform stats. Check admin privileges.</p>
          </div>
        ) : (
          <>
            {/* ── Pending Actions Alert ─────────────────────────────────── */}
            {s?.pending_actions?.total > 0 && (
              <div className="card p-4 mb-6" style={{ borderColor: '#f59e0b44', borderWidth: 1, borderStyle: 'solid' }}>
                <div className="flex items-center gap-2 mb-3">
                  <RiAlertFill size={16} style={{ color: '#f59e0b' }} />
                  <span className="text-sm font-bold" style={{ color: '#f59e0b' }}>
                    {s.pending_actions.total} action{s.pending_actions.total !== 1 ? 's' : ''} require attention
                  </span>
                </div>
                <div className="flex flex-col gap-2">
                  <ActionAlert count={s.pending_actions.datasets} label="pending dataset reviews" href="/admin/datasets" icon={RiDatabase2Fill} />
                  <ActionAlert count={s.pending_actions.kyc} label="pending KYC requests" href="/admin/payouts" icon={RiIdCardFill} />
                  <ActionAlert count={s.pending_actions.withdrawals} label="pending withdrawals" href="/admin/payouts" icon={RiBankFill} />
                </div>
              </div>
            )}

            {/* ── Top Stats ─────────────────────────────────────────────── */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <StatCard
                icon={RiGroupFill}
                label="Total Users"
                value={s?.users?.total ?? 0}
                sub={`${s?.users?.active ?? 0} active · ${s?.users?.suspended ?? 0} suspended`}
                color="#6366f1"
                href="/admin/users"
              />
              <StatCard
                icon={RiCoinsFill}
                label="Credits in Circulation"
                value={(s?.credits?.total_in_circulation ?? 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 1 })}
                sub={`${s?.credits?.wallets_with_credits ?? 0} wallets funded`}
                color="#10b981"
                href="/admin/credits"
              />
              <StatCard
                icon={RiBarChartBoxFill}
                label="Analysis Jobs"
                value={s?.jobs?.total ?? 0}
                sub={`${s?.jobs?.completed ?? 0} completed (${s?.jobs?.completion_rate ?? 0}%)`}
                color="#0ea5e9"
              />
              <StatCard
                icon={RiDatabase2Fill}
                label="Pending Reviews"
                value={s?.pending_actions?.total ?? 0}
                sub="datasets · KYC · withdrawals"
                color={s?.pending_actions?.total > 0 ? '#f59e0b' : '#64748b'}
                href="/admin/datasets"
              />
            </div>

            {/* ── Two-column layout ─────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

              {/* Users by Role */}
              <div className="card p-5 lg:col-span-1">
                <div className="flex items-center gap-2 mb-4">
                  <RiGroupFill size={16} style={{ color: '#6366f1' }} />
                  <span className="font-bold text-sm" style={{ color: 'var(--text)' }}>Users by Role</span>
                </div>
                <div className="flex flex-col gap-2">
                  {Object.entries(s?.users?.by_role ?? {}).map(([role, count]: any) => (
                    <div key={role} className="flex items-center gap-2">
                      <span
                        className="text-xs font-bold px-2 py-0.5 rounded-full capitalize"
                        style={{
                          background: `${ROLE_COLORS[role] ?? '#64748b'}22`,
                          color: ROLE_COLORS[role] ?? '#64748b',
                          minWidth: 80,
                          textAlign: 'center',
                        }}
                      >
                        {role}
                      </span>
                      <div className="flex-1 bg-gray-100 dark:bg-gray-800 rounded-full h-2 overflow-hidden">
                        <div
                          className="h-2 rounded-full"
                          style={{
                            width: `${s?.users?.total > 0 ? (count / s.users.total) * 100 : 0}%`,
                            background: ROLE_COLORS[role] ?? '#64748b',
                            transition: 'width 0.5s ease',
                          }}
                        />
                      </div>
                      <span className="text-sm font-semibold" style={{ color: 'var(--text)', minWidth: 28, textAlign: 'right' }}>
                        {count}
                      </span>
                    </div>
                  ))}
                  {s?.users?.suspended > 0 && (
                    <div className="flex items-center gap-2 mt-1 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                      <RiShieldFlashFill size={12} style={{ color: '#ef4444' }} />
                      <span className="text-xs" style={{ color: '#ef4444' }}>
                        {s.users.suspended} suspended account{s.users.suspended !== 1 ? 's' : ''}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Credits Overview */}
              <div className="card p-5 lg:col-span-1">
                <div className="flex items-center gap-2 mb-4">
                  <RiCoinsFill size={16} style={{ color: '#10b981' }} />
                  <span className="font-bold text-sm" style={{ color: 'var(--text)' }}>Credits Overview</span>
                </div>
                <div className="flex flex-col gap-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm" style={{ color: 'var(--text-3)' }}>Total in Wallets</span>
                    <span className="font-bold" style={{ color: 'var(--text)' }}>
                      {(s?.credits?.total_in_circulation ?? 0).toLocaleString()} cr
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm" style={{ color: 'var(--text-3)' }}>All-time Sold</span>
                    <span className="font-bold" style={{ color: '#10b981' }}>
                      {(s?.credits?.total_sold_all_time ?? 0).toLocaleString()} cr
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm" style={{ color: 'var(--text-3)' }}>Funded Wallets</span>
                    <span className="font-bold" style={{ color: 'var(--text)' }}>
                      {s?.credits?.wallets_with_credits ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm" style={{ color: 'var(--text-3)' }}>Job Completion</span>
                    <span className="font-bold" style={{ color: '#0ea5e9' }}>
                      {s?.jobs?.completion_rate ?? 0}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Quick Nav */}
              <div className="card p-5 lg:col-span-1">
                <div className="flex items-center gap-2 mb-4">
                  <RiSettings4Fill size={16} style={{ color: 'var(--brand)' }} />
                  <span className="font-bold text-sm" style={{ color: 'var(--text)' }}>Quick Navigation</span>
                </div>
                <div className="flex flex-col gap-2">
                  <QuickLink href="/admin/users" icon={RiGroupFill} label="User Management" description="Roles, credits & suspension" color="#6366f1" />
                  <QuickLink href="/admin/credits" icon={RiCoinsFill} label="Credit Wallets" description="Grant & track credits" color="#10b981" />
                  <QuickLink href="/admin/datasets" icon={RiDatabase2Fill} label="Dataset Review" description="Approve or reject uploads" color="#0ea5e9" />
                  <QuickLink href="/admin/payouts" icon={RiMoneyDollarCircleFill} label="Payouts & KYC" description="Withdrawal approvals" color="#f59e0b" />
                  <QuickLink href="/admin/settings" icon={RiSettings4Fill} label="Platform Settings" description="Pricing & system config" color="#8b5cf6" />
                </div>
              </div>

            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}

// src/pages/referral/index.tsx
import React, { useEffect, useState } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { referralApi } from '../../lib/api';
import { RiExternalLinkFill, RiGroupFill, RiFlashlightFill, RiGiftFill, RiFileCopyFill, RiMedalFill, RiArrowRightSFill, RiStarFill, RiAwardFill, RiShareForwardFill, RiCheckLine, RiVipCrownFill, RiLineChartFill } from 'react-icons/ri';
import toast from 'react-hot-toast';
import Link from 'next/link';
import clsx from 'clsx';

interface ReferralStats {
  referral_code: string;
  referral_link: string;
  total_referees: number;
  total_conversions: number;
  total_credits_earned: number;
  commission_pct: number;
  referral_earnings: number;
}

interface Referee {
  id: string;
  full_name: string;
  email: string;
  joined_at: string;
  is_verified: boolean;
  has_paid: boolean;
  conversion_count: number;
  credits_earned_from: number;
}

interface LeaderboardEntry {
  rank: number;
  display_name: string;
  initial: string;
  conversion_count: number;
  total_credits_earned: number;
  medal?: 'gold' | 'silver' | 'bronze';
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success(`${label} copied!`);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
      style={{
        background: copied ? 'rgba(16,185,129,0.15)' : 'var(--bg)',
        color: copied ? 'var(--success)' : 'var(--text)',
        border: `1px solid ${copied ? 'var(--success)' : 'var(--border)'}`,
      }}
    >
      {copied ? <RiCheckLine size={12} /> : <RiFileCopyFill size={12} />}
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

const medalColors = {
  gold: { bg: 'var(--surface-2)', border: 'var(--text)', text: 'var(--text)', badge: 'var(--text)' },
  silver: { bg: 'var(--surface-2)', border: 'var(--border)', text: 'var(--text-2)', badge: 'var(--text-2)' },
  bronze: { bg: 'var(--surface-2)', border: 'var(--border)', text: 'var(--text-3)', badge: 'var(--text-3)' },
};

export default function ReferralDashboard() {
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [referees, setReferees] = useState<Referee[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const [firstName, setFirstName] = useState('Researcher');

  useEffect(() => {
    const userStr = localStorage.getItem('rf_user');
    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        if (user?.full_name) {
          setFirstName(user.full_name.split(' ')[0]);
        }
      } catch (e) {}
    }
  }, []);

  useEffect(() => {
    Promise.allSettled([
      referralApi.me(),
      referralApi.myReferees(),
      referralApi.leaderboard(20),
    ]).then(([statsRes, refRes, lbRes]) => {
      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data);
      } else {
        toast.error('Failed to load your referral stats');
      }
      if (refRes.status === 'fulfilled') {
        setReferees(refRes.value.data.referees || []);
      }
      if (lbRes.status === 'fulfilled') {
        setLeaderboard(lbRes.value.data.leaderboard || []);
      }
    }).finally(() => setLoading(false));
  }, []);

  const conversionRate = stats && stats.total_referees > 0
    ? Math.round((stats.total_conversions / stats.total_referees) * 100)
    : 0;

  const topThree = leaderboard.filter(e => e.medal);
  const rest = leaderboard.filter(e => !e.medal);

  return (
    <AppLayout title="Referral Program" description="Earn credits by inviting friends to ResearchForm">
      <div style={{ padding: '0 24px 24px', maxWidth: 1100, margin: '0 auto' }}>

        {/* ── Hero (Same Solid Rich Dark Color Gradient as Credit Wallet) ── */}
        <div
          className="rounded-2xl p-8 mb-6 relative overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, #090D16 0%, #111827 50%, #0F172A 100%)',
            border: '1px solid #1E293B',
            boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.4)',
            color: '#FFFFFF',
          }}
        >
          {/* Ambient Lighting Orbs */}
          <div style={{ position: 'absolute', top: -70, right: -70, width: 280, height: 280, borderRadius: '50%', background: 'radial-gradient(circle, rgba(99,102,241,0.2) 0%, rgba(99,102,241,0) 70%)', filter: 'blur(30px)', pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', bottom: -90, left: '20%', width: 340, height: 340, borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,130,246,0.15) 0%, rgba(59,130,246,0) 70%)', filter: 'blur(40px)', pointerEvents: 'none' }} />

          <div className="relative z-10">
            <div className="flex items-start justify-between flex-wrap gap-4 mb-2">
              <div>
                <h1 style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: '1.75rem', color: '#FFFFFF', margin: 0 }}>
                  Welcome {firstName} 👋
                </h1>
                <p style={{ color: '#94A3B8', margin: '4px 0 0', fontSize: 14, fontWeight: 500 }}>
                  Ambassador activity
                </p>
              </div>
            </div>

            {/* Action cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-6">
              {/* Copy Link */}
              <div className="flex items-center justify-between p-4 rounded-2xl" style={{ background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', backdropFilter: 'blur(10px)' }}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(99,102,241,0.25)', border: '1px solid rgba(129,140,248,0.3)' }}>
                    <RiShareForwardFill size={18} style={{ color: '#A5B4FC' }} />
                  </div>
                  <div>
                    <p style={{ fontSize: 11, color: '#94A3B8', margin: 0, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600 }}>Copy your</p>
                    <p style={{ fontSize: 14, fontWeight: 700, color: '#FFFFFF', margin: 0 }}>Referral Link</p>
                  </div>
                </div>
                {stats && <CopyButton text={stats.referral_link} label="Referral link" />}
              </div>

              {/* Copy Code */}
              <div className="flex items-center justify-between p-4 rounded-2xl" style={{ background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', backdropFilter: 'blur(10px)' }}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(99,102,241,0.25)', border: '1px solid rgba(129,140,248,0.3)' }}>
                    <RiGiftFill size={18} style={{ color: '#A5B4FC' }} />
                  </div>
                  <div>
                    <p style={{ fontSize: 11, color: '#94A3B8', margin: 0, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600 }}>Copy your</p>
                    <p style={{ fontSize: 14, fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
                      Referral Code — <span style={{ color: '#60A5FA', fontFamily: 'monospace' }}>{stats?.referral_code || '…'}</span>
                    </p>
                  </div>
                </div>
                {stats && <CopyButton text={stats.referral_code} label="Referral code" />}
              </div>
            </div>
          </div>
        </div>

        {/* ── Stats Row ─────────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total Referrals', value: stats?.total_referees ?? '—', icon: RiGroupFill, color: 'var(--text)' },
            { label: 'Paid Conversions', value: stats?.total_conversions ?? '—', icon: RiFlashlightFill, color: 'var(--text)' },
            { label: 'Credits Earned', value: stats ? `${stats.total_credits_earned.toFixed(1)} cr` : '—', icon: RiAwardFill, color: 'var(--text)' },
            { label: 'Conversion Rate', value: loading ? '—' : `${conversionRate}%`, icon: RiLineChartFill, color: 'var(--text)' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="card p-5 flex items-center gap-4">
              <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0" style={{ border: '1px solid var(--border)', background: 'var(--surface-2)' }}>
                <Icon size={20} style={{ color }} />
              </div>
              <div>
                <p style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', margin: 0 }}>{value}</p>
                <p style={{ fontSize: 12, color: 'var(--text-3)', margin: 0 }}>{label}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

          {/* ── My Referrals table ─────────────────────────────── */}
          <div className="lg:col-span-3 card p-0 overflow-hidden">
            <div className="flex items-center justify-between p-5" style={{ borderBottom: '1px solid var(--border)' }}>
              <div>
                <h2 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 15, color: 'var(--text)', margin: 0 }}>
                  Your referrals
                </h2>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-bold" style={{ background: 'var(--surface-2)', color: 'var(--text)' }}>
                {stats?.total_conversions ?? 0} of {stats?.total_referees ?? 0}
              </span>
            </div>

            {loading ? (
              <div className="p-8 text-center" style={{ color: 'var(--text-3)', fontSize: 14 }}>Loading…</div>
            ) : referees.length === 0 ? (
              <div className="p-12 flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                  <RiGroupFill size={24} style={{ color: 'var(--text-3)' }} />
                </div>
                <p style={{ color: 'var(--text-3)', fontSize: 14, margin: 0, textAlign: 'center' }}>
                  No referrals yet. Share your referral code to get started!
                </p>
              </div>
            ) : (
              <div>
                {referees.map((ref, i) => (
                  <div
                    key={ref.id}
                    className="flex items-center gap-4 px-5 py-3.5"
                    style={{
                      borderBottom: i < referees.length - 1 ? '1px solid var(--border)' : 'none',
                    }}
                  >
                    {/* Avatar */}
                    <div className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold"
                      style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }}>
                      {ref.full_name[0].toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', margin: 0 }}>{ref.full_name}</p>
                      <p style={{ fontSize: 12, color: 'var(--text-3)', margin: 0 }}>
                        {new Date(ref.joined_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </p>
                    </div>
                    {/* Status */}
                    <span className="px-2.5 py-1 rounded-full text-xs font-semibold flex-shrink-0" style={{
                      background: 'var(--surface-2)', border: '1px solid var(--border)',
                      color: ref.has_paid ? 'var(--success)' : 'var(--text-3)',
                    }}>
                      {ref.has_paid ? '✅ Paid' : 'Registered'}
                    </span>
                    {/* Credits earned */}
                    {ref.credits_earned_from > 0 && (
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', flexShrink: 0 }}>
                        +{ref.credits_earned_from.toFixed(1)} cr
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── How it works ────────────────────────────────────── */}
          <div className="lg:col-span-2 card p-5">
            <h2 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 15, color: 'var(--text)', margin: '0 0 16px' }}>
              How it works
            </h2>
            <div className="flex flex-col gap-4">
              {[
                { step: '1', title: 'Share your code', desc: 'Share your unique referral link or code with friends and colleagues.' },
                { step: '2', title: 'They sign up', desc: 'Your friend registers on ResearchForm using your referral link.' },
                { step: '3', title: 'They buy credits', desc: 'When your friend purchases any credit package, you earn your commission.' },
                { step: '4', title: 'You earn credits', desc: `You automatically receive ${stats?.commission_pct || 10}% of the credits they purchase, credited to your wallet instantly.` },
              ].map(({ step, title, desc }) => (
                <div key={step} className="flex gap-3">
                  <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold" style={{ background: 'var(--text)', color: 'var(--bg)', marginTop: 1 }}>
                    {step}
                  </div>
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', margin: 0 }}>{title}</p>
                    <p style={{ fontSize: 12, color: 'var(--text-3)', margin: '2px 0 0', lineHeight: 1.5 }}>{desc}</p>
                  </div>
                </div>
              ))}
            </div>

          </div>
        </div>

        {/* ── Leaderboard ───────────────────────────────────────── */}
        <div className="card p-0 overflow-hidden mt-6">
          <div className="flex items-center justify-between p-5" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="flex items-center gap-3">
              <RiVipCrownFill size={20} style={{ color: 'var(--text)' }} />
              <div>
                <h2 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 15, color: 'var(--text)', margin: 0 }}>
                  Leaderboard
                </h2>
              </div>
            </div>
            <Link href="/referral/leaderboard" className="flex items-center gap-1 text-xs font-semibold" style={{ color: 'var(--text)' }}>
              View full <RiArrowRightSFill size={14} />
            </Link>
          </div>

          {/* Top 3 podium */}
          {topThree.length > 0 && (
            <div className="grid grid-cols-3 gap-3 p-5" style={{ background: 'var(--bg)' }}>
              {topThree.map((entry) => {
                const mc = medalColors[entry.medal!];
                return (
                  <div key={entry.rank} className="rounded-2xl p-4 text-center" style={{ background: mc.bg, border: `1px solid ${mc.border}` }}>
                    <p style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', margin: '0 0 4px' }}>{entry.display_name}</p>
                    <p style={{ fontSize: 28, fontWeight: 900, color: mc.text, margin: '0 0 8px', lineHeight: 1 }}>
                      {entry.conversion_count}
                    </p>
                    <span className="px-3 py-1 rounded-full text-xs font-bold uppercase" style={{ background: mc.badge, color: 'var(--bg)' }}>
                      {entry.medal}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Ranked list */}
          {rest.map((entry) => (
            <div key={entry.rank} className="flex items-center gap-4 px-5 py-3" style={{ borderTop: '1px solid var(--border)' }}>
              <span style={{ width: 24, textAlign: 'center', fontSize: 13, color: 'var(--text-3)', fontWeight: 600 }}>{entry.rank}</span>
              <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }}>
                {entry.initial}
              </div>
              <span className="flex-1 font-semibold" style={{ fontSize: 14, color: 'var(--text)' }}>{entry.display_name}</span>
              <div className="text-right">
                <p style={{ fontSize: 16, fontWeight: 800, color: 'var(--text)', margin: 0 }}>{entry.conversion_count}</p>
                <p style={{ fontSize: 10, color: 'var(--text-3)', margin: 0 }}>referrals</p>
              </div>
            </div>
          ))}

          {leaderboard.length === 0 && !loading && (
            <div className="p-10 text-center" style={{ color: 'var(--text-3)', fontSize: 14 }}>
              No referrals recorded yet — be the first on the board!
            </div>
          )}
        </div>

      </div>
    </AppLayout>
  );
}

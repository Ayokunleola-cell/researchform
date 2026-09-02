// src/pages/referral/leaderboard.tsx
import React, { useEffect, useState } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { referralApi } from '../../lib/api';
import { RiArrowLeftSFill, RiGiftFill, RiMedalFill, RiStarFill, RiVipCrownFill, RiLineChartFill } from 'react-icons/ri';
import toast from 'react-hot-toast';
import Link from 'next/link';

interface LeaderboardEntry {
  rank: number;
  display_name: string;
  initial: string;
  conversion_count: number;
  total_credits_earned: number;
  medal?: 'gold' | 'silver' | 'bronze';
}

const MEDAL_STYLES = {
  gold: {
    podium: 'linear-gradient(160deg, #78350f 0%, #b45309 60%, #92400e 100%)',
    border: '#d97706',
    text: '#fde68a',
    badge: '#f59e0b',
    glow: 'rgba(245,158,11,0.35)',
    icon: '🥇',
    height: 160,
  },
  silver: {
    podium: 'linear-gradient(160deg, #1e293b 0%, #334155 60%, #1e293b 100%)',
    border: '#64748b',
    text: '#cbd5e1',
    badge: '#64748b',
    glow: 'rgba(100,116,139,0.25)',
    icon: '🥈',
    height: 130,
  },
  bronze: {
    podium: 'linear-gradient(160deg, #431407 0%, #7c2d12 60%, #431407 100%)',
    border: '#c2410c',
    text: '#fed7aa',
    badge: '#ea580c',
    glow: 'rgba(234,88,12,0.25)',
    icon: '🥉',
    height: 110,
  },
};

function PodiumCard({ entry }: { entry: LeaderboardEntry }) {
  const style = MEDAL_STYLES[entry.medal!];
  const isGold = entry.medal === 'gold';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
      {/* Avatar */}
      <div style={{
        width: isGold ? 72 : 56,
        height: isGold ? 72 : 56,
        borderRadius: '50%',
        background: `hsl(${(entry.initial.charCodeAt(0) * 57) % 360}, 55%, 40%)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: isGold ? 28 : 22, fontWeight: 800, color: '#fff',
        border: `3px solid ${style.border}`,
        boxShadow: `0 0 20px ${style.glow}`,
        marginBottom: 10,
        position: 'relative',
      }}>
        {entry.initial}
        <span style={{
          position: 'absolute', bottom: -6, right: -6,
          fontSize: isGold ? 22 : 18, lineHeight: 1,
        }}>{style.icon}</span>
      </div>

      {/* Name */}
      <p style={{ fontWeight: 700, fontSize: isGold ? 15 : 13, color: '#fff', margin: '0 0 4px', textAlign: 'center' }}>
        {entry.display_name}
      </p>
      <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', margin: '0 0 10px' }}>
        {entry.total_credits_earned.toFixed(1)} cr earned
      </p>

      {/* Podium block */}
      <div style={{
        width: '100%', height: style.height,
        background: style.podium,
        borderRadius: '12px 12px 0 0',
        border: `1px solid ${style.border}`,
        borderBottom: 'none',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: `inset 0 0 30px ${style.glow}`,
      }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ fontSize: 36, fontWeight: 900, color: style.text, margin: 0, lineHeight: 1 }}>
            {entry.conversion_count}
          </p>
          <p style={{ fontSize: 11, color: style.badge, margin: '4px 0 0', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1 }}>
            referrals
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LeaderboardPage() {
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    referralApi.leaderboard(50)
      .then(res => setLeaderboard(res.data.leaderboard || []))
      .catch(() => toast.error('Failed to load leaderboard'))
      .finally(() => setLoading(false));
  }, []);

  const topThree = leaderboard.filter(e => e.medal);
  // Reorder: silver, gold, bronze for visual podium effect
  const podiumOrder = [
    topThree.find(e => e.medal === 'silver'),
    topThree.find(e => e.medal === 'gold'),
    topThree.find(e => e.medal === 'bronze'),
  ].filter(Boolean) as LeaderboardEntry[];

  const rest = leaderboard.filter(e => !e.medal);

  return (
    <AppLayout title="Ambassador Leaderboard" description="Top referrers on ResearchForm">
      <div style={{ padding: '24px', maxWidth: 800, margin: '0 auto' }}>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Link href="/referral" className="flex items-center gap-1 text-sm font-medium" style={{ color: 'var(--text-3)', textDecoration: 'none' }}>
            <RiArrowLeftSFill size={16} /> Back
          </Link>
        </div>

        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <RiVipCrownFill size={28} style={{ color: '#f59e0b' }} />
            <h1 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 800, fontSize: '1.75rem', color: 'var(--text)', margin: 0 }}>
              Ambassador Leaderboard
            </h1>
          </div>
          <p style={{ color: 'var(--text-3)', fontSize: 14, margin: 0 }}>
            Top referrers ranked by successful conversions · Updated in real time
          </p>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-3)' }}>Loading leaderboard…</div>
        ) : leaderboard.length === 0 ? (
          <div className="card p-12 text-center">
            <RiVipCrownFill size={40} style={{ color: 'var(--text-3)', marginBottom: 12, opacity: 0.4 }} />
            <p style={{ color: 'var(--text-3)', fontSize: 15, margin: 0 }}>
              No referral conversions yet. Be the first to top the board!
            </p>
            <Link href="/referral" className="btn btn-primary btn-sm mt-4" style={{ display: 'inline-flex' }}>
              Get your referral link
            </Link>
          </div>
        ) : (
          <>
            {/* ── Podium ────────────────────────────────────────────── */}
            {topThree.length > 0 && (
              <div
                className="rounded-2xl p-6 mb-6 overflow-hidden relative"
                style={{ background: 'linear-gradient(135deg, #0f0f1a 0%, #1a1030 60%, #0d1a2e 100%)' }}
              >
                {/* Glow orbs */}
                <div style={{ position: 'absolute', top: -80, left: '50%', transform: 'translateX(-50%)', width: 300, height: 300, borderRadius: '50%', background: 'rgba(245,158,11,0.08)', filter: 'blur(60px)', pointerEvents: 'none' }} />

                <div className="relative" style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
                  {podiumOrder.map(entry => (
                    <PodiumCard key={entry.rank} entry={entry} />
                  ))}
                </div>
              </div>
            )}

            {/* ── Ranked list ───────────────────────────────────────── */}
            {rest.length > 0 && (
              <div className="card p-0 overflow-hidden">
                {rest.map((entry, i) => (
                  <div
                    key={entry.rank}
                    className="flex items-center gap-4 px-5 py-3.5"
                    style={{ borderBottom: i < rest.length - 1 ? '1px solid var(--border)' : 'none' }}
                  >
                    {/* Rank number */}
                    <span style={{
                      width: 28, textAlign: 'center', fontSize: 14,
                      fontWeight: 700, color: 'var(--text-3)',
                      flexShrink: 0,
                    }}>
                      {entry.rank}
                    </span>

                    {/* Avatar circle */}
                    <div
                      className="flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
                      style={{
                        width: 38, height: 38, borderRadius: '50%',
                        background: `hsl(${(entry.initial.charCodeAt(0) * 57) % 360}, 50%, 40%)`,
                      }}
                    >
                      {entry.initial}
                    </div>

                    {/* Name */}
                    <span style={{ flex: 1, fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
                      {entry.display_name}
                    </span>

                    {/* Credits */}
                    <span style={{ fontSize: 12, color: 'var(--text-3)', marginRight: 16 }}>
                      {entry.total_credits_earned.toFixed(1)} cr earned
                    </span>

                    {/* Referral count */}
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <p style={{ fontSize: 18, fontWeight: 800, color: 'var(--text)', margin: 0, lineHeight: 1 }}>
                        {entry.conversion_count}
                      </p>
                      <p style={{ fontSize: 10, color: 'var(--text-3)', margin: 0 }}>referrals</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* CTA */}
            <div className="card p-6 mt-6 text-center" style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.06) 0%, rgba(139,92,246,0.06) 100%)', border: '1px solid rgba(99,102,241,0.15)' }}>
              <RiGiftFill size={24} style={{ color: '#6366f1', marginBottom: 10 }} />
              <h3 style={{ fontFamily: 'Syne,sans-serif', fontWeight: 700, fontSize: 16, color: 'var(--text)', margin: '0 0 6px' }}>
                Want to climb the board?
              </h3>
              <p style={{ color: 'var(--text-3)', fontSize: 13, margin: '0 0 14px' }}>
                Share your referral link and earn credits for every friend who purchases a plan.
              </p>
              <Link href="/referral" className="btn btn-primary btn-sm" style={{ display: 'inline-flex' }}>
                View My Referral Dashboard
              </Link>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}

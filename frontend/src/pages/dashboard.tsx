// src/pages/dashboard.tsx
import React, { useEffect, useState } from 'react';
import AppLayout from '../components/layout/AppLayout';
import Link from 'next/link';
import Head from 'next/head';
import {
  FileText, BarChart3, Users, TrendingUp, ArrowRight,
  Plus, Clock, CheckCircle, AlertCircle, Zap, BookOpen,
  Upload, FlaskConical
} from 'lucide-react';
import { surveysApi, analysisApi } from '../lib/api';

// ─── Mock data used when backend is offline ───────────────────────
const MOCK_SURVEYS = [
  { id: '1', title: 'Effect of Teaching Methods on Student Performance', status: 'active', response_count: 47, question_count: 12, created_at: '2026-04-01' },
  { id: '2', title: 'Factors Influencing Academic Motivation Among Undergraduates', status: 'analysed', response_count: 120, question_count: 18, created_at: '2026-03-15' },
  { id: '3', title: 'Impact of Smartphone Use on Study Hours', status: 'draft', response_count: 0, question_count: 8, created_at: '2026-04-05' },
];
const MOCK_JOBS = [
  { id: 'j1', survey_title: 'Academic Motivation Study', status: 'complete', n_rows: 120, n_columns: 18, created_at: '2026-03-18' },
  { id: 'j2', survey_title: 'Teaching Methods Survey', status: 'decode_review', n_rows: 47, n_columns: 12, created_at: '2026-04-06' },
];

const STATUS_MAP: Record<string, { label: string; cls: string; icon: any }> = {
  draft:         { label: 'Draft',         cls: 'badge-neutral',  icon: Clock },
  active:        { label: 'Active',        cls: 'badge-success',  icon: CheckCircle },
  closed:        { label: 'Closed',        cls: 'badge-warning',  icon: AlertCircle },
  analysed:      { label: 'Analysed',      cls: 'badge-brand',    icon: BarChart3 },
  pending:       { label: 'Pending',       cls: 'badge-neutral',  icon: Clock },
  decode_review: { label: 'Decode Review', cls: 'badge-warning',  icon: AlertCircle },
  analysing:     { label: 'Analysing',     cls: 'badge-brand',    icon: TrendingUp },
  complete:      { label: 'Complete',      cls: 'badge-success',  icon: CheckCircle },
  failed:        { label: 'Failed',        cls: 'badge-danger',   icon: AlertCircle },
};

function StatCard({ icon: Icon, label, value, delta, color, delay = 0 }: any) {
  return (
    <div
      className="card card-hover p-6 animate-slide-up stat-accent"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: `${color}18` }}>
          <Icon size={22} style={{ color }} />
        </div>
        {delta && <span className="badge badge-success text-xs">+{delta}%</span>}
      </div>
      <p className="text-3xl font-bold mb-1" style={{ fontFamily: 'Syne, sans-serif', color: 'var(--text)' }}>{value}</p>
      <p className="text-sm" style={{ color: 'var(--text-3)' }}>{label}</p>
    </div>
  );
}

const PIPELINE_STAGES = [
  { n: 1, label: 'Data Assembly',  desc: 'Survey / file' },
  { n: 2, label: 'Data Decode',    desc: 'Clean & classify', star: true },
  { n: 3, label: 'Brief Parsing',  desc: 'Objectives' },
  { n: 4, label: 'Test Selection', desc: 'AI selects tests' },
  { n: 5, label: 'Code Gen',       desc: 'Python code' },
  { n: 6, label: 'Code Exec',      desc: 'Run safely' },
  { n: 7, label: 'Visualisation',  desc: 'Charts' },
  { n: 8, label: 'Report Writing', desc: 'AI narrative' },
  { n: 9, label: 'Doc Build',      desc: 'Chapter 4 .docx' },
];

const QUICK_ACTIONS = [
  { icon: FileText,   label: 'Build a new survey',        desc: 'Create questions & share with respondents', href: '/surveys/new',   color: 'var(--brand)' },
  { icon: Upload,     label: 'Upload existing data',      desc: 'SPSS .sav, Excel, CSV files',               href: '/analysis',      color: 'var(--info)' },
  { icon: FlaskConical, label: 'Run statistical analysis', desc: 'AI-powered test selection & execution',    href: '/analysis',      color: 'var(--warning)' },
  { icon: BookOpen,   label: 'Generate Chapter 4 report', desc: 'Formatted Word document output',            href: '/reports',       color: 'var(--success)' },
];

export default function DashboardPage() {
  const [surveys, setSurveys] = useState<any[]>([]);
  const [jobs, setJobs]       = useState<any[]>([]);
  const [user, setUser]       = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('rf_user');
    if (stored) setUser(JSON.parse(stored));

    Promise.all([
      surveysApi.list().catch(() => ({ data: MOCK_SURVEYS })),
      analysisApi.listJobs().catch(() => ({ data: MOCK_JOBS })),
    ]).then(([sv, jb]) => {
      setSurveys((sv.data?.length ? sv.data : MOCK_SURVEYS).slice(0, 5));
      setJobs((jb.data?.length ? jb.data : MOCK_JOBS).slice(0, 5));
    }).finally(() => setLoading(false));
  }, []);

  const totalResponses = surveys.reduce((a, s) => a + (s.response_count || 0), 0);
  const activeCount    = surveys.filter(s => s.status === 'active').length;
  const completeJobs   = jobs.filter(j => j.status === 'complete').length;

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <AppLayout>
      <Head>
        <title>Dashboard — ResearchForm</title>
      </Head>
      <div className="max-w-6xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4 animate-fade-in">
          <div>
            <p style={{ color: 'var(--text-3)', fontSize: 13, marginBottom: 4 }}>{greeting()},</p>
            <h1 style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: 28, color: 'var(--text)', marginBottom: 4 }}>
              {user?.full_name || 'Researcher'} 👋
            </h1>
            <p style={{ color: 'var(--text-2)', fontSize: 14 }}>
              {user?.institution || 'ResearchForm'} · Here's your research overview
            </p>
          </div>
          <Link href="/surveys/new">
            <button className="btn btn-primary">
              <Plus size={16} />
              New Survey
            </button>
          </Link>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger">
          <StatCard icon={FileText}    label="Total Surveys"       value={loading ? '—' : surveys.length}     color="var(--brand)"   delay={0} />
          <StatCard icon={Users}       label="Total Responses"     value={loading ? '—' : totalResponses}     color="var(--success)" delay={60}  delta={totalResponses > 0 ? 12 : undefined} />
          <StatCard icon={CheckCircle} label="Active Surveys"      value={loading ? '—' : activeCount}        color="var(--info)"    delay={120} />
          <StatCard icon={BarChart3}   label="Completed Analyses"  value={loading ? '—' : completeJobs}       color="var(--warning)" delay={180} />
        </div>

        {/* Two-col content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* Recent Surveys */}
          <div className="card p-6 animate-slide-up" style={{ animationDelay: '100ms' }}>
            <div className="flex items-center justify-between mb-5">
              <h2 style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>
                Recent Surveys
              </h2>
              <Link href="/surveys">
                <span className="text-sm flex items-center gap-1" style={{ color: 'var(--brand)', cursor: 'pointer' }}>
                  View all <ArrowRight size={14} />
                </span>
              </Link>
            </div>

            {loading ? (
              <div className="space-y-3">
                {[1,2,3].map(i => <div key={i} className="skeleton h-16 w-full" />)}
              </div>
            ) : surveys.length === 0 ? (
              <div className="text-center py-10">
                <FileText size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
                <p style={{ color: 'var(--text-2)', fontSize: 14 }}>No surveys yet</p>
                <Link href="/surveys/new">
                  <button className="btn btn-primary btn-sm mt-3"><Plus size={14} /> Create your first</button>
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {surveys.map((s: any) => {
                  const status = STATUS_MAP[s.status] || STATUS_MAP.draft;
                  return (
                    <Link key={s.id} href={`/surveys/${s.id}`}>
                      <div
                        className="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all"
                        style={{ background: 'var(--surface-2)' }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'var(--surface-2)')}
                      >
                        <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(99,102,241,0.12)' }}>
                          <FileText size={16} style={{ color: 'var(--brand)' }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate" style={{ color: 'var(--text)' }}>{s.title}</p>
                          <p style={{ color: 'var(--text-3)', fontSize: 12 }}>{s.response_count || 0} responses · {s.question_count || 0} questions</p>
                        </div>
                        <span className={`badge ${status.cls} flex-shrink-0`} style={{ fontSize: 11 }}>{status.label}</span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>

          {/* Analysis Jobs */}
          <div className="card p-6 animate-slide-up" style={{ animationDelay: '160ms' }}>
            <div className="flex items-center justify-between mb-5">
              <h2 style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>
                Analysis Jobs
              </h2>
              <Link href="/analysis">
                <span className="text-sm flex items-center gap-1" style={{ color: 'var(--brand)', cursor: 'pointer' }}>
                  View all <ArrowRight size={14} />
                </span>
              </Link>
            </div>

            {loading ? (
              <div className="space-y-3">
                {[1,2,3].map(i => <div key={i} className="skeleton h-16 w-full" />)}
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-10">
                <BarChart3 size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
                <p style={{ color: 'var(--text-2)', fontSize: 14 }}>No analyses yet</p>
                <Link href="/analysis">
                  <button className="btn btn-primary btn-sm mt-3"><Zap size={14} /> Start analysis</button>
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {jobs.map((j: any) => {
                  const status = STATUS_MAP[j.status] || STATUS_MAP.pending;
                  const Icon = status.icon;
                  return (
                    <Link key={j.id} href={`/analysis/${j.id}`}>
                      <div
                        className="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all"
                        style={{ background: 'var(--surface-2)' }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'var(--surface-2)')}
                      >
                        <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(99,102,241,0.08)' }}>
                          <Icon size={16} style={{ color: 'var(--brand)' }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate" style={{ color: 'var(--text)' }}>{j.survey_title || 'File Upload'}</p>
                          <p style={{ color: 'var(--text-3)', fontSize: 12 }}>
                            {j.n_rows ? `${j.n_rows} rows · ${j.n_columns} variables` : 'Pending'}
                          </p>
                        </div>
                        <span className={`badge ${status.cls} flex-shrink-0`} style={{ fontSize: 11 }}>{status.label}</span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Quick actions */}
        <div className="animate-slide-up" style={{ animationDelay: '200ms' }}>
          <h2 style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 16, color: 'var(--text)', marginBottom: 16 }}>
            Quick Actions
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {QUICK_ACTIONS.map(({ icon: Icon, label, desc, href, color }) => (
              <Link key={label} href={href}>
                <div
                  className="card card-hover p-4 cursor-pointer flex items-center gap-4"
                >
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}15` }}>
                    <Icon size={20} style={{ color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{label}</p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{desc}</p>
                  </div>
                  <ArrowRight size={16} style={{ color: 'var(--text-3)', flexShrink: 0 }} />
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Pipeline overview */}
        <div className="card p-6 animate-slide-up" style={{ animationDelay: '240ms' }}>
          <h2 style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 16, color: 'var(--text)', marginBottom: 20 }}>
            9-Stage Analysis Pipeline
          </h2>
          <div className="flex items-center overflow-x-auto pb-2" style={{ gap: 0 }}>
            {PIPELINE_STAGES.map((stage, i) => (
              <React.Fragment key={stage.n}>
                <div className="flex flex-col items-center text-center flex-shrink-0" style={{ minWidth: 72 }}>
                  <div
                    style={{
                      width: 34, height: 34, borderRadius: '50%',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 12, fontWeight: 700, marginBottom: 6,
                      background: stage.star ? 'var(--warning)' : 'var(--surface-2)',
                      color: stage.star ? '#fff' : 'var(--text-3)',
                      border: `2px solid ${stage.star ? 'var(--warning)' : 'var(--border)'}`,
                      boxShadow: stage.star ? '0 0 12px rgba(245,158,11,0.3)' : 'none',
                    }}
                  >
                    {stage.n}
                  </div>
                  <p style={{ fontSize: 10, fontWeight: 600, color: 'var(--text)', lineHeight: 1.3 }}>{stage.label}</p>
                  <p style={{ fontSize: 9, color: 'var(--text-3)', marginTop: 2 }}>{stage.desc}</p>
                </div>
                {i < PIPELINE_STAGES.length - 1 && (
                  <div style={{ flex: 1, height: 2, background: 'var(--border)', minWidth: 10, marginBottom: 22, flexShrink: 0 }} />
                )}
              </React.Fragment>
            ))}
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 12 }}>
            ★ Stage 2 (Data Decode) pauses for your review — confirm variable types and roles before analysis proceeds.
          </p>
        </div>

      </div>
    </AppLayout>
  );
}

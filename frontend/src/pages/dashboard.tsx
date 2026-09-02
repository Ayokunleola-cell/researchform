// src/pages/dashboard.tsx
import React, { useEffect, useState } from 'react';
import AppLayout from '../components/layout/AppLayout';
import PageHeader from '../components/ui/PageHeader';
import ResearchWorkflow from '../components/ui/ResearchWorkflow';
import Link from 'next/link';
import { RiBookOpenFill, RiAddFill, RiGroupFill, RiArrowRightFill, RiFlashlightFill, RiFlaskFill, RiUpload2Fill, RiBarChart2Fill, RiErrorWarningFill, RiFileTextFill, RiShoppingBag3Fill, RiTimeFill, RiCheckboxCircleFill, RiRobotFill, RiLineChartFill } from 'react-icons/ri';
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
  draft:         { label: 'Draft',         cls: 'badge-neutral',  icon: RiTimeFill},
  active:        { label: 'Active',        cls: 'badge-success',  icon: RiCheckboxCircleFill},
  closed:        { label: 'Closed',        cls: 'badge-warning',  icon: RiErrorWarningFill},
  analysed:      { label: 'Analysed',      cls: 'badge-brand',    icon: RiBarChart2Fill},
  pending:       { label: 'Pending',       cls: 'badge-neutral',  icon: RiTimeFill},
  decode_review: { label: 'Decode Review', cls: 'badge-warning',  icon: RiErrorWarningFill},
  analysing:     { label: 'Analysing',     cls: 'badge-brand',    icon: RiLineChartFill},
  complete:      { label: 'Complete',      cls: 'badge-success',  icon: RiCheckboxCircleFill},
  failed:        { label: 'Failed',        cls: 'badge-danger',   icon: RiErrorWarningFill},
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
  { n: 1, label: 'Inspection',     desc: 'Clean & inspect' },
  { n: 2, label: 'Data Decode',    desc: 'Classify vars' },
  { n: 3, label: 'Context',        desc: 'AI maps DV/IV' },
  { n: 4, label: 'Descriptive',    desc: 'Stats + norms' },
  { n: 5, label: 'Inferential',    desc: 'Run all tests' },
  { n: 6, label: 'Visualisation',  desc: 'Charts & plots' },
  { n: 7, label: 'Report',         desc: 'Chapter 4 .docx' },
];

const QUICK_ACTIONS = [
  { icon: RiFileTextFill,   label: 'Build a new survey',        desc: 'Create questions & share with respondents', href: '/surveys/new',   color: 'var(--brand)' },
  { icon: RiUpload2Fill,     label: 'Upload existing data',      desc: 'SPSS .sav, Excel, CSV files',               href: '/analysis',      color: 'var(--info)' },
  { icon: RiFlaskFill, label: 'Run statistical analysis', desc: 'AI-powered test selection & execution',    href: '/analysis',      color: 'var(--warning)' },
  { icon: RiBookOpenFill,   label: 'Generate report', desc: 'Formatted Word document output',            href: '/reports',       color: 'var(--success)' },
  { icon: RiRobotFill,          label: 'Chat with AI analysis result', desc: 'Ask questions about your data',          href: '/chat',      color: 'var(--info)' },
];

const MARKETPLACE_ACTION = {
  icon: RiShoppingBag3Fill,
  label: 'Browse data marketplace',
  desc: 'Find or sell research datasets',
  href: '/marketplace',
  color: 'var(--brand)',
};

export default function DashboardPage() {
  const [surveys, setSurveys] = useState<any[]>([]);
  const [jobs, setJobs]       = useState<any[]>([]);
  const [user, setUser]       = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('rf_user');
    if (stored && stored !== 'undefined') {
      try { setUser(JSON.parse(stored)); } catch (e) { localStorage.removeItem('rf_user'); }
    }

    Promise.all([
      surveysApi.list().catch(() => ({ data: [] })),
      analysisApi.listJobs().catch(() => ({ data: [] })),
    ]).then(([sv, jb]) => {
      setSurveys((Array.isArray(sv.data) ? sv.data : []).slice(0, 5));
      setJobs((Array.isArray(jb.data) ? jb.data : []).slice(0, 5));
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
    <AppLayout
      title="Dashboard"
      description={user?.institution ? `${user.institution}` : 'Your research overview'}
      headerActions={
        <Link href="/surveys/new">
          <button type="button" className="btn btn-primary btn-sm">
            <RiAddFill size={16} />
            New Survey
          </button>
        </Link>
      }
    >
      <div className="page-container page-stack">
        <PageHeader
          title={`${greeting()}, ${user?.full_name?.split(' ')[0] || 'Researcher'}`}
          description="Collect data with surveys, run AI analysis, and export Chapter 4 reports — all in one place."
          actions={
            <Link href="/analysis">
              <button type="button" className="btn btn-secondary btn-sm">
                <RiUpload2Fill size={15} />
                Upload data
              </button>
            </Link>
          }
        />
        <ResearchWorkflow className="-mt-8 mb-2" />

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger">
          <StatCard icon={RiFileTextFill}    label="Total Surveys"       value={loading ? '—' : surveys.length}     color="var(--brand)"   delay={0} />
          <StatCard icon={RiGroupFill}       label="Total Responses"     value={loading ? '—' : totalResponses}     color="var(--success)" delay={60}  delta={totalResponses > 0 ? 12 : undefined} />
          <StatCard icon={RiCheckboxCircleFill} label="Active Surveys"      value={loading ? '—' : activeCount}        color="var(--info)"    delay={120} />
          <StatCard icon={RiBarChart2Fill}   label="Completed Analyses"  value={loading ? '—' : completeJobs}       color="var(--warning)" delay={180} />
        </div>

        {/* Two-col content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          <div className="card section-card animate-slide-up" style={{ animationDelay: '100ms' }}>
            <div className="section-card-header">
              <h2 className="section-title">Recent Surveys</h2>
              <Link href="/surveys" className="section-link">
                View all <RiArrowRightFill size={14} />
              </Link>
            </div>

            {loading ? (
              <div className="space-y-3">
                {[1,2,3].map(i => <div key={i} className="skeleton h-16 w-full" />)}
              </div>
            ) : surveys.length === 0 ? (
              <div className="text-center py-10">
                <RiFileTextFill size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
                <p style={{ color: 'var(--text-2)', fontSize: 14 }}>No surveys yet</p>
                <Link href="/surveys/new">
                  <button className="btn btn-primary btn-sm mt-3"><RiAddFill size={14} /> Create your first</button>
                </Link>
              </div>
            ) : (
              <div className="space-y-2 flex flex-col">
                {surveys.map((s: any) => {
                  const status = STATUS_MAP[s.status] || STATUS_MAP.draft;
                  return (
                    <Link key={s.id} href={`/surveys/${s.id}`} className="list-row">
                      <div className="list-row-icon" style={{ background: 'rgba(99,102,241,0.12)' }}>
                        <RiFileTextFill size={16} style={{ color: 'var(--brand)' }} />
                      </div>
                      <div className="list-row-body">
                        <p className="list-row-title">
                          {s.title && !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(s.title) ? s.title : 'Untitled Survey'}
                        </p>
                        <p className="list-row-meta">{s.response_count || 0} responses · {s.question_count || 0} questions</p>
                      </div>
                      <span className={`badge ${status.cls} flex-shrink-0`} style={{ fontSize: 11 }}>{status.label}</span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>

          <div className="card section-card animate-slide-up" style={{ animationDelay: '160ms' }}>
            <div className="section-card-header">
              <h2 className="section-title">Analysis Jobs</h2>
              <Link href="/analysis" className="section-link">
                View all <RiArrowRightFill size={14} />
              </Link>
            </div>

            {loading ? (
              <div className="space-y-3">
                {[1,2,3].map(i => <div key={i} className="skeleton h-16 w-full" />)}
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-10">
                <RiBarChart2Fill size={36} className="mx-auto mb-3" style={{ color: 'var(--text-3)' }} />
                <p style={{ color: 'var(--text-2)', fontSize: 14 }}>No analyses yet</p>
                <Link href="/analysis">
                  <button className="btn btn-primary btn-sm mt-3"><RiFlashlightFill size={14} /> Start analysis</button>
                </Link>
              </div>
            ) : (
              <div className="space-y-2 flex flex-col">
                {jobs.map((j: any) => {
                  const status = STATUS_MAP[j.status] || STATUS_MAP.pending;
                  const Icon = status.icon;
                  return (
                    <Link key={j.id} href={`/analysis/${j.id}`} className="list-row">
                      <div className="list-row-icon" style={{ background: 'rgba(99,102,241,0.08)' }}>
                        <Icon size={16} style={{ color: 'var(--brand)' }} />
                      </div>
                      <div className="list-row-body">
                        <p className="list-row-title">
                          {(() => {
                            const t = j.project_brief?.topic || j.survey_title;
                            if (t && !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(t)) return t;
                            return 'File Upload';
                          })()}
                        </p>
                        <p className="list-row-meta">
                          {j.n_rows ? `${j.n_rows} rows · ${j.n_columns} variables` : 'Pending'}
                        </p>
                      </div>
                      <span className={`badge ${status.cls} flex-shrink-0`} style={{ fontSize: 11 }}>{status.label}</span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="animate-slide-up" style={{ animationDelay: '200ms' }}>
          <p className="section-label">Quick actions</p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {[...QUICK_ACTIONS, MARKETPLACE_ACTION].map(({ icon: Icon, label, desc, href, color }) => (
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
                  <RiArrowRightFill size={16} style={{ color: 'var(--text-3)', flexShrink: 0 }} />
                </div>
              </Link>
            ))}
          </div>
        </div>

        </div>
      </AppLayout>
    );
}

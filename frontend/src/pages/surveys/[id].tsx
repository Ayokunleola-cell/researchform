// src/pages/surveys/[id].tsx
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import AppLayout from '../../components/layout/AppLayout';
import { QRCodeSVG } from 'qrcode.react';
import {
  Copy, Share2, Download, BarChart3, Trash2, Edit,
  Users, Clock, CheckCircle, ArrowRight, FileText,
  FlaskConical, AlertCircle, Link2, ExternalLink, Loader2
} from 'lucide-react';
import { surveysApi, exportApi, analysisApi, downloadBlob } from '../../lib/api';
import toast from 'react-hot-toast';
import clsx from 'clsx';

export default function SurveyDetailPage() {
  const router = useRouter();
  const { id } = router.query as { id: string };
  const [survey, setSurvey] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'overview' | 'responses' | 'share' | 'export'>('overview');
  const [startingAnalysis, setStartingAnalysis] = useState(false);

  const surveyUrl = typeof window !== 'undefined' ? `${window.location.origin}/s/${survey?.slug}` : '';

  useEffect(() => {
    if (!id) return;
    Promise.all([
      surveysApi.get(id),
      surveysApi.stats(id).catch(() => ({ data: { response_count: 0, completion_rate: 0 } })),
    ]).then(([sv, st]) => {
      setSurvey(sv.data);
      setStats(st.data);
    }).finally(() => setLoading(false));
  }, [id]);

  const copyLink = () => {
    navigator.clipboard.writeText(surveyUrl);
    toast.success('Link copied!');
  };

  const handleExport = async (fmt: 'csv' | 'xlsx' | 'sav' | 'codebook') => {
    try {
      const res = await exportApi[fmt](id);
      const ext = fmt === 'codebook' ? 'pdf' : fmt;
      downloadBlob(res.data, `${survey?.title || 'survey'}.${ext}`);
      toast.success(`Exported as .${ext}`);
    } catch {
      toast.error('Export failed');
    }
  };

  const handleStartAnalysis = async () => {
    setStartingAnalysis(true);
    try {
      const res = await analysisApi.startFromSurvey(id, survey?.project_brief);
      toast.success('Analysis started!');
      router.push(`/analysis/${res.data.id}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to start analysis');
    } finally {
      setStartingAnalysis(false);
    }
  };

  const handleClose = async () => {
    if (!confirm('Close this survey? Respondents will no longer be able to submit.')) return;
    await surveysApi.close(id);
    setSurvey((s: any) => ({ ...s, status: 'closed' }));
    toast.success('Survey closed');
  };

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin" size={32} style={{ color: 'var(--brand)' }} />
      </div>
    </AppLayout>
  );

  if (!survey) return (
    <AppLayout>
      <div className="text-center py-20">
        <AlertCircle size={48} className="mx-auto mb-4" style={{ color: 'var(--danger)' }} />
        <p style={{ color: 'var(--text-2)' }}>Survey not found</p>
      </div>
    </AppLayout>
  );

  const STATUS = {
    draft:    { label: 'Draft',    cls: 'badge-neutral', icon: Clock },
    active:   { label: 'Active',   cls: 'badge-success', icon: CheckCircle },
    closed:   { label: 'Closed',   cls: 'badge-warning', icon: AlertCircle },
    analysed: { label: 'Analysed', cls: 'badge-brand',   icon: BarChart3 },
  } as any;
  const status = STATUS[survey.status] || STATUS.draft;

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-start gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--text)' }}>{survey.title}</h1>
              <span className={`badge ${status.cls}`}>{status.label}</span>
            </div>
            <p style={{ color: 'var(--text-2)' }} className="text-sm">{survey.description}</p>
          </div>
          <div className="flex gap-2 ml-auto flex-shrink-0">
            <button className="btn btn-secondary btn-sm" onClick={() => router.push(`/surveys/${id}/edit`)}>
              <Edit size={14} /> Edit
            </button>
            {survey.status === 'active' && (
              <button className="btn btn-secondary btn-sm" onClick={handleClose}>
                Close Survey
              </button>
            )}
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Responses',       value: stats?.response_count || 0,         icon: Users,       color: 'var(--brand)' },
            { label: 'Completion Rate', value: `${stats?.completion_rate || 0}%`,   icon: CheckCircle, color: 'var(--success)' },
            { label: 'Questions',       value: survey.question_count || 0,          icon: FileText,    color: 'var(--info)' },
            { label: 'Avg. Time',       value: stats?.avg_duration || '—',           icon: Clock,       color: 'var(--warning)' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="card p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${color}18` }}>
                <Icon size={20} style={{ color }} />
              </div>
              <div>
                <p className="font-display font-bold text-xl" style={{ color: 'var(--text)' }}>{value}</p>
                <p className="text-xs" style={{ color: 'var(--text-3)' }}>{label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'var(--surface-2)' }}>
          {(['overview', 'share', 'export'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="flex-1 py-2 rounded-lg text-sm font-semibold capitalize transition-all"
              style={tab === t
                ? { background: 'var(--surface)', color: 'var(--brand)', boxShadow: 'var(--shadow)' }
                : { color: 'var(--text-2)', background: 'transparent' }}
            >
              {t}
            </button>
          ))}
        </div>

        {/* ── Overview ── */}
        {tab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in">
            {/* Analyse CTA */}
            <div className="card p-6 border-2" style={{ borderColor: 'var(--brand)', background: 'rgba(99,102,241,0.04)' }}>
              <div className="flex items-center gap-3 mb-3">
                <FlaskConical size={24} style={{ color: 'var(--brand)' }} />
                <h2 className="font-display font-bold" style={{ color: 'var(--text)' }}>Run AI Analysis</h2>
              </div>
              <p className="text-sm mb-4" style={{ color: 'var(--text-2)' }}>
                Push your survey responses through the 9-stage analysis pipeline.
                The AI will select the correct statistical tests, generate Python code,
                run the analysis, and build your Chapter 4.
              </p>
              {stats?.response_count > 0 ? (
                <button
                  className="btn btn-primary w-full"
                  onClick={handleStartAnalysis}
                  disabled={startingAnalysis}
                >
                  {startingAnalysis ? <Loader2 size={16} className="animate-spin" /> : <BarChart3 size={16} />}
                  {startingAnalysis ? 'Starting...' : 'Start Analysis'}
                </button>
              ) : (
                <div className="text-center py-4">
                  <AlertCircle size={24} className="mx-auto mb-2" style={{ color: 'var(--warning)' }} />
                  <p className="text-sm" style={{ color: 'var(--text-3)' }}>
                    Collect at least 1 response before running analysis
                  </p>
                </div>
              )}
            </div>

            {/* Research Brief summary */}
            <div className="card p-6">
              <h2 className="font-display font-semibold mb-4" style={{ color: 'var(--text)' }}>Research Brief</h2>
              {survey.project_brief?.topic ? (
                <div className="space-y-3 text-sm">
                  <div>
                    <span className="label" style={{ display: 'inline', marginRight: 8 }}>Topic:</span>
                    <span style={{ color: 'var(--text)' }}>{survey.project_brief.topic}</span>
                  </div>
                  <div>
                    <span className="label" style={{ display: 'inline', marginRight: 8 }}>Study Type:</span>
                    <span className="badge badge-brand capitalize">{survey.project_brief.study_type}</span>
                  </div>
                  <div>
                    <span className="label">Objectives:</span>
                    <ol className="list-decimal list-inside mt-1 space-y-1">
                      {survey.project_brief.objectives?.filter(Boolean).map((o: string, i: number) => (
                        <li key={i} style={{ color: 'var(--text-2)' }}>{o}</li>
                      ))}
                    </ol>
                  </div>
                  <div>
                    <span className="label">Hypotheses:</span>
                    <ol className="list-none mt-1 space-y-1">
                      {survey.project_brief.hypotheses?.filter(Boolean).map((h: string, i: number) => (
                        <li key={i} style={{ color: 'var(--text-2)' }}>H{i + 1}: {h}</li>
                      ))}
                    </ol>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6">
                  <p className="text-sm" style={{ color: 'var(--text-3)' }}>No research brief added</p>
                  <button className="btn btn-ghost btn-sm mt-2" onClick={() => router.push(`/surveys/${id}/edit?step=brief`)}>
                    Add Brief
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Share ── */}
        {tab === 'share' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in">
            <div className="card p-6 space-y-5">
              <h2 className="font-display font-semibold" style={{ color: 'var(--text)' }}>Share Survey</h2>

              <div>
                <label className="label">Survey Link</label>
                <div className="flex gap-2">
                  <input className="input flex-1 font-mono text-sm" value={surveyUrl} readOnly />
                  <button className="btn btn-secondary" onClick={copyLink}>
                    <Copy size={15} />
                  </button>
                  <a href={surveyUrl} target="_blank" rel="noreferrer">
                    <button className="btn btn-secondary">
                      <ExternalLink size={15} />
                    </button>
                  </a>
                </div>
              </div>

              {survey.status === 'active' ? (
                <div className="p-4 rounded-xl flex items-center gap-3" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)' }}>
                  <CheckCircle size={18} style={{ color: 'var(--success)' }} />
                  <div>
                    <p className="text-sm font-semibold" style={{ color: 'var(--success)' }}>Survey is Active</p>
                    <p className="text-xs" style={{ color: 'var(--text-2)' }}>Respondents can fill this form</p>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }}>
                  <p className="text-sm font-semibold" style={{ color: 'var(--warning)' }}>Survey is {survey.status}</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-2)' }}>Publish the survey to start collecting responses</p>
                </div>
              )}

              <div className="pt-2 space-y-2">
                <p className="text-xs font-semibold" style={{ color: 'var(--text-3)' }}>SHARE VIA</p>
                <div className="flex gap-2">
                  {[
                    { label: 'WhatsApp', color: '#25D366', href: `https://wa.me/?text=${encodeURIComponent(`Please fill this survey: ${surveyUrl}`)}` },
                    { label: 'Email', color: 'var(--brand)', href: `mailto:?subject=Survey&body=${encodeURIComponent(`Please fill this survey: ${surveyUrl}`)}` },
                    { label: 'Copy', color: 'var(--text-2)', onClick: copyLink },
                  ].map(({ label, color, href, onClick }) => (
                    href ? (
                      <a key={label} href={href} target="_blank" rel="noreferrer">
                        <button className="btn btn-secondary btn-sm" style={{ color }}>
                          {label}
                        </button>
                      </a>
                    ) : (
                      <button key={label} className="btn btn-secondary btn-sm" onClick={onClick} style={{ color }}>
                        {label}
                      </button>
                    )
                  ))}
                </div>
              </div>
            </div>

            <div className="card p-6 flex flex-col items-center gap-4">
              <h2 className="font-display font-semibold w-full" style={{ color: 'var(--text)' }}>QR Code</h2>
              <div className="p-4 rounded-xl bg-white">
                <QRCodeSVG value={surveyUrl || 'https://researchform.app'} size={200} />
              </div>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  const svg = document.querySelector('.qr-code svg') as SVGElement;
                  if (!svg) return;
                  const blob = new Blob([svg.outerHTML], { type: 'image/svg+xml' });
                  downloadBlob(blob, 'survey-qr.svg');
                }}
              >
                <Download size={15} />
                Download QR
              </button>
            </div>
          </div>
        )}

        {/* ── Export ── */}
        {tab === 'export' && (
          <div className="animate-fade-in">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {[
                { fmt: 'csv', label: 'CSV', desc: 'Comma-separated values — works with any tool', color: 'var(--success)', ext: '.csv' },
                { fmt: 'xlsx', label: 'Excel (.xlsx)', desc: 'Microsoft Excel format with formatting', color: 'var(--info)', ext: '.xlsx' },
                { fmt: 'sav', label: 'SPSS (.sav)', desc: 'SPSS format with value labels preserved', color: 'var(--warning)', ext: '.sav' },
                { fmt: 'codebook', label: 'Codebook (PDF)', desc: 'Variable definitions and coding guide', color: 'var(--brand)', ext: '.pdf' },
              ].map(({ fmt, label, desc, color, ext }) => (
                <div key={fmt} className="card p-5 flex items-center gap-4 card-hover">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}15` }}>
                    <Download size={22} style={{ color }} />
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold" style={{ color: 'var(--text)' }}>{label}</p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{desc}</p>
                  </div>
                  <button
                    className="btn btn-secondary btn-sm flex-shrink-0"
                    onClick={() => handleExport(fmt as any)}
                  >
                    Export {ext}
                  </button>
                </div>
              ))}
            </div>

            <div className="card p-5 mt-4" style={{ border: '1px solid var(--brand)', background: 'rgba(99,102,241,0.04)' }}>
              <div className="flex items-center gap-3">
                <FlaskConical size={20} style={{ color: 'var(--brand)' }} />
                <div className="flex-1">
                  <p className="font-semibold" style={{ color: 'var(--text)' }}>Direct to Analysis Pipeline</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-2)' }}>
                    Skip the file — push responses directly into the AI analysis engine
                  </p>
                </div>
                <button className="btn btn-primary btn-sm" onClick={handleStartAnalysis} disabled={startingAnalysis || !stats?.response_count}>
                  {startingAnalysis ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
                  Analyse Now
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

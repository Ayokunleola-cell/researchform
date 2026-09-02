// src/pages/surveys/[id].tsx
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import AppLayout from '../../components/layout/AppLayout';
import { QRCodeSVG } from 'qrcode.react';
import {
  RiExternalLinkFill, RiGroupFill, RiArrowRightFill, RiEdit2Fill,
  RiFlaskFill, RiBarChart2Fill, RiErrorWarningFill, RiFileCopyFill,
  RiFileTextFill, RiDownload2Fill, RiDashboardFill,
  RiTimeFill, RiCheckboxCircleFill,
  RiLoader4Line, RiDatabase2Fill, RiCloseFill, RiAlertFill,
  RiInformationFill, RiShieldCheckFill, RiArrowUpFill, RiArrowDownFill,
  RiFlowChart, RiLineChartFill, RiStackFill, RiCheckLine,
  RiListCheck2, RiLightbulbFlashFill, RiBarChartFill, RiCheckFill,
  RiSearchLine, RiBookOpenLine, RiArrowRightSLine,
} from 'react-icons/ri';
import { surveysApi, exportApi, analysisApi, downloadBlob, integrationsApi } from '../../lib/api';
import toast from 'react-hot-toast';
import clsx from 'clsx';

export default function SurveyDetailPage() {
  const router = useRouter();
  const { id } = router.query as { id: string };
  const [survey, setSurvey] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'overview' | 'share' | 'export'>('overview');
  const [startingAnalysis, setStartingAnalysis] = useState(false);
  const [tickingTime, setTickingTime] = useState<string>('-');
  const [checkingReliability, setCheckingReliability] = useState(false);
  const [reliabilityData, setReliabilityData] = useState<any>(null);
  const [showReliabilityModal, setShowReliabilityModal] = useState(false);

  const [checkingPathAnalysis, setCheckingPathAnalysis] = useState(false);
  const [pathAnalysisData, setPathAnalysisData] = useState<any>(null);
  const [showPathAnalysisModal, setShowPathAnalysisModal] = useState(false);

  const [checkingMulticollinearity, setCheckingMulticollinearity] = useState(false);
  const [multicollinearityData, setMulticollinearityData] = useState<any>(null);
  const [showMulticollinearityModal, setShowMulticollinearityModal] = useState(false);

  const [checkingNormality, setCheckingNormality] = useState(false);
  const [normalityData, setNormalityData] = useState<any>(null);
  const [showNormalityModal, setShowNormalityModal] = useState(false);

  const surveyUrl = typeof window !== 'undefined' ? `${window.location.origin}/s/${survey?.slug}` : '';

  useEffect(() => {
    if (!survey || !stats) return;
    if (survey.status !== 'active') {
      setTickingTime(stats.avg_duration || '-');
      return;
    }
    const updateTime = () => {
      const start = new Date(survey.created_at).getTime();
      const now = Date.now();
      const totalSeconds = Math.floor((now - start) / 1000);
      const days = Math.floor(totalSeconds / 86400);
      const hours = Math.floor((totalSeconds % 86400) / 3600);
      const mins = Math.floor((totalSeconds % 3600) / 60);
      let timeStr = '< 1m';
      if (days > 0) timeStr = `${days}d ${hours}h`;
      else if (hours > 0) timeStr = `${hours}h ${mins}m`;
      else if (mins > 0) timeStr = `${mins}m`;
      setTickingTime(timeStr);
    };
    updateTime();
    const interval = setInterval(updateTime, 60000);
    return () => clearInterval(interval);
  }, [survey, stats]);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      surveysApi.get(id),
      surveysApi.stats(id).catch(() => ({ data: { response_count: 0, completion_rate: 0 } })),
    ]).then(([sv, st]) => {
      setSurvey(sv.data);
      setStats(st.data);
    }).catch(() => {
      toast.error('Survey not found or access denied');
      router.push('/dashboard');
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

  const handleIntegrationExport = async (integration: 'drive' | 'sheets' | 'powerbi') => {
    try {
      if (integration === 'drive') {
        toast.loading('Exporting to Google Drive...', { id: 'export' });
        await integrationsApi.google.exportDrive('survey', id);
        toast.success('Successfully exported to Google Drive!', { id: 'export' });
      } else if (integration === 'sheets') {
        toast.loading('Exporting to Google Sheets...', { id: 'export' });
        const res = await integrationsApi.google.exportSheets('survey', id);
        toast.success('Successfully exported to Google Sheets!', { id: 'export' });
        if (res.data.url) window.open(res.data.url, '_blank');
      } else if (integration === 'powerbi') {
        toast.loading('Generating Power BI Link...', { id: 'export' });
        const res = await integrationsApi.powerbi.generateLink('survey', id);
        toast.dismiss('export');
        const url = `${window.location.origin}${res.data.feed_url}`;
        prompt('Copy your Power BI Web Feed URL:\n(Use "Get Data -> Web" in Power BI)', url);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Export failed. Have you connected your account?', { id: 'export' });
    }
  };

  const handleStartAnalysis = () => {
    router.push(`/analysis?surveyId=${id}`);
  };

  const handleClose = async () => {
    if (!confirm('Close this survey? Respondents will no longer be able to submit.')) return;
    await surveysApi.close(id);
    setSurvey((s: any) => ({ ...s, status: 'closed' }));
    toast.success('Survey closed');
  };

  const handleCheckReliability = async () => {
    try {
      setCheckingReliability(true);
      const res = await surveysApi.reliability(id);
      setReliabilityData(res.data);
      setShowReliabilityModal(true);
    } catch {
      toast.error('Failed to check reliability. Please try again.');
    } finally {
      setCheckingReliability(false);
    }
  };

  const handleCheckPathAnalysis = async () => {
    try {
      setCheckingPathAnalysis(true);
      const res = await surveysApi.pathAnalysis(id);
      setPathAnalysisData(res.data);
      setShowPathAnalysisModal(true);
    } catch {
      toast.error('Failed to run path analysis check. Please try again.');
    } finally {
      setCheckingPathAnalysis(false);
    }
  };

  const handleCheckMulticollinearity = async () => {
    try {
      setCheckingMulticollinearity(true);
      const res = await surveysApi.multicollinearity(id);
      setMulticollinearityData(res.data);
      setShowMulticollinearityModal(true);
    } catch {
      toast.error('Failed to run multicollinearity check. Please try again.');
    } finally {
      setCheckingMulticollinearity(false);
    }
  };

  const handleCheckNormality = async () => {
    try {
      setCheckingNormality(true);
      const res = await surveysApi.normality(id);
      setNormalityData(res.data);
      setShowNormalityModal(true);
    } catch {
      toast.error('Failed to run normality check. Please try again.');
    } finally {
      setCheckingNormality(false);
    }
  };

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64">
        <RiLoader4Line className="animate-spin" size={32} style={{ color: 'var(--brand)' }} />
      </div>
    </AppLayout>
  );

  if (!survey) return (
    <AppLayout>
      <div className="text-center py-20">
        <RiErrorWarningFill size={48} className="mx-auto mb-4" style={{ color: 'var(--danger)' }} />
        <p style={{ color: 'var(--text-2)' }}>Survey not found</p>
      </div>
    </AppLayout>
  );

  const STATUS = {
    draft:    { label: 'Draft',    cls: 'badge-neutral' },
    active:   { label: 'Active',   cls: 'badge-success' },
    closed:   { label: 'Closed',   cls: 'badge-warning' },
    analysed: { label: 'Analysed', cls: 'badge-brand'   },
  } as any;
  const status = STATUS[survey.status] || STATUS.draft;

  const isError = reliabilityData?.error;

  return (
    <React.Fragment>
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
                <RiEdit2Fill size={14} /> Edit
              </button>
              {survey.status === 'active' && (
                <button className="btn btn-secondary btn-sm" onClick={handleClose}>Close Survey</button>
              )}
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Responses',       value: stats?.response_count || 0,        icon: RiGroupFill,          color: 'var(--brand)' },
              { label: 'Completion Rate', value: `${stats?.completion_rate || 0}%`, icon: RiCheckboxCircleFill, color: 'var(--success)' },
              { label: 'Questions',       value: survey.question_count || 0,         icon: RiFileTextFill,       color: 'var(--info)' },
              { label: 'Running Time',    value: tickingTime,                         icon: RiTimeFill,           color: 'var(--warning)' },
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

          {/* Overview Tab */}
          {tab === 'overview' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in">

              {/* Run AI Analysis */}
              <div className="card p-6 border-2 flex flex-col" style={{ borderColor: 'var(--brand)', background: 'rgba(99,102,241,0.04)' }}>
                <div className="flex items-center gap-3 mb-3">
                  <RiFlaskFill size={24} style={{ color: 'var(--brand)' }} />
                  <h2 className="font-display font-bold" style={{ color: 'var(--text)' }}>Run AI Analysis</h2>
                </div>
                <p className="text-sm mb-4" style={{ color: 'var(--text-2)' }}>
                  Let AI automatically select the best statistical tests and generate a full research report for your survey data.
                </p>
                <div className="flex-1" />
                {stats?.response_count > 0 ? (
                  <button className="btn btn-primary w-full mt-auto" onClick={handleStartAnalysis} disabled={startingAnalysis}>
                    {startingAnalysis ? <RiLoader4Line size={16} className="animate-spin" /> : <RiBarChart2Fill size={16} />}
                    {startingAnalysis ? 'Starting...' : 'Start Analysis'}
                  </button>
                ) : (
                  <div className="text-center py-4">
                    <RiErrorWarningFill size={24} className="mx-auto mb-2" style={{ color: 'var(--warning)' }} />
                    <p className="text-sm" style={{ color: 'var(--text-3)' }}>
                      Collect at least 1 response before running analysis
                    </p>
                  </div>
                )}
              </div>

              {/* Survey Health Check */}
              <div className="card p-6 border-2 flex flex-col" style={{ borderColor: 'var(--success)', background: 'rgba(16,185,129,0.04)' }}>
                <div className="flex items-center gap-3 mb-3">
                  <RiShieldCheckFill size={24} style={{ color: 'var(--success)' }} />
                  <h2 className="font-display font-bold" style={{ color: 'var(--text)' }}>Survey Health Checks</h2>
                </div>
                <p className="text-sm mb-4" style={{ color: 'var(--text-2)' }}>
                  Run pre-analysis checks to assess your data quality and statistical readiness.
                </p>
                <div className="flex flex-col gap-2">

                  {/* Reliability */}
                  <button
                    className="btn w-full text-white"
                    style={{ background: 'var(--success)' }}
                    onClick={handleCheckReliability}
                    disabled={checkingReliability || !stats?.response_count}
                  >
                    {checkingReliability ? <RiLoader4Line size={16} className="animate-spin" /> : <RiShieldCheckFill size={16} />}
                    {checkingReliability ? 'Running...' : 'Check Reliability (Cronbach\'s α)'}
                  </button>

                  {/* Path Analysis */}
                  <button
                    className="btn w-full text-white"
                    style={{ background: 'var(--info)' }}
                    onClick={handleCheckPathAnalysis}
                    disabled={checkingPathAnalysis || !stats?.response_count}
                  >
                    {checkingPathAnalysis ? <RiLoader4Line size={16} className="animate-spin" /> : <RiFlowChart size={16} />}
                    {checkingPathAnalysis ? 'Running...' : 'Check Path Analysis Readiness'}
                  </button>

                  {/* Multicollinearity */}
                  <button
                    className="btn w-full text-white"
                    style={{ background: 'var(--warning)' }}
                    onClick={handleCheckMulticollinearity}
                    disabled={checkingMulticollinearity || !stats?.response_count}
                  >
                    {checkingMulticollinearity ? <RiLoader4Line size={16} className="animate-spin" /> : <RiStackFill size={16} />}
                    {checkingMulticollinearity ? 'Running...' : 'Check Multicollinearity (VIF)'}
                  </button>

                  {/* Normality */}
                  <button
                    className="btn w-full text-white"
                    style={{ background: '#0891b2' }}
                    onClick={handleCheckNormality}
                    disabled={checkingNormality || !stats?.response_count}
                  >
                    {checkingNormality ? <RiLoader4Line size={16} className="animate-spin" /> : <RiLineChartFill size={16} />}
                    {checkingNormality ? 'Running...' : 'Check Normality (Shapiro-Wilk)'}
                  </button>

                  {/* View last reports */}
                  <div className="flex flex-wrap gap-2 pt-1">
                    {reliabilityData && <button className="btn btn-secondary btn-sm flex-1" onClick={() => setShowReliabilityModal(true)}><RiFileTextFill size={13} /> Reliability</button>}
                    {pathAnalysisData && <button className="btn btn-secondary btn-sm flex-1" onClick={() => setShowPathAnalysisModal(true)}><RiFileTextFill size={13} /> Path</button>}
                    {multicollinearityData && <button className="btn btn-secondary btn-sm flex-1" onClick={() => setShowMulticollinearityModal(true)}><RiFileTextFill size={13} /> VIF</button>}
                    {normalityData && <button className="btn btn-secondary btn-sm flex-1" onClick={() => setShowNormalityModal(true)}><RiFileTextFill size={13} /> Normality</button>}
                  </div>

                </div>
              </div>

            </div>
          )}

          {/* Share Tab */}
          {tab === 'share' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in">
              <div className="card p-6 space-y-5">
                <h2 className="font-display font-semibold" style={{ color: 'var(--text)' }}>Share Survey</h2>
                <div>
                  <label className="label">Survey Link</label>
                  <div className="flex gap-2">
                    <input className="input flex-1 font-mono text-sm" value={surveyUrl} readOnly />
                    <button className="btn btn-secondary" onClick={copyLink}>
                      <RiFileCopyFill size={15} />
                    </button>
                    <a href={surveyUrl} target="_blank" rel="noreferrer">
                      <button className="btn btn-secondary">
                        <RiExternalLinkFill size={15} />
                      </button>
                    </a>
                  </div>
                </div>
                <div className="pt-2 space-y-2">
                  <p className="text-xs font-semibold" style={{ color: 'var(--text-3)' }}>SHARE VIA</p>
                  <div className="flex gap-2">
                    {[
                      { label: 'WhatsApp', color: '#25D366', href: `https://wa.me/?text=${encodeURIComponent('Please fill this survey: ' + surveyUrl)}` },
                      { label: 'Email',    color: 'var(--brand)', href: `mailto:?subject=Survey&body=${encodeURIComponent('Please fill this survey: ' + surveyUrl)}` },
                      { label: 'Copy',     color: 'var(--text-2)', href: null, onClick: copyLink },
                    ].map(({ label, color, href, onClick }: any) => (
                      href ? (
                        <a key={label} href={href} target="_blank" rel="noreferrer">
                          <button className="btn btn-secondary btn-sm" style={{ color }}>{label}</button>
                        </a>
                      ) : (
                        <button key={label} className="btn btn-secondary btn-sm" onClick={onClick} style={{ color }}>{label}</button>
                      )
                    ))}
                  </div>
                </div>
              </div>

              <div className="card p-6 flex flex-col items-center gap-4">
                <h2 className="font-display font-semibold w-full" style={{ color: 'var(--text)' }}>QR Code</h2>
                <div id="survey-qr-code" className="p-4 rounded-xl bg-white">
                  <QRCodeSVG value={surveyUrl || 'https://researchform.app'} size={200} />
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    const svg = document.querySelector('#survey-qr-code svg') as SVGElement;
                    if (!svg) return;
                    const svgData = new XMLSerializer().serializeToString(svg);
                    const canvas = document.createElement('canvas');
                    const PADDING = 40, QR_SIZE = 320, SIZE = QR_SIZE + PADDING * 2;
                    canvas.width = SIZE; canvas.height = SIZE;
                    const ctx = canvas.getContext('2d')!;
                    const img = new Image();
                    img.onload = () => {
                      ctx.fillStyle = '#ffffff';
                      ctx.fillRect(0, 0, SIZE, SIZE);
                      ctx.drawImage(img, PADDING, PADDING, QR_SIZE, QR_SIZE);
                      const a = document.createElement('a');
                      a.download = `${survey?.slug || 'survey'}-qr.png`;
                      a.href = canvas.toDataURL('image/png');
                      a.click();
                    };
                    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
                  }}
                >
                  <RiDownload2Fill size={15} /> Download QR
                </button>
              </div>
            </div>
          )}

          {/* Export Tab */}
          {tab === 'export' && (
            <div className="animate-fade-in">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {[
                  { fmt: 'csv',  label: 'CSV',          desc: 'Comma-separated values, works with any tool', color: 'var(--success)', ext: '.csv' },
                  { fmt: 'xlsx', label: 'Excel (.xlsx)', desc: 'Microsoft Excel format with formatting',      color: 'var(--info)',    ext: '.xlsx' },
                  { fmt: 'sav',  label: 'SPSS (.sav)',   desc: 'SPSS format with value labels preserved',    color: 'var(--warning)', ext: '.sav' },
                ].map(({ fmt, label, desc, color, ext }) => (
                  <div key={fmt} className="card p-5 flex items-center gap-4 card-hover">
                    <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}15` }}>
                      <RiDownload2Fill size={22} style={{ color }} />
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold" style={{ color: 'var(--text)' }}>{label}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{desc}</p>
                    </div>
                    <button className="btn btn-secondary btn-sm flex-shrink-0" onClick={() => handleExport(fmt as any)}>
                      Export {ext}
                    </button>
                  </div>
                ))}
              </div>

              <h3 className="font-display font-semibold mt-8 mb-4" style={{ color: 'var(--text)' }}>External Integrations</h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {[
                  { key: 'drive',   label: 'Google Drive',  desc: 'Upload CSV directly to your Drive',     color: '#1fa463', icon: RiDatabase2Fill },
                  { key: 'sheets',  label: 'Google Sheets', desc: 'Open directly in a new Google Sheet',   color: '#1fa463', icon: RiFileTextFill },
                  { key: 'powerbi', label: 'Power BI',      desc: 'Generate live web feed for dashboards', color: '#f2c811', icon: RiDashboardFill },
                ].map(({ key, label, desc, color, icon: Icon }) => (
                  <div key={key} className="card p-5 flex items-center gap-4 card-hover">
                    <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}15` }}>
                      <Icon size={22} style={{ color }} />
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold" style={{ color: 'var(--text)' }}>{label}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{desc}</p>
                    </div>
                    <button className="btn btn-secondary btn-sm flex-shrink-0" onClick={() => handleIntegrationExport(key as any)}>
                      Connect
                    </button>
                  </div>
                ))}
              </div>

              <div className="card p-5 mt-4" style={{ border: '1px solid var(--brand)', background: 'rgba(99,102,241,0.04)' }}>
                <div className="flex items-center gap-3">
                  <RiFlaskFill size={20} style={{ color: 'var(--brand)' }} />
                  <div className="flex-1">
                    <p className="font-semibold" style={{ color: 'var(--text)' }}>Direct to Analysis Pipeline</p>
                  </div>
                  <button className="btn btn-primary btn-sm" onClick={handleStartAnalysis} disabled={startingAnalysis || !stats?.response_count}>
                    {startingAnalysis ? <RiLoader4Line size={14} className="animate-spin" /> : <RiArrowRightFill size={14} />}
                    Analyse Now
                  </button>
                </div>
              </div>
            </div>
          )}

        </div>
      </AppLayout>

      {/* Reliability Report Modal */}
      {showReliabilityModal && reliabilityData && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }}
          onClick={() => setShowReliabilityModal(false)}
        >
          <div
            className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b" style={{ borderColor: 'var(--border)' }}>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: isError ? 'rgba(239,68,68,0.12)' : 'rgba(16,185,129,0.12)' }}>
                  {isError
                    ? <RiAlertFill size={22} style={{ color: 'var(--danger)' }} />
                    : <RiShieldCheckFill size={22} style={{ color: 'var(--success)' }} />
                  }
                </div>
                <div>
                  <h2 className="font-display font-bold text-lg" style={{ color: 'var(--text)' }}>Reliability Analysis Report</h2>
                  <p className="text-xs" style={{ color: 'var(--text-3)' }}>{survey?.title}</p>
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowReliabilityModal(false)} style={{ padding: '6px' }}>
                <RiCloseFill size={18} />
              </button>
            </div>

            <div className="p-6 space-y-6">

              {/* Error state */}
              {isError && (
                <div className="rounded-xl p-5 border-2" style={{ borderColor: 'var(--danger)', background: 'rgba(239,68,68,0.05)' }}>
                  <div className="flex gap-3 items-start">
                    <RiAlertFill size={22} className="shrink-0 mt-0.5" style={{ color: 'var(--danger)' }} />
                    <div>
                      <p className="font-semibold text-sm mb-1" style={{ color: 'var(--danger)' }}>Cannot Calculate Reliability</p>
                      <p className="text-sm" style={{ color: 'var(--text-2)' }}>{reliabilityData.error}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Per-Construct Mode */}
              {!isError && reliabilityData.mode === 'per_construct' && (
                <>
                  {/* Overall Summary Banner */}
                  <div className="rounded-xl p-5 border-2" style={{
                    borderColor: (reliabilityData.n_passing ?? 0) === reliabilityData.n_constructs ? 'var(--success)' : 'var(--danger)',
                    background: (reliabilityData.n_passing ?? 0) === reliabilityData.n_constructs ? 'rgba(16,185,129,0.05)' : 'rgba(239,68,68,0.05)',
                  }}>
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-widest mb-1" style={{ color: 'var(--text-3)' }}>Overall Reliability</p>
                        <p className="font-display font-bold text-4xl" style={{ color: (reliabilityData.n_passing ?? 0) === reliabilityData.n_constructs ? 'var(--success)' : 'var(--danger)' }}>
                          α = {reliabilityData.avg_alpha ?? '—'}
                        </p>
                        <p className="text-sm font-semibold mt-1" style={{ color: 'var(--text-2)' }}>
                          {reliabilityData.n_passing}/{reliabilityData.n_constructs} constructs ≥ 0.70
                        </p>
                      </div>
                      {(reliabilityData.n_passing ?? 0) === reliabilityData.n_constructs
                        ? <RiShieldCheckFill size={52} style={{ color: 'var(--success)', opacity: 0.2 }} />
                        : <RiAlertFill size={52} style={{ color: 'var(--danger)', opacity: 0.2 }} />
                      }
                    </div>
                    <p className="text-sm" style={{ color: 'var(--text-2)' }}>{reliabilityData.overall_verdict}</p>
                  </div>

                  {/* Method note */}
                  {reliabilityData.note && (
                    <div className="flex gap-2 items-start rounded-xl p-3 text-xs border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--text-3)' }}>
                      <RiInformationFill size={14} className="shrink-0 mt-0.5" style={{ color: 'var(--brand)' }} />
                      <span>{reliabilityData.note}</span>
                    </div>
                  )}

                  {/* Per-Construct Cards */}
                  {reliabilityData.constructs?.map((c: any, ci: number) => {
                    const passing = !c.error && c.alpha >= 0.70;
                    const flagConfig: Record<string, { color: string; Icon: any; label: string }> = {
                      negative_corr: { color: '#ef4444', Icon: RiArrowDownFill,    label: 'Negative r' },
                      very_low_r:    { color: '#f97316', Icon: RiAlertFill,        label: 'Very Low r' },
                      drops_alpha:   { color: '#eab308', Icon: RiArrowUpFill,      label: 'Hurts α'    },
                      low_r:         { color: '#f59e0b', Icon: RiAlertFill,        label: 'Low r'      },
                      ok:            { color: 'var(--success)', Icon: RiShieldCheckFill, label: 'OK'   },
                    };
                    return (
                      <div key={ci} className="rounded-xl border overflow-hidden" style={{ borderColor: passing ? 'rgba(16,185,129,0.3)' : c.error ? 'var(--border)' : 'rgba(239,68,68,0.3)' }}>
                        {/* Construct Header */}
                        <div className="p-4 flex items-start justify-between" style={{ background: passing ? 'rgba(16,185,129,0.05)' : c.error ? 'var(--surface-2)' : 'rgba(239,68,68,0.05)' }}>
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: passing ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)', color: passing ? 'var(--success)' : 'var(--danger)' }}>
                                {c.construct}
                              </span>
                              <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{c.name}</p>
                            </div>
                            {c.error
                              ? <p className="text-xs" style={{ color: 'var(--danger)' }}>{c.error}</p>
                              : <p className="text-xs" style={{ color: 'var(--text-3)' }}>{c.n_items} items · n = {c.n_respondents} · {c.method}</p>
                            }
                          </div>
                          {!c.error && (
                            <div className="text-right">
                              <p className="font-display font-bold text-2xl" style={{ color: passing ? 'var(--success)' : 'var(--danger)' }}>
                                {c.alpha}
                              </p>
                              <p className="text-xs" style={{ color: 'var(--text-3)' }}>{c.interpretation}</p>
                            </div>
                          )}
                        </div>

                        {!c.error && (
                          <div className="p-4 space-y-3">
                            {/* Multi-metric row */}
                            <div className="grid grid-cols-4 gap-2">
                              {[
                                { label: "Cronbach's α", value: c.alpha },
                                { label: "McDonald's ω", value: c.omega ?? '—' },
                                { label: 'Split-Half', value: c.split_half ?? '—' },
                                { label: 'Avg Inter-Item r', value: c.aiic ?? '—' },
                              ].map(({ label, value }) => (
                                <div key={label} className="text-center rounded-lg p-2 border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                                  <p className="font-bold text-sm" style={{ color: 'var(--text)' }}>{value}</p>
                                  <p className="text-xs leading-tight mt-0.5" style={{ color: 'var(--text-3)' }}>{label}</p>
                                </div>
                              ))}
                            </div>

                            {/* AIIC interpretation */}
                            {c.aiic_interp && c.aiic_interp !== 'N/A' && (
                              <p className="text-xs italic" style={{ color: 'var(--text-3)' }}>
                                <RiInformationFill size={12} className="inline mr-1" style={{ color: 'var(--brand)' }} />
                                Inter-item correlation: {c.aiic_interp}
                              </p>
                            )}

                            {/* CI */}
                            {c.alpha_ci_lower != null && (
                              <p className="text-xs" style={{ color: 'var(--text-3)' }}>
                                95% CI for α: [{c.alpha_ci_lower}, {c.alpha_ci_upper}]
                              </p>
                            )}

                            {/* Verdict */}
                            <div className="rounded-lg p-3 text-xs" style={{ background: 'var(--surface-2)', color: 'var(--text-2)' }}>
                              {c.verdict}
                            </div>

                            {/* Item diagnostics table */}
                            {c.diagnostics?.length > 0 && (
                              <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                                <div className="grid grid-cols-12 gap-1 px-3 py-2 text-xs font-bold uppercase tracking-wider" style={{ background: 'var(--surface-2)', color: 'var(--text-3)', borderBottom: '1px solid var(--border)' }}>
                                  <span className="col-span-4">Item</span>
                                  <span className="col-span-1 text-center">Mean</span>
                                  <span className="col-span-1 text-center">SD</span>
                                  <span className="col-span-2 text-center">Item-r</span>
                                  <span className="col-span-2 text-center">α–del</span>
                                  <span className="col-span-2 text-center">Status</span>
                                </div>
                                {c.diagnostics.map((diag: any, di: number) => {
                                  const cfg = flagConfig[diag.flag || 'ok'] || flagConfig['ok'];
                                  return (
                                    <div key={di}>
                                      <div className="grid grid-cols-12 gap-1 px-3 py-2 text-xs items-center" style={{ borderTop: '1px solid var(--border)', background: diag.flag !== 'ok' ? `${cfg.color}08` : 'transparent' }}>
                                        <span className="col-span-4 font-medium truncate" title={diag.label} style={{ color: 'var(--text)' }}>{diag.label || diag.item}</span>
                                        <span className="col-span-1 text-center" style={{ color: 'var(--text-2)' }}>{diag.mean}</span>
                                        <span className="col-span-1 text-center" style={{ color: 'var(--text-2)' }}>{diag.std}</span>
                                        <span className="col-span-2 text-center font-semibold" style={{ color: (diag.item_total_corr != null && diag.item_total_corr < 0.30) ? '#ef4444' : 'var(--text)' }}>
                                          {diag.item_total_corr ?? 'n/a'}
                                        </span>
                                        <span className="col-span-2 text-center font-semibold" style={{ color: diag.improves_alpha ? '#ef4444' : 'var(--text-2)' }}>
                                          {diag.alpha_if_deleted ?? 'n/a'}
                                        </span>
                                        <span className="col-span-2 flex items-center justify-center gap-1 font-semibold" style={{ color: cfg.color }}>
                                          <cfg.Icon size={11} />{cfg.label}
                                        </span>
                                      </div>
                                      {diag.recommendation && diag.flag !== 'ok' && (
                                        <div className="px-3 py-1.5 text-xs italic" style={{ color: 'var(--text-3)', background: `${cfg.color}06`, borderTop: '1px solid var(--border)' }}>
                                          <RiInformationFill size={11} className="inline mr-1" style={{ color: cfg.color }} />
                                          {diag.recommendation}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </>
              )}

              {/* Legacy single-scale fallback (if backend somehow returns old format) */}
              {!isError && reliabilityData.mode !== 'per_construct' && (
                <div className="rounded-xl p-5 border-2" style={{
                  borderColor: reliabilityData.overall_alpha >= 0.70 ? 'var(--success)' : 'var(--danger)',
                  background: reliabilityData.overall_alpha >= 0.70 ? 'rgba(16,185,129,0.05)' : 'rgba(239,68,68,0.05)',
                }}>
                  <p className="font-display font-bold text-4xl" style={{ color: reliabilityData.overall_alpha >= 0.70 ? 'var(--success)' : 'var(--danger)' }}>
                    {reliabilityData.overall_alpha}
                  </p>
                  <p className="text-sm mt-1" style={{ color: 'var(--text-2)' }}>{reliabilityData.verdict}</p>
                </div>
              )}

              {/* Footer Actions */}
              <div className="flex gap-3 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                <button className="btn btn-secondary flex-1" onClick={() => setShowReliabilityModal(false)}>
                  Close
                </button>
                {!isError && (
                  <button
                    className="btn btn-primary flex-1"
                    onClick={() => { setShowReliabilityModal(false); handleStartAnalysis(); }}
                  >
                    <RiBarChart2Fill size={15} /> Run Full Analysis
                  </button>
                )}
              </div>

            </div>
          </div>
        </div>
      )}

      {/* ─── Path Analysis Modal ─────────────────────────────────────── */}
      {showPathAnalysisModal && pathAnalysisData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }} onClick={() => setShowPathAnalysisModal(false)}>
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }} onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-6 border-b" style={{ borderColor: 'var(--border)' }}>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: pathAnalysisData.error ? 'rgba(239,68,68,0.12)' : 'rgba(59,130,246,0.12)' }}>
                  {pathAnalysisData.error ? <RiAlertFill size={22} style={{ color: 'var(--danger)' }} /> : <RiFlowChart size={22} style={{ color: 'var(--info)' }} />}
                </div>
                <div>
                  <h2 className="font-display font-bold text-lg" style={{ color: 'var(--text)' }}>Path Analysis Readiness Check</h2>
                  <p className="text-xs" style={{ color: 'var(--text-3)' }}>{survey?.title}</p>
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowPathAnalysisModal(false)} style={{ padding: '6px' }}><RiCloseFill size={18} /></button>
            </div>
            <div className="p-6 space-y-5">
              {pathAnalysisData.error ? (
                <div className="rounded-xl p-5 border-2" style={{ borderColor: 'var(--danger)', background: 'rgba(239,68,68,0.05)' }}>
                  <div className="flex gap-3 items-start">
                    <RiAlertFill size={22} className="shrink-0 mt-0.5" style={{ color: 'var(--danger)' }} />
                    <div>
                      <p className="font-semibold text-sm mb-1" style={{ color: 'var(--danger)' }}>Check Failed</p>
                      <p className="text-sm" style={{ color: 'var(--text-2)' }}>{pathAnalysisData.error}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  {/* Readiness Banner */}
                  <div className="rounded-xl p-5 border-2" style={{
                    borderColor: pathAnalysisData.readiness === 'ready' ? 'var(--success)' : pathAnalysisData.readiness === 'caution' ? '#f59e0b' : 'var(--danger)',
                    background: pathAnalysisData.readiness === 'ready' ? 'rgba(16,185,129,0.05)' : pathAnalysisData.readiness === 'caution' ? 'rgba(245,158,11,0.05)' : 'rgba(239,68,68,0.05)',
                  }}>
                    <div className="flex items-center gap-3 mb-2">
                      {pathAnalysisData.readiness === 'ready'
                        ? <RiCheckboxCircleFill size={28} style={{ color: 'var(--success)' }} />
                        : pathAnalysisData.readiness === 'caution'
                        ? <RiAlertFill size={28} style={{ color: '#f59e0b' }} />
                        : <RiErrorWarningFill size={28} style={{ color: 'var(--danger)' }} />}
                      <div>
                        <p className="font-display font-bold text-lg" style={{ color: 'var(--text)' }}>
                          {pathAnalysisData.readiness === 'ready' ? 'Ready for Path Analysis' : pathAnalysisData.readiness === 'caution' ? 'Proceed with Caution' : 'Not Ready'}
                        </p>
                        <p className="text-xs" style={{ color: 'var(--text-3)' }}>
                          {pathAnalysisData.n_passed} passed · {pathAnalysisData.n_failed} failed · {pathAnalysisData.n_critical} critical issue(s)
                        </p>
                      </div>
                    </div>
                    <p className="text-sm" style={{ color: 'var(--text-2)' }}>{pathAnalysisData.verdict}</p>
                  </div>

                  {/* Stats Row */}
                  <div className="grid grid-cols-4 gap-2">
                    {[
                      { label: 'Respondents', value: pathAnalysisData.n_respondents, Icon: RiGroupFill },
                      { label: 'Complete Cases', value: pathAnalysisData.n_complete_cases, Icon: RiCheckboxCircleFill },
                      { label: 'Scale Vars', value: pathAnalysisData.n_usable_variables, Icon: RiLineChartFill },
                      { label: 'Est. Paths', value: pathAnalysisData.n_paths_estimated, Icon: RiFlowChart },
                    ].map(({ label, value, Icon }) => (
                      <div key={label} className="rounded-xl p-3 text-center border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                        <Icon size={16} className="mx-auto mb-1" style={{ color: 'var(--info)' }} />
                        <p className="font-display font-bold text-lg" style={{ color: 'var(--text)' }}>{value}</p>
                        <p className="text-xs" style={{ color: 'var(--text-3)' }}>{label}</p>
                      </div>
                    ))}
                  </div>

                  {/* Requirements Checklist */}
                  <div>
                    <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2" style={{ color: 'var(--text)' }}><RiListCheck2 size={15} style={{ color: 'var(--brand)' }} /> Requirements Checklist (10 Criteria)</h3>
                    <div className="space-y-2">
                      {pathAnalysisData.requirements?.map((req: any, i: number) => {
                        const borderCol = req.passed === true ? 'rgba(16,185,129,0.4)' : req.passed === false ? (req.severity === 'critical' || req.severity === 'high' ? 'rgba(239,68,68,0.5)' : 'rgba(245,158,11,0.4)') : 'rgba(99,102,241,0.3)';
                        const bgCol = req.passed === true ? 'rgba(16,185,129,0.04)' : req.passed === false ? 'rgba(239,68,68,0.04)' : 'rgba(99,102,241,0.03)';
                        return (
                          <div key={i} className="rounded-xl border p-4" style={{ borderColor: borderCol, background: bgCol }}>
                            <div className="flex items-start gap-3">
                              {req.passed === true
                                ? <RiCheckboxCircleFill size={18} className="shrink-0 mt-0.5" style={{ color: 'var(--success)' }} />
                                : req.passed === false
                                ? <RiErrorWarningFill size={18} className="shrink-0 mt-0.5" style={{ color: req.severity === 'critical' || req.severity === 'high' ? 'var(--danger)' : '#f59e0b' }} />
                                : <RiInformationFill size={18} className="shrink-0 mt-0.5" style={{ color: 'var(--brand)' }} />}
                              <div className="flex-1">
                                <div className="flex items-center gap-2 flex-wrap mb-0.5">
                                  <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{req.name}</p>
                                  {req.severity && req.severity !== 'ok' && req.severity !== 'info' && req.passed === false && (
                                    <span className="text-xs px-1.5 py-0.5 rounded font-bold uppercase" style={{
                                      background: req.severity === 'critical' ? 'rgba(239,68,68,0.2)' : req.severity === 'high' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)',
                                      color: req.severity === 'critical' || req.severity === 'high' ? 'var(--danger)' : '#f59e0b',
                                    }}>{req.severity}</span>
                                  )}
                                </div>
                                <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{req.detail}</p>
                                {req.recommendation && <p className="text-xs mt-1.5 italic flex items-start gap-1" style={{ color: req.passed === false ? 'var(--danger)' : '#f59e0b' }}><RiLightbulbFlashFill size={12} className="shrink-0 mt-0.5" />{req.recommendation}</p>}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Normality per Variable */}
                  {pathAnalysisData.normality_per_variable?.length > 0 && (
                    <div>
                      <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2" style={{ color: 'var(--text)' }}><RiBarChartFill size={15} style={{ color: 'var(--brand)' }} /> Normality per Variable</h3>
                      <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                        <div className="grid grid-cols-12 gap-1 px-3 py-2 text-xs font-bold uppercase tracking-wider" style={{ background: 'var(--surface-2)', color: 'var(--text-3)' }}>
                          <span className="col-span-4">Variable</span>
                          <span className="col-span-2 text-center">Skew</span>
                          <span className="col-span-2 text-center">Kurt.</span>
                          <span className="col-span-2 text-center">SW p</span>
                          <span className="col-span-2 text-center">Status</span>
                        </div>
                        {pathAnalysisData.normality_per_variable.map((nr: any, i: number) => (
                          <div key={i} className="grid grid-cols-12 gap-1 px-3 py-2 text-xs items-center" style={{ borderTop: '1px solid var(--border)', background: nr.is_normal ? 'transparent' : 'rgba(239,68,68,0.04)' }}>
                            <span className="col-span-4 truncate font-medium" style={{ color: 'var(--text)' }}>{nr.label}</span>
                            <span className="col-span-2 text-center" style={{ color: !nr.skew_ok ? 'var(--danger)' : 'var(--text-2)' }}>{nr.skewness}</span>
                            <span className="col-span-2 text-center" style={{ color: !nr.kurt_ok ? 'var(--danger)' : 'var(--text-2)' }}>{nr.kurtosis}</span>
                            <span className="col-span-2 text-center" style={{ color: nr.sw_p !== null ? (nr.sw_ok ? 'var(--success)' : 'var(--danger)') : 'var(--text-3)' }}>
                              {nr.sw_p !== null ? nr.sw_p : 'n/a'}
                            </span>
                            <span className="col-span-2 text-center font-semibold" style={{ color: nr.is_normal ? 'var(--success)' : 'var(--danger)' }}>
                              {nr.is_normal ? <RiCheckFill size={13} /> : <RiCloseFill size={13} />}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Outlier Summary */}
                  {pathAnalysisData.outlier_summary && !pathAnalysisData.outlier_summary.error && (
                    <div className="rounded-xl border p-4" style={{
                      borderColor: pathAnalysisData.outlier_summary.severity === 'ok' ? 'rgba(16,185,129,0.4)' : pathAnalysisData.outlier_summary.severity === 'moderate' ? 'rgba(245,158,11,0.4)' : 'rgba(239,68,68,0.4)',
                      background: pathAnalysisData.outlier_summary.severity === 'ok' ? 'rgba(16,185,129,0.04)' : pathAnalysisData.outlier_summary.severity === 'moderate' ? 'rgba(245,158,11,0.04)' : 'rgba(239,68,68,0.04)',
                    }}>
                      <p className="font-semibold text-sm mb-1 flex items-center gap-2" style={{ color: 'var(--text)' }}><RiSearchLine size={14} /> Outlier Detection ({pathAnalysisData.outlier_summary.threshold})</p>
                      <p className="text-xs" style={{ color: 'var(--text-2)' }}>{pathAnalysisData.outlier_summary.note}</p>
                    </div>
                  )}

                  {/* High Correlations (Multicollinearity) */}
                  {pathAnalysisData.high_correlations?.length > 0 && (
                    <div>
                      <h3 className="font-display font-semibold text-sm mb-2 flex items-center gap-2" style={{ color: 'var(--text)' }}><RiAlertFill size={14} style={{ color: 'var(--danger)' }} /> High Intercorrelations (r ≥ 0.85) — Multicollinearity Risk</h3>
                      <div className="space-y-2">
                        {pathAnalysisData.high_correlations.map((hc: any, i: number) => (
                          <div key={i} className="rounded-xl border p-3 flex items-center justify-between text-sm" style={{ borderColor: 'rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.04)' }}>
                            <span style={{ color: 'var(--text-2)' }}>{hc.label_a} ↔ {hc.label_b}</span>
                            <span className="font-bold ml-4" style={{ color: 'var(--danger)' }}>r = {hc.r}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Linearity Correlation Matrix */}
                  {pathAnalysisData.linearity_checks?.length > 0 && (
                    <div>
                      <h3 className="font-display font-semibold text-sm mb-3 flex items-center gap-2" style={{ color: 'var(--text)' }}><RiLineChartFill size={15} style={{ color: 'var(--brand)' }} /> Pairwise Correlations (Linearity Evidence)</h3>
                      <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                        <div className="grid grid-cols-12 gap-1 px-3 py-2 text-xs font-bold uppercase tracking-wider" style={{ background: 'var(--surface-2)', color: 'var(--text-3)' }}>
                          <span className="col-span-4">Variable A</span>
                          <span className="col-span-4">Variable B</span>
                          <span className="col-span-2 text-center">r</span>
                          <span className="col-span-2 text-center">Strength</span>
                        </div>
                        {pathAnalysisData.linearity_checks.map((lc: any, i: number) => (
                          <div key={i} className="grid grid-cols-12 gap-1 px-3 py-2 text-xs items-center" style={{ borderTop: '1px solid var(--border)', background: lc.problematic_mc ? 'rgba(239,68,68,0.04)' : 'transparent' }}>
                            <span className="col-span-4 truncate" style={{ color: 'var(--text-2)' }}>{lc.label_a}</span>
                            <span className="col-span-4 truncate" style={{ color: 'var(--text-2)' }}>{lc.label_b}</span>
                            <span className="col-span-2 text-center font-semibold" style={{ color: lc.sig ? (lc.problematic_mc ? 'var(--danger)' : 'var(--success)') : 'var(--text-3)' }}>
                              {lc.r}{lc.sig ? '*' : ''}
                            </span>
                            <span className="col-span-2 text-center capitalize" style={{ color: lc.strength === 'negligible' ? 'var(--text-3)' : lc.strength === 'very_strong' || lc.problematic_mc ? 'var(--danger)' : 'var(--text-2)' }}>
                              {lc.strength?.replace('_', ' ')}
                            </span>
                          </div>
                        ))}
                      </div>
                      <p className="text-xs mt-1 italic" style={{ color: 'var(--text-3)' }}>* p &lt; .05. Red = r ≥ 0.85 (multicollinearity concern).</p>
                    </div>
                  )}

                  {/* Guidance Box */}
                  {pathAnalysisData.guidance && (
                    <div className="rounded-xl border p-4 space-y-3" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                      <p className="font-semibold text-sm flex items-center gap-2" style={{ color: 'var(--text)' }}><RiBookOpenLine size={15} style={{ color: 'var(--brand)' }} /> Path Analysis Guidance</p>

                      <div>
                        <p className="text-xs font-semibold mb-1" style={{ color: 'var(--text-3)' }}>KEY OUTPUTS TO REPORT</p>
                        <ul className="text-xs space-y-0.5" style={{ color: 'var(--text-2)' }}>
                          {pathAnalysisData.guidance.key_outputs_to_report?.map((item: string, i: number) => (
                            <li key={i} className="flex items-start gap-1"><RiArrowRightSLine size={13} className="shrink-0 mt-0.5" />{item}</li>
                          ))}
                        </ul>
                      </div>
                      {pathAnalysisData.guidance.effect_size_benchmarks && (
                        <div>
                          <p className="text-xs font-semibold mb-1" style={{ color: 'var(--text-3)' }}>EFFECT SIZE BENCHMARKS</p>
                          <p className="text-xs" style={{ color: 'var(--text-2)' }}>Path β: {pathAnalysisData.guidance.effect_size_benchmarks.direct_path}</p>
                          <p className="text-xs mt-0.5" style={{ color: 'var(--text-2)' }}>Fit: {pathAnalysisData.guidance.effect_size_benchmarks.fit_indices}</p>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
              <div className="flex gap-3 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                <button className="btn btn-secondary flex-1" onClick={() => setShowPathAnalysisModal(false)}>Close</button>
                {!pathAnalysisData.error && <button className="btn btn-primary flex-1" onClick={() => { setShowPathAnalysisModal(false); handleStartAnalysis(); }}><RiBarChart2Fill size={15} /> Run Full Analysis</button>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── Multicollinearity Modal ─────────────────────────────────── */}
      {showMulticollinearityModal && multicollinearityData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }} onClick={() => setShowMulticollinearityModal(false)}>
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }} onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-6 border-b" style={{ borderColor: 'var(--border)' }}>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(245,158,11,0.12)' }}>
                  <RiStackFill size={22} style={{ color: 'var(--warning)' }} />
                </div>
                <div>
                  <h2 className="font-display font-bold text-lg" style={{ color: 'var(--text)' }}>Multicollinearity Check (VIF)</h2>
                  <p className="text-xs" style={{ color: 'var(--text-3)' }}>{survey?.title}</p>
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowMulticollinearityModal(false)} style={{ padding: '6px' }}><RiCloseFill size={18} /></button>
            </div>
            <div className="p-6 space-y-5">
              {multicollinearityData.error ? (
                <div className="rounded-xl p-5 border-2" style={{ borderColor: 'var(--danger)', background: 'rgba(239,68,68,0.05)' }}>
                  <div className="flex gap-3 items-start">
                    <RiAlertFill size={22} className="shrink-0 mt-0.5" style={{ color: 'var(--danger)' }} />
                    <div>
                      <p className="font-semibold text-sm mb-1" style={{ color: 'var(--danger)' }}>Check Failed</p>
                      <p className="text-sm" style={{ color: 'var(--text-2)' }}>{multicollinearityData.error}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  {/* Verdict Banner */}
                  <div className="rounded-xl p-5 border-2" style={{
                    borderColor: multicollinearityData.severity_overall === 'ok' ? 'var(--success)' : multicollinearityData.severity_overall === 'moderate' ? '#f59e0b' : 'var(--danger)',
                    background: multicollinearityData.severity_overall === 'ok' ? 'rgba(16,185,129,0.05)' : multicollinearityData.severity_overall === 'moderate' ? 'rgba(245,158,11,0.05)' : 'rgba(239,68,68,0.05)',
                  }}>
                    <p className="font-display font-bold text-lg mb-1" style={{ color: 'var(--text)' }}>
                      {multicollinearityData.severity_overall === 'ok' ? '✅ No Multicollinearity' : multicollinearityData.severity_overall === 'moderate' ? '⚠️ Moderate Multicollinearity' : '🚨 Serious Multicollinearity'}
                    </p>
                    <p className="text-sm" style={{ color: 'var(--text-2)' }}>{multicollinearityData.verdict}</p>
                  </div>

                  {/* Stats Row */}
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: 'Variables', value: multicollinearityData.n_variables, Icon: RiStackFill },
                      { label: 'High VIF (≥10)', value: multicollinearityData.n_high_vif, Icon: RiAlertFill },
                      { label: 'High-r Pairs', value: multicollinearityData.n_high_correlations, Icon: RiLineChartFill },
                    ].map(({ label, value, Icon }) => (
                      <div key={label} className="rounded-xl p-4 text-center border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                        <Icon size={18} className="mx-auto mb-1" style={{ color: 'var(--warning)' }} />
                        <p className="font-display font-bold text-xl" style={{ color: 'var(--text)' }}>{value}</p>
                        <p className="text-xs" style={{ color: 'var(--text-3)' }}>{label}</p>
                      </div>
                    ))}
                  </div>

                  {/* VIF Table */}
                  {multicollinearityData.vif_results?.length > 0 && (
                    <div>
                      <h3 className="font-display font-semibold text-sm mb-3" style={{ color: 'var(--text)' }}>VIF per Variable</h3>
                      <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                        <div className="grid grid-cols-12 gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider" style={{ background: 'var(--surface-2)', color: 'var(--text-3)' }}>
                          <span className="col-span-5">Variable</span>
                          <span className="col-span-2 text-center">VIF</span>
                          <span className="col-span-2 text-center">Tolerance</span>
                          <span className="col-span-3 text-center">Status</span>
                        </div>
                        {multicollinearityData.vif_results.map((v: any, i: number) => {
                          const color = v.severity === 'high' ? 'var(--danger)' : v.severity === 'moderate' ? '#f59e0b' : 'var(--success)';
                          return (
                            <div key={i} className="grid grid-cols-12 gap-2 px-4 py-3 text-xs items-center" style={{ borderTop: '1px solid var(--border)', background: v.severity !== 'ok' ? `${color}08` : 'transparent' }}>
                              <span className="col-span-5 truncate font-medium" style={{ color: 'var(--text)' }}>{v.label}</span>
                              <span className="col-span-2 text-center font-bold" style={{ color }}>{v.vif}</span>
                              <span className="col-span-2 text-center" style={{ color: 'var(--text-3)' }}>{v.tolerance}</span>
                              <span className="col-span-3 text-center font-semibold" style={{ color }}>{v.severity === 'high' ? 'High ⚠️' : v.severity === 'moderate' ? 'Moderate' : 'OK ✓'}</span>
                            </div>
                          );
                        })}
                      </div>
                      <p className="text-xs mt-2 italic" style={{ color: 'var(--text-3)' }}>Thresholds: VIF &lt; 5 = OK, 5–10 = Moderate, &gt; 10 = Serious. Tolerance = 1/VIF.</p>
                    </div>
                  )}

                  {/* High Correlations */}
                  {multicollinearityData.high_correlations?.length > 0 && (
                    <div>
                      <h3 className="font-display font-semibold text-sm mb-3" style={{ color: 'var(--text)' }}>High Bivariate Correlations (r ≥ 0.70)</h3>
                      <div className="space-y-2">
                        {multicollinearityData.high_correlations.map((hc: any, i: number) => (
                          <div key={i} className="rounded-xl border p-3 flex items-center justify-between text-sm" style={{ borderColor: hc.severity === 'high' ? 'rgba(239,68,68,0.4)' : 'rgba(245,158,11,0.4)', background: hc.severity === 'high' ? 'rgba(239,68,68,0.04)' : 'rgba(245,158,11,0.04)' }}>
                            <span style={{ color: 'var(--text-2)' }}>{hc.label_a} ↔ {hc.label_b}</span>
                            <span className="font-bold ml-4" style={{ color: hc.severity === 'high' ? 'var(--danger)' : '#f59e0b' }}>r = {hc.r}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
              <div className="flex gap-3 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                <button className="btn btn-secondary flex-1" onClick={() => setShowMulticollinearityModal(false)}>Close</button>
                {!multicollinearityData.error && <button className="btn btn-primary flex-1" onClick={() => { setShowMulticollinearityModal(false); handleStartAnalysis(); }}><RiBarChart2Fill size={15} /> Run Full Analysis</button>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── Normality Modal ─────────────────────────────────────────── */}
      {showNormalityModal && normalityData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }} onClick={() => setShowNormalityModal(false)}>
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }} onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-6 border-b" style={{ borderColor: 'var(--border)' }}>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(99,102,241,0.12)' }}>
                  <RiLineChartFill size={22} style={{ color: 'var(--brand)' }} />
                </div>
                <div>
                  <h2 className="font-display font-bold text-lg" style={{ color: 'var(--text)' }}>Normality Check (Shapiro-Wilk)</h2>
                  <p className="text-xs" style={{ color: 'var(--text-3)' }}>{survey?.title}</p>
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowNormalityModal(false)} style={{ padding: '6px' }}><RiCloseFill size={18} /></button>
            </div>
            <div className="p-6 space-y-5">
              {normalityData.error ? (
                <div className="rounded-xl p-5 border-2" style={{ borderColor: 'var(--danger)', background: 'rgba(239,68,68,0.05)' }}>
                  <div className="flex gap-3 items-start">
                    <RiAlertFill size={22} className="shrink-0 mt-0.5" style={{ color: 'var(--danger)' }} />
                    <div>
                      <p className="font-semibold text-sm mb-1" style={{ color: 'var(--danger)' }}>Check Failed</p>
                      <p className="text-sm" style={{ color: 'var(--text-2)' }}>{normalityData.error}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  {/* Verdict Banner */}
                  <div className="rounded-xl p-5 border-2" style={{
                    borderColor: normalityData.severity === 'ok' ? 'var(--success)' : normalityData.severity === 'moderate' ? '#f59e0b' : 'var(--danger)',
                    background: normalityData.severity === 'ok' ? 'rgba(16,185,129,0.05)' : normalityData.severity === 'moderate' ? 'rgba(245,158,11,0.05)' : 'rgba(239,68,68,0.05)',
                  }}>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-display font-bold text-2xl" style={{ color: normalityData.severity === 'ok' ? 'var(--success)' : normalityData.severity === 'moderate' ? '#f59e0b' : 'var(--danger)' }}>
                          {normalityData.n_normal}/{normalityData.n_variables_checked} Normal
                        </p>
                        <p className="text-sm mt-1" style={{ color: 'var(--text-2)' }}>{normalityData.verdict}</p>
                      </div>
                      {normalityData.severity === 'ok'
                        ? <RiCheckboxCircleFill size={48} style={{ color: 'var(--success)', opacity: 0.2 }} />
                        : <RiAlertFill size={48} style={{ color: 'var(--danger)', opacity: 0.2 }} />}
                    </div>
                  </div>

                  {/* Per-variable results */}
                  <div>
                    <h3 className="font-display font-semibold text-sm mb-3" style={{ color: 'var(--text)' }}>Variable-Level Results</h3>
                    <div className="space-y-3">
                      {normalityData.results?.map((r: any, i: number) => (
                        <div key={i} className="rounded-xl border p-4" style={{
                          borderColor: r.error ? 'var(--border)' : r.is_normal ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)',
                          background: r.error ? 'var(--surface-2)' : r.is_normal ? 'rgba(16,185,129,0.04)' : 'rgba(239,68,68,0.04)',
                        }}>
                          <div className="flex items-center justify-between mb-2">
                            <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{r.label}</p>
                            {!r.error && (
                              <span className="badge text-xs" style={{
                                background: r.is_normal ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                                color: r.is_normal ? 'var(--success)' : 'var(--danger)',
                              }}>
                                {r.is_normal ? '✓ Normal' : '✗ Non-Normal'}
                              </span>
                            )}
                          </div>
                          {r.error ? (
                            <p className="text-xs" style={{ color: 'var(--text-3)' }}>{r.error}</p>
                          ) : (
                            <>
                              <div className="grid grid-cols-4 gap-2 text-xs mb-2">
                                {[
                                  { label: 'Mean', value: r.mean },
                                  { label: 'SD', value: r.std },
                                  { label: 'Skewness', value: r.skewness },
                                  { label: 'Kurtosis', value: r.kurtosis },
                                ].map(({ label, value }) => (
                                  <div key={label} className="text-center rounded-lg p-2" style={{ background: 'var(--surface-2)' }}>
                                    <p className="font-bold" style={{ color: 'var(--text)' }}>{value}</p>
                                    <p style={{ color: 'var(--text-3)' }}>{label}</p>
                                  </div>
                                ))}
                              </div>
                              <div className="grid grid-cols-2 gap-2 text-xs">
                                {r.shapiro_wilk_p !== null && (
                                  <div className="rounded-lg p-2" style={{ background: 'var(--surface-2)' }}>
                                    <p className="font-semibold" style={{ color: r.sw_normal ? 'var(--success)' : 'var(--danger)' }}>SW p = {r.shapiro_wilk_p}</p>
                                    <p style={{ color: 'var(--text-3)' }}>Shapiro-Wilk {r.sw_normal ? '(normal)' : '(non-normal)'}</p>
                                  </div>
                                )}
                                <div className="rounded-lg p-2" style={{ background: 'var(--surface-2)' }}>
                                  <p className="text-xs" style={{ color: 'var(--text-2)' }}>{r.skewness_desc}</p>
                                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>{r.kurtosis_desc}</p>
                                </div>
                              </div>
                              {r.recommendation && (
                                <p className="text-xs mt-2 italic" style={{ color: 'var(--danger)' }}>💡 {r.recommendation}</p>
                              )}
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Footnote */}
                  <div className="rounded-xl p-3 text-xs border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--text-3)' }}>
                    <RiInformationFill size={13} className="inline mr-1" />
                    {normalityData.note}
                  </div>
                </>
              )}
              <div className="flex gap-3 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                <button className="btn btn-secondary flex-1" onClick={() => setShowNormalityModal(false)}>Close</button>
                {!normalityData.error && <button className="btn btn-primary flex-1" onClick={() => { setShowNormalityModal(false); handleStartAnalysis(); }}><RiBarChart2Fill size={15} /> Run Full Analysis</button>}
              </div>
            </div>
          </div>
        </div>
      )}
    </React.Fragment>
  );
}
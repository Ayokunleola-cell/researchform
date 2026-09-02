// src/pages/chat.tsx
import React, { useState, useEffect, useRef, KeyboardEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import AppLayout from '../components/layout/AppLayout';
import { analysisApi, datanestApi, chatApi, creditsApi } from '../lib/api';
import { RiSparklingFill, RiMessage2Fill, RiExternalLinkFill, RiSendPlaneFill, RiBarChart2Fill, RiCoinsFill, RiDeleteBinFill, RiAlertFill, RiCheckboxCircleFill, RiLoader4Line, RiRobotFill, RiDatabase2Fill, RiSearchEyeFill } from 'react-icons/ri';
import Link from 'next/link';

// ─── Types ─────────────────────────────────────────────────────────────────────

type ContextType = 'general' | 'analysis' | 'dataset';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  creditsUsed?: number;
  tokensUsed?: number;
}

// ─── Suggestion chips by context ──────────────────────────────────────────────

const SUGGESTIONS: Record<ContextType, string[]> = {
  general: [
    'What statistical test should I use to compare 3 independent groups?',
    'Explain p-values and statistical significance in simple terms',
    'How do I calculate the sample size for a survey study?',
    'What is the difference between correlation and causation?',
  ],
  analysis: [
    'Summarise the key findings of this analysis',
    'Which results are statistically significant, and what do they mean practically?',
    'What are the limitations of this analysis I should mention in my report?',
    'How should I interpret the effect sizes in this result?',
  ],
  dataset: [
    'What research questions can I answer with this dataset?',
    'What are the potential biases or quality issues I should be aware of?',
    'What statistical analyses are most suitable for this data?',
    'How should I preprocess and clean this dataset before analysis?',
  ],
};

// ─── Sub-components ────────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 2px' }}>
      {[0, 1, 2].map(i => (
        <div
          key={i}
          style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--brand)',
            animation: `typingBounce 1.2s ease-in-out ${i * 0.18}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

function CreditWarningBanner({ balance, onBuyCredits }: { balance: number; onBuyCredits: () => void }) {
  const critical = balance <= 0;
  return (
    <div style={{
      margin: '0 0 12px',
      padding: '10px 14px',
      borderRadius: 10,
      background: critical ? 'rgba(239,68,68,0.08)' : 'rgba(245,158,11,0.08)',
      border: `1px solid ${critical ? 'rgba(239,68,68,0.25)' : 'rgba(245,158,11,0.25)'}`,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <RiAlertFill size={15} color={critical ? '#ef4444' : '#f59e0b'} />
        <span style={{ fontSize: 13, color: critical ? '#ef4444' : '#f59e0b', fontWeight: 500 }}>
          {critical
            ? 'No credits remaining. Top up to continue chatting.'
            : `Low credits: ${balance.toFixed(2)} remaining.`}
        </span>
      </div>
      <Link
        href="/settings/credits"
        style={{
          fontSize: 12, fontWeight: 600, color: 'white',
          background: critical ? '#ef4444' : '#f59e0b',
          padding: '4px 10px', borderRadius: 6, textDecoration: 'none',
          whiteSpace: 'nowrap',
        }}
      >
        Buy Credits
      </Link>
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const [contextType, setContextType]         = useState<ContextType>('general');
  const [selectedJob, setSelectedJob]         = useState<any>(null);
  const [selectedDataset, setSelectedDataset] = useState<any>(null);
  const [messages, setMessages]               = useState<Message[]>([]);
  const [input, setInput]                     = useState('');
  const [sending, setSending]                 = useState(false);

  // Sidebar lists
  const [jobs, setJobs]                   = useState<any[]>([]);
  const [datasets, setDatasets]           = useState<any[]>([]);
  const [loadingJobs, setLoadingJobs]     = useState(false);
  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [jobSearch, setJobSearch]         = useState('');
  const [datasetSearch, setDatasetSearch] = useState('');

  // Credits
  const [creditBalance, setCreditBalance] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef    = useRef<HTMLTextAreaElement>(null);

  // ── Fetch credit wallet ──────────────────────────────────────────────────────
  useEffect(() => {
    creditsApi.wallet()
      .then(r => setCreditBalance(parseFloat(r.data.balance)))
      .catch(() => setCreditBalance(null));
  }, []);

  // ── Auto-scroll ──────────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  // ── Load analysis jobs when that tab is first selected ───────────────────────
  useEffect(() => {
    if (contextType === 'analysis' && jobs.length === 0) {
      setLoadingJobs(true);
      analysisApi.listJobs()
        .then(r => {
          const done = (r.data || []).filter((j: any) => j.status === 'complete');
          setJobs(done);
        })
        .catch(() => {})
        .finally(() => setLoadingJobs(false));
    }
  }, [contextType]);

  // ── Load datasets when that tab is first selected ────────────────────────────
  useEffect(() => {
    if (contextType === 'dataset' && datasets.length === 0) {
      setLoadingDatasets(true);
      // Fetch both purchased/downloaded library datasets AND user's own uploaded listings
      Promise.all([
        datanestApi.library().catch(() => ({ data: [] })),
        datanestApi.myListings().catch(() => ({ data: [] }))
      ]).then(([libRes, listRes]) => {
        const owned = (libRes.data || [])
          .map((purchase: any) => purchase.dataset)
          .filter(Boolean);
        const listings = (listRes.data || []);
        
        // Combine and deduplicate by dataset ID
        const combined = [...owned, ...listings];
        const unique = Array.from(new Map(combined.map(item => [item.id, item])).values());
        
        setDatasets(unique as any[]);
      }).finally(() => setLoadingDatasets(false));
    }
  }, [contextType]);

  // ── Clear conversation when context tab changes ──────────────────────────────
  useEffect(() => {
    setSelectedJob(null);
    setSelectedDataset(null);
    setMessages([]);
  }, [contextType]);

  // ── Helpers ──────────────────────────────────────────────────────────────────

  const getContextId = () =>
    contextType === 'analysis' && selectedJob ? selectedJob.id : undefined;

  const getContextData = () => {
    if (contextType === 'dataset' && selectedDataset) {
      return {
        title:          selectedDataset.title,
        description:    selectedDataset.description,
        domain:         selectedDataset.domain,
        country:        selectedDataset.country,
        sample_size:    selectedDataset.sample_size,
        license:        selectedDataset.license,
        price_naira:    selectedDataset.price_naira,
        download_count: selectedDataset.download_count,
        average_rating: selectedDataset.average_rating,
        files:          selectedDataset.files,
      };
    }
    return undefined;
  };

  const activeContextLabel = () => {
    if (contextType === 'analysis' && selectedJob)
      return selectedJob.source_filename || `Analysis ${selectedJob.id.slice(0, 8)}`;
    if (contextType === 'dataset' && selectedDataset)
      return selectedDataset.title;
    return null;
  };

  // ── Send message ─────────────────────────────────────────────────────────────

  const sendMessage = async (text?: string) => {
    const content = (text ?? input).trim();
    if (!content || sending) return;
    if (creditBalance !== null && creditBalance <= 0) return;

    const userMsg: Message = { role: 'user', content };
    const historyForApi = messages.map(m => ({ role: m.role, content: m.content }));
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setSending(true);

    // Auto-resize textarea back
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    try {
      const res = await chatApi.send({
        message:      content,
        history:      historyForApi,
        context_type: contextType,
        context_id:   getContextId(),
        context_data: getContextData(),
      });

      const { response, credits_used, tokens_used, wallet_balance } = res.data;

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: response,
          creditsUsed: credits_used,
          tokensUsed:  tokens_used,
        },
      ]);

      // Update credit balance from server response
      if (wallet_balance !== undefined) setCreditBalance(wallet_balance);

    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail || 'Something went wrong. Please try again.';

      // 402 = no credits
      if (status === 402) {
        setCreditBalance(0);
      }

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `**Error:** ${detail}` },
      ]);
    } finally {
      setSending(false);
      setTimeout(() => textareaRef.current?.focus(), 60);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => setMessages([]);

  const selectJob = (job: any) => {
    const isAlreadySelected = selectedJob?.id === job.id;
    setSelectedJob(isAlreadySelected ? null : job);
    setMessages([]);
  };

  const selectDataset = (ds: any) => {
    const isAlreadySelected = selectedDataset?.slug === ds.slug;
    setSelectedDataset(isAlreadySelected ? null : ds);
    setMessages([]);
  };

  const filteredJobs = jobs.filter(j => {
    const name = (j.source_filename || j.id || '').toLowerCase();
    return name.includes(jobSearch.toLowerCase());
  });

  const filteredDatasets = datasets.filter(d =>
    (d.title || '').toLowerCase().includes(datasetSearch.toLowerCase()) ||
    (d.domain || '').toLowerCase().includes(datasetSearch.toLowerCase())
  );

  const noCredits = creditBalance !== null && creditBalance <= 0;
  const lowCredits = creditBalance !== null && creditBalance > 0 && creditBalance < 1;
  const showCreditWarning = noCredits || lowCredits;

  const TABS = [
    { id: 'general'  as ContextType, icon: RiMessage2Fill, label: 'General' },
    { id: 'analysis' as ContextType, icon: RiBarChart2Fill,      label: 'Analysis' },
    { id: 'dataset'  as ContextType, icon: RiDatabase2Fill,       label: 'My Data' },
  ];

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <AppLayout title="Chat with AI">
      <style>{`
        @keyframes typingBounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-7px); opacity: 1; }
        }
        @keyframes msgFadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .chat-msg-in   { animation: msgFadeIn 0.22s ease; }
        .chat-textarea { font-family: inherit; }
        .chat-textarea:focus { outline: none; border-color: var(--brand) !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important; }
        .ctx-tab.active { background: var(--brand) !important; color: var(--brand-text) !important; }
        .ctx-tab:not(.active):hover { background: var(--surface) !important; }
        .ctx-item:hover:not(.active) { background: var(--surface) !important; }
        .ctx-item.active { background: rgba(99,102,241,0.1) !important; border-left-color: var(--brand) !important; }
        .chip:hover { background: rgba(99,102,241,0.1) !important; border-color: var(--brand) !important; color: var(--brand) !important; }
        .send-btn:hover:not(:disabled) { background: #4f46e5 !important; transform: scale(1.04); }
        .send-btn:disabled { opacity: 0.45; cursor: not-allowed; }
        .clear-btn:hover { background: var(--surface-1, var(--surface)) !important; }

        .chat-markdown p   { margin: 0 0 8px; }
        .chat-markdown p:last-child { margin-bottom: 0; }
        .chat-markdown ul, .chat-markdown ol { margin: 6px 0 8px 20px; }
        .chat-markdown li  { margin-bottom: 3px; }
        .chat-markdown h1,.chat-markdown h2,.chat-markdown h3 { margin: 10px 0 4px; font-weight: 700; }
        .chat-markdown code { background: rgba(99,102,241,0.12); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
        .chat-markdown pre  { background: rgba(0,0,0,0.06); padding: 10px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
        .chat-markdown pre code { background: none; padding: 0; }
        .chat-markdown strong { font-weight: 700; }
        .chat-markdown blockquote { border-left: 3px solid var(--brand); margin: 6px 0; padding: 4px 12px; opacity: 0.85; }
      `}</style>

      <div style={{
        display: 'flex', height: 'calc(100vh - 108px)', borderRadius: 16,
        overflow: 'hidden', border: '1px solid var(--border)',
        background: 'var(--surface)', boxShadow: 'var(--shadow-sm)',
      }}>

        {/* ══════════════════════════════════════════════════
            LEFT SIDEBAR
        ═══════════════════════════════════════════════════ */}
        <div style={{
          width: 272, flexShrink: 0, display: 'flex', flexDirection: 'column',
          borderRight: '1px solid var(--border)', background: 'var(--bg)',
        }}>

          {/* Brand + credit balance */}
          <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid var(--border)' }}>



            {/* Context tabs */}
            <div style={{
              display: 'flex', gap: 4, marginTop: 10,
              background: 'var(--surface)', borderRadius: 8, padding: 3,
            }}>
              {TABS.map(({ id, icon: Icon, label }) => (
                <button
                  key={id}
                  onClick={() => setContextType(id)}
                  className={`ctx-tab${contextType === id ? ' active' : ''}`}
                  style={{
                    flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                    padding: '7px 4px', border: 'none', borderRadius: 6, cursor: 'pointer',
                    fontSize: 10, fontWeight: 600, transition: 'all 0.15s',
                    color: contextType === id ? 'white' : 'var(--text-2)',
                    background: contextType === id ? 'var(--brand)' : 'transparent',
                  }}
                >
                  <Icon size={13} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Sidebar body */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px 8px' }}>

            {/* ── General info panel ── */}
            {contextType === 'general' && (
              <div style={{ padding: '6px 4px' }}>

                {[
                  ['Methodology', 'Study design & research questions'],
                  ['Statistics', 'Tests, concepts, interpretation'],
                  ['Academic Writing', 'Papers, citations & structure'],
                ].map(([title, desc]) => (
                  <div
                    key={title}
                    style={{
                      padding: '8px 10px', borderRadius: 8, marginBottom: 6,
                      background: 'var(--surface)', border: '1px solid var(--border)',
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{title}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{desc}</div>
                  </div>
                ))}
              </div>
            )}

            {/* ── Analysis jobs list ── */}
            {contextType === 'analysis' && (
              <>
                {/* Search */}
                <div style={{ position: 'relative', marginBottom: 6 }}>
                  <RiSearchEyeFill size={12} style={{
                    position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
                    color: 'var(--text-3)', pointerEvents: 'none',
                  }} />
                  <input
                    value={jobSearch}
                    onChange={e => setJobSearch(e.target.value)}
                    placeholder="Search analyses…"
                    style={{
                      width: '100%', boxSizing: 'border-box',
                      paddingLeft: 28, paddingRight: 10, paddingTop: 7, paddingBottom: 7,
                      fontSize: 12, borderRadius: 8, border: '1px solid var(--border)',
                      background: 'var(--surface)', color: 'var(--text)',
                    }}
                  />
                </div>

                {loadingJobs ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 24, color: 'var(--text-3)', fontSize: 12 }}>
                    <RiLoader4Line size={14} style={{ animation: 'spin 1s linear infinite' }} /> Loading analyses…
                  </div>
                ) : filteredJobs.length === 0 ? (
                  <div style={{ padding: '20px 8px', textAlign: 'center', color: 'var(--text-3)', fontSize: 12, lineHeight: 1.6 }}>
                    {jobs.length === 0
                      ? <>No completed analyses yet.<br />Run an analysis to chat about its results.</>
                      : 'No matching analyses.'}
                  </div>
                ) : (
                  filteredJobs.map(job => {
                    const active = selectedJob?.id === job.id;
                    const name = job.source_filename || `Analysis ${job.id.slice(0, 8)}`;
                    const date = new Date(job.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
                    return (
                      <button
                        key={job.id}
                        onClick={() => selectJob(job)}
                        className={`ctx-item${active ? ' active' : ''}`}
                        style={{
                          width: '100%', textAlign: 'left', display: 'block', cursor: 'pointer',
                          padding: '8px 10px', borderRadius: 8, marginBottom: 3,
                          border: '1px solid transparent',
                          borderLeft: `3px solid ${active ? 'var(--brand)' : 'transparent'}`,
                          background: active ? 'rgba(99,102,241,0.08)' : 'transparent',
                          transition: 'all 0.15s',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 4 }}>
                          <span style={{
                            fontSize: 12, fontWeight: 600, color: 'var(--text)',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 175,
                          }}>{name}</span>
                          {active && <RiCheckboxCircleFill size={12} color="var(--brand)" style={{ flexShrink: 0 }} />}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2 }}>
                          {job.n_rows ? `${job.n_rows.toLocaleString()} rows · ` : ''}{date}
                        </div>
                      </button>
                    );
                  })
                )}
              </>
            )}

            {/* ── Datasets list ── */}
            {contextType === 'dataset' && (
              <>
                <div style={{ position: 'relative', marginBottom: 6 }}>
                  <RiSearchEyeFill size={12} style={{
                    position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
                    color: 'var(--text-3)', pointerEvents: 'none',
                  }} />
                  <input
                    value={datasetSearch}
                    onChange={e => setDatasetSearch(e.target.value)}
                    placeholder="Search datasets…"
                    style={{
                      width: '100%', boxSizing: 'border-box',
                      paddingLeft: 28, paddingRight: 10, paddingTop: 7, paddingBottom: 7,
                      fontSize: 12, borderRadius: 8, border: '1px solid var(--border)',
                      background: 'var(--surface)', color: 'var(--text)',
                    }}
                  />
                </div>

                {loadingDatasets ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 24, color: 'var(--text-3)', fontSize: 12 }}>
                    <RiLoader4Line size={14} style={{ animation: 'spin 1s linear infinite' }} /> Loading datasets…
                  </div>
                ) : filteredDatasets.length === 0 ? (
                  <div style={{ padding: '20px 8px', textAlign: 'center', color: 'var(--text-3)', fontSize: 12, lineHeight: 1.6 }}>
                    {datasets.length === 0
                      ? <>You haven&apos;t acquired any datasets yet.<br />Browse the <Link href="/marketplace/browse" style={{color:'var(--brand)'}}>marketplace</Link> to download or purchase datasets.</>  
                      : 'No matches found.'}
                  </div>
                ) : (
                  filteredDatasets.map(ds => {
                    const active = selectedDataset?.slug === ds.slug;
                    return (
                      <button
                        key={ds.id}
                        onClick={() => selectDataset(ds)}
                        className={`ctx-item${active ? ' active' : ''}`}
                        style={{
                          width: '100%', textAlign: 'left', display: 'block', cursor: 'pointer',
                          padding: '8px 10px', borderRadius: 8, marginBottom: 3,
                          border: '1px solid transparent',
                          borderLeft: `3px solid ${active ? 'var(--brand)' : 'transparent'}`,
                          background: active ? 'rgba(99,102,241,0.08)' : 'transparent',
                          transition: 'all 0.15s',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 4 }}>
                          <span style={{
                            fontSize: 12, fontWeight: 600, color: 'var(--text)',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 175,
                          }}>{ds.title}</span>
                          {active && <RiCheckboxCircleFill size={12} color="var(--brand)" style={{ flexShrink: 0 }} />}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 3 }}>
                          <span style={{
                            fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 4,
                            background: 'rgba(99,102,241,0.1)', color: 'var(--brand)',
                          }}>{ds.domain}</span>
                          <span style={{ fontSize: 10, color: 'var(--text-3)' }}>
                            {Number(ds.price_naira) === 0 ? 'Free' : `₦${Number(ds.price_naira).toLocaleString()}`}
                          </span>
                        </div>
                      </button>
                    );
                  })
                )}
              </>
            )}
          </div>
        </div>

        {/* ══════════════════════════════════════════════════
            MAIN CHAT AREA
        ═══════════════════════════════════════════════════ */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

          {/* Chat header */}
          <div style={{
            padding: '12px 20px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            flexShrink: 0,
          }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>
                {contextType === 'general'
                  ? ''
                  : contextType === 'analysis'
                  ? 'Analysis Chat'
                  : 'Dataset Chat'}
              </div>
              {activeContextLabel() ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
                  <RiCheckboxCircleFill size={11} color="var(--brand)" />
                  <span style={{ fontSize: 12, color: 'var(--brand)', fontWeight: 600 }}>
                    {activeContextLabel()}
                  </span>
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
                  {contextType === 'analysis'
                    ? 'Select an analysis job to discuss its results'
                    : contextType === 'dataset'
                    ? 'Select one of your owned datasets to explore it with Claude'
                    : ''}
                </div>
              )}
            </div>

            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="clear-btn"
                style={{
                  display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px',
                  borderRadius: 8, border: '1px solid var(--border)', background: 'transparent',
                  color: 'var(--text-2)', cursor: 'pointer', fontSize: 12, fontWeight: 500,
                  transition: 'background 0.15s',
                }}
              >
                <RiDeleteBinFill size={13} /> Clear
              </button>
            )}
          </div>

          {/* Messages area */}
          <div style={{
            flex: 1, overflowY: 'auto', padding: '20px 24px',
            display: 'flex', flexDirection: 'column', gap: 18,
          }}>

            {/* Welcome screen */}
            {messages.length === 0 && !sending && (
              <div style={{
                flex: 1, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                textAlign: 'center', padding: '40px 20px', gap: 20,
              }}>


                {/* Title */}
                <div>
                  <h2 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', margin: '0 0 8px' }}>
                    {contextType === 'general'
                      ? 'How can I help you today?'
                      : activeContextLabel()
                      ? `Ready to discuss ${contextType === 'analysis' ? 'your analysis' : 'this dataset'}`
                      : `Select a ${contextType === 'analysis' ? 'job' : 'dataset'} to get started`}
                  </h2>
                  <p style={{ fontSize: 14, color: 'var(--text-3)', margin: 0, maxWidth: 440, lineHeight: 1.6 }}>
                    {contextType === 'general'
                      ? 'Ask anything about research methodology, statistics, academic writing, or your data.'
                      : contextType === 'analysis' && !selectedJob
                      ? 'Pick a completed analysis from the left panel. Claude will read its full results and help you understand them.'
                      : contextType === 'dataset' && !selectedDataset
                      ? 'Pick one of your owned datasets from the left panel. Claude will help you evaluate and analyse it.'
                      : 'Claude has loaded the context. Start with a question below or try a suggestion.'}
                  </p>
                </div>

                {/* Credit warning on welcome screen */}
                {showCreditWarning && (
                  <CreditWarningBanner balance={creditBalance!} onBuyCredits={() => {}} />
                )}

                {/* Suggestion chips */}
                {(contextType === 'general' || activeContextLabel()) && !noCredits && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', maxWidth: 560 }}>
                    {SUGGESTIONS[contextType].map(s => (
                      <button
                        key={s}
                        onClick={() => sendMessage(s)}
                        className="chip"
                        disabled={sending}
                        style={{
                          padding: '8px 15px', borderRadius: 20,
                          border: '1px solid var(--border)', background: 'var(--surface)',
                          color: 'var(--text-2)', cursor: 'pointer', fontSize: 12, fontWeight: 500,
                          transition: 'all 0.15s', textAlign: 'left',
                        }}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Message bubbles */}
            {messages.map((msg, i) => (
              <div
                key={i}
                className="chat-msg-in"
                style={{
                  display: 'flex',
                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                  alignItems: 'flex-start',
                  gap: 10,
                }}
              >
                {/* Avatar */}
                <div style={{
                  width: 34, height: 34, borderRadius: 11, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, fontWeight: 800, color: 'white',
                  background: msg.role === 'user'
                    ? 'var(--brand)'
                    : 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
                }}>
                  {msg.role === 'user' ? 'U' : <RiRobotFill size={16} />}
                </div>

                {/* Bubble */}
                <div style={{ maxWidth: '72%', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{
                    padding: '10px 15px',
                    borderRadius: msg.role === 'user'
                      ? '16px 4px 16px 16px'
                      : '4px 16px 16px 16px',
                    background: msg.role === 'user' ? 'var(--brand)' : 'var(--surface-2)',
                    color: msg.role === 'user' ? 'var(--brand-text)' : 'var(--text)',
                    fontSize: 14, lineHeight: 1.65,
                  }}>
                    {msg.role === 'user' ? (
                      <span>{msg.content}</span>
                    ) : (
                      <div className="chat-markdown">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    )}
                  </div>


                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {sending && (
              <div className="chat-msg-in" style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{
                  width: 34, height: 34, borderRadius: 11, flexShrink: 0,
                  background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
                }}>
                  <RiRobotFill size={16} color="white" />
                </div>
                <div style={{
                  padding: '12px 16px', borderRadius: '4px 16px 16px 16px',
                  background: 'var(--surface-1, #f8f8ff)', border: '1px solid var(--border)',
                }}>
                  <TypingIndicator />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input bar */}
          <div style={{
            padding: '10px 20px 14px', borderTop: '1px solid var(--border)', flexShrink: 0,
          }}>
            {/* Credit warning in input area */}
            {showCreditWarning && messages.length > 0 && (
              <CreditWarningBanner balance={creditBalance!} onBuyCredits={() => {}} />
            )}

            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={noCredits}
                rows={1}
                className="chat-textarea"
                placeholder={
                  noCredits
                    ? 'No credits — top up to continue chatting'
                    : contextType === 'analysis' && !selectedJob
                    ? 'Select an analysis job on the left, or ask a general question…'
                    : contextType === 'dataset' && !selectedDataset
                    ? 'Select a dataset on the left, or ask a general question…'
                    : 'Type your message...'
                }
                style={{
                  flex: 1, resize: 'none', padding: '11px 14px',
                  borderRadius: 12, border: '1px solid var(--border)',
                  background: noCredits ? 'rgba(239,68,68,0.04)' : 'var(--surface)',
                  color: 'var(--text)', fontSize: 14, lineHeight: 1.5,
                  maxHeight: 130, overflowY: 'auto', transition: 'border-color 0.15s',
                }}
                onInput={(e) => {
                  const el = e.target as HTMLTextAreaElement;
                  el.style.height = 'auto';
                  el.style.height = Math.min(el.scrollHeight, 130) + 'px';
                }}
              />
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim() || sending || noCredits}
                className="send-btn"
                style={{
                  width: 44, height: 44, borderRadius: 12, border: 'none',
                  background: 'var(--brand)', color: 'var(--brand-text)', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, transition: 'all 0.15s',
                }}
              >
                {sending
                  ? <RiLoader4Line size={19} style={{ animation: 'spin 0.9s linear infinite' }} />
                  : <RiSendPlaneFill size={19} />
                }
              </button>
            </div>

            <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '6px 0 0', textAlign: 'center' }}>
              AI can mistakes. Please double-check responses
            </p>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

import React, { useState, useEffect, useRef } from 'react';
import { RiSendPlaneFill, RiErrorWarningFill, RiBankCardFill, RiLoader4Line, RiRobotFill, RiUserFill } from 'react-icons/ri';
import { analysisApi, creditsApi } from '../../lib/api';
import toast from 'react-hot-toast';
import ReactMarkdown from 'react-markdown';

export default function ChatPanel({ jobId }: { jobId: string }) {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [walletBalance, setWalletBalance] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchHistory();
    fetchWallet();
  }, [jobId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const fetchHistory = async () => {
    try {
      const res = await analysisApi.getChatHistory(jobId);
      setMessages(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchWallet = async () => {
    try {
      const res = await creditsApi.wallet();
      setWalletBalance(res.data.balance);
    } catch (err) {}
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (walletBalance !== null && walletBalance <= 0) {
      toast.error('Insufficient credits to send message');
      return;
    }
    const newMsg = { id: Date.now().toString(), role: 'user', content: input };
    setMessages(prev => [...prev, newMsg]);
    setInput('');
    setLoading(true);
    try {
      const res = await analysisApi.sendChatMessage(jobId, newMsg.content);
      setMessages(prev => [...prev, res.data]);
      fetchWallet();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to send message');
      setMessages(prev => prev.filter(m => m.id !== newMsg.id));
    } finally {
      setLoading(false);
    }
  };

  const noCredits = walletBalance !== null && walletBalance <= 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', border: '1px solid var(--border)', borderRadius: 16, overflow: 'hidden', background: 'var(--surface)' }}>

      {/* ── Header ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
        background: 'var(--surface-2)', flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <RiRobotFill size={13} style={{ color: 'var(--brand)' }} />
          <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--text)' }}>Chat with Results</span>
        </div>
        {walletBalance !== null && (
          <span style={{
            display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, fontWeight: 600,
            color: 'var(--text-2)', background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 20, padding: '2px 7px'
          }}>
            <RiBankCardFill size={10} style={{ color: 'var(--brand)' }} />
            {walletBalance.toFixed(2)} cr
          </span>
        )}
      </div>

      {/* ── Messages ── */}
      <div style={{ overflowY: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 10, minHeight: 250, maxHeight: 500 }}>
        {messages.length === 0 ? (
          /* Empty state — fully centred */
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            textAlign: 'center', margin: '8px 4px', padding: '24px 20px',
            gap: 12, borderRadius: 12,
            background: 'var(--surface-2)', border: '1px solid var(--border)'
          }}>
            <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'var(--surface)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <RiRobotFill size={16} style={{ color: 'var(--brand)', opacity: 0.7 }} />
            </div>
            <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>
              Ask me anything about your results
            </p>
            <p style={{ margin: 0, fontSize: 10, color: 'var(--text-3)', lineHeight: 1.5, padding: '0 8px' }}>
              e.g. "Explain the ANOVA results in simple terms"
            </p>
          </div>
        ) : (
          messages.map(msg => (
            <div key={msg.id} style={{ display: 'flex', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row', alignItems: 'flex-start', gap: 8 }}>
              {/* Avatar */}
              <div style={{
                width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: msg.role === 'user' ? 'var(--brand)' : 'var(--surface-2)',
                border: '1px solid var(--border)',
                color: msg.role === 'user' ? 'var(--brand-text)' : 'var(--text-2)'
              }}>
                {msg.role === 'user' ? <RiUserFill size={12} /> : <RiRobotFill size={12} />}
              </div>
              {/* Bubble */}
              <div style={{
                maxWidth: '80%', padding: '7px 11px',
                borderRadius: msg.role === 'user' ? '14px 4px 14px 14px' : '4px 14px 14px 14px',
                background: msg.role === 'user' ? 'var(--brand)' : 'var(--surface-2)',
                color: msg.role === 'user' ? 'var(--brand-text)' : 'var(--text)',
                fontSize: 12, lineHeight: 1.5,
                border: msg.role === 'user' ? 'none' : '1px solid var(--border)'
              }}>
                {msg.role === 'assistant' ? (
                  <div className="markdown-body" style={{ background: 'transparent', fontSize: 12 }}>
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))
        )}

        {/* Typing indicator */}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <div style={{ width: 26, height: 26, borderRadius: '50%', background: 'var(--surface-2)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <RiRobotFill size={12} style={{ color: 'var(--text-2)' }} />
            </div>
            <div style={{ padding: '7px 11px', borderRadius: '4px 14px 14px 14px', background: 'var(--surface-2)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <RiLoader4Line size={12} className="animate-spin" style={{ color: 'var(--brand)' }} />
              <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Thinking…</span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* ── Input footer ── */}
      <div style={{ padding: '8px 12px 8px', borderTop: '1px solid var(--border)', background: 'var(--surface-2)', flexShrink: 0 }}>
        {noCredits && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6, padding: '4px 8px', borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', fontSize: 10, fontWeight: 500, color: '#ef4444' }}>
            <RiErrorWarningFill size={11} />
            Out of credits — please top up to continue.
          </div>
        )}
        <form onSubmit={handleSend} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 22, padding: '4px 4px 4px 12px' }}>
          <input
            type="text"
            placeholder="Ask about your data…"
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading || noCredits}
            style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              fontSize: 12, color: 'var(--text)', minWidth: 0
            }}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading || noCredits}
            style={{
              width: 28, height: 28, borderRadius: '50%', border: 'none', flexShrink: 0,
              background: 'var(--brand)', color: 'var(--brand-text)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: (!input.trim() || loading || noCredits) ? 'not-allowed' : 'pointer',
              opacity: (!input.trim() || loading || noCredits) ? 0.45 : 1,
              transition: 'opacity 0.15s'
            }}
          >
            {loading ? <RiLoader4Line size={13} className="animate-spin" /> : <RiSendPlaneFill size={13} />}
          </button>
        </form>
        <p style={{ textAlign: 'center', fontSize: 9, color: 'var(--text-3)', margin: '4px 0 0' }}>
          Credits deducted per AI response
        </p>
      </div>

    </div>
  );
}

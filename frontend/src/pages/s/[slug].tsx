// src/pages/s/[slug].tsx — Public respondent form
import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useRouter } from 'next/router';
import { publicApi } from '../../lib/api';
import {
  RiSendPlaneFill, RiErrorWarningFill, RiCheckboxCircleFill,
  RiLoader4Line, RiCheckFill, RiUploadCloud2Line, RiFileLine,
  RiCloseLine, RiSearchLine, RiArrowUpSLine, RiArrowDownSLine,
} from 'react-icons/ri';
import { useThemeStore } from '../../lib/store';

// ── Utility: seeded shuffle (same seed = same order per session) ──────────────
function seededShuffle<T>(arr: T[], seed: number): T[] {
  const a = [...arr];
  let s = seed;
  for (let i = a.length - 1; i > 0; i--) {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    const j = Math.abs(s) % (i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// Per-question seed based on question id so randomization is stable per reload
function questionSeed(qid: string): number {
  return qid.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
}

// ── Validation helper ─────────────────────────────────────────────────────────
function validateAnswer(question: any, value: any): string | null {
  const vr = question.validation_rules || {};
  if (!value && value !== 0) return null; // only validate if answered

  if (['short_text', 'long_text'].includes(question.type)) {
    const str = String(value || '');
    if (vr.min_length && str.length < vr.min_length)
      return `Minimum ${vr.min_length} characters required (${str.length} entered)`;
    if (vr.max_length && str.length > vr.max_length)
      return `Maximum ${vr.max_length} characters allowed (${str.length} entered)`;
    if (vr.regex) {
      try {
        if (!new RegExp(vr.regex).test(str)) {
          const presetLabels: Record<string, string> = { email: 'a valid email address', phone: 'a valid phone number', url: 'a valid URL', student_id: 'a valid Student ID' };
          return vr.preset ? `Please enter ${presetLabels[vr.preset] || 'a valid value'}` : 'Value does not match the required format';
        }
      } catch { }
    }
  }

  if (question.type === 'number') {
    const num = Number(value);
    if (isNaN(num)) return 'Please enter a valid number';
    if (vr.integer_only && !Number.isInteger(num)) return 'Please enter a whole number (no decimals)';
    if (vr.min_val !== undefined && num < vr.min_val) return `Value must be at least ${vr.min_val}`;
    if (vr.max_val !== undefined && num > vr.max_val) return `Value must be at most ${vr.max_val}`;
  }

  return null;
}

// ── Skip Logic Evaluator ──────────────────────────────────────────────────────
function evaluateLogic(question: any, answers: Record<string, any>): 'visible' | 'hidden' {
  const rules: any[] = question.logic_rules || [];
  if (rules.length === 0) return 'visible';

  // All rules are AND-ed; default action is 'show'
  // We collect matching rules and apply the action of the first match
  for (const rule of rules) {
    const condAnswer = answers[rule.condition_q_id];
    let matches = false;

    switch (rule.operator) {
      case 'equals':       matches = String(condAnswer) === String(rule.value); break;
      case 'not_equals':   matches = String(condAnswer) !== String(rule.value); break;
      case 'contains':     matches = String(condAnswer || '').includes(String(rule.value)); break;
      case 'greater_than': matches = Number(condAnswer) > Number(rule.value); break;
      case 'less_than':    matches = Number(condAnswer) < Number(rule.value); break;
    }

    if (matches) {
      return rule.action === 'show' ? 'visible' : 'hidden';
    }
  }

  // No rule matched — if any rules exist and action is 'show', default to hidden; if 'hide', default to visible
  const defaultAction = rules[0]?.action === 'show' ? 'hidden' : 'visible';
  return defaultAction;
}

// ── Question Components ───────────────────────────────────────────────────────

function ShortTextInput({ question, value, onChange, error }: { question: any; value: string; onChange: (v: string) => void; error?: string }) {
  const [focused, setFocused] = useState(false);
  const vr = question.validation_rules || {};
  const charCount = (value || '').length;
  return (
    <div>
      <input
        className="w-full text-base transition-all"
        style={{
          border: `2px solid ${error ? '#ef4444' : focused ? '#4f46e5' : '#d1d5db'}`,
          borderRadius: 10, padding: '12px 16px', background: '#fff', color: '#111827',
          outline: 'none', fontSize: 15,
          boxShadow: error ? '0 0 0 4px rgba(239,68,68,0.1)' : focused ? '0 0 0 4px rgba(79,70,229,0.12)' : 'none',
        }}
        placeholder="Your answer"
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      />
      <div className="flex justify-between mt-1">
        {error && <p style={{ color: '#ef4444', fontSize: 12, fontWeight: 500 }}>{error}</p>}
        {vr.max_length && <p style={{ color: charCount > vr.max_length ? '#ef4444' : '#9ca3af', fontSize: 12, marginLeft: 'auto' }}>{charCount}/{vr.max_length}</p>}
      </div>
    </div>
  );
}

function LongTextInput({ question, value, onChange, error }: { question: any; value: string; onChange: (v: string) => void; error?: string }) {
  const [focused, setFocused] = useState(false);
  const vr = question.validation_rules || {};
  const charCount = (value || '').length;
  return (
    <div>
      <textarea
        rows={3}
        className="w-full text-base transition-all"
        style={{
          border: `2px solid ${error ? '#ef4444' : focused ? '#4f46e5' : '#d1d5db'}`,
          borderRadius: 10, padding: '12px 16px', background: '#fff', color: '#111827',
          outline: 'none', fontSize: 15, resize: 'vertical',
          boxShadow: error ? '0 0 0 4px rgba(239,68,68,0.1)' : focused ? '0 0 0 4px rgba(79,70,229,0.12)' : 'none',
          minHeight: 96,
        }}
        placeholder="Your answer"
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      />
      <div className="flex justify-between mt-1">
        {error && <p style={{ color: '#ef4444', fontSize: 12, fontWeight: 500 }}>{error}</p>}
        {vr.max_length && <p style={{ color: charCount > vr.max_length ? '#ef4444' : '#9ca3af', fontSize: 12, marginLeft: 'auto' }}>{charCount}/{vr.max_length}</p>}
      </div>
    </div>
  );
}

function SingleChoiceInput({ question, value, onChange, displayOptions }: { question: any; value: string; onChange: (v: string) => void; displayOptions: string[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {displayOptions.map((opt: string, i: number) => {
        const isSelected = value === opt;
        return (
          <button key={i} type="button" onClick={() => onChange(opt)} style={{
            display: 'flex', alignItems: 'center', gap: 14, padding: '13px 18px',
            borderRadius: 12, border: `2px solid ${isSelected ? '#4f46e5' : '#e5e7eb'}`,
            background: isSelected ? '#f0f0ff' : '#fff', cursor: 'pointer', textAlign: 'left',
            transition: 'all 0.15s ease',
            boxShadow: isSelected ? '0 0 0 3px rgba(79,70,229,0.15)' : '0 1px 2px rgba(0,0,0,0.05)',
          }}>
            <span style={{ width: 22, height: 22, borderRadius: '50%', flexShrink: 0, border: `2px solid ${isSelected ? '#4f46e5' : '#d1d5db'}`, background: isSelected ? '#4f46e5' : '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.15s' }}>
              {isSelected && <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#fff' }} />}
            </span>
            <span style={{ fontSize: 15, fontWeight: isSelected ? 600 : 400, color: isSelected ? '#3730a3' : '#374151', flex: 1 }}>{opt}</span>
            {isSelected && <RiCheckFill size={16} style={{ color: '#4f46e5', flexShrink: 0 }} />}
          </button>
        );
      })}
    </div>
  );
}

function MultiChoiceInput({ question, value, onChange, displayOptions }: { question: any; value: string[]; onChange: (v: string[]) => void; displayOptions: string[] }) {
  const selected: string[] = Array.isArray(value) ? value : [];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {displayOptions.map((opt: string, i: number) => {
        const checked = selected.includes(opt);
        return (
          <button key={i} type="button" onClick={() => onChange(checked ? selected.filter(s => s !== opt) : [...selected, opt])} style={{
            display: 'flex', alignItems: 'center', gap: 14, padding: '13px 18px',
            borderRadius: 12, border: `2px solid ${checked ? '#4f46e5' : '#e5e7eb'}`,
            background: checked ? '#f0f0ff' : '#fff', cursor: 'pointer', textAlign: 'left',
            transition: 'all 0.15s ease',
            boxShadow: checked ? '0 0 0 3px rgba(79,70,229,0.15)' : '0 1px 2px rgba(0,0,0,0.05)',
          }}>
            <span style={{ width: 22, height: 22, borderRadius: 6, flexShrink: 0, border: `2px solid ${checked ? '#4f46e5' : '#d1d5db'}`, background: checked ? '#4f46e5' : '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.15s' }}>
              {checked && <RiCheckFill size={13} style={{ color: '#fff' }} />}
            </span>
            <span style={{ fontSize: 15, fontWeight: checked ? 600 : 400, color: checked ? '#3730a3' : '#374151', flex: 1 }}>{opt}</span>
          </button>
        );
      })}
    </div>
  );
}

function LikertInput({ question, value, onChange }: { question: any; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#6b7280' }}>{question.options[0]}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#6b7280' }}>{question.options[question.options.length - 1]}</span>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {question.options.map((_: string, i: number) => {
          const val = i + 1;
          const isSelected = value === val;
          return (
            <button key={i} type="button" onClick={() => onChange(val)} title={_} style={{
              flex: 1, padding: '12px 4px', borderRadius: 10, fontWeight: 700, fontSize: 15,
              border: `2px solid ${isSelected ? '#4f46e5' : '#e5e7eb'}`,
              background: isSelected ? '#4f46e5' : '#fff', color: isSelected ? '#fff' : '#6b7280',
              cursor: 'pointer', transition: 'all 0.15s ease',
              boxShadow: isSelected ? '0 4px 12px rgba(79,70,229,0.35)' : '0 1px 2px rgba(0,0,0,0.05)',
              transform: isSelected ? 'translateY(-2px)' : 'none', minWidth: 40,
            }}>{val}</button>
          );
        })}
      </div>
    </div>
  );
}

function RatingInput({ question, value, onChange }: { question: any; value: number; onChange: (v: number) => void }) {
  const [hovered, setHovered] = useState(0);
  const max = question.scale_max || 5;
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {Array.from({ length: max }, (_, i) => i + 1).map(n => {
        const isActive = (hovered || value) >= n;
        return (
          <button key={n} type="button" onClick={() => onChange(n)} onMouseEnter={() => setHovered(n)} onMouseLeave={() => setHovered(0)} style={{
            width: 46, height: 46, borderRadius: '50%', fontWeight: 700, fontSize: 15,
            border: `2px solid ${isActive ? '#4f46e5' : '#e5e7eb'}`, background: isActive ? '#4f46e5' : '#fff',
            color: isActive ? '#fff' : '#9ca3af', cursor: 'pointer', transition: 'all 0.15s ease',
            boxShadow: value >= n ? '0 4px 12px rgba(79,70,229,0.3)' : 'none',
            transform: value === n ? 'scale(1.1)' : 'none',
          }}>{n}</button>
        );
      })}
    </div>
  );
}

function NumberInput({ question, value, onChange, error }: { question: any; value: number; onChange: (v: number) => void; error?: string }) {
  const [focused, setFocused] = useState(false);
  const vr = question.validation_rules || {};
  return (
    <div>
      <input
        type={vr.integer_only ? 'number' : 'number'}
        step={vr.integer_only ? 1 : 'any'}
        min={vr.min_val} max={vr.max_val}
        style={{
          width: 180, border: `2px solid ${error ? '#ef4444' : focused ? '#4f46e5' : '#d1d5db'}`,
          borderRadius: 10, padding: '12px 16px', background: '#fff', color: '#111827',
          outline: 'none', fontSize: 15,
          boxShadow: focused ? '0 0 0 4px rgba(79,70,229,0.12)' : 'none',
        }}
        placeholder="0"
        value={value || ''}
        onChange={e => onChange(+e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      />
      {vr.min_val !== undefined && vr.max_val !== undefined && (
        <p style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>Range: {vr.min_val} – {vr.max_val}</p>
      )}
      {error && <p style={{ color: '#ef4444', fontSize: 12, fontWeight: 500, marginTop: 4 }}>{error}</p>}
    </div>
  );
}

function DateInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [focused, setFocused] = useState(false);
  return (
    <input type="date" style={{
      width: 220, border: `2px solid ${focused ? '#4f46e5' : '#d1d5db'}`,
      borderRadius: 10, padding: '12px 16px', background: '#fff', color: '#111827', outline: 'none', fontSize: 15,
      boxShadow: focused ? '0 0 0 4px rgba(79,70,229,0.12)' : 'none',
    }} value={value || ''} onChange={e => onChange(e.target.value)} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} />
  );
}

function MatrixInput({ question, value, onChange }: { question: any; value: Record<string, number>; onChange: (v: Record<string, number>) => void }) {
  const matrixVal: Record<string, number> = value || {};
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0 }}>
        <thead>
          <tr>
            <th style={{ padding: '10px 16px', textAlign: 'left', color: '#6b7280', fontSize: 13, fontWeight: 600, background: '#f9fafb', borderRadius: '8px 0 0 0', border: '1px solid #e5e7eb' }} />
            {question.columns?.map((col: string, j: number) => (
              <th key={j} style={{ padding: '10px 16px', textAlign: 'center', color: '#374151', fontSize: 13, fontWeight: 700, background: '#f9fafb', border: '1px solid #e5e7eb', minWidth: 90 }}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {question.rows?.map((row: string, i: number) => (
            <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#fafafa' }}>
              <td style={{ padding: '12px 16px', color: '#111827', fontSize: 14, fontWeight: 500, border: '1px solid #e5e7eb', borderTop: 'none' }}>{row}</td>
              {question.columns?.map((_: any, j: number) => {
                const isSelected = matrixVal[row] === j + 1;
                return (
                  <td key={j} style={{ textAlign: 'center', border: '1px solid #e5e7eb', borderTop: 'none', padding: '8px' }}>
                    <button type="button" onClick={() => onChange({ ...matrixVal, [row]: j + 1 })} style={{
                      width: 28, height: 28, borderRadius: '50%',
                      border: `2px solid ${isSelected ? '#4f46e5' : '#d1d5db'}`,
                      background: isSelected ? '#4f46e5' : '#fff', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto', transition: 'all 0.15s',
                    }}>
                      {isSelected && <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#fff', display: 'block' }} />}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Searchable Dropdown ───────────────────────────────────────────────────────
function SearchableDropdownInput({ question, value, onChange, displayOptions }: { question: any; value: string; onChange: (v: string) => void; displayOptions: string[] }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  const filtered = displayOptions.filter(o => o.toLowerCase().includes(search.toLowerCase()));

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} style={{ position: 'relative', maxWidth: 420 }}>
      <button type="button" onClick={() => setOpen(!open)} style={{
        width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 16px', border: `2px solid ${open ? '#4f46e5' : '#d1d5db'}`,
        borderRadius: 10, background: '#fff', color: value ? '#111827' : '#9ca3af',
        fontSize: 15, cursor: 'pointer', textAlign: 'left',
        boxShadow: open ? '0 0 0 4px rgba(79,70,229,0.12)' : 'none',
      }}>
        <span>{value || '— Select an option —'}</span>
        {open ? <RiArrowUpSLine size={18} /> : <RiArrowDownSLine size={18} />}
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, marginTop: 4, zIndex: 50,
          background: '#fff', border: '1.5px solid #e5e7eb', borderRadius: 12,
          boxShadow: '0 8px 32px rgba(0,0,0,0.12)', overflow: 'hidden',
        }}>
          <div style={{ padding: '8px', borderBottom: '1px solid #f3f4f6' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#f9fafb', borderRadius: 8 }}>
              <RiSearchLine size={16} style={{ color: '#9ca3af', flexShrink: 0 }} />
              <input
                autoFocus
                placeholder="Search..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 14, color: '#111827', width: '100%' }}
              />
            </div>
          </div>
          <div style={{ maxHeight: 220, overflowY: 'auto' }}>
            {filtered.length === 0 ? (
              <p style={{ padding: '12px 16px', color: '#9ca3af', fontSize: 14 }}>No results found</p>
            ) : (
              filtered.map((opt, i) => (
                <button key={i} type="button" onClick={() => { onChange(opt); setOpen(false); setSearch(''); }} style={{
                  width: '100%', textAlign: 'left', padding: '10px 16px', background: value === opt ? '#f0f0ff' : 'transparent',
                  color: value === opt ? '#4f46e5' : '#111827', fontWeight: value === opt ? 600 : 400,
                  fontSize: 14, border: 'none', cursor: 'pointer', transition: 'background 0.1s',
                }} onMouseEnter={e => { if (value !== opt) (e.currentTarget as HTMLElement).style.background = '#f9fafb'; }}
                  onMouseLeave={e => { if (value !== opt) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
                  {opt}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function RankOrderInput({ question, value, onChange, displayOptions }: { question: any; value: string[]; onChange: (v: string[]) => void; displayOptions: string[] }) {
  const items: string[] = value && Array.isArray(value) && value.length === displayOptions.length ? value : displayOptions;

  const move = (from: number, to: number) => {
    if (to < 0 || to >= items.length) return;
    const next = [...items];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    onChange(next);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 500 }}>
      <p style={{ fontSize: 12, color: '#9ca3af', fontWeight: 500, marginBottom: 4 }}>Use the arrows to reorder items by preference</p>
      {items.map((item, i) => (
        <div key={item} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', background: '#f9fafb', border: '1.5px solid #e5e7eb',
          borderRadius: 10, color: '#111827', fontWeight: 600, fontSize: 14,
          transition: 'all 0.15s',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg, #4f46e5, #7c3aed)', color: '#fff', fontSize: 12, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{i + 1}</span>
            <span>{item}</span>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <button type="button" disabled={i === 0} onClick={() => move(i, i - 1)} style={{
              border: '1px solid #d1d5db', background: '#fff', borderRadius: 6, padding: '4px 8px',
              cursor: i === 0 ? 'not-allowed' : 'pointer', opacity: i === 0 ? 0.4 : 1, transition: 'all 0.1s',
            }}>▲</button>
            <button type="button" disabled={i === items.length - 1} onClick={() => move(i, i + 1)} style={{
              border: '1px solid #d1d5db', background: '#fff', borderRadius: 6, padding: '4px 8px',
              cursor: i === items.length - 1 ? 'not-allowed' : 'pointer', opacity: i === items.length - 1 ? 0.4 : 1, transition: 'all 0.1s',
            }}>▼</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function ConstantSumInput({ question, value, onChange }: { question: any; value: Record<string, number>; onChange: (v: Record<string, number>) => void }) {
  const current: Record<string, number> = value || {};
  const targetTotal = question.scale_max || 100;
  const currentSum = Object.values(current).reduce((acc, v) => acc + (Number(v) || 0), 0);
  const remaining = targetTotal - currentSum;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 500 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderRadius: 8,
        background: remaining === 0 ? '#ecfdf5' : remaining < 0 ? '#fef2f2' : '#eff6ff',
        border: `1px solid ${remaining === 0 ? '#10b981' : remaining < 0 ? '#ef4444' : '#3b82f6'}`,
      }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: remaining === 0 ? '#065f46' : remaining < 0 ? '#991b1b' : '#1e40af' }}>
          Total Allocated: <strong>{currentSum}</strong> / {targetTotal}
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, color: remaining === 0 ? '#059669' : remaining < 0 ? '#dc2626' : '#2563eb' }}>
          {remaining === 0 ? '✓ Balanced' : remaining < 0 ? `${Math.abs(remaining)} Over` : `${remaining} Remaining`}
        </span>
      </div>
      {question.options?.map((item: string, i: number) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <span style={{ fontSize: 14, color: '#374151', fontWeight: 500 }}>{item}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button type="button" onClick={() => onChange({ ...current, [item]: Math.max(0, (current[item] || 0) - 1) })} style={{ width: 32, height: 32, border: '1.5px solid #d1d5db', borderRadius: 8, background: '#fff', cursor: 'pointer', fontWeight: 700, fontSize: 16 }}>−</button>
            <input type="number" min="0" style={{ width: 80, border: '2px solid #d1d5db', borderRadius: 8, padding: '6px 10px', fontSize: 14, outline: 'none', textAlign: 'center' }} value={current[item] ?? ''} onChange={e => onChange({ ...current, [item]: Math.max(0, +e.target.value) })} placeholder="0" />
            <button type="button" onClick={() => onChange({ ...current, [item]: (current[item] || 0) + 1 })} style={{ width: 32, height: 32, border: '1.5px solid #d1d5db', borderRadius: 8, background: '#fff', cursor: 'pointer', fontWeight: 700, fontSize: 16 }}>+</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function SliderInput({ question, value, onChange }: { question: any; value: number; onChange: (v: number) => void }) {
  const min = question.scale_min ?? 0;
  const max = question.scale_max ?? 100;
  const currentVal = value !== undefined && value !== null ? value : Math.round((min + max) / 2);

  return (
    <div style={{ maxWidth: 480, padding: '10px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, fontSize: 13, color: '#6b7280', fontWeight: 600 }}>
        <span>{question.options?.[0] || min}</span>
        <div style={{ textAlign: 'center' }}>
          <span style={{ display: 'inline-block', background: '#4f46e5', color: '#fff', borderRadius: 8, padding: '4px 14px', fontSize: 18, fontWeight: 800 }}>{currentVal}</span>
        </div>
        <span>{question.options?.[1] || max}</span>
      </div>
      <input type="range" min={min} max={max} value={currentVal} onChange={e => onChange(+e.target.value)} style={{ width: '100%', accentColor: '#4f46e5', cursor: 'pointer', height: 6 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 12, color: '#d1d5db' }}>
        <span>{min}</span><span>{max}</span>
      </div>
    </div>
  );
}

function NPSInput({ question, value, onChange }: { question: any; value: number; onChange: (v: number) => void }) {
  return (
    <div style={{ maxWidth: 600 }}>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
        {Array.from({ length: 11 }, (_, i) => i).map(n => {
          const isSelected = value === n;
          const bg = n <= 6 ? (isSelected ? '#ef4444' : '#fff') : n <= 8 ? (isSelected ? '#f59e0b' : '#fff') : (isSelected ? '#10b981' : '#fff');
          const border = n <= 6 ? '#fca5a5' : n <= 8 ? '#fde68a' : '#6ee7b7';
          const textColor = isSelected ? '#fff' : n <= 6 ? '#991b1b' : n <= 8 ? '#92400e' : '#065f46';
          return (
            <button key={n} type="button" onClick={() => onChange(n)} style={{
              flex: 1, minWidth: 38, height: 44, borderRadius: 8, fontWeight: 700, fontSize: 15,
              border: `2px solid ${isSelected ? (n <= 6 ? '#dc2626' : n <= 8 ? '#d97706' : '#059669') : border}`,
              background: bg, color: textColor, cursor: 'pointer', transition: 'all 0.15s',
              transform: isSelected ? 'scale(1.1)' : 'none',
            }}>{n}</button>
          );
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#6b7280', fontWeight: 600 }}>
        <span>😞 {question.options?.[0] || 'Not at all likely'}</span>
        <div style={{ fontSize: 11, color: '#9ca3af', textAlign: 'center' }}>
          <span style={{ color: '#ef4444' }}>0–6 Detractors</span> · <span style={{ color: '#f59e0b' }}>7–8 Passives</span> · <span style={{ color: '#10b981' }}>9–10 Promoters</span>
        </div>
        <span>😍 {question.options?.[1] || 'Extremely likely'}</span>
      </div>
    </div>
  );
}

// ── Semantic Differential ─────────────────────────────────────────────────────
function SemanticDifferentialInput({ question, value, onChange }: { question: any; value: number; onChange: (v: number) => void }) {
  const scaleMax = question.scale_max || 7;
  const scalePoints = Array.from({ length: scaleMax }, (_, i) => i + 1);
  const leftPole = question.options?.[0] || 'Negative';
  const rightPole = question.options?.[1] || 'Positive';
  const midpoint = Math.ceil(scaleMax / 2);

  return (
    <div style={{ maxWidth: 560 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* Left label */}
        <div style={{ flex: '0 0 110px', textAlign: 'right' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#374151', lineHeight: 1.3 }}>{leftPole}</span>
        </div>
        {/* Scale buttons */}
        <div style={{ flex: 1, display: 'flex', gap: 6 }}>
          {scalePoints.map(n => {
            const isSelected = value === n;
            const isMid = n === midpoint;
            return (
              <button key={n} type="button" onClick={() => onChange(n)} style={{
                flex: 1, aspectRatio: '1', borderRadius: 10, fontWeight: 700, fontSize: 13,
                border: `2px solid ${isSelected ? '#4f46e5' : isMid ? '#e5e7eb' : '#e5e7eb'}`,
                background: isSelected ? '#4f46e5' : isMid ? '#f9fafb' : '#fff',
                color: isSelected ? '#fff' : isMid ? '#9ca3af' : '#6b7280',
                cursor: 'pointer', transition: 'all 0.15s',
                boxShadow: isSelected ? '0 4px 12px rgba(79,70,229,0.3)' : 'none',
                transform: isSelected ? 'translateY(-2px) scale(1.08)' : 'none',
                minWidth: 36, minHeight: 36,
              }}>{n}</button>
            );
          })}
        </div>
        {/* Right label */}
        <div style={{ flex: '0 0 110px', textAlign: 'left' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#374151', lineHeight: 1.3 }}>{rightPole}</span>
        </div>
      </div>
      {/* Gradient underbar */}
      <div style={{ margin: '8px 126px 0', height: 4, borderRadius: 99, background: 'linear-gradient(90deg, #ef4444, #e5e7eb 50%, #10b981)' }} />
      <p style={{ textAlign: 'center', fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
        {value ? `Selected: ${value}` : 'Click a number to respond'}
      </p>
    </div>
  );
}

// ── File Upload ───────────────────────────────────────────────────────────────
function FileUploadInput({ question, slug, value, onChange }: { question: any; slug: string; value: any; onChange: (v: any) => void }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const vr = question.validation_rules || {};
  const maxMB = vr.max_size_mb || 10;
  const acceptedTypes = vr.accepted_types || ['images', 'pdf'];

  const mimeMap: Record<string, string[]> = {
    images: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    pdf: ['application/pdf'],
    audio: ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4'],
    docs: ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
  };
  const acceptedMimes = acceptedTypes.flatMap((t: string) => mimeMap[t] || []);

  const handleFile = async (file: File) => {
    setUploadError('');
    if (acceptedMimes.length > 0 && !acceptedMimes.includes(file.type)) {
      setUploadError(`File type "${file.type}" is not accepted.`);
      return;
    }
    if (file.size > maxMB * 1024 * 1024) {
      setUploadError(`File exceeds ${maxMB} MB limit.`);
      return;
    }
    setUploading(true);
    try {
      const res = await publicApi.uploadFile(slug, file);
      onChange({ url: res.data.url, filename: res.data.filename, size: res.data.size, content_type: res.data.content_type });
    } catch (e: any) {
      setUploadError(e.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const typeLabels: Record<string, string> = { images: 'Images', pdf: 'PDF', audio: 'Audio', docs: 'Word Docs' };

  return (
    <div style={{ maxWidth: 480 }}>
      {!value ? (
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
          onClick={() => inputRef.current?.click()}
          style={{
            border: `2px dashed ${dragging ? '#4f46e5' : '#d1d5db'}`,
            borderRadius: 16, padding: '32px 24px', textAlign: 'center', cursor: 'pointer',
            background: dragging ? '#f0f0ff' : '#fafafa', transition: 'all 0.2s',
          }}
        >
          <input ref={inputRef} type="file" accept={acceptedMimes.join(',')} style={{ display: 'none' }} onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
          {uploading ? (
            <div>
              <RiLoader4Line size={32} style={{ color: '#4f46e5', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
              <p style={{ color: '#6b7280', fontWeight: 500 }}>Uploading...</p>
            </div>
          ) : (
            <div>
              <RiUploadCloud2Line size={36} style={{ color: dragging ? '#4f46e5' : '#9ca3af', margin: '0 auto 12px' }} />
              <p style={{ color: '#374151', fontWeight: 600, fontSize: 15 }}>Drop file here or click to browse</p>
              <p style={{ color: '#9ca3af', fontSize: 12, marginTop: 6 }}>
                Accepted: {acceptedTypes.map((t: string) => typeLabels[t] || t).join(', ')} · Max {maxMB} MB
              </p>
            </div>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', background: '#f0fdf4', border: '1.5px solid #bbf7d0', borderRadius: 12 }}>
          <RiFileLine size={24} style={{ color: '#10b981', flexShrink: 0 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontWeight: 600, color: '#065f46', fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value.filename}</p>
            <p style={{ color: '#6b7280', fontSize: 12 }}>{(value.size / 1024).toFixed(1)} KB · Uploaded</p>
          </div>
          <button type="button" onClick={() => onChange(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280' }}>
            <RiCloseLine size={20} />
          </button>
        </div>
      )}
      {uploadError && <p style={{ color: '#ef4444', fontSize: 13, marginTop: 8, fontWeight: 500 }}>{uploadError}</p>}
    </div>
  );
}

// ── Question Renderer ─────────────────────────────────────────────────────────
function QuestionRenderer({ question, value, onChange, slug, error }: any) {
  const displayOptions: string[] = useMemo(() => {
    const opts: string[] = question.options || [];
    if (question.randomize_options && opts.length > 1) {
      return seededShuffle(opts, questionSeed(question.id));
    }
    return opts;
  }, [question.id, question.options, question.randomize_options]);

  switch (question.type) {
    case 'short_text':             return <ShortTextInput question={question} value={value} onChange={onChange} error={error} />;
    case 'long_text':              return <LongTextInput question={question} value={value} onChange={onChange} error={error} />;
    case 'single_choice':          return <SingleChoiceInput question={question} value={value} onChange={onChange} displayOptions={displayOptions} />;
    case 'multi_choice':           return <MultiChoiceInput question={question} value={value} onChange={onChange} displayOptions={displayOptions} />;
    case 'dropdown':               return <SearchableDropdownInput question={question} value={value} onChange={onChange} displayOptions={displayOptions} />;
    case 'likert':                 return <LikertInput question={question} value={value} onChange={onChange} />;
    case 'rating':                 return <RatingInput question={question} value={value} onChange={onChange} />;
    case 'rank_order':             return <RankOrderInput question={question} value={value} onChange={onChange} displayOptions={displayOptions} />;
    case 'constant_sum':           return <ConstantSumInput question={question} value={value} onChange={onChange} />;
    case 'slider':                 return <SliderInput question={question} value={value} onChange={onChange} />;
    case 'nps':                    return <NPSInput question={question} value={value} onChange={onChange} />;
    case 'number':                 return <NumberInput question={question} value={value} onChange={onChange} error={error} />;
    case 'date':                   return <DateInput value={value} onChange={onChange} />;
    case 'matrix':                 return <MatrixInput question={question} value={value} onChange={onChange} />;
    case 'semantic_differential':  return <SemanticDifferentialInput question={question} value={value} onChange={onChange} />;
    case 'file_upload':            return <FileUploadInput question={question} slug={slug} value={value} onChange={onChange} />;
    case 'section_header':         return null;
    default:                       return <p style={{ color: '#9ca3af', fontSize: 13 }}>Unknown question type: {question.type}</p>;
  }
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function RespondentFormPage() {
  const router = useRouter();
  const { slug } = router.query as { slug: string };
  const { theme } = useThemeStore();
  const [survey, setSurvey] = useState<any>(null);
  const [questions, setQuestions] = useState<any[]>([]);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [participantEmail, setParticipantEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [alreadySubmitted, setAlreadySubmitted] = useState(false);
  const [error, setError] = useState('');
  const [emailFocused, setEmailFocused] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);

  // Force white/light theme on this page
  useEffect(() => {
    const root = document.documentElement;
    const originalClass = root.className;
    const originalColorScheme = root.style.colorScheme;
    root.classList.remove('dark');
    root.style.colorScheme = 'light';
    root.style.setProperty('--bg', '#f5f6fa');
    root.style.setProperty('--surface', '#ffffff');
    root.style.setProperty('--surface-2', '#f9fafb');
    root.style.setProperty('--text', '#111827');
    root.style.setProperty('--text-1', '#111827');
    root.style.setProperty('--text-2', '#374151');
    root.style.setProperty('--text-3', '#6b7280');
    root.style.setProperty('--border', '#e5e7eb');
    root.style.setProperty('--border-color', '#e5e7eb');
    return () => {
      root.className = originalClass;
      root.style.colorScheme = originalColorScheme;
      ['--bg', '--surface', '--surface-2', '--text', '--text-1', '--text-2', '--text-3', '--border', '--border-color'].forEach(p => root.style.removeProperty(p));
      root.classList.toggle('dark', theme === 'dark');
    };
  }, [theme]);

  useEffect(() => {
    if (!slug) return;
    publicApi.getSurvey(slug).then(r => {
      setSurvey(r.data.survey);
      setQuestions(r.data.questions || []);
    }).catch(() => setError('Survey not found or no longer active')).finally(() => setLoading(false));
  }, [slug]);

  // ── Derive visibility map from skip logic ─────────────────────────────────
  const visibilityMap = useMemo(() => {
    const map: Record<string, 'visible' | 'hidden'> = {};
    for (const q of questions) {
      map[q.id] = evaluateLogic(q, answers);
    }
    return map;
  }, [questions, answers]);

  const visibleQuestions = useMemo(() =>
    questions.filter(q => visibilityMap[q.id] === 'visible'),
    [questions, visibilityMap]
  );

  // ── Run validation on change if user has already attempted submit ─────────
  const updateAnswer = useCallback((qid: string, val: any) => {
    setAnswers(prev => {
      const next = { ...prev, [qid]: val };
      if (submitAttempted) {
        const q = questions.find(q => q.id === qid);
        if (q) {
          const err = validateAnswer(q, val);
          setValidationErrors(ve => ({ ...ve, [qid]: err || '' }));
        }
      }
      return next;
    });
  }, [submitAttempted, questions]);

  const handleSubmit = async () => {
    setSubmitAttempted(true);

    if (survey?.require_email && !participantEmail.trim()) {
      alert('Please provide your email address to submit the survey.');
      return;
    }

    // Validate all visible, required questions
    const newErrors: Record<string, string> = {};
    const missingRequired: any[] = [];

    for (const q of visibleQuestions) {
      if (q.type === 'section_header') continue;
      const answer = answers[q.id];
      const isAnswered = answer !== undefined && answer !== null && answer !== '' &&
        !(Array.isArray(answer) && answer.length === 0);

      if (q.required && !isAnswered) {
        missingRequired.push(q);
      }

      // Validate format even if not required (if answered)
      if (isAnswered) {
        const err = validateAnswer(q, answer);
        if (err) newErrors[q.id] = err;
      }
    }

    if (missingRequired.length > 0) {
      alert(`Please answer all required questions (${missingRequired.length} remaining).`);
      setValidationErrors(newErrors);
      return;
    }

    if (Object.values(newErrors).some(e => e)) {
      alert('Some answers have format errors. Please review and correct them before submitting.');
      setValidationErrors(newErrors);
      return;
    }

    setSubmitting(true);
    try {
      await publicApi.submitResponse(slug, { answers, participant_email: participantEmail.trim() });
      setSubmitted(true);
    } catch (e: any) {
      if (e.response?.status === 409) {
        setAlreadySubmitted(true);
      } else {
        alert('Submission failed. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  // ── Loading ───────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#f5f6fa', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 48, height: 48, border: '3px solid #e5e7eb', borderTopColor: '#4f46e5', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 16px' }} />
          <p style={{ color: '#9ca3af', fontSize: 14, fontWeight: 500 }}>Loading survey...</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div style={{ minHeight: '100vh', background: '#f5f6fa', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, fontFamily: 'Inter, sans-serif' }}>
        <div style={{ background: '#fff', borderRadius: 20, padding: 40, maxWidth: 420, width: '100%', textAlign: 'center', boxShadow: '0 8px 40px rgba(0,0,0,0.1)', border: '1px solid #fee2e2' }}>
          <div style={{ width: 64, height: 64, background: '#fef2f2', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' }}>
            <RiErrorWarningFill size={32} style={{ color: '#ef4444' }} />
          </div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: '#111827', marginBottom: 8 }}>Survey Unavailable</h1>
          <p style={{ color: '#6b7280', fontSize: 15, lineHeight: 1.6 }}>{error}</p>
          <p style={{ color: '#9ca3af', fontSize: 13, marginTop: 12 }}>The survey link may be incorrect or the survey has closed.</p>
        </div>
      </div>
    );
  }

  // ── Already Submitted ────────────────────────────────────────────────────
  if (alreadySubmitted) {
    return (
      <div style={{ minHeight: '100vh', background: '#f5f6fa', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, fontFamily: 'Inter, sans-serif' }}>
        <div style={{ background: '#fff', borderRadius: 20, padding: 40, maxWidth: 420, width: '100%', textAlign: 'center', boxShadow: '0 8px 40px rgba(0,0,0,0.1)' }}>
          <div style={{ width: 64, height: 64, background: '#eff6ff', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' }}>
            <RiErrorWarningFill size={32} style={{ color: '#4f46e5' }} />
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#111827', marginBottom: 10 }}>Already Submitted</h1>
          <p style={{ color: '#6b7280', fontSize: 15, lineHeight: 1.7 }}>Thank you — you have already completed this survey.</p>
          <p style={{ color: '#9ca3af', fontSize: 13, marginTop: 12 }}>Multiple submissions using the same email address are not allowed.</p>
        </div>
      </div>
    );
  }

  // ── Thank You ────────────────────────────────────────────────────────────
  if (submitted) {
    return (
      <div style={{ minHeight: '100vh', background: '#f5f6fa', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, fontFamily: 'Inter, sans-serif' }}>
        <div style={{ background: '#fff', borderRadius: 20, padding: 48, maxWidth: 440, width: '100%', textAlign: 'center', boxShadow: '0 8px 40px rgba(0,0,0,0.1)' }}>
          <div style={{ width: 72, height: 72, background: 'linear-gradient(135deg, #d1fae5, #a7f3d0)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' }}>
            <RiCheckboxCircleFill size={38} style={{ color: '#10b981' }} />
          </div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#111827', marginBottom: 12 }}>Thank You!</h1>
          <p style={{ color: '#4b5563', fontSize: 15, lineHeight: 1.7 }}>
            Your response to <strong style={{ color: '#111827' }}>{survey?.title}</strong> has been recorded successfully.
          </p>
          <div style={{ marginTop: 28, padding: '14px 24px', background: '#f0fdf4', borderRadius: 12, border: '1px solid #bbf7d0' }}>
            <p style={{ color: '#166534', fontSize: 13, fontWeight: 500 }}>Your response has been saved</p>
          </div>
        </div>
      </div>
    );
  }

  if (!survey) return null;

  const surveyTheme = survey?.theme || {};
  const bgColor = surveyTheme.backgroundColor || '#f5f6fa';
  const textColor = surveyTheme.textColor || '#111827';
  const hasBackground = !!surveyTheme.backgroundImageUrl;
  const fontFamily = surveyTheme.fontFamily === 'Roboto' ? 'Roboto, sans-serif' :
    surveyTheme.fontFamily === 'Merriweather' ? 'Merriweather, serif' :
      surveyTheme.fontFamily === 'Outfit' ? 'Outfit, sans-serif' : 'Inter, sans-serif';

  const answered = Object.keys(answers).filter(qid => {
    const v = answers[qid];
    return v !== undefined && v !== null && v !== '' && !(Array.isArray(v) && v.length === 0);
  }).length;
  const requiredCount = visibleQuestions.filter(q => q.required && q.type !== 'section_header').length;
  const progress = requiredCount > 0 ? Math.min(100, Math.round((answered / requiredCount) * 100)) : 100;

  return (
    <div style={{ minHeight: '100vh', background: bgColor, backgroundImage: hasBackground ? `url(${surveyTheme.backgroundImageUrl})` : 'none', backgroundSize: 'cover', backgroundPosition: 'center', backgroundAttachment: 'fixed', fontFamily, position: 'relative' }}>
      {hasBackground && <div style={{ position: 'fixed', inset: 0, background: `rgba(0,0,0,${surveyTheme.overlayOpacity ?? 0.4})`, zIndex: 0 }} />}

      {/* Sticky Progress Bar */}
      <div style={{ position: 'sticky', top: 0, zIndex: 50, background: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(12px)', borderBottom: '1px solid #e5e7eb', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
        <div style={{ maxWidth: 700, margin: '0 auto', padding: '12px 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ flex: 1, height: 8, borderRadius: 99, background: '#e5e7eb', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${progress}%`, borderRadius: 99, background: 'linear-gradient(90deg, #4f46e5, #7c3aed)', transition: 'width 0.6s ease' }} />
          </div>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#4f46e5', minWidth: 68, textAlign: 'right', letterSpacing: '0.04em' }}>
            {progress}% Done
          </span>
        </div>
      </div>

      {/* Content */}
      <div style={{ maxWidth: 700, margin: '0 auto', padding: '32px 16px 80px', position: 'relative', zIndex: 10, fontSize: surveyTheme.fontSize === 'small' ? 14 : surveyTheme.fontSize === 'large' ? 18 : 16 }}>

        {/* Header Picture */}
        {surveyTheme.headerPictureUrl && (
          <div style={{ width: '100%', height: 200, borderRadius: '16px 16px 0 0', overflow: 'hidden', boxShadow: '0 2px 12px rgba(0,0,0,0.1)' }}>
            <img src={surveyTheme.headerPictureUrl} alt="Survey Header" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </div>
        )}

        {/* Header Card */}
        <div style={{
          background: '#fff', borderRadius: surveyTheme.headerPictureUrl ? '0 0 16px 16px' : 16,
          padding: '36px 36px 28px', marginBottom: 20,
          boxShadow: '0 2px 16px rgba(0,0,0,0.07)', border: '1px solid #f0f0f0', position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: 'linear-gradient(90deg, #4f46e5, #7c3aed, #ec4899)' }} />
          {surveyTheme.headerText && (
            <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: '#6366f1', textTransform: 'uppercase', marginBottom: 12 }}>{surveyTheme.headerText}</p>
          )}
          <h1 style={{ fontSize: 28, fontWeight: 800, color: textColor, lineHeight: 1.25, marginBottom: 12 }}>{survey?.title}</h1>
          {survey?.description && (
            <p style={{ fontSize: 15, color: '#6b7280', lineHeight: 1.7, marginBottom: 16 }}>{survey.description}</p>
          )}
          <div style={{ paddingTop: 16, borderTop: '1px solid #f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#ef4444' }}>* Required questions</span>
            <span style={{ fontSize: 12, color: '#9ca3af' }}>{visibleQuestions.filter(q => q.type !== 'section_header').length} questions</span>
          </div>
        </div>

        {/* Email field */}
        {survey?.require_email && (
          <div style={{ background: '#fff', borderRadius: 16, padding: '24px 28px', marginBottom: 20, boxShadow: '0 2px 12px rgba(0,0,0,0.06)', border: '1.5px solid #e5e7eb' }}>
            <label style={{ display: 'block', marginBottom: 8 }}>
              <span style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>Email Address</span>
              <span style={{ color: '#ef4444', marginLeft: 4, fontWeight: 700 }}>*</span>
            </label>
            <p style={{ fontSize: 13, color: '#9ca3af', marginBottom: 12 }}>Please enter your email to submit</p>
            <input
              type="email" required placeholder="you@example.com" value={participantEmail}
              onChange={e => setParticipantEmail(e.target.value)}
              onFocus={() => setEmailFocused(true)} onBlur={() => setEmailFocused(false)}
              style={{
                width: '100%', maxWidth: 380,
                border: `2px solid ${emailFocused ? '#4f46e5' : '#d1d5db'}`,
                borderRadius: 10, padding: '12px 16px', background: '#fff', color: '#111827',
                outline: 'none', fontSize: 15,
                boxShadow: emailFocused ? '0 0 0 4px rgba(79,70,229,0.12)' : 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>
        )}

        {/* Questions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {questions.map((q, i) => {
            const visibility = visibilityMap[q.id];
            if (visibility === 'hidden') return null;

            if (q.type === 'section_header') {
              return (
                <div key={q.id} style={{ paddingTop: 16, paddingBottom: 4 }}>
                  <h2 style={{ fontSize: 20, fontWeight: 800, color: '#4f46e5', letterSpacing: '-0.01em' }}>{q.text}</h2>
                  <div style={{ height: 3, width: 36, background: 'linear-gradient(90deg, #4f46e5, #7c3aed)', borderRadius: 99, marginTop: 8 }} />
                  {q.helper_text && (
                    <p style={{ fontSize: 13, color: '#6b7280', marginTop: 6, fontStyle: 'italic' }}>{q.helper_text}</p>
                  )}
                </div>
              );
            }

            const isAnswered = (() => {
              const v = answers[q.id];
              return v !== undefined && v !== null && v !== '' && !(Array.isArray(v) && v.length === 0);
            })();
            const qError = validationErrors[q.id];
            const visibleIndex = visibleQuestions.filter(vq => vq.type !== 'section_header').findIndex(vq => vq.id === q.id) + 1;

            return (
              <div key={q.id} style={{
                background: '#fff', borderRadius: 16, padding: '24px 28px',
                border: `1.5px solid ${qError ? '#fca5a5' : isAnswered ? '#c7d2fe' : '#e5e7eb'}`,
                boxShadow: qError ? '0 2px 12px rgba(239,68,68,0.08)' : isAnswered ? '0 2px 12px rgba(79,70,229,0.07)' : '0 2px 8px rgba(0,0,0,0.05)',
                transition: 'all 0.2s ease',
              }}>
                {/* Question header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 16 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                    background: qError ? '#fee2e2' : isAnswered ? '#4f46e5' : '#f3f4f6',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, fontWeight: 800, color: qError ? '#dc2626' : isAnswered ? '#fff' : '#6b7280',
                    transition: 'all 0.2s',
                  }}>
                    {qError ? '!' : isAnswered ? <RiCheckFill size={15} /> : visibleIndex}
                  </div>
                  <div style={{ flex: 1 }}>
                    <p style={{ fontSize: 15, fontWeight: 700, color: textColor, lineHeight: 1.5 }}>
                      {q.text}
                      {q.required && <span style={{ color: '#ef4444', marginLeft: 4, fontWeight: 700 }}>*</span>}
                    </p>
                    {/* Helper text */}
                    {q.helper_text && (
                      <p style={{ fontSize: 13, color: '#9ca3af', marginTop: 5, lineHeight: 1.6, fontStyle: 'italic' }}>{q.helper_text}</p>
                    )}
                  </div>
                </div>

                <div style={{ paddingLeft: 46 }}>
                  <QuestionRenderer
                    question={q}
                    value={answers[q.id]}
                    onChange={(val: any) => updateAnswer(q.id, val)}
                    slug={slug}
                    error={qError}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Submit Button */}
        <div style={{ marginTop: 32 }}>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{
              width: '100%', padding: '17px 28px',
              background: submitting ? '#a5b4fc' : 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
              color: '#fff', border: 'none', borderRadius: 14,
              fontSize: 16, fontWeight: 700, cursor: submitting ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
              boxShadow: submitting ? 'none' : '0 6px 24px rgba(79,70,229,0.4)',
              transition: 'all 0.2s', letterSpacing: '0.01em',
            }}
          >
            {submitting
              ? <><RiLoader4Line size={22} style={{ animation: 'spin 0.8s linear infinite' }} /> Submitting...</>
              : <><RiSendPlaneFill size={20} /> Submit Response</>
            }
          </button>
          <p style={{ textAlign: 'center', fontSize: 12, color: '#9ca3af', marginTop: 16, fontWeight: 500 }}>
            Powered by <strong style={{ color: '#6b7280' }}>ResearchForm</strong> · Secure & Confidential
          </p>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
      `}</style>
    </div>
  );
}

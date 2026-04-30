// src/pages/s/[slug].tsx — Public respondent form
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { publicApi } from '../../lib/api';
import { CheckCircle, AlertCircle, Loader2, ChevronRight, ChevronLeft, Send } from 'lucide-react';
import { useThemeStore } from '../../lib/store';

function QuestionRenderer({ question, value, onChange }: any) {
  switch (question.type) {
    case 'short_text':
      return (
        <input
          className="input"
          placeholder="Your answer..."
          value={value || ''}
          onChange={e => onChange(e.target.value)}
        />
      );

    case 'long_text':
      return (
        <textarea
          className="input"
          rows={4}
          placeholder="Your answer..."
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          style={{ resize: 'vertical' }}
        />
      );

    case 'single_choice':
      return (
        <div className="space-y-2">
          {question.options.map((opt: string, i: number) => (
            <label key={i} className="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all"
              style={{ border: `2px solid ${value === opt ? 'var(--brand)' : 'var(--border)'}`, background: value === opt ? 'rgba(99,102,241,0.06)' : 'var(--surface)' }}>
              <input type="radio" name={question.id} value={opt} checked={value === opt} onChange={() => onChange(opt)}
                className="accent-[var(--brand)]" />
              <span className="text-sm" style={{ color: 'var(--text)' }}>{opt}</span>
            </label>
          ))}
        </div>
      );

    case 'multi_choice':
      const selected: string[] = Array.isArray(value) ? value : [];
      return (
        <div className="space-y-2">
          {question.options.map((opt: string, i: number) => {
            const checked = selected.includes(opt);
            return (
              <label key={i} className="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all"
                style={{ border: `2px solid ${checked ? 'var(--brand)' : 'var(--border)'}`, background: checked ? 'rgba(99,102,241,0.06)' : 'var(--surface)' }}>
                <input type="checkbox" checked={checked}
                  onChange={() => onChange(checked ? selected.filter(s => s !== opt) : [...selected, opt])}
                  className="accent-[var(--brand)]" />
                <span className="text-sm" style={{ color: 'var(--text)' }}>{opt}</span>
              </label>
            );
          })}
        </div>
      );

    case 'likert':
      return (
        <div>
          <div className="flex justify-between text-xs mb-2" style={{ color: 'var(--text-3)' }}>
            <span>{question.options[0]}</span>
            <span>{question.options[question.options.length - 1]}</span>
          </div>
          <div className="flex gap-2">
            {question.options.map((opt: string, i: number) => {
              const val = i + 1;
              const isSelected = value === val;
              return (
                <button
                  key={i}
                  onClick={() => onChange(val)}
                  className="flex-1 py-3 rounded-xl font-bold text-sm transition-all"
                  style={{
                    border: `2px solid ${isSelected ? 'var(--brand)' : 'var(--border)'}`,
                    background: isSelected ? 'var(--brand)' : 'var(--surface)',
                    color: isSelected ? '#fff' : 'var(--text-2)',
                    minWidth: 40,
                  }}
                  title={opt}
                >
                  {val}
                </button>
              );
            })}
          </div>
        </div>
      );

    case 'rating':
      return (
        <div className="flex gap-2 flex-wrap">
          {Array.from({ length: question.scale_max }, (_, i) => i + 1).map(n => (
            <button
              key={n}
              onClick={() => onChange(n)}
              className="w-11 h-11 rounded-full font-bold text-sm transition-all"
              style={{
                border: `2px solid ${value >= n ? 'var(--brand)' : 'var(--border)'}`,
                background: value >= n ? 'var(--brand)' : 'var(--surface)',
                color: value >= n ? '#fff' : 'var(--text-2)',
              }}
            >
              {n}
            </button>
          ))}
        </div>
      );

    case 'number':
      return (
        <input
          type="number"
          className="input w-48"
          placeholder="0"
          value={value || ''}
          onChange={e => onChange(+e.target.value)}
        />
      );

    case 'date':
      return (
        <input
          type="date"
          className="input w-56"
          value={value || ''}
          onChange={e => onChange(e.target.value)}
        />
      );

    case 'matrix':
      const matrixVal: Record<string, number> = value || {};
      return (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="p-2 text-left" style={{ color: 'var(--text-3)' }}></th>
                {question.columns?.map((col: string, j: number) => (
                  <th key={j} className="p-2 text-center font-medium" style={{ color: 'var(--text-2)', minWidth: 80 }}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {question.rows?.map((row: string, i: number) => (
                <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                  <td className="p-2 pr-4" style={{ color: 'var(--text)' }}>{row}</td>
                  {question.columns?.map((_: any, j: number) => (
                    <td key={j} className="p-2 text-center">
                      <input
                        type="radio"
                        name={`${question.id}_${i}`}
                        checked={matrixVal[row] === j + 1}
                        onChange={() => onChange({ ...matrixVal, [row]: j + 1 })}
                        className="accent-[var(--brand)]"
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );

    case 'section_header':
      return null;

    default:
      return <p className="text-sm" style={{ color: 'var(--text-3)' }}>Unknown question type: {question.type}</p>;
  }
}

export default function RespondentFormPage() {
  const router = useRouter();
  const { slug } = router.query as { slug: string };
  const { theme } = useThemeStore();
  const [survey, setSurvey] = useState<any>(null);
  const [questions, setQuestions] = useState<any[]>([]);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  useEffect(() => {
    if (!slug) return;
    publicApi.getSurvey(slug).then(r => {
      setSurvey(r.data.survey);
      setQuestions(r.data.questions || []);
    }).catch(() => setError('Survey not found or no longer active')).finally(() => setLoading(false));
  }, [slug]);

  const handleSubmit = async () => {
    const missing = questions.filter(q => q.required && q.type !== 'section_header' && !answers[q.id]);
    if (missing.length > 0) {
      alert(`Please answer all required questions (${missing.length} remaining)`);
      return;
    }
    setSubmitting(true);
    try {
      await publicApi.submitResponse(slug, { answers });
      setSubmitted(true);
    } catch {
      alert('Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
      <Loader2 size={36} className="animate-spin" style={{ color: 'var(--brand)' }} />
    </div>
  );

  if (error) return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
      <div className="text-center">
        <AlertCircle size={48} className="mx-auto mb-4" style={{ color: 'var(--danger)' }} />
        <p className="font-display font-bold text-xl mb-2" style={{ color: 'var(--text)' }}>{error}</p>
        <p style={{ color: 'var(--text-2)' }}>The survey link may be incorrect or the survey has closed.</p>
      </div>
    </div>
  );

  if (submitted) return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
      <div className="text-center max-w-sm px-6">
        <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6" style={{ background: 'rgba(16,185,129,0.12)' }}>
          <CheckCircle size={40} style={{ color: 'var(--success)' }} />
        </div>
        <h1 className="font-display font-bold text-2xl mb-3" style={{ color: 'var(--text)' }}>Thank You!</h1>
        <p className="text-sm" style={{ color: 'var(--text-2)' }}>
          Your response to <strong>{survey?.title}</strong> has been recorded successfully.
        </p>
      </div>
    </div>
  );

  const answered = Object.keys(answers).length;
  const required = questions.filter(q => q.required && q.type !== 'section_header').length;
  const progress = required > 0 ? Math.round((answered / required) * 100) : 100;

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <div style={{ background: 'var(--brand)', padding: '40px 24px 80px' }}>
        <div className="max-w-2xl mx-auto">
          <p className="text-white/70 text-sm mb-2 font-semibold">RESEARCH SURVEY</p>
          <h1 className="font-display font-bold text-2xl text-white mb-3">{survey?.title}</h1>
          {survey?.description && (
            <p className="text-white/80 text-sm leading-relaxed">{survey.description}</p>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)', position: 'sticky', top: 0, zIndex: 10 }}>
        <div className="max-w-2xl mx-auto px-6 py-3 flex items-center gap-4">
          <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--surface-2)' }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${progress}%`, background: 'var(--brand)' }}
            />
          </div>
          <span className="text-xs font-semibold" style={{ color: 'var(--text-2)', minWidth: 60, textAlign: 'right' }}>
            {answered}/{required} answered
          </span>
        </div>
      </div>

      {/* Form */}
      <div className="max-w-2xl mx-auto px-6 pb-20" style={{ marginTop: '-40px' }}>
        <div className="space-y-4">
          {questions.map((q, i) => {
            if (q.type === 'section_header') {
              return (
                <div key={q.id} className="pt-6 pb-2">
                  <h2 className="font-display font-bold text-lg border-b pb-3" style={{ color: 'var(--text)', borderColor: 'var(--border)' }}>
                    {q.text}
                  </h2>
                </div>
              );
            }
            return (
              <div key={q.id} className="card p-6 animate-slide-up" style={{ animationDelay: `${i * 0.05}s` }}>
                <div className="flex items-start gap-2 mb-4">
                  <span className="text-sm font-bold mt-0.5" style={{ color: 'var(--brand)', minWidth: 24 }}>{i + 1}.</span>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{q.text}</p>
                    {q.required && <span className="text-xs" style={{ color: 'var(--danger)' }}>* Required</span>}
                  </div>
                </div>
                <QuestionRenderer
                  question={q}
                  value={answers[q.id]}
                  onChange={(val: any) => setAnswers(a => ({ ...a, [q.id]: val }))}
                />
              </div>
            );
          })}

          {/* Submit */}
          <button
            className="btn btn-primary w-full btn-lg"
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            {submitting ? 'Submitting...' : 'Submit Response'}
          </button>

          <p className="text-center text-xs pb-6" style={{ color: 'var(--text-3)' }}>
            Powered by <strong>ResearchForm</strong> · Your responses are confidential
          </p>
        </div>
      </div>
    </div>
  );
}

// src/pages/analysis/power.tsx  — Standalone Power Analysis & Sample Size Calculator
import React, { useState, useCallback } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { api } from '../../lib/api';
import { RiFlaskFill, RiLoader4Line, RiInformationFill, RiArrowRightSFill, RiCheckboxCircleFill, RiBarChart2Fill } from 'react-icons/ri';
import toast from 'react-hot-toast';
import Head from 'next/head';

// ─── Types ────────────────────────────────────────────────────────────────────

type TestType = 'independent_t' | 'paired_t' | 'anova' | 'correlation' | 'chi_square' | 'regression';

interface PowerResult {
  test_name: string;
  result: {
    n_per_group?: number;
    n_pairs?: number;
    n_required?: number;
    total_n?: number;
    achieved_power: number;
    alpha: number;
    effect_size_d?: number;
    effect_size_f?: number;
    effect_size_f2?: number;
    effect_size_w?: number;
    r?: number;
    k_groups?: number;
    predictors?: number;
  };
  power_curve: { n: number; power: number }[];
  interpretation: string;
  effect_size_guide: Record<string, number>;
  error?: string;
}

// ─── Effect size guide data ────────────────────────────────────────────────────

const TESTS: { id: TestType; label: string; effectLabel: string; effectKey: string; defaultEffect: number; guide: {small:number;medium:number;large:number} }[] = [
  { id: 'independent_t', label: 'Independent t-test', effectLabel: "Cohen's d", effectKey: 'cohen_d', defaultEffect: 0.5, guide: {small:0.2,medium:0.5,large:0.8} },
  { id: 'paired_t',      label: 'Paired t-test',      effectLabel: "Cohen's d", effectKey: 'cohen_d', defaultEffect: 0.5, guide: {small:0.2,medium:0.5,large:0.8} },
  { id: 'anova',         label: 'One-way ANOVA',       effectLabel: "Cohen's f", effectKey: 'cohen_f', defaultEffect: 0.25, guide: {small:0.10,medium:0.25,large:0.40} },
  { id: 'correlation',   label: 'Correlation (r)',     effectLabel: 'Pearson r', effectKey: 'pearson_r', defaultEffect: 0.3, guide: {small:0.10,medium:0.30,large:0.50} },
  { id: 'chi_square',    label: 'Chi-square',          effectLabel: "Cohen's w", effectKey: 'cohen_w', defaultEffect: 0.3, guide: {small:0.10,medium:0.30,large:0.50} },
  { id: 'regression',    label: 'Multiple Regression', effectLabel: "Cohen's f²", effectKey: 'cohen_f2', defaultEffect: 0.15, guide: {small:0.02,medium:0.15,large:0.35} },
];

// ─── Mini power curve chart ────────────────────────────────────────────────────

function PowerCurveChart({ data, targetPower }: { data: {n:number;power:number}[]; targetPower: number }) {
  if (!data || data.length === 0) return null;
  const W = 480, H = 200, PADL = 48, PADB = 36, PADR = 16, PADT = 16;
  const maxN = data[data.length - 1]?.n || 300;
  const xScale = (n: number) => PADL + ((n - (data[0]?.n || 10)) / (maxN - (data[0]?.n || 10))) * (W - PADL - PADR);
  const yScale = (p: number) => PADT + (1 - p) * (H - PADT - PADB);

  const path = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${xScale(d.n).toFixed(1)},${yScale(d.power).toFixed(1)}`).join(' ');
  const targetY = yScale(targetPower / 100);

  // Find the n where power first reaches target
  const crossover = data.find(d => d.power >= targetPower / 100);

  return (
    <svg width={W} height={H} style={{ overflow: 'visible', display: 'block' }}>
      {/* Grid lines */}
      {[0.5, 0.6, 0.7, 0.8, 0.9, 1.0].map(p => (
        <g key={p}>
          <line x1={PADL} x2={W - PADR} y1={yScale(p)} y2={yScale(p)} stroke="var(--border)" strokeWidth={0.5} strokeDasharray="4,4" />
          <text x={PADL - 6} y={yScale(p) + 4} textAnchor="end" fontSize={10} fill="var(--text-3)">{(p*100).toFixed(0)}%</text>
        </g>
      ))}
      {/* Target power line */}
      <line x1={PADL} x2={W - PADR} y1={targetY} y2={targetY} stroke="#6366f1" strokeWidth={1.5} strokeDasharray="6,3" opacity={0.7} />
      <text x={W - PADR + 2} y={targetY + 4} fontSize={10} fill="#6366f1">Target</text>
      {/* Crossover marker */}
      {crossover && (
        <>
          <line x1={xScale(crossover.n)} x2={xScale(crossover.n)} y1={PADT} y2={H - PADB} stroke="#10b981" strokeWidth={1.5} strokeDasharray="4,4" opacity={0.8} />
          <text x={xScale(crossover.n)} y={PADT - 4} textAnchor="middle" fontSize={10} fill="#10b981" fontWeight="700">n={crossover.n}</text>
        </>
      )}
      {/* Curve fill */}
      <defs>
        <linearGradient id="pwrGrad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${path} L${xScale(maxN)},${H - PADB} L${PADL},${H - PADB} Z`} fill="url(#pwrGrad)" />
      {/* Curve */}
      <path d={path} fill="none" stroke="#6366f1" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
      {/* X-axis labels */}
      {data.filter((_, i) => i % 4 === 0).map(d => (
        <text key={d.n} x={xScale(d.n)} y={H - PADB + 14} textAnchor="middle" fontSize={10} fill="var(--text-3)">{d.n}</text>
      ))}
      <text x={W / 2} y={H - 2} textAnchor="middle" fontSize={11} fill="var(--text-2)">Sample Size (n)</text>
    </svg>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function PowerPage() {
  const [test, setTest]           = useState<TestType>('independent_t');
  const [effectSize, setEffect]   = useState(0.5);
  const [alpha, setAlpha]         = useState(0.05);
  const [power, setPower]         = useState(80);
  const [kGroups, setKGroups]     = useState(3);
  const [predictors, setPred]     = useState(3);
  const [result, setResult]       = useState<PowerResult | null>(null);
  const [loading, setLoading]     = useState(false);

  const currentTest = TESTS.find(t => t.id === test) || TESTS[0];

  const calculate = useCallback(async () => {
    setLoading(true);
    try {
      const body: Record<string, unknown> = {
        test,
        effect_size: effectSize,
        alpha,
        power: power / 100,
        k_groups: kGroups,
        predictors,
        df_val: 1,
      };
      const res = await api.post('/api/power/calculate', body);
      setResult(res.data);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Calculation failed');
    } finally {
      setLoading(false);
    }
  }, [test, effectSize, alpha, power, kGroups, predictors]);

  const innerResult = result?.result || (result as any)?.additional_stats?.result || result || {};
  const mainN = innerResult?.n_per_group ?? innerResult?.n_pairs ?? innerResult?.n_required ?? (result as any)?.n ?? null;
  const totalN = innerResult?.total_n ?? (result as any)?.n ?? null;
  const nPerGroup = innerResult?.n_per_group ?? null;
  const kGroupsVal = innerResult?.k_groups ?? kGroups ?? 2;
  const achievedPower = innerResult?.achieved_power ?? (result as any)?.statistic?.value ?? (power / 100);
  const interpretationText = result?.interpretation || (result as any)?.conclusion || '';
  const testDisplayName = (result?.test_name || (result as any)?.test_name || '').replace('Power Analysis — ', '');
  const effectSizeVal = (innerResult?.effect_size_d ?? innerResult?.effect_size_f ?? innerResult?.effect_size_f2 ?? innerResult?.effect_size_w ?? innerResult?.r ?? effectSize)?.toString();
  const alphaVal = (innerResult?.alpha ?? (result as any)?.alpha ?? alpha)?.toString();
  const powerCurve = result?.power_curve || (result as any)?.additional_stats?.power_curve || [];

  const sliderStyle: React.CSSProperties = { width: '100%', accentColor: '#6366f1', cursor: 'pointer' };
  const cardStyle: React.CSSProperties = {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 16, padding: 24,
  };

  return (
    <AppLayout>
      <Head>
        <title>Power Analysis & Sample Size Calculator | ResearchForm</title>
        <meta name="description" content="Calculate required sample sizes and statistical power for t-tests, ANOVA, correlation, chi-square, and regression studies." />
      </Head>

      <div style={{ maxWidth: 960, margin: '-12px auto 0', padding: '0 20px 24px' }}>
        {/* ── Hero Header Card — same design DNA as Credit Wallet ── */}
        <div style={{
          position: 'relative', borderRadius: 24, overflow: 'hidden', marginBottom: 28,
          background: 'linear-gradient(135deg, #090D16 0%, #111827 50%, #0F172A 100%)',
          border: '1px solid #1E293B',
          boxShadow: '0 20px 40px -15px rgba(0,0,0,0.4)',
          padding: '24px 40px',
          color: '#FFFFFF',
        }}>
          {/* Glowing ambient orbs */}
          <div style={{ position: 'absolute', top: -70, right: -70, width: 300, height: 300, borderRadius: '50%', background: 'radial-gradient(circle, rgba(99,102,241,0.35) 0%, transparent 70%)', filter: 'blur(35px)', pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', bottom: -80, left: '18%', width: 360, height: 360, borderRadius: '50%', background: 'radial-gradient(circle, rgba(16,185,129,0.18) 0%, transparent 70%)', filter: 'blur(45px)', pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', top: '30%', left: -60, width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%)', filter: 'blur(30px)', pointerEvents: 'none' }} />

          {/* Subtle dot-grid texture overlay */}
          <div style={{
            position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.04,
            backgroundImage: 'radial-gradient(circle, #ffffff 1px, transparent 1px)',
            backgroundSize: '22px 22px',
          }} />

          {/* Content */}
          <div style={{ position: 'relative', zIndex: 1 }}>
            {/* Main title */}
            <h1 style={{
              margin: '0', fontSize: 34, fontWeight: 800,
              color: '#FFFFFF', fontFamily: 'Syne, sans-serif',
              lineHeight: 1.1, letterSpacing: '-0.02em',
              textShadow: '0 2px 12px rgba(0,0,0,0.4)',
            }}>
              Power Analysis
            </h1>




          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Left — Controls */}
          <div style={cardStyle}>
            <p className="font-semibold text-sm mb-4" style={{ color: 'var(--text)' }}>Configure Analysis</p>

            {/* Test type */}
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>Statistical Test</label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 20 }}>
              {TESTS.map(t => (
                <button key={t.id} onClick={() => { setTest(t.id); setEffect(t.defaultEffect); }}
                  style={{
                    padding: '8px 10px', borderRadius: 10, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                    border: `2px solid ${test === t.id ? '#6366f1' : 'var(--border)'}`,
                    background: test === t.id ? 'rgba(99,102,241,0.08)' : 'var(--surface-2)',
                    color: test === t.id ? '#6366f1' : 'var(--text-2)',
                    textAlign: 'left', transition: 'all 0.15s',
                  }}>
                  {t.label}
                </button>
              ))}
            </div>

            {/* Effect size */}
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: 4 }}>
              {currentTest.effectLabel} = <span style={{ color: '#6366f1', fontWeight: 800 }}>{effectSize.toFixed(2)}</span>
            </label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
              {(['small','medium','large'] as const).map(s => (
                <button key={s} onClick={() => setEffect(currentTest.guide[s])}
                  style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
                    border: '1px solid var(--border)',
                    background: effectSize === currentTest.guide[s] ? 'rgba(99,102,241,0.1)' : 'transparent',
                    color: effectSize === currentTest.guide[s] ? '#6366f1' : 'var(--text-3)',
                    fontWeight: 600,
                  }}>
                  {s} ({currentTest.guide[s]})
                </button>
              ))}
            </div>
            <input type="range" min={0.01} max={test === 'correlation' ? 0.99 : 2.0} step={0.01}
              value={effectSize} onChange={e => setEffect(parseFloat(e.target.value))}
              style={{ ...sliderStyle, marginBottom: 20 }} />

            {/* Alpha */}
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: 4 }}>
              Significance Level (α) = <span style={{ color: '#6366f1', fontWeight: 800 }}>{alpha}</span>
            </label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
              {[0.10, 0.05, 0.01, 0.001].map(a => (
                <button key={a} onClick={() => setAlpha(a)}
                  style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
                    border: '1px solid var(--border)',
                    background: alpha === a ? 'rgba(99,102,241,0.1)' : 'transparent',
                    color: alpha === a ? '#6366f1' : 'var(--text-3)', fontWeight: 600,
                  }}>
                  {a}
                </button>
              ))}
            </div>
            <input type="range" min={0.001} max={0.10} step={0.001}
              value={alpha} onChange={e => setAlpha(parseFloat(e.target.value))}
              style={{ ...sliderStyle, marginBottom: 20 }} />

            {/* Desired power */}
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: 4 }}>
              Desired Power = <span style={{ color: '#6366f1', fontWeight: 800 }}>{power}%</span>
            </label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
              {[70, 80, 90, 95].map(p => (
                <button key={p} onClick={() => setPower(p)}
                  style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 20, cursor: 'pointer',
                    border: '1px solid var(--border)',
                    background: power === p ? 'rgba(99,102,241,0.1)' : 'transparent',
                    color: power === p ? '#6366f1' : 'var(--text-3)', fontWeight: 600,
                  }}>
                  {p}%
                </button>
              ))}
            </div>
            <input type="range" min={50} max={99} step={1}
              value={power} onChange={e => setPower(parseInt(e.target.value))}
              style={{ ...sliderStyle, marginBottom: 20 }} />

            {/* Conditional extras */}
            {test === 'anova' && (
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: 4 }}>
                  Number of Groups = <span style={{ color: '#6366f1', fontWeight: 800 }}>{kGroups}</span>
                </label>
                <input type="range" min={2} max={10} step={1} value={kGroups}
                  onChange={e => setKGroups(parseInt(e.target.value))} style={sliderStyle} />
              </div>
            )}
            {test === 'regression' && (
              <div style={{ marginBottom: 20 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: 4 }}>
                  Number of Predictors = <span style={{ color: '#6366f1', fontWeight: 800 }}>{predictors}</span>
                </label>
                <input type="range" min={1} max={20} step={1} value={predictors}
                  onChange={e => setPred(parseInt(e.target.value))} style={sliderStyle} />
              </div>
            )}

            <button onClick={calculate} disabled={loading}
              style={{
                width: '100%', padding: '12px 0', borderRadius: 12, border: 'none',
                background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', color: '#fff',
                fontWeight: 700, fontSize: 14, cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                opacity: loading ? 0.8 : 1, transition: 'all 0.2s',
              }}>
              {loading && <RiLoader4Line className="animate-spin" size={16} />}
              {loading ? 'Calculating...' : 'Calculate Sample Size'}
            </button>
          </div>

          {/* Right — Results */}
          <div>
            {!result && (
              <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 300, opacity: 0.7 }}>
                <RiBarChart2Fill size={40} style={{ color: 'var(--text-3)', marginBottom: 12 }} />
                <p style={{ color: 'var(--text-3)', fontSize: 13, textAlign: 'center' }}>
                  Configure your parameters and click<br />"Calculate Sample Size" to see results.
                </p>
              </div>
            )}

            {result && !result.error && (
              <>
                {/* Main result card */}
                <div style={{
                  background: 'linear-gradient(135deg,rgba(99,102,241,0.12),rgba(139,92,246,0.08))',
                  border: '2px solid rgba(99,102,241,0.3)', borderRadius: 16, padding: 24, marginBottom: 16,
                  textAlign: 'center',
                }}>
                  <p style={{ margin: 0, fontSize: 13, color: 'var(--text-2)', marginBottom: 4 }}>Required Sample Size</p>
                  <p style={{ margin: 0, fontSize: 52, fontWeight: 900, color: '#6366f1', lineHeight: 1 }}>
                    {mainN ?? '—'}
                  </p>
                  {totalN && nPerGroup && (
                    <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-3)' }}>
                      {nPerGroup} per group × {kGroupsVal} groups = {totalN} total
                    </p>
                  )}
                  <div style={{ marginTop: 12, padding: '8px 16px', borderRadius: 20, background: 'rgba(99,102,241,0.1)', display: 'inline-block' }}>
                    <span style={{ fontSize: 13, color: '#6366f1', fontWeight: 600 }}>
                      Achieved Power: {((achievedPower || 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Interpretation */}
                {interpretationText && (
                  <div style={{ ...cardStyle, marginBottom: 16, borderLeft: '3px solid #6366f1' }}>
                    <div className="flex items-start gap-2">
                      <RiInformationFill size={16} style={{ color: '#6366f1', flexShrink: 0, marginTop: 2 }} />
                      <p 
                        style={{ margin: 0, fontSize: 13, color: 'var(--text)', lineHeight: 1.6 }}
                        dangerouslySetInnerHTML={{ __html: interpretationText.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>') }} 
                      />
                    </div>
                  </div>
                )}

                {/* Parameters used */}
                <div style={{ ...cardStyle, marginBottom: 16 }}>
                  <p className="font-semibold text-xs mb-3" style={{ color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Parameters</p>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    {[
                      ['Test', testDisplayName || 'Power Analysis'],
                      ['Effect Size', effectSizeVal ?? '—'],
                      ['Alpha (α)', alphaVal ?? '0.05'],
                      ['Power (1−β)', `${((achievedPower || 0) * 100).toFixed(1)}%`],
                    ].map(([label, val]) => (
                      <div key={label} style={{ padding: '8px 12px', borderRadius: 8, background: 'var(--surface-2)' }}>
                        <p style={{ margin: 0, fontSize: 10, color: 'var(--text-3)', fontWeight: 600, marginBottom: 2 }}>{label}</p>
                        <p style={{ margin: 0, fontSize: 13, color: 'var(--text)', fontWeight: 700 }}>{val}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Power curve */}
                {powerCurve && powerCurve.length > 0 && (
                  <div style={cardStyle}>
                    <p className="font-semibold text-xs mb-3" style={{ color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Power Curve</p>
                    <PowerCurveChart data={powerCurve} targetPower={power} />
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Effect size reference */}
        <div style={{ ...cardStyle, marginTop: 20 }}>
          <p className="font-semibold text-sm mb-3" style={{ color: 'var(--text)' }}>Effect Size Reference (Cohen, 1988)</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12 }}>
            {TESTS.map(t => (
              <div key={t.id} style={{ padding: '12px', borderRadius: 10, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                <p style={{ margin: '0 0 6px', fontSize: 11, fontWeight: 700, color: 'var(--text-2)' }}>{t.label}</p>
                <p style={{ margin: '0 0 2px', fontSize: 11, color: 'var(--text-3)' }}><b style={{color:'#10b981'}}>Small</b>: {t.guide.small}</p>
                <p style={{ margin: '0 0 2px', fontSize: 11, color: 'var(--text-3)' }}><b style={{color:'#f59e0b'}}>Medium</b>: {t.guide.medium}</p>
                <p style={{ margin: 0, fontSize: 11, color: 'var(--text-3)' }}><b style={{color:'#ef4444'}}>Large</b>: {t.guide.large}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

// src/pages/login.tsx
import React, { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { authApi } from '../lib/api';
import { FlaskConical, Eye, EyeOff, Loader2, CheckCircle, Zap } from 'lucide-react';
import Cookies from 'js-cookie';
import toast from 'react-hot-toast';
import { useThemeStore } from '../lib/store';
import Head from 'next/head';

const DEMO = { email: 'demo@researchform.app', password: 'demo1234' };

const FEATURES = [
  'Build surveys with 10 question types',
  'AI selects the right statistical tests',
  'Auto-generates Python analysis code',
  'Writes Chapter 4 in Nigerian university format',
  'Exports .docx, SPSS, Excel, CSV',
];

export default function LoginPage() {
  const router = useRouter();
  const { theme, toggleTheme } = useThemeStore();
  const [form, setForm] = useState({ email: '', password: '' });
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await authApi.login({ email: form.email, password: form.password });
      Cookies.set('rf_token', res.data.access_token, { expires: 7 });
      localStorage.setItem('rf_user', JSON.stringify(res.data.user || { full_name: 'Researcher', email: form.email }));
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Sign in failed. Check your connection or credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setForm(DEMO);
    setLoading(true);
    try {
      const res = await authApi.login({ email: DEMO.email, password: DEMO.password });
      Cookies.set('rf_token', res.data.access_token, { expires: 7 });
      localStorage.setItem('rf_user', JSON.stringify(res.data.user));
      toast.success('Signed in safely!');
      router.push('/dashboard');
    } catch {
      setError('Could not connect to backend.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Sign In — ResearchForm</title>
        <meta name="description" content="Sign in to ResearchForm — the AI-powered academic research platform for Nigerian researchers." />
      </Head>

      <div className="min-h-screen flex" style={{ background: 'var(--bg)' }}>
        {/* Left — hero panel */}
        <div
          className="hidden lg:flex flex-col justify-between w-[52%] p-14 relative overflow-hidden"
          style={{ background: 'linear-gradient(145deg, #4f46e5 0%, #6366f1 40%, #818cf8 100%)' }}
        >
          {/* Background blobs */}
          <div style={{ position: 'absolute', top: -80, right: -80, width: 320, height: 320, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', bottom: -60, left: -60, width: 240, height: 240, borderRadius: '50%', background: 'rgba(255,255,255,0.05)', pointerEvents: 'none' }} />

          {/* Logo */}
          <div className="flex items-center gap-3 relative z-10">
            <div style={{ width: 44, height: 44, borderRadius: 12, background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FlaskConical size={22} color="#fff" />
            </div>
            <span style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 22, color: '#fff', letterSpacing: '-0.02em' }}>
              ResearchForm
            </span>
          </div>

          {/* Headline */}
          <div className="relative z-10">
            <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 16 }}>
              For Nigerian & West African Researchers
            </p>
            <h1 style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: 42, color: '#fff', lineHeight: 1.1, marginBottom: 20 }}>
              Survey. Analyse.<br />Publish Chapter 4.
            </h1>
            <p style={{ color: 'rgba(255,255,255,0.75)', fontSize: 16, lineHeight: 1.7, marginBottom: 36, maxWidth: 440 }}>
              Build research surveys, collect data, and let AI run your full statistical analysis — selecting the right tests, generating code, and writing your chapter in Nigerian university format.
            </p>

            {/* Feature checklist */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {FEATURES.map(f => (
                <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <CheckCircle size={16} color="rgba(255,255,255,0.9)" />
                  <span style={{ color: 'rgba(255,255,255,0.85)', fontSize: 14 }}>{f}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, position: 'relative', zIndex: 10 }}>
            {[
              { n: '9', label: 'Pipeline Stages' },
              { n: '10', label: 'Question Types' },
              { n: '8', label: 'Statistical Tests' },
            ].map(({ n, label }) => (
              <div key={label} style={{ background: 'rgba(255,255,255,0.12)', borderRadius: 12, padding: '14px 16px', backdropFilter: 'blur(8px)' }}>
                <p style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: 28, color: '#fff', lineHeight: 1 }}>{n}</p>
                <p style={{ color: 'rgba(255,255,255,0.65)', fontSize: 12, marginTop: 4 }}>{label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right — login form */}
        <div className="flex-1 flex items-center justify-center p-8" style={{ background: 'var(--bg)' }}>
          <div style={{ width: '100%', maxWidth: 420 }} className="animate-slide-up">
            {/* Mobile logo */}
            <div className="lg:hidden flex items-center gap-3 mb-8">
              <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <FlaskConical size={20} color="#fff" />
              </div>
              <span style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 20, color: 'var(--text)' }}>ResearchForm</span>
            </div>

            <h2 style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 28, color: 'var(--text)', marginBottom: 4 }}>
              Welcome back
            </h2>
            <p style={{ color: 'var(--text-2)', fontSize: 14, marginBottom: 28 }}>
              Sign in to your account to continue
            </p>

            {/* Demo CTA */}
            <button
              onClick={handleDemo}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: 10,
                border: '2px dashed var(--brand)',
                background: 'rgba(99,102,241,0.06)',
                color: 'var(--brand)',
                fontWeight: 600,
                fontSize: 14,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                marginBottom: 24,
                transition: 'all 0.2s ease',
                fontFamily: 'DM Sans, sans-serif',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(99,102,241,0.12)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'rgba(99,102,241,0.06)')}
            >
              <Zap size={16} />
              Try Demo — No sign up needed
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
              <span style={{ color: 'var(--text-3)', fontSize: 12, fontWeight: 600 }}>OR SIGN IN</span>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>

            {/* Error */}
            {error && (
              <div style={{ padding: '12px 14px', borderRadius: 8, marginBottom: 16, fontSize: 14, background: 'rgba(239,68,68,0.08)', color: 'var(--danger)', border: '1px solid rgba(239,68,68,0.2)' }}>
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label className="label">Email address</label>
                <input
                  className="input"
                  type="email"
                  placeholder="you@university.edu.ng"
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  autoComplete="email"
                />
              </div>

              <div>
                <label className="label">Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    className="input"
                    type={showPass ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                    style={{ paddingRight: 44 }}
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPass(!showPass)}
                    style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 4 }}
                  >
                    {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                className="btn btn-primary btn-lg"
                disabled={loading}
                style={{ width: '100%', marginTop: 4 }}
              >
                {loading ? <Loader2 size={18} className="animate-spin" /> : null}
                {loading ? 'Signing in…' : 'Sign In'}
              </button>
            </form>

            <p style={{ textAlign: 'center', fontSize: 14, color: 'var(--text-2)', marginTop: 20 }}>
              Don't have an account?{' '}
              <Link href="/register">
                <span style={{ color: 'var(--brand)', fontWeight: 600, cursor: 'pointer' }}>Sign up free</span>
              </Link>
            </p>

            {/* Demo credentials reminder */}
            <div style={{ marginTop: 28, padding: 14, borderRadius: 10, background: 'var(--surface-2)', border: '1px solid var(--border)', fontSize: 13 }}>
              <p style={{ color: 'var(--text-3)', fontWeight: 600, marginBottom: 4 }}>Demo credentials:</p>
              <p style={{ color: 'var(--text-2)', fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>
                demo@researchform.app / demo1234
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// src/pages/register.tsx
import React, { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Head from 'next/head';
import { authApi } from '../lib/api';
import { FlaskConical, Eye, EyeOff, Loader2 } from 'lucide-react';
import Cookies from 'js-cookie';
import toast from 'react-hot-toast';

const INSTITUTIONS = [
  'University of Lagos (UNILAG)',
  'Obafemi Awolowo University (OAU)',
  'University of Nigeria, Nsukka (UNN)',
  'Ahmadu Bello University (ABU)',
  'University of Ibadan (UI)',
  'University of Benin (UNIBEN)',
  'University of Port Harcourt (UNIPORT)',
  'University of Calabar (UNICAL)',
  'Lagos State University (LASU)',
  'Covenant University',
  'Babcock University',
  'Other',
];

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    full_name: '', email: '', password: '', confirm: '',
    institution: '', department: '', level: 'undergraduate',
  });
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password !== form.confirm) { setError('Passwords do not match'); return; }
    if (form.password.length < 8) { setError('Password must be at least 8 characters'); return; }
    setLoading(true); setError('');
    try {
      const res = await authApi.register({ ...form, username: form.email });
      Cookies.set('rf_token', res.data.access_token, { expires: 7 });
      localStorage.setItem('rf_user', JSON.stringify(res.data.user || form));
      toast.success('Account created! Welcome to ResearchForm 🎉');
      router.push('/dashboard');
    } catch {
      // Demo bypass
      const mockUser = { full_name: form.full_name, email: form.email, institution: form.institution, role: 'researcher' };
      Cookies.set('rf_token', 'demo_token', { expires: 7 });
      localStorage.setItem('rf_user', JSON.stringify(mockUser));
      toast.success('Account created (demo mode)!');
      router.push('/dashboard');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Create Account — ResearchForm</title>
      </Head>
      <div className="min-h-screen flex items-center justify-center p-6" style={{ background: 'var(--bg-secondary)' }}>
        <div style={{ width: '100%', maxWidth: 520 }} className="animate-slide-up">
          {/* Logo */}
          <div className="flex items-center gap-3 justify-center mb-8">
            <div style={{ width: 44, height: 44, borderRadius: 12, background: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <FlaskConical size={22} color="#fff" />
            </div>
            <span style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 22, color: 'var(--text)' }}>ResearchForm</span>
          </div>

          <div className="card p-8">
            <h1 style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 24, color: 'var(--text)', marginBottom: 4 }}>
              Create your account
            </h1>
            <p style={{ color: 'var(--text-2)', fontSize: 14, marginBottom: 24 }}>
              Start your AI-powered research journey
            </p>

            {error && (
              <div style={{ padding: '12px 14px', borderRadius: 8, marginBottom: 16, fontSize: 14, background: 'rgba(239,68,68,0.08)', color: 'var(--danger)', border: '1px solid rgba(239,68,68,0.2)' }}>
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Full Name *</label>
                  <input className="input" placeholder="e.g. Adebayo Johnson" value={form.full_name} onChange={e => set('full_name', e.target.value)} required />
                </div>
                <div>
                  <label className="label">Email *</label>
                  <input className="input" type="email" placeholder="you@university.edu.ng" value={form.email} onChange={e => set('email', e.target.value)} required />
                </div>
              </div>

              <div>
                <label className="label">Institution *</label>
                <select className="input" value={form.institution} onChange={e => set('institution', e.target.value)} required>
                  <option value="">Select your institution...</option>
                  {INSTITUTIONS.map(inst => <option key={inst} value={inst}>{inst}</option>)}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Department</label>
                  <input className="input" placeholder="e.g. Computer Science" value={form.department} onChange={e => set('department', e.target.value)} />
                </div>
                <div>
                  <label className="label">Academic Level</label>
                  <select className="input" value={form.level} onChange={e => set('level', e.target.value)}>
                    <option value="undergraduate">Undergraduate (BSc/HND)</option>
                    <option value="postgraduate">Postgraduate (MSc/MA)</option>
                    <option value="phd">PhD</option>
                    <option value="lecturer">Lecturer/Supervisor</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="label">Password *</label>
                <div style={{ position: 'relative' }}>
                  <input
                    className="input"
                    type={showPass ? 'text' : 'password'}
                    placeholder="At least 8 characters"
                    value={form.password}
                    onChange={e => set('password', e.target.value)}
                    style={{ paddingRight: 44 }}
                    required
                  />
                  <button type="button" onClick={() => setShowPass(!showPass)}
                    style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)' }}>
                    {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div>
                <label className="label">Confirm Password *</label>
                <input
                  className="input"
                  type="password"
                  placeholder="Re-enter password"
                  value={form.confirm}
                  onChange={e => set('confirm', e.target.value)}
                  required
                />
              </div>

              <button type="submit" className="btn btn-primary btn-lg" style={{ width: '100%', marginTop: 4 }} disabled={loading}>
                {loading ? <Loader2 size={18} className="animate-spin" /> : null}
                {loading ? 'Creating account…' : 'Create Account'}
              </button>
            </form>

            <p style={{ textAlign: 'center', fontSize: 14, color: 'var(--text-2)', marginTop: 20 }}>
              Already have an account?{' '}
              <Link href="/login">
                <span style={{ color: 'var(--brand)', fontWeight: 600, cursor: 'pointer' }}>Sign in</span>
              </Link>
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

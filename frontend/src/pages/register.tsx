// src/pages/register.tsx
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Head from 'next/head';
import { authApi } from '../lib/api';
import {
  RiFlaskFill, RiLoader4Line, RiEyeCloseLine, RiEyeLine,
  RiCheckFill, RiArrowLeftLine,
  RiMailLine, RiLockLine, RiUserLine,
} from 'react-icons/ri';
import Cookies from 'js-cookie';
import toast from 'react-hot-toast';

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    full_name: '', email: '', password: '',
    institution: '', department: '', role: 'student',
  });
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState<string>('register');
  const [otpCode, setOtpCode] = useState('');
  const [referralCode, setReferralCode] = useState('');
  const [showRefField, setShowRefField] = useState(false);
  const [refFromUrl, setRefFromUrl] = useState(false);

  const [focusedField, setFocusedField] = useState('');

  useEffect(() => {
    if (router.query.ref) {
      const code = String(router.query.ref);
      setReferralCode(code);
      setRefFromUrl(true);
      if (typeof window !== 'undefined') localStorage.setItem('rf_pending_ref', code);
    } else if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('rf_pending_ref');
      if (saved) { setReferralCode(saved); setRefFromUrl(true); }
    }
  }, [router.query.ref]);

  const clearPendingRef = () => {
    if (typeof window !== 'undefined') localStorage.removeItem('rf_pending_ref');
  };

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  // Password strength
  const pwStrength = (() => {
    const p = form.password;
    if (!p) return 0;
    let s = 0;
    if (p.length >= 8) s++;
    if (/[A-Z]/.test(p)) s++;
    if (/[0-9]/.test(p)) s++;
    if (/[^A-Za-z0-9]/.test(p)) s++;
    return s;
  })();
  const pwColors = ['#ef4444', '#f97316', '#f59e0b', '#10b981'];
  const pwLabels = ['Too weak', 'Fair', 'Good', 'Strong'];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password.length <= 7) { setError('Password must be at least 8 characters'); return; }

    setLoading(true); setError('');
    try {
      const res = await authApi.register({ ...form, username: form.email, referral_code: referralCode });
      if (res.data.status === 'pending_verification') {
        setStep('otp');
        toast.success('Verification code sent to your email!');
      } else {
        clearPendingRef();
        Cookies.set('rf_token', res.data.access_token, { expires: 7 });
        localStorage.setItem('rf_user', JSON.stringify(res.data.user || form));
        toast.success('Account created! Welcome to ResearchForm');
        router.push('/dashboard');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await authApi.verifyOtp({ email: form.email, otp_code: otpCode, purpose: 'register' });
      clearPendingRef();
      Cookies.set('rf_token', res.data.access_token, { expires: 7 });
      localStorage.setItem('rf_user', JSON.stringify(res.data.user || form));
      toast.success('Account verified! Welcome to ResearchForm');
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Verification failed. Invalid or expired code.');
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = (field: string): React.CSSProperties => ({
    width: '100%',
    background: focusedField === field ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.04)',
    border: `1.5px solid ${focusedField === field ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.09)'}`,
    borderRadius: 10,
    padding: '11px 14px 11px 42px',
    color: '#fff',
    fontSize: 14,
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'all 0.2s ease',
    boxShadow: focusedField === field ? '0 0 0 3px rgba(255,255,255,0.1)' : 'none',
  });

  const iconStyle = (field: string): React.CSSProperties => ({
    position: 'absolute',
    left: 13,
    top: '50%',
    transform: 'translateY(-50%)',
    color: focusedField === field ? '#fff' : 'rgba(255,255,255,0.2)',
    transition: 'color 0.2s',
    pointerEvents: 'none',
  });

  return (
    <div style={{
      minHeight: '100vh',
      background: '#000',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      color: '#fff',
    }}>
      <Head>
        <title>Create Account — ResearchForm</title>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
        <style>{`
          * { box-sizing: border-box; }
          @keyframes fade-up { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
          @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
          .reg-page-enter { animation: fade-up 0.45s cubic-bezier(0.16,1,0.3,1) forwards; }
          input:-webkit-autofill, input:-webkit-autofill:focus {
            -webkit-box-shadow: 0 0 0 1000px #000 inset !important;
            -webkit-text-fill-color: #fff !important;
            transition: background-color 5000s ease-in-out 0s;
          }
          input::placeholder { color: rgba(255,255,255,0.22) !important; }
          .rf-google-btn:hover { background: rgba(255,255,255,0.08) !important; border-color: rgba(255,255,255,0.18) !important; }
          .rf-submit-btn:not(:disabled):hover { transform: translateY(-1px); box-shadow: 0 8px 30px rgba(255,255,255,0.2) !important; }
          .rf-submit-btn:not(:disabled):active { transform: translateY(0); }
        `}</style>
      </Head>

      {/* ── Top bar ── */}
      <div style={{ position: 'relative', zIndex: 1, padding: '14px 28px', display: 'flex', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ width: 30, height: 30, borderRadius: 9, background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <RiFlaskFill size={15} color="#fff" />
          </div>
          <span style={{ fontWeight: 700, fontSize: 16, letterSpacing: '-0.02em' }}>ResearchForm</span>
        </div>
      </div>

      {/* ── Center container ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '20px 20px 24px', position: 'relative', zIndex: 1 }}>
        <div className="reg-page-enter" style={{ width: '100%', maxWidth: 400 }}>

          {step === 'register' ? (
            <>
              {/* Title */}
              <div style={{ textAlign: 'center', marginBottom: 18 }}>
                <h1 className="text-[28px] font-bold font-['Syne'] tracking-tight mb-0 leading-[1.15]">
                  Get started
                </h1>
              </div>

              {/* Card */}
              <div style={{ padding: '4px 0' }}>

                {/* Error banner */}
                {error && (
                  <div style={{ padding: '10px 14px', borderRadius: 9, marginBottom: 18, fontSize: 13, background: 'rgba(239,68,68,0.08)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.2)', lineHeight: 1.5 }}>
                    {error}
                  </div>
                )}

                {/* Google */}
                <button 
                  type="button"
                  onClick={() => window.location.href = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/auth/social/google/login`}
                  className="w-full flex items-center justify-center gap-2 py-0.5 px-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 hover:border-white/20 transition-all text-sm font-semibold mb-2 group shadow-lg shadow-black/50"
                >
                  <svg width="15" height="15" viewBox="0 0 18 18">
                    <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
                    <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
                    <path fill="#FBBC05" d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z"/>
                    <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 7.293C4.672 5.163 6.656 3.58 9 3.58z"/>
                  </svg>
                  Continue with Google
                </button>

                {/* Divider */}
                <div className="flex items-center gap-4 mb-2">
                  <div className="h-px flex-1 bg-gradient-to-r from-transparent to-white/10"></div>
                  <span className="text-[11px] font-bold text-white/30 uppercase tracking-widest">or</span>
                  <div className="h-px flex-1 bg-gradient-to-l from-transparent to-white/10"></div>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="flex flex-col gap-4">

                  {/* Name */}
                  <div>
                    <input
                      className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/30 focus:bg-black/60 transition-all"
                      placeholder="Your Name"
                      value={form.full_name}
                      onChange={e => set('full_name', e.target.value)}
                      required
                    />
                  </div>

                  {/* Email */}
                  <div>
                    <input
                      className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/30 focus:bg-black/60 transition-all"
                      type="email"
                      placeholder="Email Address"
                      value={form.email}
                      onChange={e => set('email', e.target.value)}
                      required
                    />
                  </div>

                  {/* Password */}
                  <div>
                    <div className="relative">
                      <input
                        className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/30 focus:bg-black/60 transition-all pr-10"
                        type={showPass ? 'text' : 'password'}
                        placeholder="Password (Minimum 8 characters)"
                        value={form.password}
                        onChange={e => set('password', e.target.value)}
                        required
                      />
                      <button type="button" onClick={() => setShowPass(!showPass)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors">
                        {showPass ? <RiEyeCloseLine size={16} /> : <RiEyeLine size={16} />}
                      </button>
                    </div>
                    {/* Strength bar */}
                    {form.password.length > 0 && (
                      <div className="mt-2 flex items-center gap-2">
                        <div className="flex-1 flex gap-1">
                          {[0,1,2,3].map(i => (
                            <div key={i} className="flex-1 h-1 rounded-sm transition-colors duration-300" style={{ background: i < pwStrength ? pwColors[pwStrength - 1] : 'rgba(255,255,255,0.08)' }} />
                          ))}
                        </div>
                        <span className="text-[11px] font-semibold min-w-[50px]" style={{ color: pwStrength > 0 ? pwColors[pwStrength - 1] : 'transparent' }}>
                          {pwStrength > 0 ? pwLabels[pwStrength - 1] : ''}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Referral code */}
                  {refFromUrl ? (
                    <div className="flex items-center gap-2 px-3 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-sm text-emerald-400">
                      <RiCheckFill size={14} />
                      Referral code applied: <strong>{referralCode}</strong>
                    </div>
                  ) : (
                    <div>
                      <button type="button" onClick={() => setShowRefField(f => !f)}
                        className="text-xs text-white/30 hover:text-white/60 transition-colors">
                        {showRefField ? '− Hide referral code' : '+ Have a referral code?'}
                      </button>
                      {showRefField && (
                        <input
                          className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/30 focus:bg-black/60 transition-all mt-2"
                          placeholder="Referral Code (e.g. ABC12345)"
                          value={referralCode}
                          onChange={e => setReferralCode(e.target.value.toUpperCase().trim())}
                          maxLength={12}
                        />
                      )}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-white text-black font-bold text-sm py-1.5 rounded-xl hover:bg-gray-200 transition-all flex items-center justify-center gap-2 mt-4 disabled:opacity-70 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:shadow-[0_0_25px_rgba(255,255,255,0.2)]"
                  >
                    {loading ? <RiLoader4Line size={18} className="animate-spin" /> : null}
                    {loading ? 'Creating account...' : 'Start for free'}
                  </button>
                </form>
              </div>

              {/* Sign in link */}
              <p style={{ textAlign: 'center', marginTop: 22, fontSize: 13, color: 'rgba(255,255,255,0.3)' }}>
                Already have an account?{' '}
                <Link href="/login" style={{ color: '#fff', fontWeight: 600, textDecoration: 'underline' }}>
                  Or sign in instead
                </Link>
              </p>

              <p className="text-center mt-12 text-[11px] text-white/40 leading-relaxed whitespace-nowrap mx-auto">
                By continuing, you agree to researchform's{' '}
                <Link href="/terms" target="_blank" className="text-white hover:underline font-medium">Terms of Service</Link>
                {' '}and{' '}
                <Link href="/privacy" target="_blank" className="text-white hover:underline font-medium">Privacy Policy</Link>.
              </p>
            </>
          ) : (
            /* ── OTP step ── */
            <div className="reg-page-enter">
              <button onClick={() => setStep('register')}
                style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit', marginBottom: 28, padding: 0, transition: 'color 0.2s' }}
                onMouseOver={e => (e.currentTarget.style.color = '#fff')}
                onMouseOut={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}>
                <RiArrowLeftLine size={14} /> Back to registration
              </button>

              <div style={{ textAlign: 'center', marginBottom: 28 }}>

                <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 8 }}>Check your email</h1>
                <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.38)', lineHeight: 1.6 }}>
                  We sent a 6-digit code to<br />
                  <span style={{ color: '#a5b4fc', fontWeight: 600 }}>{form.email}</span>
                </p>
              </div>

              <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 18, padding: '28px' }}>
                {error && (
                  <div style={{ padding: '10px 14px', borderRadius: 9, marginBottom: 16, fontSize: 13, background: 'rgba(239,68,68,0.08)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.2)' }}>
                    {error}
                  </div>
                )}

                <form onSubmit={handleVerifyOtp} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.45)', marginBottom: 10, textAlign: 'center', letterSpacing: '0.05em' }}>
                      ENTER VERIFICATION CODE
                    </label>
                    <input
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      placeholder="——————"
                      value={otpCode}
                      onChange={e => setOtpCode(e.target.value.replace(/\D/g, ''))}
                      style={{
                        width: '100%',
                        background: focusedField === 'otp' ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.04)',
                        border: `1.5px solid ${focusedField === 'otp' ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.09)'}`,
                        borderRadius: 10,
                        padding: '10px 14px',
                        color: '#fff',
                        fontSize: 22,
                        fontFamily: "'SF Mono', 'Fira Code', monospace",
                        letterSpacing: '0.5em',
                        textAlign: 'center',
                        outline: 'none',
                        transition: 'all 0.2s',
                        boxShadow: focusedField === 'otp' ? '0 0 0 3px rgba(255,255,255,0.1)' : 'none',
                      }}
                      onFocus={() => setFocusedField('otp')}
                      onBlur={() => setFocusedField('')}
                      required
                    />
                    {/* Progress dots */}
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 5, marginTop: 10 }}>
                      {[0,1,2,3,4,5].map(i => (
                        <div key={i} style={{ width: 7, height: 7, borderRadius: '50%', background: i < otpCode.length ? '#fff' : 'rgba(255,255,255,0.1)', transition: 'all 0.2s', transform: i < otpCode.length ? 'scale(1.2)' : 'scale(1)' }} />
                      ))}
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="rf-submit-btn"
                    disabled={loading || otpCode.length !== 6}
                    style={{
                      width: '100%', padding: '13px', borderRadius: 10, border: 'none',
                      cursor: loading || otpCode.length !== 6 ? 'not-allowed' : 'pointer',
                      background: loading || otpCode.length !== 6 ? 'rgba(255,255,255,0.15)' : '#fff',
                      color: loading || otpCode.length !== 6 ? 'rgba(255,255,255,0.4)' : '#000',
                      fontWeight: 700, fontSize: 15, fontFamily: 'inherit',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                      boxShadow: !loading && otpCode.length === 6 ? '0 4px 20px rgba(255,255,255,0.15)' : 'none',
                      transition: 'all 0.25s ease',
                    }}>
                    {loading ? <RiLoader4Line size={17} style={{ animation: 'spin 0.75s linear infinite' }} /> : <RiCheckFill size={15} />}
                    {loading ? 'Verifying…' : 'Verify Account'}
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

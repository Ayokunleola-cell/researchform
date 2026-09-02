// src/pages/login.tsx
import React, { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { authApi } from '../lib/api';
import { RiEyeCloseFill, RiEyeFill, RiFlaskFill, RiLoader4Line, RiCloseLine } from 'react-icons/ri';
import Cookies from 'js-cookie';
import toast from 'react-hot-toast';
import Head from 'next/head';

const DEMO = { email: 'demo@researchform.app', password: 'password123' };

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: '', password: '' });
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  // flow: 'email' -> 'password' (modal) -> 'otp' (modal)
  const [step, setStep] = useState<'email' | 'password' | 'otp'>('email');
  const [otpCode, setOtpCode] = useState('');
  const [isMfa, setIsMfa] = useState(false);

  const handleEmailCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.email) return;
    setLoading(true);
    setError('');
    try {
      // demo bypass
      if (form.email === DEMO.email) {
        setStep('password');
        setLoading(false);
        return;
      }

      const res = await authApi.checkEmail({ email: form.email });
      if (res.data.exists) {
        setStep('password');
      } else {
        setError('Sorry, we could not find your account.');
      }
    } catch (err: any) {
      setError('Error checking email. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.password) return;
    setLoading(true);
    setError('');
    try {
      const res = await authApi.login({ email: form.email, password: form.password });
      if (res.data.status === 'pending_verification') {
        setStep('otp');
        if (res.data.mfa) {
          setIsMfa(true);
          toast.success('Please enter the code from your Authenticator App.');
        } else {
          setIsMfa(false);
          toast.success('Verification code sent to your email!');
        }
      } else {
        Cookies.set('rf_token', res.data.access_token, { expires: 7 });
        localStorage.setItem('rf_user', JSON.stringify(res.data.user || { full_name: 'Researcher', email: form.email }));
        router.push('/dashboard');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Wrong password. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await authApi.verifyOtp({ email: form.email, otp_code: otpCode, purpose: 'login' });
      Cookies.set('rf_token', res.data.access_token, { expires: 7 });
      localStorage.setItem('rf_user', JSON.stringify(res.data.user || { full_name: 'Researcher', email: form.email }));
      toast.success('Signed in safely!');
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Verification failed. Invalid or expired code.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setForm(DEMO);
    setLoading(true);
    setError('');
    try {
      const res = await authApi.login({ email: DEMO.email, password: DEMO.password });
      if (res.data.status === 'pending_verification') {
         setStep('otp');
         toast.success('Demo verification code sent to email!');
      } else {
         Cookies.set('rf_token', res.data.access_token, { expires: 7 });
         localStorage.setItem('rf_user', JSON.stringify(res.data.user || { full_name: 'Demo Researcher', email: DEMO.email }));
         toast.success('Welcome! Signed in as Demo User.');
         router.push('/dashboard');
      }
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 401) {
        setError('Demo login failed. Please try logging in manually with demo@researchform.app / password123');
      } else if (status) {
        setError(detail || `Login error (${status}). Please try again.`);
      } else {
        setError('Could not reach the backend server. Make sure it is running on http://localhost:8000');
      }
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

      {/* Main Base Page (Email Step) */}
      <div className="min-h-screen flex bg-[#0a0a0b] text-white font-sans selection:bg-indigo-500/30 relative">
        {/* Left Panel - Image Background */}
        <div className="hidden lg:flex flex-col justify-between w-[55%] relative overflow-hidden bg-black p-14">
          <div 
            className="absolute inset-0 bg-cover bg-center transition-transform duration-10000 hover:scale-105" 
            style={{ backgroundImage: 'url(/login-hero.png)', opacity: 0.85 }} 
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0a0a0b] via-[#0a0a0b]/40 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-r from-[#0a0a0b]/80 to-transparent" />
          
          <div className="relative z-10 flex items-center gap-3">
            <RiFlaskFill size={32} className="text-white" />
            <span className="text-2xl font-bold font-['Syne'] tracking-tight">ResearchForm</span>
          </div>

          <div className="relative z-10 max-w-lg mb-8">
            <h1 className="text-5xl lg:text-[64px] font-extrabold text-white leading-[1.05] mb-8 tracking-tight font-['Syne'] drop-shadow-lg">
              From idea to<br />final chapter.
            </h1>
            <p className="text-lg text-white/70 mb-10 font-light leading-relaxed max-w-md">
              A complete research workflow: survey generation, data collection, and AI-powered statistical analysis with professional control.
            </p>
            <div className="flex gap-6 text-[11px] font-bold tracking-[0.2em] uppercase text-white/50 items-center">
              <span className="hover:text-white transition-colors cursor-default">Surveys</span>
              <span className="w-8 border-b border-white/20"></span>
              <span className="hover:text-white transition-colors cursor-default">Analysis</span>
              <span className="w-8 border-b border-white/20"></span>
              <span className="hover:text-white transition-colors cursor-default">Publishing</span>
            </div>
          </div>
        </div>

        {/* Right Panel - Form (Email only) */}
        <div className="flex-1 flex flex-col items-center justify-center p-8 relative overflow-y-auto">
          <div className="w-full max-w-[380px] animate-slide-up my-auto">
            
            {/* Mobile Logo */}
            <div className="lg:hidden flex flex-col items-center mb-12">
              <RiFlaskFill size={48} className="text-white mb-4 drop-shadow-[0_0_15px_rgba(255,255,255,0.3)]" />
              <span className="text-2xl font-bold font-['Syne'] tracking-tight">ResearchForm</span>
            </div>

            <div className="text-center mb-10">
              <h2 className="text-[28px] font-bold font-['Syne'] tracking-tight mb-2">Welcome</h2>
              <p className="text-white/50 text-sm">Sign in to your account to continue</p>
            </div>

            {error && step === 'email' && (
              <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center font-medium animate-fade-in">
                {error}
              </div>
            )}

            <button 
              type="button"
              onClick={() => window.location.href = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/auth/social/google/login`}
              className="w-full flex items-center justify-center gap-2 py-0.5 px-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 hover:border-white/20 transition-all text-sm font-semibold mb-8 group shadow-lg shadow-black/50"
            >
              <svg width="15" height="15" viewBox="0 0 18 18">
                <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
                <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
                <path fill="#FBBC05" d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z"/>
                <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 7.293C4.672 5.163 6.656 3.58 9 3.58z"/>
              </svg>
              Continue with Google
            </button>

            <div className="flex items-center gap-4 mb-8">
              <div className="h-px flex-1 bg-gradient-to-r from-transparent to-white/10"></div>
              <span className="text-[11px] font-bold text-white/30 uppercase tracking-widest">or</span>
              <div className="h-px flex-1 bg-gradient-to-l from-transparent to-white/10"></div>
            </div>

            <form onSubmit={handleEmailCheck} className="flex flex-col gap-4">
              <div>
                <input
                  type="email"
                  placeholder="Email or username"
                  className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/30 focus:bg-black/60 transition-all"
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-white text-black font-bold text-sm py-1.5 rounded-xl hover:bg-gray-200 transition-all flex items-center justify-center gap-2 mt-4 disabled:opacity-70 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:shadow-[0_0_25px_rgba(255,255,255,0.2)]"
              >
                {loading ? <RiLoader4Line size={18} className="animate-spin" /> : null}
                {loading ? 'Checking...' : 'Sign in'}
              </button>
            </form>

            <div className="mt-12 text-center">
              <p className="text-xs text-white/40">
                Don&apos;t have an account?{' '}
                <Link href="/register" className="text-white font-semibold hover:underline">
                  Sign up
                </Link>
              </p>
            </div>
          </div>
        </div>

        {/* Modal Overlay (Password & OTP steps) */}
        {(step === 'password' || step === 'otp') && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 animate-fade-in">
            <div className="w-full max-w-[500px] bg-[#101012] border border-white/10 rounded-2xl shadow-2xl relative flex flex-col p-8 min-h-[400px]">
              
              {/* Modal Header */}
              <div className="flex items-center justify-between mb-10 relative">
                {/* Dummy div to balance flex spacing */}
                <div className="w-9"></div>
                
                <div className="absolute left-1/2 -translate-x-1/2 text-white">
                  <RiFlaskFill size={32} />
                </div>
                
                <button 
                  type="button"
                  aria-label="Close"
                  onClick={() => {
                    setStep('email');
                    setError('');
                  }} 
                  className="p-2 -mr-2 rounded-full hover:bg-white/10 transition-colors text-white/60 hover:text-white"
                >
                  <RiCloseLine size={22} />
                </button>
              </div>

              {/* Password Step */}
              {step === 'password' && (
                <div className="flex-1 flex flex-col justify-center animate-slide-up pb-8">
                  <h2 className="text-[28px] font-bold font-['Syne'] tracking-tight mb-8">Login</h2>
                  
                  {error && (
                    <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center font-medium animate-fade-in">
                      {error}
                    </div>
                  )}

                  <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-4">
                    {/* Readonly Username Display */}
                    <div>
                      <input
                        type="email"
                        placeholder="Username"
                        style={{
                          width: '100%',
                          background: 'var(--surface)',
                          border: '1px solid var(--border)',
                          borderRadius: 12,
                          padding: '9px 16px',
                          fontSize: 14,
                          color: 'var(--text-3)',
                          outline: 'none',
                          cursor: 'not-allowed',
                          opacity: 0.7,
                        }}
                        value={form.email}
                        disabled
                      />
                    </div>
                    
                    {/* Password Input */}
                    <div>
                      <div style={{ position: 'relative' }}>
                        <input
                          type={showPass ? 'text' : 'password'}
                          placeholder="Enter your password"
                          style={{
                            width: '100%',
                            background: 'var(--surface)',
                            border: '1px solid var(--border)',
                            borderRadius: 12,
                            padding: '9px 42px 9px 16px',
                            fontSize: 14,
                            color: 'var(--text)',
                            outline: 'none',
                            transition: 'border-color 0.2s',
                            boxSizing: 'border-box',
                          }}
                          value={form.password}
                          onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                          autoFocus
                          required
                          onFocus={e => (e.target.style.borderColor = 'var(--brand)')}
                          onBlur={e => (e.target.style.borderColor = 'var(--border)')}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPass(!showPass)}
                          style={{
                            position: 'absolute', right: 12, top: '50%',
                            transform: 'translateY(-50%)',
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: 'var(--text-3)', padding: 0, display: 'flex',
                            alignItems: 'center',
                          }}
                        >
                          {showPass ? <RiEyeCloseFill size={16} /> : <RiEyeFill size={16} />}
                        </button>
                      </div>
                    </div>

                    <div className="mt-1">
                      <Link href="/forgot-password" className="text-xs text-white/50 hover:text-white transition-colors">
                        Forgot password?
                      </Link>
                    </div>

                    <button
                      type="submit"
                      disabled={loading || !form.password}
                      className="w-full bg-white text-black font-bold text-sm py-1.5 rounded-xl hover:bg-gray-200 transition-all flex items-center justify-center gap-2 mt-4 disabled:opacity-70 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:shadow-[0_0_25px_rgba(255,255,255,0.2)]"
                    >
                      {loading ? <RiLoader4Line size={18} className="animate-spin" /> : null}
                      {loading ? 'Signing in...' : 'Sign in'}
                    </button>
                  </form>
                </div>
              )}

              {/* OTP Step */}
              {step === 'otp' && (
                <div className="flex-1 flex flex-col justify-center animate-fade-in pb-8">
                  <div className="text-center mb-8">
                    <h2 className="text-[28px] font-bold font-['Syne'] tracking-tight mb-3">
                      {isMfa ? 'Authenticator Code' : 'Check your email'}
                    </h2>
                    <p className="text-sm text-white/50 leading-relaxed">
                      {isMfa 
                        ? 'Open your Authenticator app to view your code.'
                        : <>We sent a 6-digit verification code to<br/><strong className="text-white/80">{form.email}</strong></>
                      }
                    </p>
                  </div>

                  {error && (
                    <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center font-medium animate-fade-in">
                      {error}
                    </div>
                  )}

                  <form onSubmit={handleVerifyOtp} className="flex flex-col gap-6">
                    <input
                      type="text"
                      maxLength={6}
                      placeholder="••••••"
                      value={otpCode}
                      onChange={e => setOtpCode(e.target.value.replace(/\D/g, ''))}
                      className="w-full bg-[#1a1a1c] border border-white/20 rounded-xl px-4 py-1.5 text-center text-2xl tracking-[0.5em] text-white placeholder-white/20 focus:outline-none focus:border-indigo-500/50 transition-all"
                      required
                      autoFocus
                    />

                    <button
                      type="submit"
                      disabled={loading || otpCode.length !== 6}
                      className="w-full mt-4 bg-white text-black font-bold text-sm py-1.5 rounded-xl hover:bg-gray-200 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {loading ? <RiLoader4Line size={18} className="animate-spin" /> : null}
                      {loading ? 'Verifying...' : 'Verify'}
                    </button>
                  </form>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

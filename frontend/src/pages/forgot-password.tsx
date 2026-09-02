import React, { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { RiLoader4Line, RiFlaskFill } from 'react-icons/ri';
import { authApi } from '../lib/api';
import toast from 'react-hot-toast';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    setError('');
    try {
      await authApi.forgotPassword({ email });
      setSuccess(true);
      toast.success('Reset link sent to your email.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send reset link.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Forgot Password — ResearchForm</title>
      </Head>

      <div className="min-h-screen bg-[#0a0a0b] flex flex-col items-center justify-center p-8 text-white font-sans selection:bg-indigo-500/30 relative">
        {/* Top Left Logo */}
        <div className="absolute top-8 left-8 flex items-center gap-2">
          <RiFlaskFill size={20} className="text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.3)]" />
          <span className="text-lg font-bold font-['Syne'] tracking-tight">ResearchForm</span>
        </div>

        <div className="w-full max-w-[380px] animate-slide-up">

          <div className="text-center mb-10">
            <h2 className="text-[28px] font-bold font-['Syne'] tracking-tight mb-2">Reset Password</h2>
            <p className="text-white/50 text-sm">Enter your email to receive a reset link</p>
          </div>

          {error && (
            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center font-medium animate-fade-in">
              {error}
            </div>
          )}

          {success ? (
            <div className="text-center animate-fade-in">
              <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm text-center font-medium">
                We've sent a password reset link to <strong>{email}</strong>. Please check your inbox.
              </div>
              <Link href="/login" className="w-full bg-white text-black font-bold text-sm py-1.5 rounded-xl hover:bg-gray-200 transition-all flex items-center justify-center gap-2 mt-4 shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:shadow-[0_0_25px_rgba(255,255,255,0.2)]">
                Return to Login
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div>
                <input
                  type="email"
                  placeholder="Email Address"
                  className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/30 focus:bg-black/60 transition-all"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading || !email}
                className="w-full bg-white text-black font-bold text-sm py-1.5 rounded-xl hover:bg-gray-200 transition-all flex items-center justify-center gap-2 mt-4 disabled:opacity-70 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:shadow-[0_0_25px_rgba(255,255,255,0.2)]"
              >
                {loading ? <RiLoader4Line size={18} className="animate-spin" /> : null}
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>
            </form>
          )}

          <div className="mt-12 text-center">
            <p className="text-xs text-white/40">
              Remembered your password?{' '}
              <Link href="/login" className="text-white font-semibold hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

import React from 'react';
import Link from 'next/link';
import Head from 'next/head';
import { RiFlaskFill, RiHome5Fill, RiDashboardFill } from 'react-icons/ri';

export default function NotFound() {
  return (
    <>
      <Head>
        <title>404 — Page Not Found | ResearchForm</title>
      </Head>
      <div
        className="min-h-screen flex flex-col items-center justify-center p-6 text-center"
        style={{
          background: 'var(--bg)',
          color: 'var(--text)',
          fontFamily: 'Inter, sans-serif',
        }}
      >
        <Link href="/" className="flex items-center gap-2 mb-8" style={{ textDecoration: 'none' }}>
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg"
            style={{
              background: 'linear-gradient(135deg, var(--brand, #6366f1), #4f46e5)',
              color: '#fff',
            }}
          >
            <RiFlaskFill size={22} />
          </div>
          <span
            className="text-xl font-bold"
            style={{ fontFamily: 'Syne, sans-serif', color: 'var(--text)' }}
          >
            ResearchForm
          </span>
        </Link>

        <div
          className="inline-flex items-center justify-center px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider mb-4 border"
          style={{
            background: 'rgba(99, 102, 241, 0.1)',
            borderColor: 'rgba(99, 102, 241, 0.25)',
            color: 'var(--brand, #6366f1)',
          }}
        >
          Error 404
        </div>

        <h1
          className="text-4xl md:text-5xl font-extrabold mb-3"
          style={{
            fontFamily: 'Syne, sans-serif',
            letterSpacing: '-0.02em',
            color: 'var(--text)',
          }}
        >
          Page Not Found
        </h1>

        <p
          className="text-base md:text-lg max-w-md mb-8"
          style={{ color: 'var(--text-3, #94a3b8)', lineHeight: 1.6 }}
        >
          The page you are looking for doesn't exist, has been removed, or you do not have permission to view it.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/dashboard"
            className="btn btn-primary flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm shadow-md"
            style={{ textDecoration: 'none' }}
          >
            <RiDashboardFill size={16} />
            Go to Dashboard
          </Link>

          <Link
            href="/"
            className="btn btn-ghost flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm border"
            style={{
              borderColor: 'var(--border)',
              color: 'var(--text)',
              textDecoration: 'none',
            }}
          >
            <RiHome5Fill size={16} />
            Back to Home
          </Link>
        </div>
      </div>
    </>
  );
}


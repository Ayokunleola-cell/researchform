// src/components/layout/AppLayout.tsx
import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Head from 'next/head';
import {
  LayoutDashboard, FileText, BarChart3, Settings,
  Moon, Sun, LogOut, FlaskConical,
  Plus, Bell, Menu, X, BookOpen, ChevronRight
} from 'lucide-react';
import { useThemeStore } from '../../lib/store';
import clsx from 'clsx';

const NAV = [
  { href: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/surveys',    icon: FileText,         label: 'Surveys' },
  { href: '/analysis',   icon: BarChart3,        label: 'Analysis' },
  { href: '/reports',    icon: BookOpen,         label: 'Reports' },
  { href: '/settings',   icon: Settings,         label: 'Settings' },
];

export default function AppLayout({ children, title }: { children: React.ReactNode; title?: string }) {
  const router = useRouter();
  const { theme, toggleTheme } = useThemeStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    const stored = localStorage.getItem('rf_user');
    if (stored) setUser(JSON.parse(stored));
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  // Close sidebar on navigation
  useEffect(() => { setSidebarOpen(false); }, [router.pathname]);

  const handleLogout = () => {
    localStorage.removeItem('rf_user');
    document.cookie = 'rf_token=; max-age=0; path=/';
    router.push('/login');
  };

  const activeNav = NAV.find(n => router.pathname.startsWith(n.href));
  const pageTitle = activeNav?.label || 'ResearchForm';

  return (
    <div className="flex min-h-screen transition-theme" style={{ background: 'var(--bg)' }}>
      <Head>
        <title>{title ? `${title} — ResearchForm` : 'ResearchForm'}</title>
      </Head>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 lg:hidden"
          style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        className={clsx(
          'sidebar transition-all duration-300',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Logo */}
        <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid var(--border)' }}>
          <Link href="/dashboard">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <div style={{
                width: 38, height: 38, borderRadius: 10,
                background: 'linear-gradient(135deg, var(--brand) 0%, var(--brand-dark) 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: 'var(--glow)',
              }}>
                <FlaskConical size={18} color="#fff" />
              </div>
              <div>
                <p style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 15, color: 'var(--text)', lineHeight: 1.1 }}>
                  ResearchForm
                </p>
                <p style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 1 }}>Academic Research Platform</p>
              </div>
            </div>
          </Link>
        </div>

        {/* New survey CTA */}
        <div style={{ padding: '14px 16px' }}>
          <Link href="/surveys/new">
            <button className="btn btn-primary w-full btn-sm" style={{ width: '100%', justifyContent: 'center' }}>
              <Plus size={15} />
              New Survey
            </button>
          </Link>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '0 12px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {NAV.map(({ href, icon: Icon, label }) => {
            const active = router.pathname === href || (href !== '/dashboard' && router.pathname.startsWith(href));
            return (
              <Link key={href} href={href}>
                <span className={clsx('sidebar-item', active && 'active')}>
                  <Icon size={18} />
                  {label}
                  {active && <ChevronRight size={13} style={{ marginLeft: 'auto', opacity: 0.5 }} />}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* Bottom */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="sidebar-item"
            style={{ width: '100%', border: 'none', background: 'none' }}
            aria-label="Toggle theme"
          >
            {theme === 'light'
              ? <><Moon size={17} /><span>Dark Mode</span></>
              : <><Sun size={17} /><span>Light Mode</span></>
            }
          </button>

          {/* User card */}
          {user && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 10, background: 'var(--surface-2)', marginTop: 4 }}>
              <div style={{
                width: 34, height: 34, borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--brand), var(--brand-dark))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#fff', fontSize: 13, fontWeight: 700, flexShrink: 0,
              }}>
                {user.full_name?.[0]?.toUpperCase() || 'R'}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user.full_name}
                </p>
                <p style={{ fontSize: 11, color: 'var(--text-3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user.institution || user.email}
                </p>
              </div>
              <button
                onClick={handleLogout}
                className="btn btn-ghost btn-icon"
                style={{ flexShrink: 0, color: 'var(--text-3)' }}
                title="Log out"
              >
                <LogOut size={15} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }} className="transition-all duration-300 lg:ml-[256px]">
        {/* Top bar */}
        <header
          style={{
            position: 'sticky', top: 0, zIndex: 20,
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '0 24px', height: 60,
            background: 'var(--surface)',
            borderBottom: '1px solid var(--border)',
            backdropFilter: 'blur(10px)',
          }}
        >
          {/* Mobile hamburger */}
          <button
            className="lg:hidden btn btn-ghost btn-icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle menu"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>

          {/* Page title */}
          <div style={{ flex: 1 }}>
            <p style={{ fontFamily: 'Syne, sans-serif', fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>
              {pageTitle}
            </p>
          </div>

          {/* Notifications */}
          <button
            className="btn btn-ghost btn-icon"
            style={{ position: 'relative' }}
            aria-label="Notifications"
          >
            <Bell size={18} />
            <span style={{
              position: 'absolute', top: 7, right: 7,
              width: 7, height: 7, borderRadius: '50%',
              background: 'var(--brand)',
              border: '1.5px solid var(--surface)',
            }} />
          </button>
        </header>

        {/* Page content */}
        <main
          style={{ flex: 1, padding: 24 }}
          className="animate-fade-in"
        >
          {children}
        </main>
      </div>
    </div>
  );
}

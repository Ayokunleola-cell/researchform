// src/components/layout/AppLayout.tsx
import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { RiFlaskFill, RiCloseFill, RiArrowRightSFill, RiDashboardFill, RiFileCheckFill, RiGlobalFill, RiSearchEyeFill, RiBookOpenFill, RiMoonFill, RiFileTextFill, RiFileCopyFill, RiWallet3Fill, RiMoneyDollarCircleFill, RiRobotFill, RiPriceTag3Fill, RiQuestionFill, RiSunFill, RiCheckLine, RiAddFill, RiArrowDownSFill, RiLogoutBoxRFill, RiBarChart2Fill, RiCoinsFill, RiGiftFill, RiMenuFill, RiSettings3Fill, RiBookShelfFill, RiShoppingBag3Fill , RiMenuFoldLine, RiMenuUnfoldLine} from 'react-icons/ri';
import { creditsApi } from '../../lib/api';
import { useThemeStore, useCurrencyStore, CURRENCIES, useLayoutStore } from '../../lib/store';
import { useLanguageStore, LANGUAGES, useTranslation } from '../../lib/i18n';
import clsx from 'clsx';
import type { Breadcrumb } from '../ui/PageHeader';
import toast from 'react-hot-toast';
import ActiveJobsPanel from './ActiveJobsPanel';
import { startGlobalPoller } from '../../lib/analysisStore';

const NAV_GROUPS = [
  {
    label: 'Workspace',
    items: [
      { href: '/dashboard', icon: RiDashboardFill, label: 'Dashboard' },
      { href: '/surveys', icon: RiFileTextFill, label: 'Surveys' },
    ],
  },
  {
    label: 'Research pipeline',
    items: [
      { href: '/analysis', icon: RiBarChart2Fill, label: 'Analysis' },
      { href: '/reports', icon: RiBookOpenFill, label: 'Reports' },
      { href: '/chat', icon: RiRobotFill, label: 'Chat with AI' },
    ],
  },
  {
    label: 'Tools',
    items: [
      { href: '/build-model',        icon: RiFlaskFill,     label: 'Build Model' },
      { href: '/analysis/power',     icon: RiBarChart2Fill, label: 'Power Analysis' },
    ],
  },
  {
    label: 'Marketplace',
    items: [
      { href: '/marketplace', icon: RiShoppingBag3Fill, label: 'Overview' },
      { href: '/marketplace/browse', icon: RiSearchEyeFill, label: 'Browse Datasets' },
      { href: '/marketplace/library', icon: RiBookShelfFill, label: 'My Library' },
      { href: '/marketplace/sell', icon: RiPriceTag3Fill, label: 'Sell Data' },
    ],
  },
  {
    label: 'Community',
    items: [
      { href: '/referral', icon: RiGiftFill, label: 'Refer & Earn' },
    ],
  },
];

const SETTINGS_NAV = { href: '/settings', icon: RiSettings3Fill, label: 'Settings' };

// ─── Referral Dropdown Component ────────────────────────────────────────────
function ReferralDropdown() {
  const [open, setOpen] = React.useState(false);
  const [code, setCode] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const user = typeof window !== 'undefined'
      ? JSON.parse(localStorage.getItem('rf_user') || 'null')
      : null;
    if (user?.referral_code) setCode(user.referral_code);
  }, []);

  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleCopy = async () => {
    const link = `${window.location.origin}/register?ref=${code}`;
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="topbar-icon-btn"
        title="Refer & Earn"
        style={{ position: 'relative' }}
      >
        <RiGiftFill size={18} />
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 10px)', right: 0, zIndex: 9999,
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 14, boxShadow: '0 12px 40px rgba(0,0,0,0.18)',
          minWidth: 260, padding: '16px',
        }}>
          <div className="flex items-center gap-2 mb-3">
            <RiGiftFill size={15} style={{ color: '#6366f1' }} />
            <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)' }}>Refer & Earn Credits</span>
          </div>

          {code && (
            <>
              <div className="mb-3 p-3 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                <p style={{ fontSize: 10, color: 'var(--text-3)', margin: '0 0 2px', textTransform: 'uppercase', letterSpacing: 1 }}>Your referral code</p>
                <p style={{ fontSize: 18, fontWeight: 800, color: 'var(--brand)', margin: 0, fontFamily: 'monospace', letterSpacing: 2 }}>{code}</p>
              </div>
              <button
                onClick={handleCopy}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold mb-3 transition-all"
                style={{
                  background: copied ? 'rgba(16,185,129,0.12)' : 'rgba(99,102,241,0.1)',
                  color: copied ? '#10b981' : '#6366f1',
                  border: `1px solid ${copied ? 'rgba(16,185,129,0.3)' : 'rgba(99,102,241,0.3)'}`,
                }}
              >
                {copied ? <RiCheckLine size={14} /> : <RiFileCopyFill size={14} />}
                {copied ? 'Link Copied!' : 'Copy Referral Link'}
              </button>
            </>
          )}

        </div>
      )}
    </div>
  );
}

type AppLayoutProps = {
  children: React.ReactNode;
  title?: string;
  description?: string;
  breadcrumbs?: Breadcrumb[];
  headerActions?: React.ReactNode;
};

export default function AppLayout({
  children,
  title,
  description,
  breadcrumbs,
  headerActions,
}: AppLayoutProps) {
  const router = useRouter();
  const { theme, toggleTheme } = useThemeStore();
  const { currency, setCurrency, getCurrencyInfo, ratesUpdatedAt } = useCurrencyStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { sidebarCollapsed, setSidebarCollapsed } = useLayoutStore();
  const [user, setUser] = useState<any>(null);
  const [creditBalance, setCreditBalance] = useState<number | null>(null);
  const [currencyOpen, setCurrencyOpen] = useState(false);
  const [languageOpen, setLanguageOpen] = useState(false);
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { t } = useTranslation();
  const { language, setLanguage } = useLanguageStore();
  // Only read persisted currency after mount to avoid SSR mismatch
  const currencyInfo = mounted ? getCurrencyInfo() : { flag: '', code: '', symbol: '' };
  const isSidebarMini = mounted ? sidebarCollapsed : false;
  const navRef = useRef<HTMLElement>(null);
  const savedScrollTop = useRef(0);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    const loadUser = () => {
      const stored = localStorage.getItem('rf_user');
      if (stored && stored !== 'undefined') {
        try { 
          const parsedUser = JSON.parse(stored);
          setUser(parsedUser); 
        } catch (e) { localStorage.removeItem('rf_user'); }
      }
    };
    
    loadUser();
    
    window.addEventListener('rf_user_updated', loadUser);
    return () => window.removeEventListener('rf_user_updated', loadUser);
  }, []);

  useEffect(() => {
    if (!user) return;
    creditsApi.wallet()
      .then((res) => setCreditBalance(res.data.balance))
      .catch(() => setCreditBalance(null));
  }, [user, router.pathname]);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  // Save scroll position before navigation, restore after
  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    // Restore saved scroll immediately when pathname changes
    nav.scrollTop = savedScrollTop.current;
  }, [router.pathname]);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    const saveScroll = () => { savedScrollTop.current = nav.scrollTop; };
    nav.addEventListener('scroll', saveScroll, { passive: true });
    return () => nav.removeEventListener('scroll', saveScroll);
  }, []);

  useEffect(() => { setSidebarOpen(false); }, [router.pathname]);

  // Start the global analysis poller once — persists across all page navigations
  useEffect(() => { startGlobalPoller(); }, []);

  const handleLogout = () => {
    localStorage.removeItem('rf_user');
    document.cookie = 'rf_token=; max-age=0; path=/';
    router.push('/login');
  };

  const allNavItems = [
    ...NAV_GROUPS.flatMap(g => g.items),
    SETTINGS_NAV,
  ];
  const activeNav = allNavItems.find(
    n => router.pathname === n.href || (n.href !== '/dashboard' && router.pathname.startsWith(n.href))
  );
  const headerTitle = title || (activeNav ? t(activeNav.label) : 'ResearchForm');

  const isActive = (href: string) => {
    if (router.pathname === href) return true;
    if (href === '/dashboard' || href === '/marketplace') return false;
    if (href === '/marketplace/browse') {
      return (
        router.pathname.startsWith('/marketplace/browse') ||
        router.pathname.startsWith('/marketplace/datasets')
      );
    }
    return router.pathname.startsWith(href);
  };

  return (
    <div className="app-shell transition-theme">
      <Head>
        <title>{title ? `${title} — ResearchForm` : 'ResearchForm'}</title>
      </Head>

      {sidebarOpen && (
        <div className="sidebar-overlay lg:hidden" onClick={() => setSidebarOpen(false)} aria-hidden />
      )}

      <aside className={clsx('sidebar', sidebarOpen ? 'sidebar-open' : 'sidebar-closed', isSidebarMini && 'sidebar-mini')}>
        <div className="sidebar-brand" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link href="/dashboard" className="sidebar-brand-link">
            <div className="sidebar-logo">
              <RiFlaskFill size={18} color="var(--brand-text)" />
            </div>
            <div>
              <p className="sidebar-brand-name">ResearchForm</p>
              <p className="sidebar-brand-tag">Research Platform</p>
            </div>
          </Link>
          {/* Mobile close button — visible only when sidebar is open on small screens */}
          {sidebarOpen && (
            <button
              className="lg:hidden btn btn-ghost btn-icon"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close menu"
              style={{ marginLeft: 'auto', flexShrink: 0 }}
            >
              <RiCloseFill size={20} />
            </button>
          )}
          <button
            className="hidden lg:flex"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={isSidebarMini ? "Expand Menu" : "Collapse Menu"}
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 4 }}
          >
            {isSidebarMini ? <RiMenuUnfoldLine size={18} /> : <RiMenuFoldLine size={18} />}
          </button>
        </div>

        <nav ref={navRef} className="sidebar-nav">
          <div className="sidebar-cta">
          <Link href="/surveys/new" className="custom-sidebar-action">
            <div className="action-icon-wrapper">
              <RiAddFill size={16} />
            </div>
            <span className="sidebar-cta-text">New Survey</span>
          </Link>
          <Link href="/analysis" className="custom-sidebar-action">
            <div className="action-icon-wrapper">
              <RiBarChart2Fill size={16} />
            </div>
            <span className="sidebar-cta-text">New Analysis</span>
          </Link>
        </div>
          {NAV_GROUPS.map(group => (
            <div key={group.label} className="sidebar-nav-group">
              <p className="sidebar-nav-label">{t(group.label)}</p>
              {group.items.map(({ href, icon: Icon, label }) => {
                const active = isActive(href);
                return (
                  <Link key={href} href={href} className={clsx('sidebar-item', active && 'active')}>
                    <Icon size={18} />
                    <span className="sidebar-item-text">{t(label)}</span>
                    {active && <RiArrowRightSFill size={13} className="sidebar-item-chevron" />}
                  </Link>
                );
              })}
            </div>
          ))}

          {user?.role === 'admin' && (
            <div className="sidebar-nav-group">
              <p className="sidebar-nav-label">{t('Admin Panel')}</p>
              <Link href="/admin/users" className={clsx('sidebar-item', isActive('/admin/users') && 'active')}>
                <RiSearchEyeFill size={18} />
                <span className="sidebar-item-text">{t('Manage Users')}</span>
              </Link>
              <Link href="/admin/datasets" className={clsx('sidebar-item', isActive('/admin/datasets') && 'active')}>
                <RiFileCheckFill size={18} />
                <span className="sidebar-item-text">{t('Review Datasets')}</span>
              </Link>
              <Link href="/admin/payouts" className={clsx('sidebar-item', isActive('/admin/payouts') && 'active')}>
                <RiWallet3Fill size={18} />
                <span className="sidebar-item-text">{t('KYC & Payouts')}</span>
              </Link>
              <Link href="/admin/credits" className={clsx('sidebar-item', isActive('/admin/credits') && 'active')}>
                <RiCoinsFill size={18} />
                <span className="sidebar-item-text">{t('Manage Credits')}</span>
              </Link>
              <Link href="/admin/settings" className={clsx('sidebar-item', isActive('/admin/settings') && 'active')}>
                <RiSettings3Fill size={18} />
                <span className="sidebar-item-text">{t('Platform Settings')}</span>
              </Link>
              <Link href="/admin/referral" className={clsx('sidebar-item', isActive('/admin/referral') && 'active')}>
                <RiGiftFill size={18} />
                <span className="sidebar-item-text">{t('Referral Program')}</span>
              </Link>
            </div>
          )}

          {/* Active analysis jobs panel — persists across navigation */}
          <ActiveJobsPanel collapsed={sidebarCollapsed} />

        </nav>

      
      </aside>


      <div className={clsx("app-main", isSidebarMini && "sidebar-mini-active")}>
        <header className="app-topbar">
          <button
            type="button"
            className="lg:hidden btn btn-ghost btn-icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle menu"
          >
            {sidebarOpen ? <RiCloseFill size={20} /> : <RiMenuFill size={20} />}
          </button>

          <div className="app-topbar-title">
            {/* Titles and breadcrumbs removed per request */}
          </div>

          {headerActions && <div className="app-topbar-actions">{headerActions}</div>}

          <div className="app-topbar-menu">
            <Link href="/settings/credits" className="topbar-icon-btn" title="Credits">
              <RiCoinsFill size={18} />
              {creditBalance !== null && <span className="topbar-badge">{creditBalance.toFixed(1)}</span>}
            </Link>

            {/* Referral Gift Button */}
            <ReferralDropdown />

            <button onClick={toggleTheme} className="topbar-icon-btn" title="Toggle Theme">
              {theme === 'light' ? <RiMoonFill size={18} /> : <RiSunFill size={18} />}
            </button>

            {user && (
              <div style={{ position: 'relative' }}>
                <button 
                  onClick={() => setProfileDropdownOpen(o => !o)}
                  className="topbar-avatar" 
                  title={`Logged in as ${user.full_name}`}
                  style={{ border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  {/* If user has a photo_url, use img, otherwise initial */}
                  {user.photo_url ? (
                    <img src={user.photo_url} alt={user.full_name} style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
                  ) : (
                    user.full_name?.[0]?.toUpperCase() || 'R'
                  )}
                </button>
                
                {profileDropdownOpen && (
                  <>
                    <div
                      style={{ position: 'fixed', inset: 0, zIndex: 40 }}
                      onClick={() => setProfileDropdownOpen(false)}
                    />
                    <div style={{
                      position: 'absolute', top: 'calc(100% + 8px)', right: 0, zIndex: 50,
                      background: 'var(--surface)', border: '1px solid var(--border)',
                      borderRadius: 12, boxShadow: 'var(--shadow-lg)',
                      minWidth: 200, padding: '8px 0', overflow: 'hidden',
                      display: 'flex', flexDirection: 'column'
                    }}>
                      <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border)', marginBottom: 8 }}>
                        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>{user.full_name}</p>
                        <p style={{ fontSize: 12, color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</p>
                      </div>
                      
                      <Link 
                        href="/settings" 
                        onClick={() => setProfileDropdownOpen(false)}
                        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', color: 'var(--text-2)', fontSize: 14, transition: 'background 0.15s' }}
                        className="hover:bg-surface-alt hover:text-primary"
                      >
                        <RiSettings3Fill size={16} />
                        {t('Settings')}
                      </Link>
                      

                      
                      <Link
                        href="/help"
                        onClick={() => setProfileDropdownOpen(false)}
                        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', color: 'var(--text-2)', fontSize: 14, transition: 'background 0.15s', border: 'none', textDecoration: 'none' }}
                        className="hover:bg-surface-alt hover:text-primary"
                      >
                        <RiQuestionFill size={16} />
                        {t('Get Help')}
                      </Link>
                      
                      <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
                      
                      <button 
                        onClick={handleLogout}
                        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', color: 'var(--danger)', fontSize: 14, border: 'none', background: 'transparent', width: '100%', cursor: 'pointer' }}
                        className="hover:bg-danger/10"
                      >
                        <RiLogoutBoxRFill size={16} />
                        {t('Sign Out')}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </header>

        <main className="app-content animate-fade-in">
          {children}
        </main>
      </div>
    </div>
  );
}

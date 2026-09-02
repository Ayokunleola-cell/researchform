import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import AppLayout from '../../components/layout/AppLayout';
import { creditsApi } from '../../lib/api';
import { useCurrencyStore, CURRENCIES } from '../../lib/store';
import { RiShieldFill, RiFlashlightFill, RiGlobalFill, RiBarChart2Fill, RiCoinsFill, RiArrowRightUpLine, RiBankCardFill, RiArrowRightDownLine, RiStarFill, RiSparklingFill, RiCheckLine, RiLoader4Line, RiPulseFill } from 'react-icons/ri';
import toast from 'react-hot-toast';

const PACKAGE_ICONS = [RiFlashlightFill, RiStarFill, RiSparklingFill, RiShieldFill];
const PACKAGE_GRADIENTS = [
  'linear-gradient(135deg, rgba(59,130,246,0.22), rgba(59,130,246,0.05)), var(--surface)', // Blue for Starter
  'linear-gradient(135deg, rgba(99,102,241,0.22), rgba(99,102,241,0.05)), var(--surface)', // Indigo for Standard
  'linear-gradient(135deg, rgba(16,185,129,0.22), rgba(16,185,129,0.05)), var(--surface)', // Emerald for Pro
  'linear-gradient(135deg, rgba(245,158,11,0.25), rgba(245,158,11,0.06)), var(--surface)', // Amber for Lab
];

const getPackageBenefits = (label: string) => {
  const l = label.toLowerCase();
  if (l.includes('starter')) return ['Perfect for single small projects', 'Full access to all statistical tests', 'Export reports to PDF & DOCX', 'Credits never expire'];
  if (l.includes('standard')) return ['Ideal for multiple surveys & research', 'Better value per credit', 'Full access to all statistical tests', 'Export reports to PDF & DOCX'];
  if (l.includes('pro')) return ['For professional researchers', 'Best value for frequent users', 'Full access to all statistical tests', 'Export reports to PDF & DOCX'];
  if (l.includes('lab')) return ['For research teams & departments', 'Highest discount per credit', 'Full access to all statistical tests', 'Export reports to PDF & DOCX'];
  return ['Full access to all statistical tests', 'Export reports to PDF & DOCX', 'Credits never expire'];
};

// Gateway display config
const GATEWAY_CONFIG = {
  paystack: { label: 'Paystack', color: 'var(--text)', bg: 'var(--surface-2)', desc: 'Cards, bank transfer, USSD & more' },
  stripe:   { label: 'Stripe',   color: 'var(--text)', bg: 'var(--surface-2)', desc: 'Cards, Apple Pay, Google Pay & more' },
};

export default function AnalysisCreditsPage() {
  const router = useRouter();
  const { currency, setCurrency, getCurrencyInfo, formatPrice } = useCurrencyStore();
  const [mounted, setMounted] = useState(false);
  // Defer reading persisted currency until client-side to avoid SSR hydration mismatch
  const currencyInfo = mounted ? getCurrencyInfo() : { flag: '', code: 'NGN', symbol: '₦', name: 'Nigerian Naira', rateFromNGN: 1 };

  const [balance, setBalance] = useState<number | null>(null);
  const [packages, setPackages] = useState<any[]>([]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [buying, setBuying] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(true);
  const [paystackEnabled, setPaystackEnabled] = useState(false);
  const [stripeEnabled, setStripeEnabled] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [selectedPkg, setSelectedPkg] = useState<string | null>(null);
  const [currencyPickerOpen, setCurrencyPickerOpen] = useState(false);
  // Selected gateway per package
  const [pkgGateway, setPkgGateway] = useState<Record<string, 'paystack' | 'stripe'>>({});
  const verifiedRef = useRef<string | null>(null);

  useEffect(() => { setMounted(true); }, []);

  const getGateway = (pkgId: string): 'paystack' | 'stripe' => pkgGateway[pkgId] || 'paystack';

  const load = useCallback(async () => {
    try {
      const [cfg, w, p, t] = await Promise.all([
        creditsApi.config(),
        creditsApi.wallet(),
        creditsApi.packages(),
        creditsApi.transactions(30),
      ]);
      setDevMode(cfg.data.dev_mode);
      setPaystackEnabled(cfg.data.paystack_enabled);
      setStripeEnabled(cfg.data.stripe_enabled);
      setBalance(w.data.balance);
      setPackages(p.data.packages || []);
      setTransactions(t.data || []);
    } catch {
      toast.error('Failed to load credit wallet');
    } finally {
      setLoading(false);
    }
  }, []);

  const completePurchase = useCallback(
    async (packageId: string, reference?: string) => {
      const res = await creditsApi.purchase(packageId, reference);
      setBalance(res.data.balance);
      if (res.data.already_processed) {
        toast.success('Payment already applied to your wallet');
      } else {
        toast.success(`${res.data.credits_added} credits added to your wallet!`);
      }
      await load();
      router.replace('/settings/credits', undefined, { shallow: true });
    },
    [load, router]
  );

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!router.isReady || loading) return;
    const ref = typeof router.query.reference === 'string' ? router.query.reference : '';
    const pkgId = typeof router.query.package_id === 'string' ? router.query.package_id : '';
    const provider = typeof router.query.provider === 'string' ? router.query.provider : 'paystack';
    if (!ref || !pkgId) return;
    if (verifiedRef.current === ref) return;
    verifiedRef.current = ref;
    setVerifying(true);
    (async () => {
      try {
        if (!devMode) {
          const res = await creditsApi.verifyCheckout(ref, pkgId, provider);
          setBalance(res.data.balance);
          toast.success(res.data.already_processed
            ? 'Credits already in your wallet'
            : `Payment successful — ${res.data.credits_added} credits added`);
          await load();
          router.replace('/settings/credits', undefined, { shallow: true });
        } else {
          await completePurchase(pkgId, ref);
        }
      } catch (err: any) {
        toast.error(err.response?.data?.detail || 'Could not verify payment');
      } finally {
        setVerifying(false);
      }
    })();
  }, [router.isReady, router.query.reference, router.query.package_id, router.query.provider, loading, devMode, load, router, completePurchase]);

  const handleBuy = async (packageId: string, gateway: 'paystack' | 'stripe') => {
    setBuying(`${packageId}-${gateway}`);
    try {
      if (devMode) { await completePurchase(packageId); return; }
      if (gateway === 'paystack' && paystackEnabled) {
        const res = await creditsApi.initCheckout(packageId, 'paystack');
        window.location.href = res.data.authorization_url; return;
      }
      if (gateway === 'stripe' && stripeEnabled) {
        const res = await creditsApi.initCheckout(packageId, 'stripe');
        window.location.href = res.data.authorization_url; return;
      }
      toast.error(`${gateway === 'stripe' ? 'Stripe' : 'Paystack'} is not configured. Contact support.`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Checkout failed');
    } finally {
      setBuying(null);
    }
  };

  const totalSpent = transactions.filter(t => t.amount < 0).reduce((a, t) => a + Math.abs(t.amount), 0);
  const totalAdded = transactions.filter(t => t.amount > 0).reduce((a, t) => a + t.amount, 0);

  return (
    <AppLayout title="Credits" description="Manage your AI credits">
      <div style={{ maxWidth: 920, margin: '0 auto', padding: '0 24px 48px' }}>

        {/* ── Hero Balance Card (Solid Rich Dark Color Gradient) ── */}
        <div style={{
          position: 'relative', borderRadius: 24, overflow: 'hidden', marginBottom: 28,
          background: 'linear-gradient(135deg, #090D16 0%, #111827 50%, #0F172A 100%)',
          border: '1px solid #1E293B',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.4)',
          padding: '40px 40px 36px',
          color: '#FFFFFF',
        }}>
          {/* Glowing Ambient Background Orbs */}
          <div style={{ position: 'absolute', top: -70, right: -70, width: 280, height: 280, borderRadius: '50%', background: 'radial-gradient(circle, rgba(99,102,241,0.3) 0%, rgba(99,102,241,0) 70%)', filter: 'blur(30px)', pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', bottom: -90, left: '20%', width: 340, height: 340, borderRadius: '50%', background: 'radial-gradient(circle, rgba(59,130,246,0.2) 0%, rgba(59,130,246,0) 70%)', filter: 'blur(40px)', pointerEvents: 'none' }} />

          {verifying && (
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(15, 23, 42, 0.95)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, borderRadius: 24, zIndex: 10, backdropFilter: 'blur(8px)' }}>
              <RiLoader4Line size={22} style={{ color: '#818CF8', animation: 'spin 1s linear infinite' }} />
              <span style={{ color: '#FFFFFF', fontWeight: 600, fontSize: 15 }}>Verifying payment…</span>
            </div>
          )}

          <div style={{ position: 'relative', zIndex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(99,102,241,0.25)', border: '1px solid rgba(129,140,248,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 8px rgba(99,102,241,0.3)' }}>
                    <RiCoinsFill size={18} color="#A5B4FC" />
                  </div>
                  <span style={{ color: '#A5B4FC', fontSize: 13, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>Credit Wallet</span>
                </div>
                {loading ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <RiLoader4Line size={20} style={{ color: '#94A3B8', animation: 'spin 1s linear infinite' }} />
                    <span style={{ color: '#CBD5E1', fontSize: 15 }}>Loading balance…</span>
                  </div>
                ) : (
                  <>
                    <p style={{ margin: 0, fontSize: 52, fontWeight: 800, color: '#FFFFFF', fontFamily: 'Syne, sans-serif', lineHeight: 1, letterSpacing: '-0.02em', textShadow: '0 2px 10px rgba(0,0,0,0.3)' }}>{balance?.toFixed(2) ?? '0.00'}</p>
                    <p style={{ margin: '8px 0 0', color: '#94A3B8', fontSize: 13, fontWeight: 700, letterSpacing: '0.08em' }}>AVAILABLE CREDITS</p>
                  </>
                )}
              </div>
            </div>
            {!loading && (
              <div style={{ display: 'flex', gap: 32, marginTop: 32, flexWrap: 'wrap', paddingTop: 20, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                {[
                  { label: 'Total Added', value: `+${totalAdded.toFixed(1)}`, color: '#34D399' },
                  { label: 'Total Spent', value: `-${totalSpent.toFixed(1)}`, color: '#F87171' },
                  { label: 'Transactions', value: transactions.length, color: '#60A5FA' },
                ].map(s => (
                  <div key={s.label}>
                    <p style={{ margin: 0, fontSize: 11, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>{s.label}</p>
                    <p style={{ margin: '4px 0 0', fontSize: 22, fontWeight: 800, color: s.color, fontFamily: 'Syne, sans-serif' }}>{s.value}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Currency Info Bar ── */}
        {!loading && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 16, padding: '14px 20px', marginBottom: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, boxShadow: 'var(--shadow)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                Showing prices in {currencyInfo.name} ({currencyInfo.symbol})
              </span>
            </div>
            <div style={{ position: 'relative' }}>
              <button onClick={() => setCurrencyPickerOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600, border: '1.5px solid var(--border)', background: 'var(--bg-secondary)', color: 'var(--text)', cursor: 'pointer' }}>
                <span>{currencyInfo.flag}</span>
                <span>{currencyInfo.code}</span>
                <span style={{ fontSize: 10, color: 'var(--text-3)' }}>▾</span>
              </button>
              {currencyPickerOpen && (
                <>
                  <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setCurrencyPickerOpen(false)} />
                  <div style={{ position: 'absolute', top: 'calc(100% + 6px)', right: 0, zIndex: 50, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, boxShadow: 'var(--shadow-lg)', minWidth: 160, padding: '4px 0' }}>
                    {CURRENCIES.map(c => (
                      <button key={c.code} onClick={() => { setCurrency(c.code); setCurrencyPickerOpen(false); }} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '6px 12px', background: currency === c.code ? 'rgba(99,102,241,0.08)' : 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left' }}>
                        <span style={{ fontSize: 15 }}>{c.flag}</span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', flex: 1 }}>{c.code}</span>
                        <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{c.symbol}</span>
                        {currency === c.code && <RiCheckLine size={12} style={{ color: 'var(--brand)', flexShrink: 0 }} />}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── Buy Credits ── */}
        {!loading && (
          <section style={{ marginBottom: 36 }}>
            <h2 style={{ margin: '0 0 20px', fontSize: 18, fontWeight: 700, color: 'var(--text)', fontFamily: 'Syne, sans-serif', display: 'flex', alignItems: 'center', gap: 8 }}>
              Buy Credits
            </h2>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
              {packages.map((pkg, i) => {
                const Icon = PACKAGE_ICONS[i % PACKAGE_ICONS.length];
                const gradient = PACKAGE_GRADIENTS[i % PACKAGE_GRADIENTS.length];
                const isSelected = selectedPkg === pkg.id;
                const selectedGateway = getGateway(pkg.id);
                const isPopular = i === 1;

                return (
                  <div
                    key={pkg.id}
                    onClick={() => setSelectedPkg(isSelected ? null : pkg.id)}
                    style={{
                      position: 'relative', background: gradient,
                      border: isSelected ? '2px solid var(--text)' : '1.5px solid var(--border)',
                      borderRadius: 16, padding: '16px 16px 14px', cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      boxShadow: isSelected ? '0 0 0 3px var(--border), var(--shadow)' : 'var(--shadow)',
                      transform: isSelected ? 'translateY(-2px)' : 'none',
                      display: 'flex', flexDirection: 'column',
                    }}
                  >
                    {isPopular && (
                      <div style={{ position: 'absolute', top: -1, left: '50%', transform: 'translateX(-50%)', background: 'var(--text)', borderRadius: '0 0 6px 6px', padding: '2px 8px', fontSize: 9, fontWeight: 700, color: 'var(--bg)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Popular</div>
                    )}

                    {/* Centered Top Section */}
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
                      <div style={{ width: 34, height: 34, borderRadius: 10, marginBottom: 10, background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border)' }}>
                        <Icon size={16} color="var(--text)" />
                      </div>

                      <p style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text)' }}>{pkg.label}</p>
                      <p style={{ margin: '5px 0 3px', fontSize: 24, fontWeight: 800, color: 'var(--text)', fontFamily: 'Syne, sans-serif', lineHeight: 1 }}>
                        {pkg.credits}<span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-3)', marginLeft: 3 }}>cr</span>
                      </p>
                      <p style={{ margin: '0 0 32px', fontSize: 11, color: 'var(--text-2)', lineHeight: 1.4 }}>{pkg.description}</p>

                      {/* Price */}
                      <div style={{ marginBottom: 28 }}>
                        <p style={{ margin: 0, fontSize: 22, fontWeight: 800, color: 'var(--text)', fontFamily: 'Syne, sans-serif' }}>
                          {formatPrice(pkg.price_naira)}
                        </p>
                      </div>
                    </div>

                    {/* Benefits */}
                    <div style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {getPackageBenefits(pkg.label).map((benefit, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                          <RiCheckLine size={14} color="var(--text)" style={{ marginTop: 2, flexShrink: 0 }} />
                          <span style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.3 }}>{benefit}</span>
                        </div>
                      ))}
                    </div>

                    {/* Spacer to push buttons to the bottom */}
                    <div style={{ flex: 1 }} />

                    {/* Gateway Toggle */}
                    {!devMode && (
                      <div style={{ display: 'flex', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)', marginBottom: 8 }} onClick={e => e.stopPropagation()}>
                        {(['paystack', 'stripe'] as const).map(gw => {
                          const cfg = GATEWAY_CONFIG[gw];
                          const active = selectedGateway === gw;
                          return (
                            <button
                              key={gw}
                              onClick={() => setPkgGateway(prev => ({ ...prev, [pkg.id]: gw }))}
                              style={{
                                flex: 1, padding: '5px 4px', border: 'none', cursor: 'pointer', fontSize: 10, fontWeight: 600,
                                background: active ? cfg.bg : 'transparent',
                                color: active ? cfg.color : 'var(--text-3)',
                                transition: 'all 0.15s',
                              }}
                            >
                              {cfg.label}
                            </button>
                          );
                        })}
                      </div>
                    )}         

                    {/* Gateway description - removed for compactness */}

                    {/* Buy Button */}
                    {devMode ? (
                      <button
                        type="button"
                        disabled={!!buying || verifying}
                        onClick={(e) => { e.stopPropagation(); handleBuy(pkg.id, 'paystack'); }}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                          width: '100%', padding: '9px 0', borderRadius: 9, border: 'none',
                          cursor: buying ? 'not-allowed' : 'pointer', background: 'var(--text)',
                          color: 'var(--bg)', fontWeight: 700, fontSize: 12,
                          opacity: buying ? 0.7 : 1, transition: 'opacity 0.2s',
                          boxShadow: '0 4px 14px rgba(0,0,0,0.1)',
                        }}
                      >
                        {buying === `${pkg.id}-paystack` ? <RiLoader4Line size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <RiBankCardFill size={13} />}
                        {buying === `${pkg.id}-paystack` ? 'Processing…' : 'Buy Credit'}
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={!!buying || verifying}
                        onClick={(e) => { e.stopPropagation(); handleBuy(pkg.id, selectedGateway); }}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                          width: '100%', padding: '9px 0', borderRadius: 9, border: 'none',
                          cursor: buying ? 'not-allowed' : 'pointer',
                          background: 'var(--text)',
                          color: 'var(--bg)', fontWeight: 700, fontSize: 12,
                          opacity: buying ? 0.7 : 1, transition: 'all 0.2s',
                          boxShadow: '0 4px 14px rgba(0,0,0,0.1)',
                        }}
                      >
                        {buying === `${pkg.id}-${selectedGateway}` ? <RiLoader4Line size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <RiBankCardFill size={13} />}
                        {buying === `${pkg.id}-${selectedGateway}` ? 'Processing…' : `Pay with ${GATEWAY_CONFIG[selectedGateway].label}`}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* ── Transaction History ── */}
        {!loading && (
          <section>
            <h2 style={{ margin: '0 0 16px', fontSize: 18, fontWeight: 700, color: 'var(--text)', fontFamily: 'Syne, sans-serif', display: 'flex', alignItems: 'center', gap: 8 }}>
              Transaction History
            </h2>

            {transactions.length === 0 ? (
              <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 16, padding: '40px 24px', textAlign: 'center' }}>
                <div style={{ width: 48, height: 48, borderRadius: 14, background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px', border: '1px solid var(--border)' }}>
                  <RiCoinsFill size={22} style={{ color: 'var(--text)' }} />
                </div>
                <p style={{ margin: 0, color: 'var(--text-2)', fontSize: 14 }}>No transactions yet</p>
                <p style={{ margin: '4px 0 0', color: 'var(--text-3)', fontSize: 12 }}>Buy credits to get started</p>
              </div>
            ) : (
              <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 16, overflow: 'hidden', boxShadow: 'var(--shadow)' }}>
                {transactions.map((tx, idx) => {
                  const isCredit = tx.amount >= 0;
                  return (
                    <div key={tx.id} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px', borderBottom: idx < transactions.length - 1 ? '1px solid var(--border)' : 'none' }}>
                      <div style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, background: isCredit ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {isCredit ? <RiArrowRightUpLine size={16} style={{ color: 'var(--success)' }} /> : <RiArrowRightDownLine size={16} style={{ color: 'var(--danger)' }} />}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{tx.description}</p>
                        <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--text-3)' }}>
                          {new Date(tx.created_at).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'Syne, sans-serif', color: isCredit ? 'var(--success)' : 'var(--danger)' }}>
                          {isCredit ? '+' : ''}{Number(tx.amount).toFixed(2)}
                        </span>
                        <p style={{ margin: 0, fontSize: 10, color: 'var(--text-3)' }}>credits</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '60px 0' }}>
            <RiLoader4Line size={20} style={{ animation: 'spin 1s linear infinite', color: 'var(--brand)' }} />
            <span style={{ fontSize: 14, color: 'var(--text-3)' }}>Loading your wallet…</span>
          </div>
        )}

        <style>{`
          @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        `}</style>
      </div>
    </AppLayout>
  );
}

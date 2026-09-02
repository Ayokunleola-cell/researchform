import React, { useEffect, useState } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { adminApi } from '../../lib/api';
import toast from 'react-hot-toast';
import { RiCheckLine, RiAddFill, RiGroupFill, RiSave3Fill, RiErrorWarningFill, RiPercentFill, RiDeleteBinFill, RiGiftFill, RiBankCardFill, RiMoneyDollarCircleFill, RiShieldCheckFill, RiSettings3Fill, RiRefreshLine, RiStore2Fill, RiBox3Fill, RiLoader4Line, RiToggleFill } from 'react-icons/ri';

interface CreditPackage {
  id: string;
  label: string;
  credits: number;
  price_naira: number;
  description: string;
}

interface SettingRow {
  key: string;
  label: string;
  description: string;
  type: 'number' | 'boolean' | 'text';
  step?: string;
  section: string;
  icon?: any;
}

const SETTINGS_SCHEMA: SettingRow[] = [
  {
    key: 'base_operations_cost',
    label: 'Base Operations Cost',
    description: 'Flat credit fee added to every analysis job to cover operational overhead.',
    type: 'number', step: '0.01', section: 'billing', icon: RiMoneyDollarCircleFill,
  },
  {
    key: 'credit_markup_multiplier',
    label: 'Credit Markup Multiplier',
    description: 'Multiplies raw AI API cost to set required credits (e.g. 3.0 = 200% margin).',
    type: 'number', step: '0.1', section: 'billing', icon: RiPercentFill,
  },
  {
    key: 'allow_registrations',
    label: 'Allow New Registrations',
    description: 'Toggle to pause new user signups during maintenance.',
    type: 'boolean', section: 'users', icon: RiGroupFill,
  },
  {
    key: 'signup_bonus_credits',
    label: 'Signup Bonus Credits',
    description: 'Free analysis credits granted to new users on email verification.',
    type: 'number', step: '0.1', section: 'users', icon: RiGiftFill,
  },
  {
    key: 'auto_approve_datasets',
    label: 'Auto-Approve Datasets',
    description: 'If enabled, new datasets bypass manual review and go live immediately.',
    type: 'boolean', section: 'marketplace', icon: RiStore2Fill,
  },
  {
    key: 'marketplace_commission_percent',
    label: 'Marketplace Commission (%)',
    description: 'Percentage of each dataset sale taken by the platform.',
    type: 'number', step: '0.1', section: 'marketplace', icon: RiPercentFill,
  },
];

const SECTIONS = [
  { id: 'billing', label: 'Billing & Credits', icon: RiBankCardFill, color: '#6366f1' },
  { id: 'users', label: 'Users & Auth', icon: RiGroupFill, color: '#10b981' },
  { id: 'marketplace', label: 'Marketplace', icon: RiStore2Fill, color: '#f59e0b' },
  { id: 'packages', label: 'Credit Packages', icon: RiBox3Fill, color: '#8b5cf6' },
];

function Toggle({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      type="button"
      onClick={onChange}
      className="flex items-center gap-2 transition-all"
      style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0 }}
    >
      <div className="relative rounded-full transition-all" style={{
        width: 48, height: 26,
        background: checked ? 'var(--brand)' : 'var(--border)',
        transition: 'background 0.2s',
      }}>
        <span style={{
          position: 'absolute',
          top: 3, left: checked ? 24 : 3,
          width: 20, height: 20,
          borderRadius: '50%',
          background: 'white',
          transition: 'left 0.2s',
          boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
        }} />
      </div>
      <span className="text-sm font-medium" style={{ color: checked ? 'var(--brand)' : 'var(--text-3)' }}>
        {checked ? 'Enabled' : 'Disabled'}
      </span>
    </button>
  );
}

import AdminGuard from '../../components/admin/AdminGuard';

export default function AdminSettingsPage() {
  return (
    <AdminGuard>
      <AdminSettingsPageContent />
    </AdminGuard>
  );
}

function AdminSettingsPageContent() {
  const [settings, setSettings] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [packages, setPackages] = useState<CreditPackage[]>([]);
  const [savingPackages, setSavingPackages] = useState(false);
  const [activeSection, setActiveSection] = useState('billing');
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());

  const loadData = async () => {
    try {
      const [settingsRes, pkgRes] = await Promise.all([
        adminApi.getSettings(),
        adminApi.getCreditPackages(),
      ]);
      setSettings(settingsRes.data);
      setPackages(pkgRes.data.packages || []);
    } catch (err: any) {
      toast.error(err.response?.status === 403 ? "You don't have admin privileges" : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleSave = async (key: string, value: string) => {
    setSaving(key);
    try {
      await adminApi.updateSetting(key, value);
      setSavedKeys(prev => new Set(Array.from(prev).concat(key)));
      setTimeout(() => setSavedKeys(prev => { const s = new Set(Array.from(prev)); s.delete(key); return s; }), 2000);
      await loadData();
    } catch {
      toast.error('Failed to update setting');
    } finally {
      setSaving(null);
    }
  };

  const handleToggle = async (key: string, currentValue: string) => {
    const next = currentValue === 'true' ? 'false' : 'true';
    setSettings((prev: any) => ({ ...prev, [key]: next }));
    await handleSave(key, next);
  };

  const sectionSettings = (sectionId: string) =>
    SETTINGS_SCHEMA.filter(s => s.section === sectionId);

  return (
    <AppLayout title="Platform Settings" breadcrumbs={[{ label: 'Admin', href: '/admin/settings' }, { label: 'Settings' }]}>
      <div style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold" style={{ fontFamily: 'Syne, sans-serif', color: 'var(--text)', margin: 0 }}>
              Platform Settings
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
              Configure global platform behavior, pricing, and features
            </p>
          </div>
          <button onClick={loadData} className="btn btn-ghost flex items-center gap-2 text-sm">
            <RiRefreshLine size={15} /> Refresh
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center p-20"><RiLoader4Line className="animate-spin text-brand" size={32} /></div>
        ) : (
          <div className="grid lg:grid-cols-4 gap-6">
            {/* Sidebar Nav */}
            <div className="lg:col-span-1">
              <nav className="card p-2 sticky top-4">
                {SECTIONS.map(section => (
                  <button key={section.id} onClick={() => setActiveSection(section.id)}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all text-left"
                    style={{
                      background: activeSection === section.id ? `${section.color}12` : 'transparent',
                      color: activeSection === section.id ? section.color : 'var(--text-2)',
                      border: activeSection === section.id ? `1px solid ${section.color}30` : '1px solid transparent',
                    }}>
                    <section.icon size={17} />
                    {section.label}
                  </button>
                ))}
              </nav>
            </div>

            {/* Main Content */}
            <div className="lg:col-span-3 space-y-4">
              {activeSection !== 'packages' ? (
                <div className="card p-6">
                  {(() => {
                    const sec = SECTIONS.find(s => s.id === activeSection)!;
                    return (
                      <div className="flex items-center gap-3 mb-6 pb-5" style={{ borderBottom: '1px solid var(--border)' }}>
                        <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: `${sec.color}15` }}>
                          <sec.icon size={22} style={{ color: sec.color }} />
                        </div>
                        <div>
                          <h2 className="font-bold text-lg" style={{ color: 'var(--text)', margin: 0, fontFamily: 'Syne,sans-serif' }}>{sec.label}</h2>
                          <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>
                            {sectionSettings(activeSection).length} configurable parameters
                          </p>
                        </div>
                      </div>
                    );
                  })()}

                  <div className="space-y-6">
                    {sectionSettings(activeSection).map((s) => (
                      <div key={s.key}>
                        <div className="flex items-start justify-between gap-6">
                          <div className="flex-1">
                            <label className="block font-semibold text-sm mb-0.5" style={{ color: 'var(--text)' }}>
                              {s.label}
                            </label>
                            <p className="text-xs mb-3" style={{ color: 'var(--text-3)', lineHeight: 1.5 }}>
                              {s.description}
                            </p>
                          </div>
                        </div>

                        {s.type === 'boolean' ? (
                          <div className="flex items-center gap-4">
                            <Toggle
                              checked={(settings[s.key] ?? 'true') === 'true'}
                              onChange={() => handleToggle(s.key, settings[s.key] ?? 'true')}
                            />
                            {saving === s.key && <RiLoader4Line size={14} className="animate-spin" style={{ color: 'var(--brand)' }} />}
                            {savedKeys.has(s.key) && (
                              <span className="flex items-center gap-1 text-xs" style={{ color: '#10b981' }}>
                                <RiCheckLine size={12} /> Saved
                              </span>
                            )}
                          </div>
                        ) : (
                          <div className="flex gap-3">
                            <input
                              type={s.type}
                              step={s.step}
                              className="input flex-1"
                              value={settings[s.key] ?? ''}
                              onChange={e => setSettings((prev: any) => ({ ...prev, [s.key]: e.target.value }))}
                            />
                            <button
                              type="button"
                              className="btn btn-primary flex items-center gap-2"
                              disabled={saving === s.key}
                              onClick={() => handleSave(s.key, settings[s.key])}
                            >
                              {saving === s.key
                                ? <RiLoader4Line size={16} className="animate-spin" />
                                : savedKeys.has(s.key)
                                  ? <RiCheckLine size={16} />
                                  : <RiSave3Fill size={16} />}
                              {savedKeys.has(s.key) ? 'Saved!' : 'Save'}
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                /* Credit Packages Section */
                <div className="card p-6">
                  <div className="flex items-center gap-3 mb-6 pb-5" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: '#8b5cf615' }}>
                      <RiBox3Fill size={22} style={{ color: '#8b5cf6' }} />
                    </div>
                    <div>
                      <h2 className="font-bold text-lg" style={{ color: 'var(--text)', margin: 0, fontFamily: 'Syne,sans-serif' }}>Credit Packages</h2>
                      <p className="text-xs" style={{ color: 'var(--text-3)', margin: 0 }}>Set prices, credit amounts, and labels for each plan</p>
                    </div>
                  </div>

                  {packages.length === 0 && (
                    <div className="p-6 text-center rounded-xl mb-4" style={{ background: 'var(--surface-2)', border: '1px dashed var(--border)' }}>
                      <RiBox3Fill size={28} className="mx-auto mb-2" style={{ color: 'var(--text-3)' }} />
                      <p className="text-sm" style={{ color: 'var(--text-3)' }}>No credit packages configured. Add one below.</p>
                    </div>
                  )}

                  <div className="space-y-4 mb-4">
                    {packages.map((pkg, i) => (
                      <div key={i} className="p-4 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                        <div className="flex justify-between items-center mb-3">
                          <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Package #{i + 1}</span>
                          <button onClick={() => setPackages(packages.filter((_, idx) => idx !== i))}
                            className="p-1.5 rounded-lg transition-colors"
                            style={{ color: '#ef4444', background: 'rgba(239,68,68,0.08)' }}>
                            <RiDeleteBinFill size={14} />
                          </button>
                        </div>
                        <div className="grid grid-cols-2 gap-3 mb-3">
                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Label</label>
                            <input className="input w-full" value={pkg.label}
                              onChange={e => { const up = [...packages]; up[i] = { ...up[i], label: e.target.value }; setPackages(up); }} />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Package ID</label>
                            <input className="input w-full" value={pkg.id}
                              onChange={e => { const up = [...packages]; up[i] = { ...up[i], id: e.target.value }; setPackages(up); }} />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Credits</label>
                            <input type="number" min="1" step="1" className="input w-full" value={pkg.credits}
                              onChange={e => { const up = [...packages]; up[i] = { ...up[i], credits: parseFloat(e.target.value) || 0 }; setPackages(up); }} />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Price (₦)</label>
                            <input type="number" min="0" step="100" className="input w-full" value={pkg.price_naira}
                              onChange={e => { const up = [...packages]; up[i] = { ...up[i], price_naira: parseFloat(e.target.value) || 0 }; setPackages(up); }} />
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-3)' }}>Description</label>
                          <input className="input w-full" placeholder="e.g. ~5–8 reports"
                            value={pkg.description}
                            onChange={e => { const up = [...packages]; up[i] = { ...up[i], description: e.target.value }; setPackages(up); }} />
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="flex gap-3">
                    <button onClick={() => setPackages([...packages, { id: `pkg_${Date.now()}`, label: 'New Plan', credits: 50, price_naira: 2500, description: '' }])}
                      className="btn btn-secondary flex items-center gap-2">
                      <RiAddFill size={15} /> Add Package
                    </button>
                    <button disabled={savingPackages}
                      className="btn btn-primary flex items-center gap-2 ml-auto"
                      onClick={async () => {
                        setSavingPackages(true);
                        try {
                          await adminApi.updateCreditPackages(packages);
                          toast.success('Credit packages saved! ✓');
                        } catch { toast.error('Failed to save packages'); }
                        finally { setSavingPackages(false); }
                      }}>
                      {savingPackages ? <RiLoader4Line size={15} className="animate-spin" /> : <RiSave3Fill size={15} />}
                      Save All Packages
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

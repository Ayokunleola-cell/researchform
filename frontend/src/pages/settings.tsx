// src/pages/settings.tsx
import React, { useState, useEffect } from 'react';
import AppLayout from '../components/layout/AppLayout';
import { useThemeStore } from '../lib/store';
import { RiShieldFill, RiComputerFill, RiArrowRightFill, RiSunFill, RiMoonFill, RiUpload2Fill, RiCoinsFill, RiWallet3Fill, RiPaletteFill, RiNotification3Fill, RiCheckLine, RiLoader4Line, RiDatabase2Fill, RiUserFill } from 'react-icons/ri';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { usersApi } from '../lib/api';
import clsx from 'clsx';

export default function SettingsPage() {
  const { theme, setTheme } = useThemeStore();
  const [profile, setProfile] = useState<any>({ 
    full_name: '', email: '', institution: '', role: 'student', photo_url: '',
    preferences: {
      font: 'Times New Roman 12pt',
      line_spacing: 'Double-spaced',
      citation_style: 'APA 7th Edition',
      significance_level: '0.05',
      academic_tradition: 'nigerian'
    }
  });
  const [saved, setSaved] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    const user = localStorage.getItem('rf_user');
    if (user && user !== 'undefined') {
      try { 
        const parsed = JSON.parse(user);
        setProfile(parsed);
        if (parsed.role === 'admin') setIsAdmin(true);
      } catch (e) { localStorage.removeItem('rf_user'); }
    }
  }, []);

  const saveProfile = async () => {
    setSaving(true);
    try {
      const res = await usersApi.updateProfile({
        full_name: profile.full_name,
        institution: profile.institution,
        role: profile.role,
        preferences: profile.preferences
      });
      const updatedUser = { ...profile, ...res.data };
      localStorage.setItem('rf_user', JSON.stringify(updatedUser));
      setProfile(updatedUser);
      setSaved(true);
      toast.success('Profile saved');
      setTimeout(() => setSaved(false), 2000);
      
      // Force AppLayout to update by dispatching a custom event
      window.dispatchEvent(new Event('rf_user_updated'));
    } catch (error) {
      toast.error('Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    setUploading(true);
    try {
      const res = await usersApi.uploadAvatar(formData);
      const photo_url = res.data.photo_url;
      
      const updatedUser = { ...profile, photo_url };
      localStorage.setItem('rf_user', JSON.stringify(updatedUser));
      setProfile(updatedUser);
      toast.success('Profile picture updated!');
      
      // Force AppLayout to update
      window.dispatchEvent(new Event('rf_user_updated'));
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to upload image');
    } finally {
      setUploading(false);
    }
  };

  return (
    <AppLayout
      title="Settings"
      breadcrumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Settings' }]}
    >
      <div className="page-container-narrow page-stack">
        <div>
          <h1 className="page-title">Account & preferences</h1>
          <p className="page-description">Manage your profile, appearance, and notification preferences.</p>
        </div>

        <Link href="/settings/payouts" className="card p-5 flex items-center gap-4 card-hover no-underline">
          <div className="p-3 rounded-lg" style={{ background: 'rgba(16, 185, 129, 0.12)' }}>
            <RiWallet3Fill size={22} className="text-emerald-500" />
          </div>
          <div className="flex-1">
            <p className="font-semibold text-primary m-0">Payouts & Wallet</p>
            <p className="text-sm text-secondary m-0">
              Manage your earnings, verify identity, and request withdrawals.
            </p>
          </div>
          <RiArrowRightFill size={18} className="text-muted" />
        </Link>

        <Link href="/settings/credits" className="card p-5 flex items-center gap-4 card-hover no-underline">
          <div className="p-3 rounded-lg" style={{ background: 'rgba(99, 102, 241, 0.12)' }}>
            <RiCoinsFill size={22} className="text-brand" />
          </div>
          <div className="flex-1">
            <p className="font-semibold text-primary m-0">Analysis credits</p>
            <p className="text-sm text-secondary m-0">
              Buy credits for Analysis.
            </p>
          </div>
          <RiArrowRightFill size={18} className="text-muted" />
        </Link>

        <Link href="/settings/integrations" className="card p-5 flex items-center gap-4 card-hover no-underline">
          <div className="p-3 rounded-lg" style={{ background: 'rgba(99, 102, 241, 0.12)' }}>
            <RiDatabase2Fill size={22} className="text-brand" />
          </div>
          <div className="flex-1">
            <p className="font-semibold text-primary m-0">Integrations</p>
            <p className="text-sm text-secondary m-0">
              Manage your connected external tools and platforms.
            </p>
          </div>
          <RiArrowRightFill size={18} className="text-muted" />
        </Link>

        {/* Appearance */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-5">
            <RiPaletteFill size={20} style={{ color: 'var(--brand)' }} />
            <h2 className="font-display font-semibold" style={{ color: 'var(--text)' }}>Appearance</h2>
          </div>

          <label className="label mb-3">Theme</label>
          <div className="grid grid-cols-2 gap-3">
            {[
              { value: 'light', icon: RiSunFill,     label: 'Light' },
              { value: 'dark',  icon: RiMoonFill,    label: 'Dark' },
            ].map(({ value, icon: Icon, label }) => (
              <button
                key={value}
                onClick={() => setTheme(value as any)}
                className="flex items-center gap-3 p-4 rounded-xl border-2 transition-all text-left"
                style={{
                  borderColor: theme === value ? 'var(--brand)' : 'var(--border)',
                  background: theme === value ? 'rgba(99,102,241,0.06)' : 'var(--surface-2)',
                }}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ background: theme === value ? 'var(--brand)' : 'var(--surface)', color: theme === value ? 'var(--brand-text)' : 'var(--text-2)' }}
                >
                  <Icon size={20} />
                </div>
                <div>
                  <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{label}</p>
                </div>
                {theme === value && (
                  <div className="ml-auto">
                    <div className="w-5 h-5 rounded-full flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                      <RiCheckLine size={12} className="text-white" />
                    </div>
                  </div>
                )}
              </button>
            ))}
          </div>


        </div>

        {/* Profile */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-5">
            <RiUserFill size={20} style={{ color: 'var(--brand)' }} />
            <h2 className="font-display font-semibold" style={{ color: 'var(--text)' }}>Profile</h2>
          </div>

          <div className="flex items-center gap-6 mb-8">
            <div 
              className="relative group cursor-pointer w-20 h-20 rounded-full overflow-hidden border-2" 
              style={{ borderColor: 'var(--border)' }}
              onClick={() => document.getElementById('avatar-upload')?.click()}
            >
              {profile.photo_url ? (
                <img src={profile.photo_url} className="w-full h-full object-cover" alt="Avatar" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-2xl font-semibold bg-surface-alt text-brand" style={{ background: 'var(--surface-2)' }}>
                  {profile.full_name?.[0]?.toUpperCase() || 'R'}
                </div>
              )}
              <div className="absolute inset-0 bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                {uploading ? <RiLoader4Line size={20} className="text-white animate-spin" /> : <RiUpload2Fill size={20} className="text-white" />}
              </div>
              <input type="file" id="avatar-upload" className="hidden" accept="image/*" onChange={handleAvatarUpload} disabled={uploading} />
            </div>
            <div>
              <p className="font-semibold" style={{ color: 'var(--text)' }}>Profile Picture</p>
              <p className="text-sm" style={{ color: 'var(--text-3)' }}>PNG, JPG up to 5MB</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Full Name</label>
              <input className="input" value={profile.full_name} onChange={e => setProfile({...profile, full_name: e.target.value})} placeholder="Your full name" />
            </div>
            <div>
              <label className="label">Email</label>
              <input 
                className="input opacity-70 cursor-not-allowed bg-gray-50 dark:bg-gray-800" 
                value={profile.email} 
                readOnly 
                disabled
                title="Your email is your unique identifier and cannot be changed."
              />
            </div>
            <div>
              <label className="label">Organization / Institution</label>
              <input className="input" value={profile.institution || ''} onChange={e => setProfile({...profile, institution: e.target.value})} placeholder="Company or University name..." />
            </div>
            <div>
              <label className="label">Role</label>
              <select className="input" value={profile.role || 'other'} onChange={e => setProfile({...profile, role: e.target.value})}>
                <optgroup label="Corporate / Professional">
                  <option value="analyst">Data Analyst / Market Researcher</option>
                  <option value="manager">Product / Operations Manager</option>
                  <option value="hr">HR Professional</option>
                  <option value="consultant">Consultant</option>
                  <option value="seller">Data Seller</option>
                  <option value="other">Other Professional</option>
                </optgroup>
                <optgroup label="Academic">
                  <option value="student">Student</option>
                  <option value="researcher">Academic Researcher</option>
                  <option value="lecturer">Lecturer / Professor</option>
                </optgroup>
              </select>
            </div>
          </div>

          <button className="btn btn-primary mt-5" onClick={saveProfile} disabled={saving}>
            {saving ? <RiLoader4Line size={15} className="animate-spin" /> : (saved ? <RiCheckLine size={15} /> : null)}
            {saving ? 'Saving...' : (saved ? 'Saved!' : 'Save Profile')}
          </button>
        </div>

        {/* Report Format */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-5">
            <RiDatabase2Fill size={20} style={{ color: 'var(--brand)' }} />
            <h2 className="font-display font-semibold" style={{ color: 'var(--text)' }}>Report Format</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-5 text-sm">
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Font Type</label>
              <select 
                className="input py-2 px-3 w-full cursor-pointer" 
                value={profile.preferences?.font_type || 'Times New Roman'}
                onChange={(e) => setProfile({...profile, preferences: {...profile.preferences, font_type: e.target.value}})}
              >
                <option value="Times New Roman">Times New Roman</option>
                <option value="Arial">Arial</option>
                <option value="Calibri">Calibri</option>
                <option value="DM Sans">DM Sans (App Default)</option>
                <option value="Syne">Syne</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Font Size</label>
              <select 
                className="input py-2 px-3 w-full cursor-pointer" 
                value={profile.preferences?.font_size || '14px'}
                onChange={(e) => setProfile({...profile, preferences: {...profile.preferences, font_size: e.target.value}})}
              >
                <option value="12px">12px (Small)</option>
                <option value="14px">14px (Standard)</option>
                <option value="16px">16px (Large)</option>
                <option value="18px">18px (Extra Large)</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Line Spacing</label>
              <select 
                className="input py-2 px-3 w-full cursor-pointer"
                value={profile.preferences?.line_spacing || 'Double-spaced'}
                onChange={(e) => setProfile({...profile, preferences: {...profile.preferences, line_spacing: e.target.value}})}
              >
                <option value="Double-spaced">Double-spaced</option>
                <option value="1.5 Lines">1.5 Lines</option>
                <option value="Single-spaced">Single-spaced</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Citation Style</label>
              <select 
                className="input py-2 px-3 w-full cursor-pointer"
                value={profile.preferences?.citation_style || 'APA 7th Edition'}
                onChange={(e) => setProfile({...profile, preferences: {...profile.preferences, citation_style: e.target.value}})}
              >
                <option value="APA 7th Edition">APA 7th Edition</option>
                <option value="MLA 9th Edition">MLA 9th Edition</option>
                <option value="Harvard">Harvard</option>
                <option value="Chicago">Chicago</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Significance Level</label>
              <select 
                className="input py-2 px-3 w-full cursor-pointer"
                value={profile.preferences?.significance_level || '0.05'}
                onChange={(e) => setProfile({...profile, preferences: {...profile.preferences, significance_level: e.target.value}})}
              >
                <option value="0.05">α = 0.05</option>
                <option value="0.01">α = 0.01</option>
                <option value="0.10">α = 0.10</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>Hypothesis Language</label>
              <select 
                className="input py-2 px-3 w-full cursor-pointer"
                value={profile.preferences?.academic_tradition || 'nigerian'}
                onChange={(e) => setProfile({...profile, preferences: {...profile.preferences, academic_tradition: e.target.value}})}
              >
                <option value="nigerian">Nigerian University Format</option>
                <option value="uk">UK Standard</option>
                <option value="apa">US APA Format</option>
                <option value="standard">Global Standard</option>
              </select>
            </div>
          </div>
          <div className="mt-5 pt-5 border-t border-dashed" style={{ borderColor: 'var(--border)' }}>
            <button className="btn btn-primary" onClick={saveProfile} disabled={saving}>
              {saving ? <RiLoader4Line size={15} className="animate-spin" /> : (saved ? <RiCheckLine size={15} /> : null)}
              {saving ? 'Saving...' : (saved ? 'Saved!' : 'Save Format')}
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

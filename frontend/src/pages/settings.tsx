// src/pages/settings.tsx
import React, { useState, useEffect } from 'react';
import AppLayout from '../components/layout/AppLayout';
import { useThemeStore } from '../lib/store';
import { Moon, Sun, Monitor, User, Bell, Shield, Database, Palette, Check } from 'lucide-react';
import toast from 'react-hot-toast';
import clsx from 'clsx';

export default function SettingsPage() {
  const { theme, setTheme } = useThemeStore();
  const [profile, setProfile] = useState({ full_name: '', email: '', institution: '', role: 'student' });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const user = localStorage.getItem('rf_user');
    if (user) setProfile(JSON.parse(user));
  }, []);

  const saveProfile = () => {
    localStorage.setItem('rf_user', JSON.stringify(profile));
    setSaved(true);
    toast.success('Profile saved');
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <AppLayout>
      <div className="max-w-3xl mx-auto space-y-6">
        <div>
          <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--text)' }}>Settings</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-2)' }}>Manage your account and preferences</p>
        </div>

        {/* Appearance */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-5">
            <Palette size={20} style={{ color: 'var(--brand)' }} />
            <h2 className="font-display font-semibold" style={{ color: 'var(--text)' }}>Appearance</h2>
          </div>

          <label className="label mb-3">Theme</label>
          <div className="grid grid-cols-2 gap-3">
            {[
              { value: 'light', icon: Sun,     label: 'Light',  desc: 'White background' },
              { value: 'dark',  icon: Moon,    label: 'Dark',   desc: '#212121 background' },
            ].map(({ value, icon: Icon, label, desc }) => (
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
                  style={{ background: theme === value ? 'var(--brand)' : 'var(--surface)', color: theme === value ? '#fff' : 'var(--text-2)' }}
                >
                  <Icon size={20} />
                </div>
                <div>
                  <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{label}</p>
                  <p className="text-xs" style={{ color: 'var(--text-3)' }}>{desc}</p>
                </div>
                {theme === value && (
                  <div className="ml-auto">
                    <div className="w-5 h-5 rounded-full flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                      <Check size={12} className="text-white" />
                    </div>
                  </div>
                )}
              </button>
            ))}
          </div>

          {/* Preview */}
          <div className="mt-4 p-4 rounded-xl border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
            <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-3)' }}>PREVIEW</p>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg" style={{ background: 'var(--brand)' }} />
              <div className="flex-1">
                <div className="h-3 rounded-full w-3/4 mb-2" style={{ background: 'var(--text)', opacity: 0.7 }} />
                <div className="h-2 rounded-full w-1/2" style={{ background: 'var(--text-3)', opacity: 0.5 }} />
              </div>
            </div>
          </div>
        </div>

        {/* Profile */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-5">
            <User size={20} style={{ color: 'var(--brand)' }} />
            <h2 className="font-display font-semibold" style={{ color: 'var(--text)' }}>Profile</h2>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Full Name</label>
              <input className="input" value={profile.full_name} onChange={e => setProfile(p => ({ ...p, full_name: e.target.value }))} placeholder="Your full name" />
            </div>
            <div>
              <label className="label">Email</label>
              <input className="input" value={profile.email} onChange={e => setProfile(p => ({ ...p, email: e.target.value }))} placeholder="email@example.com" type="email" />
            </div>
            <div>
              <label className="label">Institution</label>
              <input className="input" value={profile.institution} onChange={e => setProfile(p => ({ ...p, institution: e.target.value }))} placeholder="University of..." />
            </div>
            <div>
              <label className="label">Role</label>
              <select className="input" value={profile.role} onChange={e => setProfile(p => ({ ...p, role: e.target.value }))}>
                <option value="student">Student</option>
                <option value="researcher">Researcher</option>
                <option value="lecturer">Lecturer</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>

          <button className="btn btn-primary mt-5" onClick={saveProfile}>
            {saved ? <Check size={15} /> : null}
            {saved ? 'Saved!' : 'Save Profile'}
          </button>
        </div>

        {/* Report Format */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-5">
            <Database size={20} style={{ color: 'var(--brand)' }} />
            <h2 className="font-display font-semibold" style={{ color: 'var(--text)' }}>Report Format</h2>
          </div>
          <div className="space-y-3 text-sm" style={{ color: 'var(--text-2)' }}>
            <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: 'var(--surface-2)' }}>
              <span>Font</span>
              <span className="badge badge-brand">Times New Roman 12pt</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: 'var(--surface-2)' }}>
              <span>Line Spacing</span>
              <span className="badge badge-brand">Double-spaced</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: 'var(--surface-2)' }}>
              <span>Citation Style</span>
              <span className="badge badge-brand">APA 7th Edition</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: 'var(--surface-2)' }}>
              <span>Significance Level</span>
              <span className="badge badge-brand">α = 0.05</span>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl" style={{ background: 'var(--surface-2)' }}>
              <span>Hypothesis Language</span>
              <span className="badge badge-brand">Nigerian University Format</span>
            </div>
          </div>
          <p className="text-xs mt-3" style={{ color: 'var(--text-3)' }}>
            Report format is fixed to Nigerian university academic standards. Custom formats coming in v2.
          </p>
        </div>
      </div>
    </AppLayout>
  );
}

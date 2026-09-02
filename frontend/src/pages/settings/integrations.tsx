import React, { useState, useEffect } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { RiExternalLinkFill, RiDownload2Fill, RiRefreshLine, RiLink, RiAlertFill, RiSettings3Fill } from 'react-icons/ri';
import axios from 'axios';
import Link from 'next/link';

// Use standard API client logic
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
});
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default function IntegrationsPage() {
  const [googleConnected, setGoogleConnected] = useState(false);
  const [googleEmail, setGoogleEmail] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      setLoading(true);
      const res = await api.get('/integrations/google/status');
      if (res.data.connected) {
        setGoogleConnected(true);
        setGoogleEmail(res.data.email);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleConnectGoogle = async () => {
    try {
      const res = await api.get('/integrations/google/auth-url');
      window.location.href = res.data.auth_url;
    } catch (e) {
      alert("Failed to get Google authorization URL");
    }
  };

  return (
    <AppLayout>
      <div style={{ maxWidth: 800, margin: '0 auto', padding: '40px 20px' }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
          <RiSettings3Fill size={24} color="var(--brand)" />
          Integrations
        </h1>
        <p style={{ color: 'var(--text-2)', marginBottom: 32 }}>
          Connect ResearchForm to your favorite external tools.
        </p>

        {/* Google Workspace */}
        <div style={{ background: 'var(--surface)', borderRadius: 12, border: '1px solid var(--border)', padding: 24, marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>Google Workspace</h2>
              <p style={{ color: 'var(--text-3)', fontSize: 14 }}>Connect your Google account</p>
            </div>
            {loading ? (
              <RiRefreshLine size={20} style={{ animation: 'spin 1s linear infinite', color: 'var(--text-3)' }} />
            ) : googleConnected ? (
              <span style={{ padding: '6px 12px', background: 'rgba(34,197,94,0.1)', color: '#22c55e', borderRadius: 20, fontSize: 13, fontWeight: 600 }}>
                Connected
              </span>
            ) : (
              <button onClick={handleConnectGoogle} style={{ padding: '8px 16px', background: 'var(--brand)', color: 'white', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
                Connect Google
              </button>
            )}
          </div>
          
          {googleConnected && (
            <div style={{ marginTop: 20, padding: 16, background: 'rgba(0,0,0,0.02)', borderRadius: 8 }}>
              <p style={{ fontSize: 14, color: 'var(--text-2)', marginBottom: 12 }}>
                Connected as: <strong>{googleEmail}</strong>
              </p>
              <button disabled style={{ padding: '6px 12px', background: 'transparent', color: '#ef4444', border: '1px solid #ef4444', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'not-allowed', opacity: 0.5 }}>
                Disconnect Account
              </button>
              <p style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 8 }}>To disconnect, revoke access in your Google Account settings.</p>
            </div>
          )}
        </div>

        {/* Power BI */}
        <div style={{ background: 'var(--surface)', borderRadius: 12, border: '1px solid var(--border)', padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>Microsoft Power BI</h2>
              <p style={{ color: 'var(--text-3)', fontSize: 14 }}>Generate secure, live data feeds for your surveys and datasets to consume in Power BI Desktop.</p>
            </div>
          </div>
          <div style={{ marginTop: 20 }}>
            <p style={{ fontSize: 14, color: 'var(--text-2)', marginBottom: 16 }}>
              To connect a dataset to Power BI:
            </p>
            <ol style={{ fontSize: 14, color: 'var(--text-2)', paddingLeft: 20, lineHeight: 1.6 }}>
              <li>Go to your Survey Results or Dataset listing.</li>
              <li>Click <strong>Export & Integrations</strong> &gt; <strong>Connect to Power BI</strong>.</li>
              <li>Copy the secure feed URL.</li>
              <li>In Power BI Desktop, select <strong>Get Data</strong> &gt; <strong>Web</strong> and paste the URL.</li>
            </ol>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

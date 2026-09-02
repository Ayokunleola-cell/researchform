// src/pages/_app.tsx
import type { AppProps } from 'next/app';
import { useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import { SWRConfig } from 'swr';
import { fetcher } from '../lib/fetcher';
import { useThemeStore, fetchAndApplyLiveRates, autoDetectLocationAndCurrency } from '../lib/store';
import CookieConsent from '../components/ui/CookieConsent';
import '../styles/globals.css';

export default function App({ Component, pageProps }: AppProps) {
  const { theme } = useThemeStore();

  useEffect(() => {
    // Apply theme on change; default to dark for new users
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  // Ensure dark class is set immediately on first mount for new users
  useEffect(() => {
    const stored = localStorage.getItem('rf-theme');
    if (!stored) {
      document.documentElement.classList.add('dark');
    }
  }, []);


  // Fetch live exchange rates and auto-detect currency location once on app load
  useEffect(() => {
    fetchAndApplyLiveRates();
    autoDetectLocationAndCurrency();
  }, []);

  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: false }}>
      <Component {...pageProps} />
      <CookieConsent />
      <Toaster
        position="top-center"
        toastOptions={{
          className: 'toast-custom',
          duration: 3000,
          style: {
            fontFamily: "'DM Sans', sans-serif",
            fontSize: '14px',
          },
          success: { icon: null },
          error: { icon: null },
        }}
      />
    </SWRConfig>
  );
}


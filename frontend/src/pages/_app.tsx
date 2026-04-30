// src/pages/_app.tsx
import type { AppProps } from 'next/app';
import { useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import { useThemeStore } from '../lib/store';
import '../styles/globals.css';

export default function App({ Component, pageProps }: AppProps) {
  const { theme } = useThemeStore();

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  return (
    <>
      <Component {...pageProps} />
      <Toaster
        position="top-right"
        toastOptions={{
          className: 'toast-custom',
          duration: 3000,
          style: {
            fontFamily: "'DM Sans', sans-serif",
            fontSize: '14px',
          },
        }}
      />
    </>
  );
}

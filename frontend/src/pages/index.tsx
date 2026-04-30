// src/pages/index.tsx
import { useEffect } from 'react';
import { useRouter } from 'next/router';
import Cookies from 'js-cookie';

export default function IndexPage() {
  const router = useRouter();
  useEffect(() => {
    const token = Cookies.get('rf_token');
    if (token) {
      router.replace('/dashboard');
    } else {
      router.replace('/login');
    }
  }, [router]);
  return null;
}

import React, { useEffect } from 'react';
import { useRouter } from 'next/router';
import Cookies from 'js-cookie';
import { RiLoader4Line } from 'react-icons/ri';

export default function AuthCallback() {
  const router = useRouter();

  useEffect(() => {
    if (!router.isReady) return;

    const { token, user, error } = router.query;

    if (error) {
      router.push(`/login?error=${error}`);
      return;
    }

    if (token) {
      Cookies.set('rf_token', token as string, { expires: 7 });
      
      if (user) {
        try {
          const parsedUser = JSON.parse(user as string);
          localStorage.setItem('rf_user', JSON.stringify(parsedUser));
        } catch (e) {
          console.error("Failed to parse user from query param");
        }
      }

      router.push('/dashboard');
    } else {
      router.push('/login');
    }
  }, [router.isReady, router.query]);

  return (
    <div className="min-h-screen flex items-center justify-center flex-col gap-4" style={{ background: 'var(--bg)' }}>
      <RiLoader4Line size={32} className="animate-spin text-brand" />
      <p className="text-secondary font-medium">Completing sign in...</p>
    </div>
  );
}

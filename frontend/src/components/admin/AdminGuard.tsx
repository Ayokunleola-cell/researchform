import React, { useEffect, useState } from 'react';
import NotFound from '../ui/NotFound';

interface AdminGuardProps {
  children: React.ReactNode;
}

export default function AdminGuard({ children }: AdminGuardProps) {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('rf_user');
      if (stored && stored !== 'undefined') {
        const user = JSON.parse(stored);
        if (user && user.role === 'admin') {
          setIsAdmin(true);
          return;
        }
      }
    } catch (e) {
      console.error('Admin check error:', e);
    }
    setIsAdmin(false);
  }, []);

  if (isAdmin === null) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    );
  }

  if (!isAdmin) {
    return <NotFound />;
  }

  return <>{children}</>;
}

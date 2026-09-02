import React, { useState, useEffect } from 'react';

interface CookieConsentProps {
  delayMs?: number;
}

export default function CookieConsent({ delayMs = 2500 }: CookieConsentProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [preferences, setPreferences] = useState({
    strictlyNecessary: true,
    analytics: false,
    marketing: false
  });

  useEffect(() => {
    const consent = localStorage.getItem('cookie-consent');
    if (!consent) {
      const effectiveDelay = process.env.NODE_ENV === 'test' ? 0 : delayMs;
      if (effectiveDelay === 0) {
        setIsVisible(true);
      } else {
        const timer = setTimeout(() => {
          setIsVisible(true);
        }, effectiveDelay);
        return () => clearTimeout(timer);
      }
    } else {
      try {
        const parsed = JSON.parse(consent);
        if (parsed.analytics !== undefined) {
          setPreferences(prev => ({ ...prev, ...parsed }));
        }
      } catch (e) {}
    }
  }, [delayMs]);

  const savePreferences = (prefs: any) => {
    localStorage.setItem('cookie-consent', JSON.stringify(prefs));
    setIsVisible(false);
    setShowSettings(false);
  };

  const handleAcceptAll = () => {
    savePreferences({ strictlyNecessary: true, analytics: true, marketing: true });
  };

  const handleRejectAll = () => {
    savePreferences({ strictlyNecessary: true, analytics: false, marketing: false });
  };

  const handleSaveSettings = () => {
    savePreferences(preferences);
  };

  if (!isVisible && !showSettings) return null;

  return (
    <>
      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 z-[10000] flex items-center justify-center p-4">
          <div className="bg-[var(--surface)] w-full max-w-lg rounded-xl shadow-xl overflow-hidden animate-in zoom-in-95">
            <div className="px-6 py-4 border-b border-[var(--border)] flex justify-between items-center bg-[var(--surface-2)]">
              <h3 className="text-lg font-bold text-[var(--text)]">Cookie Settings</h3>
              <button onClick={() => setShowSettings(false)} className="text-[var(--text-3)] hover:text-[var(--text)]">
                ✕
              </button>
            </div>
            
            <div className="p-6 space-y-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h4 className="font-semibold text-[var(--text)] mb-1">Strictly Necessary</h4>
                  <p className="text-sm text-[var(--text-2)]">These cookies are essential for the website to function properly. They cannot be disabled.</p>
                </div>
                <input type="checkbox" checked disabled className="w-5 h-5 shrink-0 accent-[#0066FF] cursor-not-allowed" />
              </div>

              <div className="flex items-start justify-between gap-4">
                <div>
                  <h4 className="font-semibold text-[var(--text)] mb-1">Analytics</h4>
                  <p className="text-sm text-[var(--text-2)]">Help us understand how visitors interact with our platform by collecting reporting information anonymously.</p>
                </div>
                <input 
                  type="checkbox" 
                  checked={preferences.analytics} 
                  onChange={(e) => setPreferences({...preferences, analytics: e.target.checked})}
                  className="w-5 h-5 shrink-0 accent-[#0066FF] cursor-pointer" 
                />
              </div>

              <div className="flex items-start justify-between gap-4">
                <div>
                  <h4 className="font-semibold text-[var(--text)] mb-1">Marketing</h4>
                  <p className="text-sm text-[var(--text-2)]">Used to track visitors across websites to display relevant and engaging advertisements.</p>
                </div>
                <input 
                  type="checkbox" 
                  checked={preferences.marketing} 
                  onChange={(e) => setPreferences({...preferences, marketing: e.target.checked})}
                  className="w-5 h-5 shrink-0 accent-[#0066FF] cursor-pointer" 
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-[var(--border)] bg-[var(--surface-2)] flex justify-end gap-3">
              <button 
                onClick={handleRejectAll}
                className="px-4 py-2 text-sm font-semibold text-[var(--text-2)] hover:text-[var(--text)]"
              >
                Reject All
              </button>
              <button 
                onClick={handleSaveSettings}
                className="px-4 py-2 text-sm font-semibold text-white bg-[#0066FF] hover:bg-[#0052cc] rounded-md transition-colors"
              >
                Save Settings
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom Banner */}
      {isVisible && !showSettings && (
        <div className="fixed bottom-0 left-0 w-full bg-[var(--surface)] border-t border-[var(--border)] shadow-[0_-4px_20px_rgba(0,0,0,0.1)] z-[9999] p-4 md:p-6 animate-in slide-in-from-bottom-5">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 md:gap-8">
            <p className="text-sm text-[var(--text-2)] flex-1 text-center md:text-left leading-relaxed font-medium">
              By clicking “Accept All Cookies”, you agree to the storing of cookies on your device to enhance site navigation, analyze site usage, and assist in our marketing efforts.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 shrink-0">
              <button
                onClick={() => setShowSettings(true)}
                className="text-sm font-semibold text-[var(--text-3)] hover:text-[var(--text)] transition-colors px-3 py-2"
              >
                Cookies Settings
              </button>
              <button
                onClick={handleRejectAll}
                className="text-sm font-semibold text-[var(--text)] bg-[var(--surface-2)] hover:bg-[var(--surface-3)] border border-[var(--border)] transition-colors px-5 py-2.5 rounded-md"
              >
                Reject All
              </button>
              <button
                onClick={handleAcceptAll}
                className="text-sm font-semibold text-white bg-[#0066FF] hover:bg-[#0052cc] transition-colors px-5 py-2.5 rounded-md shadow-sm"
              >
                Accept All Cookies
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

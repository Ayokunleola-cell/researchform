// src/lib/store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ThemeStore {
  theme: 'light' | 'dark';
  toggleTheme: () => void;
  setTheme: (t: 'light' | 'dark') => void;
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      theme: 'dark',
      toggleTheme: () =>
        set((s) => {
          const next = s.theme === 'light' ? 'dark' : 'light';
          document.documentElement.classList.toggle('dark', next === 'dark');
          return { theme: next };
        }),
      setTheme: (t) => {
        document.documentElement.classList.toggle('dark', t === 'dark');
        set({ theme: t });
      },
    }),
    { name: 'rf-theme' }
  )
);

export interface LayoutStore {
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (c: boolean) => void;
}

export const useLayoutStore = create<LayoutStore>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      setSidebarCollapsed: (c) => set({ sidebarCollapsed: c }),
    }),
    { name: 'rf-layout' }
  )
);

// ─── API ────────────────────────────────────────────────────────────
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─── Survey Store ────────────────────────────────────────────────────
interface SurveyStore {
  currentSurvey: any | null;
  questions: any[];
  setCurrentSurvey: (s: any) => void;
  setQuestions: (q: any[]) => void;
  addQuestion: (q: any) => void;
  updateQuestion: (id: string, patch: any) => void;
  removeQuestion: (id: string) => void;
  reorderQuestions: (ids: string[]) => void;
}

export const useSurveyStore = create<SurveyStore>((set) => ({
  currentSurvey: null,
  questions: [],
  setCurrentSurvey: (s) => set({ currentSurvey: s }),
  setQuestions: (q) => set({ questions: q }),
  addQuestion: (q) => set((s) => ({ questions: [...s.questions, q] })),
  updateQuestion: (id, patch) =>
    set((s) => ({
      questions: s.questions.map((q) => (q.id === id ? { ...q, ...patch } : q)),
    })),
  removeQuestion: (id) =>
    set((s) => ({ questions: s.questions.filter((q) => q.id !== id) })),
  reorderQuestions: (ids) =>
    set((s) => ({
      questions: ids.map((id) => s.questions.find((q) => q.id === id)!),
    })),
}));

// ─── Analysis Job Store ──────────────────────────────────────────────
interface JobStore {
  currentJob: any | null;
  setCurrentJob: (j: any) => void;
  pollInterval: ReturnType<typeof setInterval> | null;
  setPollInterval: (i: ReturnType<typeof setInterval> | null) => void;
}

export const useJobStore = create<JobStore>((set) => ({
  currentJob: null,
  setCurrentJob: (j) => set({ currentJob: j }),
  pollInterval: null,
  setPollInterval: (i) => set({ pollInterval: i }),
}));

// ─── Currency Store ──────────────────────────────────────────────────
export type CurrencyCode = 'NGN' | 'USD';

export interface CurrencyInfo {
  code: CurrencyCode;
  name: string;
  symbol: string;
  flag: string;
  // Rate vs NGN (how many NGN = 1 unit of this currency) — fallback static
  rateFromNGN: number;
}

// Static fallback rates (NGN base → how many NGN per 1 unit of foreign currency)
export const CURRENCIES: CurrencyInfo[] = [
  { code: 'NGN', name: 'Nigerian Naira', symbol: '₦', flag: '🇳🇬', rateFromNGN: 1 },
  { code: 'USD', name: 'US Dollar',      symbol: '$', flag: '🇺🇸', rateFromNGN: 1650 },
];

interface CurrencyStore {
  currency: CurrencyCode;
  manualSelection: boolean;
  autoDetected: boolean;
  // Live rates keyed by CurrencyCode → NGN per unit
  liveRates: Partial<Record<CurrencyCode, number>>;
  ratesUpdatedAt: number | null;
  setCurrency: (c: CurrencyCode) => void;
  updateLiveRates: (rates: Partial<Record<CurrencyCode, number>>) => void;
  getCurrencyInfo: () => CurrencyInfo;
  convertFromNGN: (ngnAmount: number) => number;
  formatPrice: (ngnAmount: number) => string;
  setAutoDetected: () => void;
}

const getRate = (code: CurrencyCode, liveRates: Partial<Record<CurrencyCode, number>>): number => {
  return liveRates[code] ?? CURRENCIES.find(c => c.code === code)?.rateFromNGN ?? 1;
};

export const useCurrencyStore = create<CurrencyStore>()(
  persist(
    (set, get) => ({
      currency: 'NGN',
      manualSelection: false,
      autoDetected: false,
      liveRates: {},
      ratesUpdatedAt: null,
      setCurrency: (c) => {
        set({ currency: c, manualSelection: true });
        fetchAndApplyLiveRates(true);
      },
      setAutoDetected: () => set({ autoDetected: true }),
      updateLiveRates: (rates) => set({ liveRates: rates, ratesUpdatedAt: Date.now() }),
      getCurrencyInfo: () => {
        const { currency, liveRates } = get();
        const base = CURRENCIES.find(c => c.code === currency) || CURRENCIES[0];
        return { ...base, rateFromNGN: getRate(currency, liveRates) };
      },
      convertFromNGN: (ngnAmount: number) => {
        const { currency, liveRates } = get();
        return ngnAmount / getRate(currency, liveRates);
      },
      formatPrice: (ngnAmount: number) => {
        const { currency, liveRates } = get();
        const info = CURRENCIES.find(c => c.code === currency) || CURRENCIES[0];
        const rate = getRate(currency, liveRates);
        const converted = ngnAmount / rate;
        return `${info.symbol}${converted < 10 ? converted.toFixed(2) : converted.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
      },
    }),
    { name: 'rf-currency' }
  )
);

// ─── Live Rate Fetcher ────────────────────────────────────────────────
// Uses open.er-api.com (free, no API key, cached 1hr on server)
// Converts USD-base rates to NGN-base (how many NGN per 1 unit of currency)
const RATES_CACHE_KEY = 'rf_live_rates_cache';
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

export async function fetchAndApplyLiveRates(force = false): Promise<void> {
  if (typeof window === 'undefined') return;
  try {
    // Check localStorage cache first
    const cached = localStorage.getItem(RATES_CACHE_KEY);
    if (cached && !force) {
      const { rates, ts } = JSON.parse(cached);
      if (Date.now() - ts < CACHE_TTL_MS) {
        useCurrencyStore.getState().updateLiveRates(rates);
        return;
      }
    }
    // Fetch NGN-based rates: 1 NGN = X foreign
    const res = await fetch('https://open.er-api.com/v6/latest/NGN', { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    if (data.result !== 'success' || !data.rates) return;

    // data.rates[currency] = how many foreign units per 1 NGN
    // We need the inverse: how many NGN per 1 foreign unit
    const r = data.rates as Record<string, number>;
    const ngnPerUnit: Partial<Record<CurrencyCode, number>> = {};
    const codes: CurrencyCode[] = ['USD'];
    for (const code of codes) {
      if (r[code] && r[code] > 0) {
        ngnPerUnit[code] = Math.round((1 / r[code]) * 100) / 100;
      }
    }
    ngnPerUnit['NGN'] = 1;

    // Cache and apply
    localStorage.setItem(RATES_CACHE_KEY, JSON.stringify({ rates: ngnPerUnit, ts: Date.now() }));
    useCurrencyStore.getState().updateLiveRates(ngnPerUnit);
  } catch {
    // Silently fall back to static rates on any network/parse error
  }
}

export async function autoDetectLocationAndCurrency(): Promise<void> {
  if (typeof window === 'undefined') return;
  
  const store = useCurrencyStore.getState();
  
  // Do not overwrite if the user has manually selected a currency, or if we already auto-detected.
  if (store.manualSelection || store.autoDetected) return;

  try {
    const res = await fetch('https://ipapi.co/json/');
    if (!res.ok) throw new Error('Location API failed');
    const data = await res.json();
    
    // Auto detect: if Nigeria -> NGN, else -> USD
    if (data.country_code === 'NG') {
      useCurrencyStore.setState({ currency: 'NGN' });
    } else {
      useCurrencyStore.setState({ currency: 'USD' });
    }
    
    store.setAutoDetected();
  } catch (error) {
    // If adblocker blocks ipapi or any network error, default to USD if not set
    useCurrencyStore.setState({ currency: 'USD' });
    store.setAutoDetected();
  }
}

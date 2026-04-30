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
      theme: 'light',
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

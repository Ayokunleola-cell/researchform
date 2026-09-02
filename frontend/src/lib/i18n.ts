import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const LANGUAGES = [
  { code: 'en-US', label: 'English (United States)' },
  { code: 'fr-FR', label: 'Français (France)' },
  { code: 'de-DE', label: 'Deutsch (Deutschland)' },
  { code: 'hi-IN', label: 'हिन्दी (भारत)' },
  { code: 'id-ID', label: 'Indonesia (Indonesia)' },
  { code: 'it-IT', label: 'Italiano (Italia)' },
  { code: 'ja-JP', label: '日本語 (日本)' },
  { code: 'ko-KR', label: '한국어 (대한민국)' },
  { code: 'pt-BR', label: 'Português (Brasil)' },
  { code: 'es-419', label: 'Español (Latinoamérica)' },
  { code: 'es-ES', label: 'Español (España)' },
];

type LanguageStore = {
  language: string;
  setLanguage: (lang: string) => void;
};

export const useLanguageStore = create<LanguageStore>()(
  persist(
    (set) => ({
      language: 'en-US',
      setLanguage: (language: string) => set({ language }),
    }),
    {
      name: 'rf_language',
    }
  )
);

// Baseline dictionary for navigation elements
const DICTIONARY: Record<string, Record<string, string>> = {
  'fr-FR': {
    'Workspace': 'Espace de travail',
    'Dashboard': 'Tableau de bord',
    'Surveys': 'Sondages',
    'Research pipeline': 'Pipeline de recherche',
    'Analysis': 'Analyse',
    'Reports': 'Rapports',
    'Chat with AI': 'Discuter avec l\'IA',
    'Marketplace': 'Place de marché',
    'Overview': 'Aperçu',
    'Browse Datasets': 'Parcourir les jeux de données',
    'My Library': 'Ma bibliothèque',
    'Sell Data': 'Vendre des données',
    'Admin Panel': 'Panneau d\'administration',
    'Manage Users': 'Gérer les utilisateurs',
    'Review Datasets': 'Examiner les jeux de données',
    'Manage Credits': 'Gérer les crédits',
    'Platform Settings': 'Paramètres de la plateforme',
    'Settings': 'Paramètres',
    'Language': 'Langue',
    'Get Help': 'Obtenir de l\'aide',
    'Sign Out': 'Se déconnecter',
  },
  'es-ES': {
    'Workspace': 'Espacio de trabajo',
    'Dashboard': 'Panel de control',
    'Surveys': 'Encuestas',
    'Research pipeline': 'Canal de investigación',
    'Analysis': 'Análisis',
    'Reports': 'Informes',
    'Chat with AI': 'Chatear con IA',
    'Marketplace': 'Mercado',
    'Overview': 'Visión general',
    'Browse Datasets': 'Explorar conjuntos de datos',
    'My Library': 'Mi biblioteca',
    'Sell Data': 'Vender datos',
    'Admin Panel': 'Panel de administración',
    'Manage Users': 'Gestionar usuarios',
    'Review Datasets': 'Revisar conjuntos de datos',
    'Manage Credits': 'Gestionar créditos',
    'Platform Settings': 'Configuración de la plataforma',
    'Settings': 'Configuración',
    'Language': 'Idioma',
    'Get Help': 'Obtener ayuda',
    'Sign Out': 'Cerrar sesión',
  },
  'es-419': {
    'Workspace': 'Espacio de trabajo',
    'Dashboard': 'Panel de control',
    'Surveys': 'Encuestas',
    'Research pipeline': 'Línea de investigación',
    'Analysis': 'Análisis',
    'Reports': 'Reportes',
    'Chat with AI': 'Chatear con IA',
    'Marketplace': 'Mercado',
    'Overview': 'Resumen',
    'Browse Datasets': 'Explorar bases de datos',
    'My Library': 'Mi biblioteca',
    'Sell Data': 'Vender datos',
    'Admin Panel': 'Panel de administración',
    'Manage Users': 'Administrar usuarios',
    'Review Datasets': 'Revisar bases de datos',
    'Manage Credits': 'Administrar créditos',
    'Platform Settings': 'Ajustes de plataforma',
    'Settings': 'Configuraciones',
    'Language': 'Idioma',
    'Get Help': 'Ayuda',
    'Sign Out': 'Cerrar sesión',
  },
  'de-DE': {
    'Workspace': 'Arbeitsbereich',
    'Dashboard': 'Dashboard',
    'Surveys': 'Umfragen',
    'Research pipeline': 'Forschungs-Pipeline',
    'Analysis': 'Analyse',
    'Reports': 'Berichte',
    'Chat with AI': 'Mit KI chatten',
    'Marketplace': 'Marktplatz',
    'Overview': 'Übersicht',
    'Browse Datasets': 'Datensätze durchsuchen',
    'My Library': 'Meine Bibliothek',
    'Sell Data': 'Daten verkaufen',
    'Admin Panel': 'Admin-Panel',
    'Manage Users': 'Benutzer verwalten',
    'Review Datasets': 'Datensätze prüfen',
    'Manage Credits': 'Credits verwalten',
    'Platform Settings': 'Plattform-Einstellungen',
    'Settings': 'Einstellungen',
    'Language': 'Sprache',
    'Get Help': 'Hilfe erhalten',
    'Sign Out': 'Abmelden',
  },
};

export function useTranslation() {
  const { language } = useLanguageStore();

  const t = (key: string): string => {
    // English is the default key in the app
    if (language === 'en-US') return key;

    const langDict = DICTIONARY[language];
    if (langDict && langDict[key]) {
      return langDict[key];
    }
    
    return key; // Fallback to english string
  };

  return { t, language };
}

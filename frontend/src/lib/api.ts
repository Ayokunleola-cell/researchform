// src/lib/api.ts
import axios from 'axios';
import Cookies from 'js-cookie';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = Cookies.get('rf_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      Cookies.remove('rf_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// ─── Auth ─────────────────────────────────────────────────────────
export const authApi = {
  login:    (data: any) => api.post('/auth/login', data),
  register: (data: any) => api.post('/auth/register', data),
  me:       ()         => api.get('/auth/me'),
};

// ─── Surveys ──────────────────────────────────────────────────────
export const surveysApi = {
  list:        ()           => api.get('/surveys'),
  create:      (data: any)  => api.post('/surveys', data),
  get:         (id: string) => api.get(`/surveys/${id}`),
  update:      (id: string, data: any) => api.patch(`/surveys/${id}`, data),
  delete:      (id: string) => api.delete(`/surveys/${id}`),
  publish:     (id: string) => api.post(`/surveys/${id}/publish`),
  close:       (id: string) => api.post(`/surveys/${id}/close`),
  stats:       (id: string) => api.get(`/surveys/${id}/stats`),
  responses:   (id: string) => api.get(`/surveys/${id}/responses`),
};

// ─── Questions ────────────────────────────────────────────────────
export const questionsApi = {
  list:    (surveyId: string)             => api.get(`/surveys/${surveyId}/questions`),
  create:  (surveyId: string, data: any)  => api.post(`/surveys/${surveyId}/questions`, data),
  update:  (surveyId: string, qId: string, data: any) => api.patch(`/surveys/${surveyId}/questions/${qId}`, data),
  delete:  (surveyId: string, qId: string)             => api.delete(`/surveys/${surveyId}/questions/${qId}`),
  reorder: (surveyId: string, ids: string[]) => api.post(`/surveys/${surveyId}/questions/reorder`, { ids }),
};

// ─── Public Survey (Respondent) ────────────────────────────────────
export const publicApi = {
  getSurvey:    (slug: string)              => api.get(`/public/surveys/${slug}`),
  submitResponse: (slug: string, data: any) => api.post(`/public/surveys/${slug}/respond`, data),
};

// ─── Analysis ─────────────────────────────────────────────────────
export const analysisApi = {
  startFromSurvey: (surveyId: string, brief: any) => api.post(`/analysis/start`, { survey_id: surveyId, project_brief: brief }),
  startFromFile:   (formData: FormData)            => api.post(`/analysis/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  getJob:          (jobId: string)                 => api.get(`/analysis/jobs/${jobId}`),
  listJobs:        ()                              => api.get(`/analysis/jobs`),
  approveDecoded:  (jobId: string, overrides: any) => api.post(`/analysis/jobs/${jobId}/approve-decode`, overrides),
  rejectDecoded:   (jobId: string)                 => api.post(`/analysis/jobs/${jobId}/reject-decode`),
  getReport:       (jobId: string)                 => api.get(`/analysis/jobs/${jobId}/report`, { responseType: 'blob' }),
  getCharts:       (jobId: string)                 => api.get(`/analysis/jobs/${jobId}/charts`),
};

// ─── Export ────────────────────────────────────────────────────────
export const exportApi = {
  csv:      (surveyId: string) => api.get(`/export/${surveyId}/csv`,  { responseType: 'blob' }),
  excel:    (surveyId: string) => api.get(`/export/${surveyId}/xlsx`, { responseType: 'blob' }),
  spss:     (surveyId: string) => api.get(`/export/${surveyId}/sav`,  { responseType: 'blob' }),
  codebook: (surveyId: string) => api.get(`/export/${surveyId}/codebook`, { responseType: 'blob' }),
};

// ─── Helpers ────────────────────────────────────────────────────────
export function downloadBlob(blob: Blob, filename: string) {
  const url  = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href  = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

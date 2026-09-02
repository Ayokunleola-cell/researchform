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
  login:      (data: any) => api.post('/auth/login', data),
  register:   (data: any) => api.post('/auth/register', data),
  verifyOtp:  (data: any) => api.post('/auth/verify-otp', data),
  checkEmail: (data: { email: string }) => api.post('/auth/check-email', data),
  me:         ()          => api.get('/auth/me'),
  mfaSetup:   ()          => api.post('/auth/mfa/setup'),
  mfaEnable:  (data: any) => api.post('/auth/mfa/enable', data),
  mfaDisable: ()          => api.post('/auth/mfa/disable'),
  forgotPassword: (data: { email: string }) => api.post('/auth/forgot-password', data),
  resetPassword: (data: any) => api.post('/auth/reset-password', data),
};

// ─── Users ────────────────────────────────────────────────────────
export const usersApi = {
  me:            () => api.get('/users/me'),
  updateProfile: (data: { full_name?: string, institution?: string, role?: string, preferences?: any }) => api.patch('/users/me', data),
  uploadAvatar:  (data: FormData) => api.post('/users/me/avatar', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
};

// ─── Surveys ──────────────────────────────────────────────────────
export const surveysApi = {
  list:         ()           => api.get('/surveys'),
  create:       (data: any)  => api.post('/surveys', data),
  get:          (id: string) => api.get(`/surveys/${id}`),
  update:       (id: string, data: any) => api.patch(`/surveys/${id}`, data),
  // Safe settings save — NEVER changes survey status
  saveSettings: (id: string, data: { theme?: any; allow_multiple?: boolean; require_email?: boolean }) =>
    api.patch(`/surveys/${id}/settings`, data),
  reliability:       (id: string) => api.get(`/surveys/${id}/reliability`),
  pathAnalysis:      (id: string) => api.get(`/surveys/${id}/path-analysis`),
  multicollinearity: (id: string) => api.get(`/surveys/${id}/multicollinearity`),
  normality:         (id: string) => api.get(`/surveys/${id}/normality`),
  delete:       (id: string) => api.delete(`/surveys/${id}`),
  publish:      (id: string) => api.post(`/surveys/${id}/publish`),
  close:        (id: string) => api.post(`/surveys/${id}/close`),
  stats:        (id: string) => api.get(`/surveys/${id}/stats`),
  responses:    (id: string) => api.get(`/surveys/${id}/responses`),
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
  getSurvey:      (slug: string)              => api.get(`/public/surveys/${slug}`),
  submitResponse: (slug: string, data: any)   => api.post(`/public/surveys/${slug}/respond`, data),
  uploadFile:     (slug: string, file: File)  => {
    const form = new FormData();
    form.append('file', file);
    return api.post(`/public/surveys/${slug}/upload-file`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// ─── Analysis ─────────────────────────────────────────────────────
export const analysisApi = {
  startFromSurvey: (data: any) => api.post('/analysis/start', data),
  // Legacy full-inspect (kept for marketplace import path)
  inspectFile: (data: FormData) => api.post('/analysis/inspect-file', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  // Lightweight column parse — used by wizard Step 5 (no cleaning, no quality report)
  parseColumns: (data: FormData) => api.post('/analysis/parse-columns', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  startFromFile: (data: FormData) => api.post('/analysis/upload', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  variableAdvisor: (data: { brief: any }) => api.post('/analysis/variable-advisor', data),

  getJob:          (jobId: string)                 => api.get(`/analysis/jobs/${jobId}`),
  getJobPreview:   (jobId: string)                 => api.get(`/analysis/jobs/${jobId}/preview`),
  listJobs:        ()                              => api.get(`/analysis/jobs`),
  approveDecoded:  (jobId: string, overrides: any) => api.post(`/analysis/jobs/${jobId}/approve-decode`, overrides),
  rejectDecoded:   (jobId: string)                 => api.post(`/analysis/jobs/${jobId}/reject-decode`),
  retryJob:        (jobId: string)                 => api.post(`/analysis/jobs/${jobId}/retry`),
  deleteJob:       (jobId: string)                 => api.delete(`/analysis/jobs/${jobId}`),
  unlockAnalysis:  (jobId: string)                 => api.post(`/analysis/jobs/${jobId}/unlock`),
  getReport:       (jobId: string)                 => api.get(`/analysis/jobs/${jobId}/report`, { responseType: 'blob' }),
  getReportPdf:    (jobId: string)                 => api.get(`/analysis/jobs/${jobId}/report/pdf`, { responseType: 'blob' }),
  getRawReport:    (jobId: string)                 => api.get(`/analysis/jobs/${jobId}/report/raw`, { responseType: 'blob' }),
  getRawReportPdf: (jobId: string)                 => api.get(`/analysis/jobs/${jobId}/report/raw/pdf`, { responseType: 'blob' }),
  getJobBilling:   (jobId: string)                 => api.get(`/analysis/jobs/${jobId}/billing`),
  getCharts:       (jobId: string)                 => api.get(`/analysis/jobs/${jobId}/charts`),
  getChatHistory:  (jobId: string)                 => api.get(`/analysis/${jobId}/chat`),
  sendChatMessage: (jobId: string, message: string)=> api.post(`/analysis/${jobId}/chat`, { message }),
  generatePresentation: (jobId: string)            => api.post(`/analysis/jobs/${jobId}/presentation/generate`),
  unlockPresentation:   (jobId: string)            => api.post(`/analysis/jobs/${jobId}/presentation/unlock`),
  getPresentation:      (jobId: string)            => api.get(`/analysis/jobs/${jobId}/presentation/download`, { responseType: 'blob' }),
  // Preprocessing gate
  submitPreprocessingChoice: (jobId: string, payload: { mode: 'auto' | 'manual'; manual_choices?: Record<string, string> }) =>
    api.post(`/analysis/jobs/${jobId}/preprocessing-choice`, payload),
};


// ─── Analysis credits (separate from marketplace) ───────────────────
export const creditsApi = {
  config:       () => api.get('/credits/config'),
  wallet:       () => api.get('/credits/wallet'),
  transactions: (limit = 50) => api.get('/credits/transactions', { params: { limit } }),
  packages:     () => api.get('/credits/packages'),
  estimate:     (body: {
    study_types: string[];
    auto_select_techniques: boolean;
    technique_count: number;
    qualitative_file_count: number;
    has_chapters_doc: boolean;
    report_type: string;
  }) => api.post('/credits/estimate', body),
  purchase:     (packageId: string, paymentReference?: string) =>
    api.post('/credits/purchase', { package_id: packageId, payment_reference: paymentReference }),
  initCheckout: (packageId: string, provider: string = 'paystack') =>
    api.post('/credits/checkout/initialize', { package_id: packageId, provider }),
  verifyCheckout: (reference: string, packageId: string, provider: string = 'paystack') =>
    api.get(`/credits/checkout/verify/${encodeURIComponent(reference)}`, { params: { package_id: packageId, provider } }),
};

// ─── Admin ────────────────────────────────────────────────────────
export const adminApi = {
  users:             () => api.get('/admin/users'),
  wallets:           () => api.get('/admin/credits/wallets'),
  grantCredits:      (userId: string, amount: number, description: string) => api.post('/admin/credits/grant', { user_id: userId, amount, description }),
  getSettings:       () => api.get('/admin/settings'),
  updateSetting:     (key: string, value: string) => api.post(`/admin/settings/${key}`, { value }),
  getCreditPackages: () => api.get('/admin/credit-packages'),
  updateCreditPackages: (packages: any[]) => api.put('/admin/credit-packages', { packages }),
  pendingDatasets:   () => api.get('/admin/datasets/pending'),
  reviewDataset:     (id: string, status: string, reason?: string) => api.post(`/admin/datasets/${id}/review`, { status, rejection_reason: reason }),
  downloadDataset:   (id: string) => api.get(`/admin/datasets/${id}/download`),
  
  // KYC & Withdrawals
  kycRequests:       () => api.get('/admin/kyc-requests'),
  reviewKyc:         (id: string, status: string, reason?: string) => api.post(`/admin/kyc-requests/${id}/review`, { status, rejection_reason: reason }),
  withdrawals:       () => api.get('/admin/withdrawals'),
  reviewWithdrawal:  (id: string, status: string, reason?: string) => api.post(`/admin/withdrawals/${id}/review`, { status, rejection_reason: reason }),

  // User Access Control
  suspendUser:       (userId: string, suspended: boolean) => api.patch(`/admin/users/${userId}/suspend`, { suspended }),
  changeRole:        (userId: string, role: string) => api.patch(`/admin/users/${userId}/role`, { role }),
  getUser:           (userId: string) => api.get(`/admin/users/${userId}`),

  // Platform Overview
  stats:             () => api.get('/admin/stats'),
};


export const walletApi = {
  submitKyc:     (data: FormData) => api.post('/wallet/kyc-submit', data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  withdraw:      (payload: any) => api.post('/wallet/withdraw', payload),
  buyCredits:    (package_id: string) => api.post('/wallet/buy-credits', { package_id }),
  getSellerWallet: () => api.get('/datanest/sell/wallet'),
  getKycStatus:    () => api.get('/datanest/sell/verify/status'),
};

// ─── Integrations ──────────────────────────────────────────────────
export const integrationsApi = {
  google: {
    status: () => api.get('/integrations/google/status'),
    authUrl: () => api.get('/integrations/google/auth-url'),
    exportDrive: (resource_type: string, resource_id: string) => 
      api.post('/integrations/google/export-drive', { resource_type, resource_id }),
    exportSheets: (resource_type: string, resource_id: string) => 
      api.post('/integrations/google/export-sheets', { resource_type, resource_id }),
  },
  powerbi: {
    generateLink: (resource_type: string, resource_id: string) => 
      api.post(`/integrations/powerbi/generate-link?resource_type=${resource_type}&resource_id=${resource_id}`),
  }
};

export type CreditEstimate = {
  credits_required: number;
  wallet_balance: number;
  likely_sufficient: boolean;
  input_tokens: number;
  output_tokens: number;
  note?: string;
};

export type JobBilling = {
  credits_required: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  call_count: number;
  wallet_balance: number;
  can_download: boolean;
  report_paid: boolean;
  presentation_paid: boolean;
  presentation_generated: boolean;
  presentation_credits_required?: number;
  report_ready: boolean;
  credits_charged?: number | null;
  markup_multiplier?: number;
  rate_per_1k_input?: number;
  rate_per_1k_output?: number;
  minimum_credits?: number;
};

// ─── Export ────────────────────────────────────────────────────────
export const exportApi = {
  csv:      (surveyId: string) => api.get(`/export/${surveyId}/csv`,  { responseType: 'blob' }),
  xlsx:     (surveyId: string) => api.get(`/export/${surveyId}/xlsx`, { responseType: 'blob' }),
  sav:      (surveyId: string) => api.get(`/export/${surveyId}/sav`,  { responseType: 'blob' }),
  codebook: (surveyId: string) => api.get(`/export/${surveyId}/codebook`, { responseType: 'blob' }),
};

// ─── DataNest Marketplace (via ResearchForm backend proxy) ────────────────────
// All calls go through /datanest/* on the ResearchForm backend (port 8000).
// The backend proxy forwards to DataNest and returns graceful empty states
// if DataNest is offline, so marketplace pages never hard-crash.
export const datanestApi = {
  // ── Public catalogue ──────────────────────────────────────────────
  featured:    ()                          => api.get('/datanest/featured'),
  trending:    ()                          => api.get('/datanest/trending'),
  domains:     ()                          => api.get('/datanest/domains'),
  datasets:    (params?: Record<string, any>) => api.get('/datanest/datasets', { params }),
  getDataset:  (slug: string)              => api.get(`/datanest/datasets/${slug}`),
  preview:     (slug: string)              => api.get(`/datanest/datasets/${slug}/preview`),
  reviews:     (slug: string, page = 1)   => api.get(`/datanest/datasets/${slug}/reviews`, { params: { page } }),
  createReview:(slug: string, data: { rating: number; title?: string; body: string }) => api.post(`/datanest/datasets/${slug}/reviews`, data),

  // ── Library & Purchases ───────────────────────────────────────────
  library:      ()                         => api.get('/datanest/me/library'),
  purchase:     (slug: string)             => api.post(`/datanest/datasets/${slug}/purchase`),
  downloadFree: (slug: string)             => api.post(`/datanest/datasets/${slug}/download-free`),
  downloadFile: (token: string)            => api.get(`/datanest/download/${token}`, { responseType: 'blob' }),

  // ── Seller dashboard ──────────────────────────────────────────────
  myListings:    ()                        => api.get('/datanest/sell/listings'),
  analytics:     ()                        => api.get('/datanest/sell/analytics'),
  uploadDataset: (data: FormData)          => api.post('/datanest/sell/datasets', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
};


// ─── General AI Chat ─────────────────────────────────────────────────────────
// POST /chat/general — context-aware Claude chat with credit deduction
export const chatApi = {
  send: (params: {
    message: string;
    history: Array<{ role: string; content: string }>;
    context_type?: string;   // 'general' | 'analysis' | 'dataset'
    context_id?: string;     // job_id when context_type === 'analysis'
    context_data?: any;      // dataset metadata when context_type === 'dataset'
  }) => api.post('/chat/general', {
    message:      params.message,
    history:      params.history,
    context_type: params.context_type  ?? 'general',
    context_id:   params.context_id   ?? null,
    context_data: params.context_data ?? null,
  }),
};

// ─── Referral API ──────────────────────────────────────────────────────
export const referralApi = {
  /** Get current user's referral code, link, and stats */
  me: () => api.get('/referral/me'),
  /** List all users who signed up with your referral code */
  myReferees: () => api.get('/referral/my-referees'),
  /** Public leaderboard — top referrers by conversion count */
  leaderboard: (limit = 20) => api.get(`/referral/leaderboard?limit=${limit}`),
};

export const adminReferralApi = {
  stats: () => api.get('/referral/admin/stats'),
  events: (limit = 50, offset = 0) => api.get(`/referral/admin/events?limit=${limit}&offset=${offset}`),
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

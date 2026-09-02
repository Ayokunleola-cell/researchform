import { api } from './api';

/**
 * Global fetcher for SWR. Uses our configured axios instance
 * which automatically handles auth tokens and redirects on 401.
 * 
 * @param url The API endpoint to fetch
 */
export const fetcher = (url: string) => api.get(url).then(res => res.data);

import Cookies from 'js-cookie';
import { datanestApi } from './api';

export const DATANEST_DOWNLOAD_BASE =
  process.env.NEXT_PUBLIC_DATANEST_URL || 'http://localhost:8001/api/market';

export function marketplaceDownloadUrl(token: string) {
  return `${DATANEST_DOWNLOAD_BASE}/download/${token}`;
}

export type MarketplaceDatasetMeta = {
  slug: string;
  title: string;
  description?: string;
  domain?: string;
  country?: string;
  price_naira?: number;
  file_name?: string;
  original_filename?: string;
};

export class MarketplaceImportError extends Error {
  code: 'PURCHASE_REQUIRED' | 'NOT_FOUND' | 'DOWNLOAD_FAILED' | 'UNAVAILABLE';

  constructor(code: MarketplaceImportError['code'], message: string) {
    super(message);
    this.code = code;
    this.name = 'MarketplaceImportError';
  }
}

export function buildMarketplaceAnalysisUrl(params: {
  slug?: string;
  downloadToken?: string;
  title?: string;
}) {
  const sp = new URLSearchParams({ source: 'marketplace' });
  if (params.slug) sp.set('slug', params.slug);
  if (params.downloadToken) sp.set('token', params.downloadToken);
  if (params.title) sp.set('title', params.title);
  return `/analysis?${sp.toString()}`;
}

function parseFilenameFromDisposition(header: string | null): string | null {
  if (!header) return null;
  const match = /filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i.exec(header);
  return match?.[1]?.trim() || null;
}

function guessFilename(dataset: MarketplaceDatasetMeta, disposition: string | null): string {
  const fromHeader = parseFilenameFromDisposition(disposition);
  if (fromHeader) return decodeURIComponent(fromHeader);

  const named =
    dataset.file_name ||
    dataset.original_filename ||
    `${dataset.slug || 'dataset'}.csv`;

  if (/\.\w{2,5}$/i.test(named)) return named;
  return `${named}.csv`;
}

function extractDownloadToken(url: string): string | null {
  const match = url.match(/\/download\/([^/?#]+)/);
  return match?.[1] ?? null;
}

async function fetchDatasetBlob(downloadUrl: string): Promise<{ blob: Blob; disposition: string | null }> {
  const token = extractDownloadToken(downloadUrl);
  if (token) {
    try {
      const res = await datanestApi.downloadFile(token);
      const disposition =
        (res.headers?.['content-disposition'] as string | undefined) ?? null;
      return { blob: res.data as Blob, disposition };
    } catch {
      throw new MarketplaceImportError('DOWNLOAD_FAILED', 'Could not download dataset file');
    }
  }

  const auth = Cookies.get('rf_token');
  const headers: Record<string, string> = {};
  if (auth) headers.Authorization = `Bearer ${auth}`;

  const res = await fetch(downloadUrl, { headers, credentials: 'include' });
  if (!res.ok) {
    throw new MarketplaceImportError(
      'DOWNLOAD_FAILED',
      `Could not download dataset file (${res.status})`
    );
  }
  return {
    blob: await res.blob(),
    disposition: res.headers.get('content-disposition'),
  };
}

async function resolveOwnedDownloadToken(slug: string): Promise<string | null> {
  try {
    const lib = await datanestApi.library();
    const items = Array.isArray(lib.data) ? lib.data : [];
    const owned = items.find((p: { dataset?: { slug?: string } }) => p.dataset?.slug === slug);
    return owned?.download_token ?? null;
  } catch {
    return null;
  }
}

async function resolveDownloadUrl(
  slug: string,
  dataset: MarketplaceDatasetMeta,
  downloadToken?: string
): Promise<string> {
  if (downloadToken) {
    return marketplaceDownloadUrl(downloadToken);
  }

  const ownedToken = await resolveOwnedDownloadToken(slug);
  if (ownedToken) {
    return marketplaceDownloadUrl(ownedToken);
  }

  const isFree = (dataset.price_naira ?? 0) <= 0;
  if (isFree) {
    const res = await datanestApi.downloadFree(slug);
    const data = res.data;
    if (data.download_url) return data.download_url;
    if (data.download_token) return marketplaceDownloadUrl(data.download_token);
    throw new MarketplaceImportError('DOWNLOAD_FAILED', 'No download link returned for free dataset');
  }

  throw new MarketplaceImportError(
    'PURCHASE_REQUIRED',
    'Purchase or download this dataset before analyzing it'
  );
}

/** Fetch a marketplace dataset as a browser File for the analysis wizard. */
export async function importMarketplaceDataset(options: {
  slug?: string;
  downloadToken?: string;
}): Promise<{ file: File; dataset: MarketplaceDatasetMeta }> {
  let dataset: MarketplaceDatasetMeta;

  if (options.slug) {
    try {
      const res = await datanestApi.getDataset(options.slug);
      dataset = { slug: options.slug, ...res.data };
    } catch {
      throw new MarketplaceImportError('NOT_FOUND', 'Dataset not found');
    }
  } else if (options.downloadToken) {
    dataset = {
      slug: 'library',
      title: 'Marketplace dataset',
    };
  } else {
    throw new MarketplaceImportError('UNAVAILABLE', 'Missing dataset identifier');
  }

  const slug = options.slug || dataset.slug;
  const downloadUrl = options.downloadToken
    ? marketplaceDownloadUrl(options.downloadToken)
    : await resolveDownloadUrl(slug, dataset, options.downloadToken);

  const { blob, disposition } = await fetchDatasetBlob(downloadUrl);
  const filename = guessFilename(dataset, disposition);
  const file = new File([blob], filename, {
    type: blob.type || 'application/octet-stream',
  });

  return { file, dataset };
}

/** Brief fields prefilled from marketplace metadata. */
export function briefFromMarketplaceDataset(dataset: MarketplaceDatasetMeta) {
  const population = dataset.country
    ? `Respondents / units in ${dataset.country}`
    : '';

  return {
    topic: dataset.title || '',
    population,
    study_type: 'quantitative' as const,
  };
}

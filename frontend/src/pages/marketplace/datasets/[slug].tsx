import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import AppLayout from '../../../components/layout/AppLayout';
import PageContent from '../../../components/ui/PageContent';
import LoadingBlock from '../../../components/ui/LoadingBlock';
import { datanestApi } from '../../../lib/api';
import { useCurrencyPrice } from '../../../lib/useCurrencyPrice';
import MarketplaceNav from '../../../components/marketplace/MarketplaceNav';
import { marketplaceDownloadUrl, buildMarketplaceAnalysisUrl } from '../../../lib/marketplaceAnalysis';
import { RiShoppingCartFill, RiGroupFill, RiFileTextFill, RiDownload2Fill, RiStarFill, RiTimeFill, RiGlobalFill, RiCheckboxCircleFill, RiLoader4Line, RiFolderFill, RiDatabase2Fill, RiPulseFill } from 'react-icons/ri';
import toast from 'react-hot-toast';

export default function DatasetDetailPage() {
  const router = useRouter();
  const { slug } = router.query;
  
  const [dataset, setDataset] = useState<any>(null);
  const [preview, setPreview] = useState<any>(null);
  const [reviews, setReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [reviewRating, setReviewRating] = useState(0);
  const [reviewTitle, setReviewTitle] = useState('');
  const [reviewBody, setReviewBody] = useState('');
  const [reviewHover, setReviewHover] = useState(0);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [hasPurchased, setHasPurchased] = useState(false);
  const [downloadToken, setDownloadToken] = useState<string | null>(null);

  // price_naira is 0 until dataset loads — hook handles 0 as free
  const price = useCurrencyPrice(dataset?.price_naira ?? 0);

  useEffect(() => {
    if (!slug) return;
    
    setLoading(true);
    datanestApi.getDataset(slug as string)
      .then(res => {
        setDataset(res.data);
        
        // Load reviews
        datanestApi.reviews(slug as string)
          .then(r => setReviews(r.data))
          .catch(() => {});
          
        // Load preview
        setPreviewLoading(true);
        datanestApi.preview(slug as string)
          .then(p => setPreview(p.data))
          .catch(() => setPreview(null))
          .finally(() => setPreviewLoading(false));

        // Check ownership
        const user = localStorage.getItem('rf_user');
        if (user && user !== 'undefined') {
          datanestApi.library().then(res => {
            const owned = res.data.find((p: any) => p.dataset?.slug === slug || p.slug === slug);
            if (owned) {
              setHasPurchased(true);
              setDownloadToken(owned.download_token);
            }
          }).catch(() => {});
        }
      })
      .catch(err => {
        toast.error("Dataset not found or unavailable.");
        router.push('/marketplace');
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const loadReviews = () => {
    if (!slug) return;
    datanestApi.reviews(slug as string).then(r => setReviews(r.data)).catch(() => {});
  };

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reviewRating) { toast.error('Please select a star rating'); return; }
    if (!reviewBody.trim()) { toast.error('Please write a review'); return; }
    setSubmittingReview(true);
    try {
      await datanestApi.createReview(slug as string, { rating: reviewRating, title: reviewTitle, body: reviewBody });
      toast.success('Review submitted! Thank you.');
      setReviewRating(0); setReviewTitle(''); setReviewBody('');
      loadReviews();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to submit review. You may need to purchase the dataset first.');
    } finally {
      setSubmittingReview(false);
    }
  };

  if (loading) {
    return (
      <AppLayout title="Dataset details">
        <PageContent width="wide">
          <LoadingBlock label="Loading dataset details…" />
        </PageContent>
      </AppLayout>
    );
  }

  if (!dataset) return null;

  const isFree = price.isFree;

  return (
    <AppLayout
      title={dataset.title}
      breadcrumbs={[
        { label: 'Marketplace', href: '/marketplace' },
        { label: 'Browse', href: '/marketplace/browse' },
        { label: dataset.title.length > 40 ? `${dataset.title.slice(0, 40)}…` : dataset.title },
      ]}
    >
      <PageContent width="wide">
        <MarketplaceNav />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Header Info */}
          <div className="card p-6">
            <div className="flex flex-wrap gap-2 mb-4">
              {dataset.domain && <span className="badge badge-brand">{dataset.domain}</span>}
              {dataset.country && <span className="badge badge-secondary">{dataset.country}</span>}
              {dataset.status === 'verified' && (
                <span className="badge badge-success flex items-center gap-1">
                  <RiCheckboxCircleFill size={12} /> Verified
                </span>
              )}
            </div>
            
            <h1 className="page-title mb-2">{dataset.title}</h1>
            
            <div className="flex flex-wrap items-center gap-4 text-sm text-secondary mb-6">
              <div className="flex items-center gap-1">
                <RiStarFill size={16} className={dataset.average_rating > 0 ? "text-warning" : "text-muted"} />
                <span className="font-medium text-primary">{dataset.average_rating > 0 ? dataset.average_rating : "No ratings"}</span>
                <span className="text-muted">({reviews.length} reviews)</span>
              </div>
              <div className="flex items-center gap-1">
                <RiDownload2Fill size={16} className="text-muted" />
                <span>{dataset.download_count} downloads</span>
              </div>
              {dataset.published_at && (
                <div className="flex items-center gap-1">
                  <RiTimeFill size={16} className="text-muted" />
                  <span>Published {new Date(dataset.published_at).toLocaleDateString()}</span>
                </div>
              )}
            </div>
            
            <div className="prose prose-sm max-w-none text-secondary">
              <p>{dataset.description}</p>
            </div>
          </div>
          
          {/* Data Preview */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="section-title" style={{ margin: 0 }}>Data Preview</h3>
              <span style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 500 }}>Showing first 10 rows — preview only</span>
            </div>
            
            {previewLoading ? (
              <div className="flex items-center justify-center py-10">
                <RiLoader4Line size={24} className="animate-spin text-brand" />
              </div>
            ) : preview ? (
              <div
                className="data-table-wrap"
                style={{ userSelect: 'none', WebkitUserSelect: 'none' }}
                onCopy={(e) => e.preventDefault()}
                onContextMenu={(e) => e.preventDefault()}
              >
                <table className="data-table">
                  <thead>
                    <tr>
                      {preview.columns.map((col: string, i: number) => (
                        <th key={i}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.slice(0, 10).map((row: any, i: number) => (
                      <tr key={i}>
                        {preview.columns.map((col: string, j: number) => (
                          <td key={j} className="truncate-cell">
                            {row[col] !== null ? String(row[col]) : <span className="text-muted italic">null</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-10 bg-surface-2 rounded-lg border border-dashed border-gray-300 dark:border-gray-700">
                <RiDatabase2Fill size={32} className="text-muted mb-2" />
                <p className="text-secondary text-sm">Preview not available for this dataset format.</p>
              </div>
            )}
          </div>
          
          {/* Reviews */}
          <div className="card p-6">
            <h3 className="section-title mb-6">Reviews</h3>

            {/* Write a review form */}
            <form onSubmit={handleSubmitReview} className="mb-6 p-4 rounded-xl" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
              <p className="text-sm font-semibold mb-3" style={{ color: 'var(--text)' }}>Write a Review</p>
              {/* Star rating picker */}
              <div className="flex items-center gap-1 mb-3">
                {[1,2,3,4,5].map(n => (
                  <button key={n} type="button"
                    onMouseEnter={() => setReviewHover(n)}
                    onMouseLeave={() => setReviewHover(0)}
                    onClick={() => setReviewRating(n)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px' }}
                  >
                    <RiStarFill size={22} style={{ color: n <= (reviewHover || reviewRating) ? '#f59e0b' : 'var(--border)', transition: 'color 0.15s' }} />
                  </button>
                ))}
                {reviewRating > 0 && <span className="text-xs ml-1" style={{ color: 'var(--text-3)' }}>{['','Poor','Fair','Good','Very Good','Excellent'][reviewRating]}</span>}
              </div>
              <input
                className="input w-full mb-2"
                placeholder="Review title (optional)"
                value={reviewTitle}
                onChange={e => setReviewTitle(e.target.value)}
                maxLength={120}
              />
              <textarea
                className="input w-full mb-3"
                rows={3}
                placeholder="Share your experience with this dataset..."
                value={reviewBody}
                onChange={e => setReviewBody(e.target.value)}
                style={{ resize: 'vertical' }}
                required
              />
              <button type="submit" className="btn btn-primary btn-sm" disabled={submittingReview}>
                {submittingReview ? 'Submitting...' : 'Submit Review'}
              </button>
            </form>

            {reviews.length === 0 ? (
              <p className="text-secondary text-sm italic">No reviews yet. Be the first to review!</p>
            ) : (
              <div className="space-y-4">
                {reviews.map((review) => (
                  <div key={review.id} className="pb-4 mb-4 last:mb-0 last:pb-0" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-sm text-primary">{review.reviewer?.full_name || 'Anonymous User'}</span>
                      <div className="flex items-center text-warning">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <RiStarFill key={i} size={12} fill={i < review.rating ? "currentColor" : "none"} />
                        ))}
                      </div>
                    </div>
                    {review.title && <p className="font-bold text-sm text-primary mb-1">{review.title}</p>}
                    <p className="text-sm text-secondary">{review.body}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
          
        </div>
        
        {/* Sidebar */}
        <div className="space-y-6">
          
          {/* Action Card */}
          <div className="card p-6">
            <div className="text-center mb-6">
              <span className="page-title" style={{ fontSize: '1.75rem' }}>
                {price.formatted}
              </span>
              {!isFree && <p className="text-xs text-muted mt-1">One-time purchase</p>}
            </div>
            
            <button 
              className="btn btn-primary w-full mb-3 py-3" 
              onClick={async () => {
                if (isFree) {
                  try {
                    const res = await datanestApi.downloadFree(dataset.slug);
                    if (res.data.download_url) {
                      window.open(res.data.download_url, '_blank');
                    } else if (res.data.download_token) {
                      window.open(marketplaceDownloadUrl(res.data.download_token), '_blank');
                    }
                  } catch (e: any) {
                    toast.error(e.response?.data?.detail || "Failed to download");
                  }
                } else if (hasPurchased && downloadToken) {
                  window.open(marketplaceDownloadUrl(downloadToken), '_blank');
                } else {
                  router.push(`/marketplace/datasets/${dataset.slug}/purchase`);
                }
              }}
            >
              {isFree || hasPurchased ? (
                <><RiDownload2Fill size={18} /> Download Now</>
              ) : (
                <><RiShoppingCartFill size={18} /> Buy Dataset</>
              )}
            </button>
            <button
              type="button"
              className="btn btn-secondary w-full"
              onClick={() => {
                if (!isFree && !hasPurchased) {
                  toast.error("Please purchase this dataset to analyze it.");
                  router.push(`/marketplace/datasets/${dataset.slug}/purchase`);
                } else {
                  router.push(buildMarketplaceAnalysisUrl({ slug: dataset.slug, title: dataset.title }));
                }
              }}
            >
              <RiPulseFill size={16} /> Analyze
            </button>
            
            <p className="text-[10px] text-center text-muted mt-4">
              By downloading, you agree to the{' '}
              <a href="/marketplace/data-use-agreement" target="_blank" rel="noreferrer" style={{ color: 'var(--brand)', textDecoration: 'underline' }}>Data Use Agreement</a>.
            </p>
          </div>
          
          {/* Metadata */}
          <div className="card p-6">
            <h3 className="font-bold text-sm text-primary mb-4 uppercase tracking-wider">Dataset Information</h3>
            
            <ul className="space-y-4 text-sm">
              <li className="flex gap-3">
                <RiFolderFill size={16} className="text-muted shrink-0 mt-0.5" />
                <div>
                  <p className="text-muted text-xs">Domain</p>
                  <p className="text-primary font-medium">{dataset.domain || 'Unspecified'}</p>
                </div>
              </li>
              <li className="flex gap-3">
                <RiGlobalFill size={16} className="text-muted shrink-0 mt-0.5" />
                <div>
                  <p className="text-muted text-xs">Region/Country</p>
                  <p className="text-primary font-medium">{dataset.country || 'Unspecified'}</p>
                </div>
              </li>
              <li className="flex gap-3">
                <RiFileTextFill size={16} className="text-muted shrink-0 mt-0.5" />
                <div>
                  <p className="text-muted text-xs">License</p>
                  <p className="text-primary font-medium">{dataset.license || 'Custom'}</p>
                </div>
              </li>
              <li className="flex gap-3">
                <RiGroupFill size={16} className="text-muted shrink-0 mt-0.5" />
                <div>
                  <p className="text-muted text-xs">Seller</p>
                  <p className="text-brand font-medium cursor-pointer hover:underline">
                    {dataset.seller?.full_name || `@${dataset.seller?.username}` || 'Unknown'}
                  </p>
                </div>
              </li>
            </ul>
          </div>
          
        </div>
        </div>
      </PageContent>
    </AppLayout>
  );
}

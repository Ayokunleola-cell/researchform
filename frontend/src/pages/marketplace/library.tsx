import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import AppLayout from '../../components/layout/AppLayout';
import PageContent from '../../components/ui/PageContent';
import PageHeader from '../../components/ui/PageHeader';
import LoadingBlock from '../../components/ui/LoadingBlock';
import { datanestApi } from '../../lib/api';
import MarketplaceNav from '../../components/marketplace/MarketplaceNav';
import EmptyState from '../../components/ui/EmptyState';
import { marketplaceDownloadUrl, buildMarketplaceAnalysisUrl } from '../../lib/marketplaceAnalysis';
import { RiExternalLinkFill, RiBarChart2Fill, RiDownload2Fill, RiBookShelfFill, RiSearchEyeFill } from 'react-icons/ri';
import toast from 'react-hot-toast';

export default function MyLibraryPage() {
  const [purchases, setPurchases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLibrary();
  }, []);

  const fetchLibrary = async () => {
    try {
      setLoading(true);
      const res = await datanestApi.library();
      setPurchases(res.data);
    } catch {
      toast.error('Failed to load your library. Sign in and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppLayout
      title="My Library"
      description="Datasets you have purchased or downloaded"
      breadcrumbs={[{ label: 'Marketplace', href: '/marketplace' }, { label: 'My Library' }]}
    >
      <PageContent width="wide">
        <MarketplaceNav />

        <PageHeader
          title="My library"
          description="Every free or paid acquisition appears here. Download files anytime or reopen the listing."
        />

        <div className="card p-3 flex items-center gap-3 mb-4">
          <div
            className="p-2 rounded-lg flex-shrink-0"
            style={{ background: 'rgba(99, 102, 241, 0.12)' }}
          >
            <RiBookShelfFill size={20} className="text-brand" />
          </div>
          <div>
            <p className="text-sm text-secondary m-0">
              Purchased datasets stay in your library permanently. Use them in Analysis by uploading the downloaded file.
            </p>
          </div>
        </div>

        {loading ? (
          <LoadingBlock label="Loading your library…" />
        ) : purchases.length === 0 ? (
          <EmptyState
            icon={RiBookShelfFill}
            title="Your library is empty"
            description="You haven't purchased any datasets yet."
            action={
              <Link href="/marketplace/browse" className="btn btn-primary">
                <RiSearchEyeFill size={16} /> Browse datasets
              </Link>
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {purchases.map((purchase) => {
              const slug = purchase.dataset?.slug;
              const title = purchase.dataset?.title || 'Unknown dataset';
              return (
                <article key={purchase.id} className="card library-card">
                  <div className="flex gap-2 mb-2">
                    <span className="badge badge-secondary text-[10px] uppercase">
                      {purchase.dataset?.domain || 'Data'}
                    </span>
                    {purchase.payment_provider === 'free' && (
                      <span className="badge badge-success text-[10px] uppercase">Free</span>
                    )}
                  </div>
                  <h3 className="section-title text-base mb-1 line-clamp-2">{title}</h3>
                  <p className="text-xs text-muted mb-4">
                    Acquired{' '}
                    {new Date(purchase.created_at).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </p>
                  <div className="library-card-actions flex-wrap">
                    <Link
                      href={buildMarketplaceAnalysisUrl({
                        slug,
                        downloadToken: purchase.download_token,
                        title,
                      })}
                      className="btn btn-primary flex-1 text-sm min-w-[120px]"
                    >
                      <RiBarChart2Fill size={16} /> Analyze
                    </Link>
                    <a
                      href={marketplaceDownloadUrl(purchase.download_token)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-secondary flex-1 text-sm min-w-[120px]"
                    >
                      <RiDownload2Fill size={16} /> Download
                    </a>
                    {slug && (
                      <Link
                        href={`/marketplace/datasets/${slug}`}
                        className="btn btn-secondary btn-icon"
                        title="View dataset"
                      >
                        <RiExternalLinkFill size={16} />
                      </Link>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </PageContent>
    </AppLayout>
  );
}

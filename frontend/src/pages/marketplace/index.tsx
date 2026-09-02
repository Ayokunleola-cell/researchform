import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import AppLayout from '../../components/layout/AppLayout';
import PageContent from '../../components/ui/PageContent';
import LoadingBlock from '../../components/ui/LoadingBlock';
import { datanestApi } from '../../lib/api';
import { DatasetCard } from '../../components/marketplace/DatasetCard';
import MarketplaceNav from '../../components/marketplace/MarketplaceNav';
import MarketplaceHero from '../../components/marketplace/MarketplaceHero';
import EmptyState from '../../components/ui/EmptyState';
import { getDomainIcon } from '../../components/marketplace/constants';
import { RiPriceTag3Fill, RiArrowRightFill, RiBookShelfFill, RiDatabase2Fill, RiSearchEyeFill } from 'react-icons/ri';

export default function MarketplaceHomePage() {
  const router = useRouter();
  const [featured, setFeatured] = useState<any[]>([]);
  const [trending, setTrending] = useState<any[]>([]);
  const [domains, setDomains] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      datanestApi.featured().catch(() => ({ data: [] })),
      datanestApi.trending().catch(() => ({ data: [] })),
      datanestApi.domains().catch(() => ({ data: [] })),
    ]).then(([f, t, d]) => {
      setFeatured(f.data);
      setTrending(t.data);
      setDomains(d.data.slice(0, 12));
    }).finally(() => setLoading(false));
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    router.push(`/marketplace/browse?q=${encodeURIComponent(search.trim())}`);
  };

  const hasContent = domains.length > 0 || featured.length > 0 || trending.length > 0;

  return (
    <AppLayout
      title="Data Marketplace"
      description="Discover and acquire research datasets"
      breadcrumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Marketplace' }]}
    >
      <PageContent width="wide">
        <MarketplaceNav />
        <MarketplaceHero search={search} onSearchChange={setSearch} onSubmit={handleSearch} />

        <div className="marketplace-quick-actions">
          <Link href="/marketplace/browse" className="card marketplace-quick-action">
            <span className="marketplace-quick-action-icon"><RiSearchEyeFill size={18} /></span>
            <span className="font-semibold text-sm text-primary">Browse all</span>
            <span className="text-xs text-secondary">Filter by domain and price</span>
          </Link>
          <Link href="/marketplace/library" className="card marketplace-quick-action">
            <span className="marketplace-quick-action-icon"><RiBookShelfFill size={18} /></span>
            <span className="font-semibold text-sm text-primary">My library</span>
            <span className="text-xs text-secondary">Your downloads</span>
          </Link>
          <Link href="/marketplace/sell" className="card marketplace-quick-action">
            <span className="marketplace-quick-action-icon"><RiPriceTag3Fill size={18} /></span>
            <span className="font-semibold text-sm text-primary">Sell data</span>
            <span className="text-xs text-secondary">List a dataset</span>
          </Link>
        </div>

        {loading ? (
          <LoadingBlock label="Loading marketplace…" />
        ) : !hasContent ? (
          <EmptyState
            icon={RiDatabase2Fill}
            title="Marketplace is warming up"
            description="No datasets are listed yet. Check back soon, or be the first to list your research data."
            action={
              <Link href="/marketplace/sell" className="btn btn-primary">
                <RiPriceTag3Fill size={16} /> List a dataset
              </Link>
            }
          />
        ) : (
          <>
            {domains.length > 0 && (
              <section>
                <div className="section-card-header">
                  <h2 className="section-title">Browse by domain</h2>
                  <Link href="/marketplace/browse" className="section-link">
                    View all <RiArrowRightFill size={14} />
                  </Link>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  {domains.map((d: { domain: string; count: number }) => {
                    const DomainIcon = getDomainIcon(d.domain);
                    return (
                      <Link
                        key={d.domain}
                        href={`/marketplace/browse?domain=${encodeURIComponent(d.domain)}`}
                        className="card card-hover domain-tile"
                      >
                        <DomainIcon size={24} className="text-brand mb-2" />
                        <p className="text-xs font-semibold text-primary">{d.domain}</p>
                        <p className="text-[10px] text-muted mt-1">{d.count} datasets</p>
                      </Link>
                    );
                  })}
                </div>
              </section>
            )}

            {featured.length > 0 && (
              <section>
                <div className="section-card-header">
                  <h2 className="section-title">Featured datasets</h2>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {featured.map((d: any) => (
                    <DatasetCard key={d.id} dataset={d} />
                  ))}
                </div>
              </section>
            )}

            {trending.length > 0 && (
              <section>
                <div className="section-card-header">
                  <h2 className="section-title">Trending this week</h2>
                  <Link href="/marketplace/browse?sort=downloads" className="section-link">
                    See more <RiArrowRightFill size={14} />
                  </Link>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {trending.slice(0, 8).map((d: any) => (
                    <DatasetCard key={d.id} dataset={d} />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </PageContent>
    </AppLayout>
  );
}

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import AppLayout from '../../components/layout/AppLayout';
import PageContent from '../../components/ui/PageContent';
import PageHeader from '../../components/ui/PageHeader';
import LoadingBlock from '../../components/ui/LoadingBlock';
import { datanestApi } from '../../lib/api';
import { DatasetCard } from '../../components/marketplace/DatasetCard';
import MarketplaceNav from '../../components/marketplace/MarketplaceNav';
import EmptyState from '../../components/ui/EmptyState';
import { MARKETPLACE_DOMAINS } from '../../components/marketplace/constants';
import { RiArrowLeftSFill, RiCloseFill, RiArrowRightSFill, RiFilter3Fill, RiDatabase2Fill, RiSearchEyeFill } from 'react-icons/ri';
import clsx from 'clsx';
import Link from 'next/link';
import toast from 'react-hot-toast';

function buildBrowseQuery(params: {
  q?: string;
  domain?: string;
  price_type?: string;
  sort?: string;
  page?: number;
}) {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.domain) sp.set('domain', params.domain);
  if (params.price_type) sp.set('price_type', params.price_type);
  if (params.sort && params.sort !== 'newest') sp.set('sort', params.sort);
  if (params.page && params.page > 1) sp.set('page', String(params.page));
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export default function BrowsePage() {
  const router = useRouter();

  const [inputVal, setInputVal] = useState('');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const [domainFilter, setDomainFilter] = useState('');
  const [priceFilter, setPriceFilter] = useState('');
  const [sortFilter, setSortFilter] = useState('newest');

  useEffect(() => {
    if (!router.isReady) return;
    const { q, domain, price_type, sort, page: pageQ } = router.query;
    if (typeof q === 'string') {
      setQuery(q);
      setInputVal(q);
    }
    if (typeof domain === 'string') {
      setDomainFilter(domain);
      setShowFilters(true);
    }
    if (typeof price_type === 'string') setPriceFilter(price_type);
    if (typeof sort === 'string') setSortFilter(sort);
    if (typeof pageQ === 'string') setPage(Math.max(1, parseInt(pageQ, 10) || 1));
  }, [router.isReady, router.query]);

  const syncUrl = useCallback(
    (overrides: Partial<{ q: string; domain: string; price_type: string; sort: string; page: number }> = {}) => {
      const next = {
        q: overrides.q !== undefined ? overrides.q : query,
        domain: overrides.domain !== undefined ? overrides.domain : domainFilter,
        price_type: overrides.price_type !== undefined ? overrides.price_type : priceFilter,
        sort: overrides.sort !== undefined ? overrides.sort : sortFilter,
        page: overrides.page !== undefined ? overrides.page : page,
      };
      router.replace(`/marketplace/browse${buildBrowseQuery(next)}`, undefined, { shallow: true });
    },
    [query, domainFilter, priceFilter, sortFilter, page, router]
  );

  const fetchDatasets = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, per_page: 20, sort: sortFilter };
      if (query.trim()) params.q = query.trim();
      if (domainFilter) params.domain = domainFilter;
      if (priceFilter) params.price_type = priceFilter;

      const res = await datanestApi.datasets(params);
      setResults(res.data.items || []);
      setTotal(res.data.total || 0);
      setTotalPages(res.data.pages || 1);
    } catch {
      toast.error('Failed to load datasets');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query, page, domainFilter, priceFilter, sortFilter]);

  useEffect(() => {
    if (router.isReady) fetchDatasets();
  }, [fetchDatasets, router.isReady]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setQuery(inputVal.trim());
    setPage(1);
    syncUrl({ q: inputVal.trim(), page: 1 });
  };

  const clearSearch = () => {
    setInputVal('');
    setQuery('');
    setPage(1);
    syncUrl({ q: '', page: 1 });
  };

  const updateFilter = (
    key: 'domain' | 'price_type' | 'sort',
    value: string,
    resetPage = true
  ) => {
    const pg = resetPage ? 1 : page;
    if (key === 'domain') {
      setDomainFilter(value);
      syncUrl({ domain: value, page: pg });
    } else if (key === 'price_type') {
      setPriceFilter(value);
      syncUrl({ price_type: value, page: pg });
    } else {
      setSortFilter(value);
      syncUrl({ sort: value, page: pg });
    }
    if (resetPage) setPage(1);
  };

  const clearAllFilters = () => {
    setDomainFilter('');
    setPriceFilter('');
    setSortFilter('newest');
    setPage(1);
    syncUrl({ domain: '', price_type: '', sort: 'newest', page: 1 });
  };

  const activeFilters = [
    query && { label: `"${query}"`, clear: clearSearch },
    domainFilter && {
      label: domainFilter,
      clear: () => updateFilter('domain', ''),
    },
    priceFilter && {
      label: priceFilter === 'free' ? 'Free only' : 'Paid only',
      clear: () => updateFilter('price_type', ''),
    },
    sortFilter !== 'newest' && {
      label: `Sort: ${sortFilter.replace('_', ' ')}`,
      clear: () => updateFilter('sort', 'newest'),
    },
  ].filter(Boolean) as { label: string; clear: () => void }[];

  return (
    <AppLayout
      title="Browse Datasets"
      description="Search and filter research datasets"
      breadcrumbs={[{ label: 'Marketplace', href: '/marketplace' }, { label: 'Browse' }]}
    >
      <PageContent width="wide">
        <MarketplaceNav />

        <PageHeader
          title="Browse datasets"
          description="Search the catalog, filter by domain or price, and open any listing for previews and download."
        />

      <form onSubmit={handleSearch} className="-mt-2 mb-6">
        <div 
          className="flex items-center p-1.5 bg-white border border-gray-200 rounded-full shadow-sm hover:shadow-md transition-all duration-300 focus-within:ring-4 focus-within:ring-indigo-500/10 focus-within:border-indigo-400"
          style={{ maxWidth: '850px' }}
        >
          <div className="relative flex-1 flex items-center min-w-[200px]">
            <RiSearchEyeFill size={18} className="absolute left-4 text-gray-400 pointer-events-none" />
            <input
              className="w-full bg-transparent pl-12 pr-10 py-2.5 text-[15px] text-gray-900 placeholder-gray-400 focus:outline-none"
              placeholder="Search datasets by title, topic, or keyword…"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              aria-label="Search datasets"
            />
            {inputVal && (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-2 p-1.5 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100 transition-colors"
                aria-label="Clear search"
              >
                <RiCloseFill size={14} />
              </button>
            )}
          </div>
          
          <div className="h-8 w-px bg-gray-200 mx-1 hidden sm:block"></div>

          <button
            type="button"
            className={clsx(
              'hidden sm:flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-full transition-colors',
              showFilters ? 'bg-indigo-50 text-indigo-700' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900'
            )}
            onClick={() => setShowFilters((f) => !f)}
            aria-expanded={showFilters}
          >
            <RiFilter3Fill size={16} /> Filters
          </button>

          <button 
            type="submit" 
            className="flex items-center gap-2 px-7 py-3 ml-1 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-sm font-bold rounded-full shadow-md hover:shadow-lg transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-70 disabled:hover:scale-100" 
            disabled={loading}
          >
            Search
          </button>
        </div>

        {/* Mobile filter button row */}
        <div className="mt-3 flex sm:hidden">
          <button
            type="button"
            className={clsx(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-full border transition-colors w-full justify-center shadow-sm',
              showFilters ? 'bg-indigo-50 text-indigo-700 border-indigo-200' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
            )}
            onClick={() => setShowFilters((f) => !f)}
            aria-expanded={showFilters}
          >
            <RiFilter3Fill size={16} /> {showFilters ? 'Hide Filters' : 'Show Filters'}
          </button>
        </div>
      </form>

      {showFilters && (
        <div className="card p-4 mb-4 animate-fade-in">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="label" htmlFor="filter-domain">Domain</label>
              <select
                id="filter-domain"
                className="input"
                value={domainFilter}
                onChange={(e) => updateFilter('domain', e.target.value)}
              >
                <option value="">All domains</option>
                {MARKETPLACE_DOMAINS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="filter-price">Price</label>
              <select
                id="filter-price"
                className="input"
                value={priceFilter}
                onChange={(e) => updateFilter('price_type', e.target.value)}
              >
                <option value="">All prices</option>
                <option value="free">Free datasets</option>
                <option value="paid">Premium datasets</option>
              </select>
            </div>
            <div>
              <label className="label" htmlFor="filter-sort">Sort by</label>
              <select
                id="filter-sort"
                className="input"
                value={sortFilter}
                onChange={(e) => updateFilter('sort', e.target.value)}
              >
                <option value="newest">Newest first</option>
                <option value="downloads">Most downloaded</option>
                <option value="rating">Highest rated</option>
                <option value="price_asc">Price: low to high</option>
                <option value="price_desc">Price: high to low</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {activeFilters.length > 0 && (
        <div className="filter-chips">
          {activeFilters.map((f) => (
            <span key={f.label} className="filter-chip">
              {f.label}
              <button type="button" onClick={f.clear} aria-label={`Remove filter ${f.label}`}>
                <RiCloseFill size={12} />
              </button>
            </span>
          ))}
          <button type="button" className="text-xs text-brand font-medium hover:underline" onClick={clearAllFilters}>
            Clear all
          </button>
        </div>
      )}

      <div className="flex items-center justify-between mb-4 text-sm text-secondary">
        <p>
          {loading
            ? 'Searching…'
            : query
              ? `${total.toLocaleString()} results for "${query}"`
              : `${total.toLocaleString()} datasets`}
        </p>
        {!loading && totalPages > 1 && (
          <span>Page {page} of {totalPages}</span>
        )}
      </div>

      {loading ? (
        <LoadingBlock label="Searching datasets…" />
      ) : results.length === 0 ? (
        <EmptyState
          icon={RiDatabase2Fill}
          title="No datasets found"
          description="Try different keywords, remove filters, or browse all domains."
          action={
            <Link href="/marketplace" className="btn btn-secondary">
              Back to overview
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {results.map((dataset) => (
            <DatasetCard key={dataset.id} dataset={dataset} />
          ))}
        </div>
      )}

      {totalPages > 1 && !loading && (
        <div className="flex items-center justify-center gap-3 mt-8">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              const pg = Math.max(1, page - 1);
              setPage(pg);
              syncUrl({ page: pg });
            }}
            disabled={page === 1}
          >
            <RiArrowLeftSFill size={14} /> Prev
          </button>
          <span className="text-sm text-secondary">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              const pg = Math.min(totalPages, page + 1);
              setPage(pg);
              syncUrl({ page: pg });
            }}
            disabled={page === totalPages}
          >
            Next <RiArrowRightSFill size={14} />
          </button>
        </div>
      )}
      </PageContent>
    </AppLayout>
  );
}

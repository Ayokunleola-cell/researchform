import React from 'react';
import { RiSearchEyeFill } from 'react-icons/ri';
import clsx from 'clsx';

type MarketplaceHeroProps = {
  search: string;
  onSearchChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  compact?: boolean;
};

export default function MarketplaceHero({
  search,
  onSearchChange,
  onSubmit,
  compact = false,
}: MarketplaceHeroProps) {
  return (
    <section className={clsx('app-hero marketplace-hero', compact && 'app-hero-compact')}>
      <div className="app-hero-glow" aria-hidden />
      <div className="app-hero-inner">
        {!compact && (
          <>

            <h1 className="app-hero-title">Find research-ready datasets</h1>
            <p className="app-hero-desc">
              Buy, sell, or download survey and experimental data, ready for analysis.
            </p>
          </>
        )}
        <form onSubmit={onSubmit} className="marketplace-hero-search">
          <div className="marketplace-hero-search-field">
            <RiSearchEyeFill size={18} className="marketplace-hero-search-icon" aria-hidden />
            <input
              type="search"
              className="input marketplace-hero-input"
              placeholder="Search by topic, domain, or keyword…"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              aria-label="Search datasets"
            />
          </div>
          <button type="submit" className="btn marketplace-hero-submit">
            Search
          </button>
        </form>
      </div>
    </section>
  );
}

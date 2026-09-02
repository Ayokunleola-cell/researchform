import React from 'react';
import Link from 'next/link';
import { RiDownload2Fill, RiArrowRightFill, RiStarFill } from 'react-icons/ri';
import clsx from 'clsx';
import { useCurrencyPrice } from '../../lib/useCurrencyPrice';

export type MarketplaceDataset = {
  id: string;
  slug: string;
  title: string;
  description?: string;
  domain?: string;
  country?: string;
  price_naira: number;
  download_count?: number;
  average_rating?: number;
};

type DatasetCardProps = {
  dataset: MarketplaceDataset;
  href?: string;
  onClick?: () => void;
};

export function DatasetCard({ dataset, href, onClick }: DatasetCardProps) {
  const { formatted, isFree } = useCurrencyPrice(dataset.price_naira);
  const linkHref = href ?? `/marketplace/datasets/${dataset.slug}`;

  const inner = (
    <>
      <div className="dataset-card-head">
        <h3 className="dataset-card-title">{dataset.title}</h3>
        <span className={clsx('badge whitespace-nowrap', isFree ? 'badge-success' : 'badge-brand')}>
          {formatted}
        </span>
      </div>

      <p className="dataset-card-desc">
        {dataset.description || 'No description provided.'}
      </p>

      <div className="dataset-card-tags">
        {dataset.domain && (
          <span className="badge badge-secondary text-[10px]">{dataset.domain}</span>
        )}
        {dataset.country && (
          <span className="badge badge-secondary text-[10px]">{dataset.country}</span>
        )}
      </div>

      <div className="dataset-card-foot">
        <span className="dataset-card-stat">
          <RiDownload2Fill size={12} aria-hidden />
          {(dataset.download_count ?? 0).toLocaleString()}
        </span>
        <span className="dataset-card-stat">
          <RiStarFill
            size={12}
            aria-hidden
            className={dataset.average_rating && dataset.average_rating > 0 ? 'text-warning' : ''}
          />
          {dataset.average_rating && Number(dataset.average_rating) > 0
            ? Number(dataset.average_rating).toFixed(1)
            : 'New'}
        </span>
        <span className="dataset-card-cta">
          View <RiArrowRightFill size={12} aria-hidden />
        </span>
      </div>
    </>
  );

  if (onClick) {
    return (
      <article
        className="card card-hover dataset-card"
        onClick={onClick}
        onKeyDown={(e) => e.key === 'Enter' && onClick()}
        role="button"
        tabIndex={0}
      >
        {inner}
      </article>
    );
  }

  return (
    <Link href={linkHref} className="card card-hover dataset-card">
      {inner}
    </Link>
  );
}

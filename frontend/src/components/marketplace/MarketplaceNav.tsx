import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { RiPriceTag3Fill, RiArrowRightSFill, RiShoppingBag3Fill, RiSearchEyeFill, RiBookOpenFill } from 'react-icons/ri';
import clsx from 'clsx';

const TABS = [
  {
    href: '/marketplace',
    icon: RiShoppingBag3Fill,
    label: 'Overview',
    match: (path: string) => path === '/marketplace',
  },
  {
    href: '/marketplace/browse',
    icon: RiSearchEyeFill,
    label: 'Browse',
    match: (path: string) =>
      path.startsWith('/marketplace/browse') || path.startsWith('/marketplace/datasets'),
  },
  {
    href: '/marketplace/library',
    icon: RiBookOpenFill,
    label: 'My Library',
    match: (path: string) => path.startsWith('/marketplace/library'),
  },
  {
    href: '/marketplace/sell',
    icon: RiPriceTag3Fill,
    label: 'Sell Data',
    match: (path: string) => path.startsWith('/marketplace/sell'),
  },
] as const;

export default function MarketplaceNav({ className }: { className?: string }) {
  const router = useRouter();
  const path = router.pathname;

  return (
    <nav
      className={clsx('workflow-strip marketplace-nav', className)}
      aria-label="Marketplace sections"
    >
      {TABS.map((tab, i) => {
        const active = tab.match(path);
        const Icon = tab.icon;
        return (
          <React.Fragment key={tab.href}>
            <Link
              href={tab.href}
              className={clsx('workflow-step', active && 'workflow-step-active')}
            >
              <div className="workflow-step-icon">
                <Icon size={18} />
              </div>
              <div className="workflow-step-text">
                <span className="workflow-step-label">{tab.label}</span>
              </div>
            </Link>
            {i < TABS.length - 1 && (
              <RiArrowRightSFill size={16} className="workflow-step-sep" aria-hidden />
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}

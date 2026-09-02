import React from 'react';
import clsx from 'clsx';

type PageContentProps = {
  children: React.ReactNode;
  /** default 72rem · narrow 48rem · wide 80rem · full no max-width */
  width?: 'default' | 'narrow' | 'wide' | 'full';
  className?: string;
  stack?: boolean;
};

const WIDTH_CLASS = {
  default: 'page-container',
  narrow: 'page-container-narrow',
  wide: 'page-container-wide',
  full: 'page-container-full',
} as const;

export default function PageContent({
  children,
  width = 'default',
  className,
  stack = true,
}: PageContentProps) {
  return (
    <div className={clsx(WIDTH_CLASS[width], stack && 'page-stack', className)}>
      {children}
    </div>
  );
}

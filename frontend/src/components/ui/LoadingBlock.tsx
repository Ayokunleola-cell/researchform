import React from 'react';
import { RiLoader4Line } from 'react-icons/ri';

type LoadingBlockProps = {
  label?: string;
  className?: string;
};

export default function LoadingBlock({ label = 'Loading…', className }: LoadingBlockProps) {
  return (
    <div className={className ?? 'loading-block'} role="status" aria-live="polite">
      <RiLoader4Line size={36} className="animate-spin text-brand" aria-hidden />
      <p className="text-secondary text-sm m-0">{label}</p>
    </div>
  );
}

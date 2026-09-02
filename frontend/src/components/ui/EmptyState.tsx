import React from 'react';
import type { IconType } from 'react-icons';

type EmptyStateProps = {
  icon: IconType;
  title: string;
  description?: string;
  action?: React.ReactNode;
};

export default function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="card p-12 flex flex-col items-center justify-center text-center">
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center bg-brand/10 mb-4">
        <Icon size={28} className="text-brand" />
      </div>
      <h3 className="text-xl font-bold mb-2">{title}</h3>
      {description && <p className="text-secondary mb-6 max-w-sm">{description}</p>}
      {action && <div>{action}</div>}
    </div>
  );
}

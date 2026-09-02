import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { RiBarChart2Fill, RiArrowRightSFill, RiBookOpenFill, RiFileTextFill } from 'react-icons/ri';
import clsx from 'clsx';

const STEPS = [
  {
    id: 'collect',
    href: '/surveys',
    icon: RiFileTextFill,
    label: 'Collect',
    desc: 'Build surveys & gather responses',
    match: (path: string) => path.startsWith('/surveys'),
  },
  {
    id: 'analyze',
    href: '/analysis',
    icon: RiBarChart2Fill,
    label: 'Analyze',
    desc: 'Run the analysis',
    match: (path: string) => path.startsWith('/analysis'),
  },
  {
    id: 'report',
    href: '/reports',
    icon: RiBookOpenFill,
    label: 'Report',
    desc: 'Download Report',
    match: (path: string) => path.startsWith('/reports'),
  },
] as const;

export default function ResearchWorkflow({ className }: { className?: string }) {
  const router = useRouter();
  const path = router.pathname;

  return (
    <div className={clsx('workflow-strip', className)} role="navigation" aria-label="Research workflow">
      {STEPS.map((step, i) => {
        const active = step.match(path);
        const Icon = step.icon;
        return (
          <React.Fragment key={step.id}>
            <Link href={step.href} className={clsx('workflow-step', active && 'workflow-step-active')}>
              <div className="workflow-step-icon">
                <Icon size={18} />
              </div>
              <div className="workflow-step-text">
                <span className="workflow-step-label">{step.label}</span>
                <span className="workflow-step-desc">{step.desc}</span>
              </div>
            </Link>
            {i < STEPS.length - 1 && (
              <RiArrowRightSFill size={16} className="workflow-step-sep" aria-hidden />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

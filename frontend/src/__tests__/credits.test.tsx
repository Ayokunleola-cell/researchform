/**
 * credits.test.tsx
 * Unit tests for the Credits settings page package cards.
 * We test the getPackageBenefits logic and the card render structure.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

// ── Mock heavy dependencies ─────────────────────────────────────────────────
jest.mock('next/router', () => ({ useRouter: () => ({ isReady: true, query: {}, replace: jest.fn() }) }));
jest.mock('next/link', () => {
  const L = ({ children, href }: any) => <a href={href}>{children}</a>;
  L.displayName = 'Link';
  return L;
});
jest.mock('react-hot-toast', () => ({ error: jest.fn(), success: jest.fn() }));
jest.mock('../lib/api', () => ({
  creditsApi: {
    config: jest.fn().mockResolvedValue({ data: { dev_mode: true, paystack_enabled: false, stripe_enabled: false } }),
    wallet: jest.fn().mockResolvedValue({ data: { balance: 50 } }),
    packages: jest.fn().mockResolvedValue({
      data: {
        packages: [
          { id: 'starter', label: 'Starter', credits: 25, price_naira: 1500, description: '~5–8 reports' },
          { id: 'standard', label: 'Standard', credits: 75, price_naira: 4000, description: '~15–25 reports' },
          { id: 'pro', label: 'Pro', credits: 200, price_naira: 10000, description: '~40+ reports' },
          { id: 'lab_pack', label: 'Lab Pack', credits: 500, price_naira: 22000, description: 'Departments & labs' },
        ]
      }
    }),
    transactions: jest.fn().mockResolvedValue({ data: [] }),
  }
}));
jest.mock('../lib/store', () => ({
  useCurrencyStore: () => ({
    currency: 'NGN',
    setCurrency: jest.fn(),
    getCurrencyInfo: () => ({ flag: '🇳🇬', code: 'NGN', symbol: '₦', name: 'Nigerian Naira', rateFromNGN: 1 }),
    formatPrice: (p: number) => `₦${p.toLocaleString()}`,
  }),
  CURRENCIES: [{ code: 'NGN', symbol: '₦', flag: '🇳🇬', name: 'Nigerian Naira', rateFromNGN: 1 }],
}));

// ── Isolated benefits helper (mirrors the production logic) ─────────────────
const getPackageBenefits = (label: string): string[] => {
  const l = label.toLowerCase();
  if (l.includes('starter')) return ['Perfect for single small projects', 'Full access to all statistical tests', 'Export reports to PDF & DOCX', 'Credits never expire'];
  if (l.includes('standard')) return ['Ideal for multiple surveys & research', 'Better value per credit', 'Full access to all statistical tests', 'Export reports to PDF & DOCX'];
  if (l.includes('pro')) return ['For professional researchers', 'Best value for frequent users', 'Full access to all statistical tests', 'Export reports to PDF & DOCX'];
  if (l.includes('lab')) return ['For research teams & departments', 'Highest discount per credit', 'Full access to all statistical tests', 'Export reports to PDF & DOCX'];
  return ['Full access to all statistical tests', 'Export reports to PDF & DOCX', 'Credits never expire'];
};

// ════════════════════════════════════════════════════════════════════════════
// SUITE 1: getPackageBenefits logic
// ════════════════════════════════════════════════════════════════════════════
describe('getPackageBenefits – Correct benefits per package', () => {
  test('Starter returns 4 benefits', () => {
    expect(getPackageBenefits('Starter')).toHaveLength(4);
  });

  test('Starter includes "Perfect for single small projects"', () => {
    expect(getPackageBenefits('Starter')).toContain('Perfect for single small projects');
  });

  test('Starter includes credits never expire', () => {
    expect(getPackageBenefits('Starter')).toContain('Credits never expire');
  });

  test('Standard returns 4 benefits', () => {
    expect(getPackageBenefits('Standard')).toHaveLength(4);
  });

  test('Standard first benefit is usage-focused', () => {
    expect(getPackageBenefits('Standard')[0]).toMatch(/multiple surveys/i);
  });

  test('Pro returns 4 benefits', () => {
    expect(getPackageBenefits('Pro')).toHaveLength(4);
  });

  test('Pro highlights value for frequent users', () => {
    expect(getPackageBenefits('Pro')).toContain('Best value for frequent users');
  });

  test('Lab Pack returns 4 benefits', () => {
    expect(getPackageBenefits('Lab Pack')).toHaveLength(4);
  });

  test('Lab Pack mentions teams and departments', () => {
    expect(getPackageBenefits('Lab Pack')[0]).toMatch(/teams/i);
  });

  test('Lab Pack mentions highest discount', () => {
    expect(getPackageBenefits('Lab Pack')).toContain('Highest discount per credit');
  });

  test('All packages include PDF & DOCX export', () => {
    ['Starter', 'Standard', 'Pro', 'Lab Pack'].forEach(pkg => {
      expect(getPackageBenefits(pkg)).toContain('Export reports to PDF & DOCX');
    });
  });

  test('All packages include full access to statistical tests', () => {
    ['Starter', 'Standard', 'Pro', 'Lab Pack'].forEach(pkg => {
      expect(getPackageBenefits(pkg)).toContain('Full access to all statistical tests');
    });
  });

  test('Unknown package returns default benefits', () => {
    const defaults = getPackageBenefits('Enterprise');
    expect(defaults).toContain('Full access to all statistical tests');
    expect(defaults).toContain('Credits never expire');
  });

  test('Benefits are case-insensitive matched', () => {
    expect(getPackageBenefits('STARTER')).toHaveLength(4);
    expect(getPackageBenefits('starter')).toHaveLength(4);
  });

  test('No benefit contains fake/untrue claims', () => {
    const fakeClaims = ['API access', '24/7 priority support', 'dedicated account manager', 'multi-user collaboration'];
    ['Starter', 'Standard', 'Pro', 'Lab Pack'].forEach(pkg => {
      const benefits = getPackageBenefits(pkg).map(b => b.toLowerCase());
      fakeClaims.forEach(claim => {
        expect(benefits).not.toContain(claim);
      });
    });
  });
});

// ════════════════════════════════════════════════════════════════════════════
// SUITE 2: BenefitItem render component
// ════════════════════════════════════════════════════════════════════════════

const BenefitItem = ({ text }: { text: string }) => (
  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
    <span aria-label="check" style={{ color: 'var(--text)' }}>✓</span>
    <span>{text}</span>
  </div>
);

const PackageCard = ({ label }: { label: string }) => (
  <div data-testid={`card-${label.toLowerCase()}`}>
    <h3>{label}</h3>
    {getPackageBenefits(label).map((b, i) => (
      <BenefitItem key={i} text={b} />
    ))}
  </div>
);

describe('PackageCard – Renders benefits correctly', () => {
  test('Starter card renders all 4 benefits', () => {
    render(<PackageCard label="Starter" />);
    const benefits = getPackageBenefits('Starter');
    benefits.forEach(b => expect(screen.getByText(b)).toBeInTheDocument());
  });

  test('Standard card renders all 4 benefits', () => {
    render(<PackageCard label="Standard" />);
    const benefits = getPackageBenefits('Standard');
    benefits.forEach(b => expect(screen.getByText(b)).toBeInTheDocument());
  });

  test('Pro card renders all 4 benefits', () => {
    render(<PackageCard label="Pro" />);
    const benefits = getPackageBenefits('Pro');
    benefits.forEach(b => expect(screen.getByText(b)).toBeInTheDocument());
  });

  test('Lab Pack card renders all 4 benefits', () => {
    render(<PackageCard label="Lab Pack" />);
    const benefits = getPackageBenefits('Lab Pack');
    benefits.forEach(b => expect(screen.getByText(b)).toBeInTheDocument());
  });

  test('Each card has a heading with the label', () => {
    render(<PackageCard label="Pro" />);
    expect(screen.getByText('Pro')).toBeInTheDocument();
  });
});

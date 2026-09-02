/**
 * CookieConsent.test.tsx
 * Unit tests for the CookieConsent banner and settings modal.
 */
import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import CookieConsent from '../components/ui/CookieConsent';

// Mock next/link
jest.mock('next/link', () => {
  const MockLink = ({ children, href }: any) => <a href={href}>{children}</a>;
  MockLink.displayName = 'MockLink';
  return MockLink;
});

// ── Helper ──────────────────────────────────────────────────────────────────
const clearConsent = () => localStorage.removeItem('cookie-consent');
const getConsent = () => localStorage.getItem('cookie-consent');

// ════════════════════════════════════════════════════════════════════════════
// SUITE 1: Banner Visibility
// ════════════════════════════════════════════════════════════════════════════
describe('CookieConsent – Banner Visibility', () => {
  beforeEach(() => clearConsent());

  test('shows banner when no consent stored', () => {
    render(<CookieConsent />);
    expect(screen.getByRole('button', { name: /accept all cookies/i })).toBeInTheDocument();
  });

  test('hides banner when consent already stored', () => {
    localStorage.setItem('cookie-consent', JSON.stringify({ strictlyNecessary: true }));
    render(<CookieConsent />);
    expect(screen.queryByRole('button', { name: /accept all cookies/i })).not.toBeInTheDocument();
  });

  test('displays the full consent statement', () => {
    render(<CookieConsent />);
    expect(screen.getByText(/storing of cookies on your device/i)).toBeInTheDocument();
  });

  test('shows three action buttons', () => {
    render(<CookieConsent />);
    expect(screen.getByText('Cookies Settings')).toBeInTheDocument();
    expect(screen.getByText('Reject All')).toBeInTheDocument();
    expect(screen.getByText('Accept All Cookies')).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════════
// SUITE 2: Accept All
// ════════════════════════════════════════════════════════════════════════════
describe('CookieConsent – Accept All', () => {
  beforeEach(() => clearConsent());

  test('clicking Accept All hides the banner', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Accept All Cookies'));
    expect(screen.queryByText(/accept all cookies/i)).not.toBeInTheDocument();
  });

  test('clicking Accept All saves all-true preferences to localStorage', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Accept All Cookies'));
    const saved = JSON.parse(getConsent()!);
    expect(saved.strictlyNecessary).toBe(true);
    expect(saved.analytics).toBe(true);
    expect(saved.marketing).toBe(true);
  });
});

// ════════════════════════════════════════════════════════════════════════════
// SUITE 3: Reject All
// ════════════════════════════════════════════════════════════════════════════
describe('CookieConsent – Reject All', () => {
  beforeEach(() => clearConsent());

  test('clicking Reject All hides the banner', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Reject All'));
    expect(screen.queryByText('Reject All')).not.toBeInTheDocument();
  });

  test('clicking Reject All saves only strictly-necessary as true', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Reject All'));
    const saved = JSON.parse(getConsent()!);
    expect(saved.strictlyNecessary).toBe(true);
    expect(saved.analytics).toBe(false);
    expect(saved.marketing).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════
// SUITE 4: Settings Modal
// ════════════════════════════════════════════════════════════════════════════
describe('CookieConsent – Settings Modal', () => {
  beforeEach(() => clearConsent());

  test('clicking Cookies Settings opens the modal', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Cookies Settings'));
    expect(screen.getByText('Cookie Settings')).toBeInTheDocument();
  });

  test('modal shows three categories', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Cookies Settings'));
    expect(screen.getByText('Strictly Necessary')).toBeInTheDocument();
    expect(screen.getByText('Analytics')).toBeInTheDocument();
    expect(screen.getByText('Marketing')).toBeInTheDocument();
  });

  test('strictly necessary checkbox is checked and disabled', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Cookies Settings'));
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes[0]).toBeChecked();
    expect(checkboxes[0]).toBeDisabled();
  });

  test('analytics and marketing checkboxes start unchecked', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Cookies Settings'));
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes[1]).not.toBeChecked(); // analytics
    expect(checkboxes[2]).not.toBeChecked(); // marketing
  });

  test('can toggle analytics on', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Cookies Settings'));
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);
    expect(checkboxes[1]).toBeChecked();
  });

  test('Save Settings persists custom preferences', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Cookies Settings'));
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]); // enable analytics
    fireEvent.click(screen.getByText('Save Settings'));
    const saved = JSON.parse(getConsent()!);
    expect(saved.analytics).toBe(true);
    expect(saved.marketing).toBe(false);
  });

  test('closing modal with X keeps banner visible', () => {
    render(<CookieConsent />);
    fireEvent.click(screen.getByText('Cookies Settings'));
    fireEvent.click(screen.getByText('✕'));
    expect(screen.getByText('Accept All Cookies')).toBeInTheDocument();
  });
});

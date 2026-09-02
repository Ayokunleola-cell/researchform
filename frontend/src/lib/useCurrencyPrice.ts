/**
 * useCurrencyPrice — converts a NGN price using the global currency store.
 * Returns { formatted, isFree } where `formatted` is the display string.
 * Uses a mounted guard to avoid SSR hydration mismatches.
 */
import { useState, useEffect } from 'react';
import { useCurrencyStore } from './store';

export function useCurrencyPrice(priceNaira: number) {
  const { formatPrice, getCurrencyInfo } = useCurrencyStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const isFree = priceNaira <= 0;

  if (isFree) return { formatted: 'Free', isFree: true, symbol: '', currencyCode: 'NGN' };

  const info = getCurrencyInfo();

  if (!mounted) {
    // Safe SSR fallback — always NGN until hydrated
    return {
      formatted: `₦${priceNaira.toLocaleString()}`,
      isFree: false,
      symbol: '₦',
      currencyCode: 'NGN',
    };
  }

  return {
    formatted: formatPrice(priceNaira),
    isFree: false,
    symbol: info.symbol,
    currencyCode: info.code,
  };
}

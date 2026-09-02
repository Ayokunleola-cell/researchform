import React from 'react';
import Link from 'next/link';
import { RiErrorWarningFill, RiCoinsFill, RiCheckboxCircleFill } from 'react-icons/ri';
import type { CreditEstimate } from '../../lib/api';

type AnalysisCostBannerProps = {
  estimate: CreditEstimate | null;
  loading?: boolean;
};

export default function AnalysisCostBanner({ estimate, loading }: AnalysisCostBannerProps) {
  return null;
}

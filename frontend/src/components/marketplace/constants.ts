import type { IconType } from 'react-icons';
import { RiBrainFill, RiBriefcaseFill, RiGroupFill, RiScalesFill, RiHeartPulseFill, RiBankFill, RiSeedlingFill, RiGraduationCapFill, RiCpuFill, RiGlobalFill, RiFolderFill, RiPieChartFill, RiLineChartFill } from 'react-icons/ri';

export const MARKETPLACE_DOMAINS = [
  'Education',
  'Health & Medicine',
  'Agriculture',
  'Economics & Finance',
  'Psychology',
  'Sociology',
  'Environment',
  'Technology',
  'Business',
  'Political Science',
  'Law',
  'Demographics',
] as const;

export const DOMAIN_ICONS: Record<string, IconType> = {
  Education: RiGraduationCapFill,
  'Health & Medicine': RiHeartPulseFill,
  Agriculture: RiSeedlingFill,
  'Economics & Finance': RiLineChartFill,
  Psychology: RiBrainFill,
  Sociology: RiGroupFill,
  Environment: RiGlobalFill,
  Technology: RiCpuFill,
  Business: RiBriefcaseFill,
  'Political Science': RiBankFill,
  Law: RiScalesFill,
  Demographics: RiPieChartFill,
};

export function getDomainIcon(domain: string): IconType {
  return DOMAIN_ICONS[domain] || RiFolderFill;
}

export { DATANEST_DOWNLOAD_BASE, marketplaceDownloadUrl } from '../../lib/marketplaceAnalysis';

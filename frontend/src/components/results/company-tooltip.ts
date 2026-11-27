import type { CompanyResult } from '@/api'

/** Hover text for a company chip or tag: what the company does and its fit score. */
export function companyTooltip(company: CompanyResult): string {
  const score = company.score != null ? `Score ${company.score}` : ''
  return [company.description, score].filter(Boolean).join(' · ')
}

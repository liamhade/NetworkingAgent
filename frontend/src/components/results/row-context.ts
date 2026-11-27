import type { CompanyResult, PersonResult, PinKind, PinMap, StatusKind, StatusMap } from '@/api'

/** Everything a card or row needs from the page: marks, pins and the actions on them. */
export interface RowContext {
  statuses: StatusMap
  pins: PinMap
  pin: (kind: PinKind, key: string, name: string, pinned: boolean) => void
  onToggleStatus: (kind: StatusKind, key: string, active: boolean) => void
  /** Open the message drawer for a person. */
  message: (person: PersonResult, company: CompanyResult) => void
  /** Add or remove a company from the company filter. */
  toggleCompany: (companyId: string) => void
  selectedCompanies: ReadonlySet<string>
  searchId: string | null
  /** A company came back from an on-demand people search; replace it in the results. */
  onCompanyFound: (company: CompanyResult) => void
}

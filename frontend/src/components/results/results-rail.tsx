import { Icon } from '@/components/icon'
import { type CompanyCount, type Filter, STRONG_FIT, type SortId } from '@/utils/job-list'
import { companyTooltip } from './company-tooltip'

const FILTERS: { id: Filter; label: string; icon?: 'users' | 'pin' }[] = [
  { id: 'strong', label: `Strong fit ${STRONG_FIT}+` },
  { id: 'hasPeople', label: 'Has contacts', icon: 'users' },
  { id: 'notApplied', label: 'Not applied' },
  { id: 'pinned', label: 'Pinned', icon: 'pin' },
]

const SORTS: { id: SortId; label: string }[] = [
  { id: 'fit', label: 'Best fit' },
  { id: 'pinned', label: 'Pinned first' },
  { id: 'experience', label: 'Least experience required' },
  { id: 'name', label: 'Company A-Z' },
]

/** Filters, sort and the company multi-select. Rendered inside the page's rail. */
export function ResultsRail({
  filters,
  onToggleFilter,
  sort,
  onSort,
  companies,
  selected,
  onToggleCompany,
}: {
  filters: ReadonlySet<Filter>
  onToggleFilter: (filter: Filter) => void
  sort: SortId
  onSort: (sort: SortId) => void
  companies: CompanyCount[]
  selected: ReadonlySet<string>
  onToggleCompany: (companyId: string) => void
}) {
  return (
    <>
      <div className="toolbar" role="toolbar" aria-label="View options">
        <div className="chips" role="group" aria-label="Filters">
          {FILTERS.map((filter) => (
            <button
              key={filter.id}
              type="button"
              className="chip"
              aria-pressed={filters.has(filter.id)}
              onClick={() => onToggleFilter(filter.id)}
            >
              {filter.icon && <Icon name={filter.icon} />}
              {filter.label}
            </button>
          ))}
        </div>
        <span className="sp" />
        <label className="tb-lab" htmlFor="results-sort">
          Sort
        </label>
        <select
          id="results-sort"
          value={sort}
          onChange={(event) => onSort(event.target.value as SortId)}
        >
          {SORTS.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      {companies.length > 0 && (
        <nav className="index" aria-label="Companies">
          <h2>Companies</h2>
          <ul className="colist">
            {companies.map(({ id, company, jobs }) => (
              <li key={id}>
                <button
                  type="button"
                  aria-pressed={selected.has(id)}
                  title={companyTooltip(company)}
                  onClick={() => onToggleCompany(id)}
                >
                  <span className="nm">{company.name}</span>{' '}
                  <span className="sc num">{jobs}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </>
  )
}

import type { CompanyResult } from '@/api'
import { Icon } from '@/components/icon'

/** Companies the search found that have no matching job, so they are not lost. */
export function CompaniesWithoutJobs({ companies }: { companies: CompanyResult[] }) {
  if (companies.length === 0) return null
  return (
    <section className="nojobs" aria-label="Companies without matching jobs">
      <h2>Companies without matching jobs</h2>
      <ul className="rows card">
        {companies.map((company, index) => (
          <li className="row" key={`${company.key || company.name}-${index}`}>
            {company.url ? (
              <a className="rtitle" href={company.url} target="_blank" rel="noreferrer">
                {company.name}
                <Icon name="ext" />
                <span className="sr"> (opens company page)</span>
              </a>
            ) : (
              <span className="rtitle plain">{company.name}</span>
            )}
            {company.description && <p className="rdesc">{company.description}</p>}
          </li>
        ))}
      </ul>
    </section>
  )
}

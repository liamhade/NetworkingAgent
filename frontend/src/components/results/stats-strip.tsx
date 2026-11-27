import type { Totals } from '@/utils/job-list'

type Kind = 'co' | 'job' | 'per' | 'app' | 'con' | 'pin'

function Stat({ kind, value, label }: { kind: Kind; value: number; label: string }) {
  return (
    <div className={`stat ${kind}`} role="listitem">
      <span className="n num">{value}</span>
      <span className="l">{label}</span>
    </div>
  )
}

export function StatsStrip({ totals }: { totals: Totals }) {
  return (
    <section className="strip" aria-label="Summary">
      <div className="stats" role="list" aria-label="Search totals">
        <Stat kind="job" value={totals.jobs} label="Jobs" />
        <Stat kind="co" value={totals.companies} label="Companies" />
        <Stat kind="per" value={totals.contacts} label="Contacts" />
        <Stat kind="app" value={totals.applied} label="Applied" />
        <Stat kind="con" value={totals.connected} label="Connected" />
        <Stat kind="pin" value={totals.pinned} label="Pinned" />
      </div>
    </section>
  )
}

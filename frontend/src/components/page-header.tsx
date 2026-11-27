interface PageHeaderProps {
  title: string
  /** One short line (or a row of meta items) under the title. */
  subtitle?: React.ReactNode
  /** Keep the subtitle on one line, cutting its last item short instead of wrapping. */
  subtitleOneLine?: boolean
  /** Small trail above the title, e.g. a breadcrumb. */
  crumbs?: React.ReactNode
  /** Right-aligned controls: sort, counts, primary actions. */
  actions?: React.ReactNode
}

/** The one page header every top-level page uses: [crumbs] / title / subtitle, actions at right. */
export function PageHeader({ title, subtitle, subtitleOneLine, crumbs, actions }: PageHeaderProps) {
  return (
    <header className="page-head">
      <div className="page-head-main">
        {crumbs && <div className="crumbs">{crumbs}</div>}
        <h1>{title}</h1>
        {subtitle && <div className={subtitleOneLine ? 'sub one-line' : 'sub'}>{subtitle}</div>}
      </div>
      {actions && <div className="page-head-actions">{actions}</div>}
    </header>
  )
}

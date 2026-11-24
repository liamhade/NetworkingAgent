const timeFormat = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })
const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

export const fullDateFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'full',
  timeStyle: 'short',
})

/** "3:41 PM" for today, "Yesterday, 3:41 PM", otherwise "Nov 3, 3:41 PM". */
export function formatRelativeDate(date: Date, now = new Date()): string {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfYesterday = new Date(startOfToday)
  startOfYesterday.setDate(startOfYesterday.getDate() - 1)
  if (date >= startOfToday) return timeFormat.format(date)
  if (date >= startOfYesterday) return `Yesterday, ${timeFormat.format(date)}`
  return dateTimeFormat.format(date)
}

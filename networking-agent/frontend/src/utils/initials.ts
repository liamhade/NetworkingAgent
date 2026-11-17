/** Avatar initials: first and last word ("Ann Lee" -> "AL"); "?" for an empty name. */
export function initials(name: string): string {
  const parts = name.trim().split(/[\s_]+/).filter(Boolean)
  if (parts.length === 0) return '?'
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

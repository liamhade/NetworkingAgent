/** The schools box is one text field: names separated by semicolons or new lines. */
export function parseSchools(text: string): string[] {
  return text
    .split(/[;\n]/)
    .map((name) => name.trim())
    .filter(Boolean)
}

export function formatSchools(schools: string[] | undefined): string {
  return (schools ?? []).join('; ')
}

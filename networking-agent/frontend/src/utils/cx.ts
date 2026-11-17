/** Join class names, skipping falsy values: `cx('row', pinned && 'pinned')`. */
export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

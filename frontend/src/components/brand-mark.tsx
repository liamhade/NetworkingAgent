/**
 * The Enishi mark (縁, the bond between people): two people joined by one thread.
 * Thread in `--accent`, people in `--text`, so it follows the theme. Source:
 * docs/brand/enishi-mark.svg. Decorative: label the link or heading around it.
 */
export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <svg className="brand-mark" viewBox="0 0 64 64" width={size} height={size} aria-hidden="true">
      <path
        d="M13 41 C 18 23, 30 13, 38 19 C 46 25, 40 39, 31 35 C 23 31, 30 17, 42 21 C 49 23, 50 33, 51 41"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="13" cy="43" r="5" fill="var(--text)" />
      <circle cx="51" cy="43" r="5" fill="var(--text)" />
    </svg>
  )
}

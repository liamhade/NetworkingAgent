/**
 * The page-wide CSS `zoom` (`--ui-zoom` in linen.css). Pointer coordinates and
 * getBoundingClientRect() are in screen pixels; divide by this to get CSS pixels.
 */
export function uiZoom(): number {
  const zoom = parseFloat(getComputedStyle(document.documentElement).zoom)
  return zoom > 0 ? zoom : 1
}

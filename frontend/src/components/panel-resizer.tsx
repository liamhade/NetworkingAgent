import { useRef } from 'react'
import { uiZoom } from '@/utils/ui-zoom'
import type { PanelWidthSpec } from '@/utils/sidebar-width'

interface PanelResizerProps {
  spec: PanelWidthSpec
  width: number
  setWidth: (width: number) => void
  commit: (width: number) => void
  /** Accessible name, e.g. "Resize previous searches". */
  label: string
  /** Id of the panel being resized. */
  controls: string
  className: string
}

/**
 * Drag handle on a left-hand panel's right edge. Arrow keys nudge it, Home / End jump to the
 * limits, double-click resets the width.
 */
export function PanelResizer({
  spec,
  width,
  setWidth,
  commit,
  label,
  controls,
  className,
}: PanelResizerProps) {
  const drag = useRef<{ startX: number; startWidth: number; last: number; zoom: number } | null>(null)

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    drag.current = { startX: event.clientX, startWidth: width, last: width, zoom: uiZoom() }
    document.body.classList.add('resizing')
  }
  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return
    const { startX, startWidth, zoom } = drag.current
    drag.current.last = startWidth + (event.clientX - startX) / zoom
    setWidth(drag.current.last)
  }
  const endDrag = () => {
    if (!drag.current) return
    commit(drag.current.last)
    drag.current = null
    document.body.classList.remove('resizing')
  }
  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 48 : 16
    const next =
      event.key === 'ArrowLeft'
        ? width - step
        : event.key === 'ArrowRight'
          ? width + step
          : event.key === 'Home'
            ? spec.min
            : event.key === 'End'
              ? spec.max
              : null
    if (next === null) return
    event.preventDefault()
    commit(next)
  }

  return (
    <div
      className={className}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-controls={controls}
      aria-valuenow={width}
      aria-valuemin={spec.min}
      aria-valuemax={spec.max}
      tabIndex={0}
      title="Drag to resize · double-click to reset"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onKeyDown={onKeyDown}
      onDoubleClick={() => commit(spec.initial)}
    />
  )
}

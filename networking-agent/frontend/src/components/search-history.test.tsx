import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { SearchSummary } from '@/api'
import { SearchHistory } from '@/components/search-history'

beforeEach(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

const search = (id: string, status: SearchSummary['status']): SearchSummary => ({
  id,
  title: `Title ${id}`,
  created_at: '2026-11-01T10:00:00Z',
  status,
})

describe('SearchHistory status', () => {
  it('marks running and failed searches, not finished ones', () => {
    render(
      <SearchHistory
        searches={[search('a', 'running'), search('b', 'error'), search('c', 'done')]}
        loading={false}
        error={null}
        activeId={null}
        user={null}
        onSelect={() => {}}
        onNewSearch={() => {}}
      />,
    )
    expect(screen.getAllByText('Searching…')).toHaveLength(1)
    expect(screen.getByRole('progressbar', { name: 'Search in progress' })).toBeInTheDocument()
    expect(screen.getAllByText('Failed')).toHaveLength(1)
    expect(screen.getByText('Title c')).toBeInTheDocument()
  })
})

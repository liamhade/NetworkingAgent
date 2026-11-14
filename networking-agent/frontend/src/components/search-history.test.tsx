import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
        onCancel={() => {}}
      />,
    )
    expect(screen.getAllByText('Searching…')).toHaveLength(1)
    expect(screen.getByRole('progressbar', { name: 'Search in progress' })).toBeInTheDocument()
    expect(screen.getAllByText('Failed')).toHaveLength(1)
    expect(screen.getByText('Title c')).toBeInTheDocument()
  })
})

describe('SearchHistory cancel', () => {
  const renderPanel = (searches: SearchSummary[], cancelError: string | null = null) => {
    const onCancel = vi.fn()
    const onSelect = vi.fn()
    render(
      <SearchHistory
        searches={searches}
        loading={false}
        error={null}
        activeId={null}
        user={null}
        onSelect={onSelect}
        onNewSearch={() => {}}
        onCancel={onCancel}
        cancelError={cancelError}
      />,
    )
    return { onCancel, onSelect }
  }

  it('offers Cancel only on running searches and reports which one', async () => {
    const { onCancel, onSelect } = renderPanel([
      search('a', 'running'),
      search('b', 'error'),
      search('c', 'done'),
      search('d', 'cancelled'),
    ])
    expect(screen.getAllByRole('button', { name: /^Cancel search/ })).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Cancel search: Title a' }))
    expect(onCancel).toHaveBeenCalledWith('a')
    expect(onSelect).not.toHaveBeenCalled() // Cancelling does not open the search.
  })

  it('marks cancelled searches', () => {
    renderPanel([search('d', 'cancelled')])
    expect(screen.getByText('Cancelled')).toBeInTheDocument()
    expect(screen.queryByText('Searching…')).not.toBeInTheDocument()
  })

  it('shows why a cancel failed', () => {
    renderPanel([], 'That search is not running.')
    expect(screen.getByRole('alert')).toHaveTextContent('That search is not running.')
  })
})

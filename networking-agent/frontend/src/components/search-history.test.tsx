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
        onDelete={async () => {}}
      />,
    )
    expect(screen.getAllByText('Searching…')).toHaveLength(1)
    expect(screen.getByText('Status: Searching')).toBeInTheDocument()
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
        onDelete={async () => {}}
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

describe('SearchHistory delete', () => {
  const renderPanel = (searches: SearchSummary[], deleteError: string | null = null) => {
    const onDelete = vi.fn().mockResolvedValue(undefined)
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
        onCancel={() => {}}
        onDelete={onDelete}
        deleteError={deleteError}
      />,
    )
    return { onDelete, onSelect }
  }

  it('offers Delete on every search except running ones', () => {
    renderPanel([
      search('a', 'running'),
      search('b', 'error'),
      search('c', 'done'),
      search('d', 'cancelled'),
    ])
    expect(screen.getAllByRole('button', { name: /^Delete search/ })).toHaveLength(3)
    expect(screen.queryByRole('button', { name: 'Delete search: Title a' })).not.toBeInTheDocument()
  })

  it('asks for confirmation, and Keep deletes nothing', async () => {
    const { onDelete, onSelect } = renderPanel([search('b', 'error')])
    await userEvent.click(screen.getByRole('button', { name: 'Delete search: Title b' }))
    expect(onDelete).not.toHaveBeenCalled()
    expect(screen.getByText('Delete this search?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Keep' }))
    expect(screen.queryByText('Delete this search?')).not.toBeInTheDocument()
    expect(onDelete).not.toHaveBeenCalled()
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('deletes the confirmed search by id', async () => {
    const { onDelete } = renderPanel([search('b', 'error'), search('c', 'done')])
    await userEvent.click(screen.getByRole('button', { name: 'Delete search: Title c' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete search: Title c' }))
    expect(onDelete).toHaveBeenCalledWith('c')
    expect(screen.queryByText('Delete this search?')).not.toBeInTheDocument()
  })

  it('shows why a delete failed', () => {
    renderPanel([], 'That search is still running. Cancel it before deleting.')
    expect(screen.getByRole('alert')).toHaveTextContent('still running')
  })
})

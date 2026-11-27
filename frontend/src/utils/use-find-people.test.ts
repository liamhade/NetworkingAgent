import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompanyResult } from '@/api'
import { useFindPeople } from '@/utils/use-find-people'

// A plain function, not vi.fn(): vitest's mock bookkeeping leaves rejected results unhandled.
const api = vi.hoisted(() => ({ impl: (() => undefined) as (...args: unknown[]) => unknown }))
vi.mock('@/api', () => ({ findPeople: (...args: unknown[]) => api.impl(...args) }))

const calls = vi.fn()
function respondWith(make: () => Promise<CompanyResult>) {
  api.impl = (...args) => {
    calls(...args)
    return make()
  }
}
const acme = { name: 'Acme' } as CompanyResult

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function card(searchId: string, companyKey: string, jobKey: string, onFound = vi.fn()) {
  return renderHook(() => useFindPeople({ searchId, companyKey, jobKey, onFound }))
}

describe('useFindPeople', () => {
  beforeEach(() => calls.mockReset())

  it('runs one search for two cards of the same company, and both show loading', async () => {
    const pending = deferred<CompanyResult>()
    respondWith(() => pending.promise)
    const first = card('s1', 'company:acme', 'job:a')
    const second = card('s1', 'company:acme', 'job:b')

    let started!: Promise<void>
    act(() => {
      started = first.result.current.run()
    })
    act(() => {
      void second.result.current.run()
    })

    expect(calls).toHaveBeenCalledTimes(1)
    expect(first.result.current.loading).toBe(true)
    expect(second.result.current.loading).toBe(true)

    await act(async () => {
      pending.resolve(acme)
      await started
    })
    expect(first.result.current.loading).toBe(false)
    expect(second.result.current.loading).toBe(false)
  })

  it('searches different companies in parallel', () => {
    const pending = deferred<CompanyResult>()
    respondWith(() => pending.promise)
    const one = card('s2', 'company:one', 'job:a')
    const two = card('s2', 'company:two', 'job:b')
    act(() => {
      void one.result.current.run()
      void two.result.current.run()
    })
    expect(calls).toHaveBeenCalledTimes(2)
    pending.resolve(acme)
  })

  it('shares a failure with every card of the company', async () => {
    respondWith(() => Promise.reject(new Error('boom')))
    const first = card('s3', 'company:acme', 'job:a')
    const second = card('s3', 'company:acme', 'job:b')
    await act(async () => {
      await first.result.current.run()
    })
    expect(second.result.current.error).toBe('boom')
    expect(second.result.current.loading).toBe(false)
  })

  it('hands the result to the card that started the search', async () => {
    respondWith(() => Promise.resolve(acme))
    const onFound = vi.fn()
    const first = card('s4', 'company:acme', 'job:a', onFound)
    await act(async () => {
      await first.result.current.run()
    })
    expect(onFound).toHaveBeenCalledWith(acme)
  })
})

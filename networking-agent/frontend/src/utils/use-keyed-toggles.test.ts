import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PinKind, PinMap } from '@/api'
import { useKeyedToggles } from '@/utils/use-keyed-toggles'

const EMPTY: PinMap = { company: {}, job: {}, person: {} }
const FAIL = 'Could not save that pin.'

/** A promise plus handles to settle it from the test. */
function deferred() {
  let resolve!: () => void
  let reject!: (error: Error) => void
  const promise = new Promise<void>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function setup(save: (kind: PinKind, key: string, on: boolean) => Promise<void>) {
  return renderHook(() => useKeyedToggles<PinKind>(EMPTY, save, FAIL))
}

describe('useKeyedToggles', () => {
  beforeEach(() => {
    // Failed saves are logged; keep test output quiet.
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('starts from the empty map with no error', () => {
    const { result } = setup(vi.fn())
    expect(result.current.map).toEqual(EMPTY)
    expect(result.current.error).toBeNull()
  })

  it('load replaces the map, filling missing kinds, and clears the error', () => {
    const { result } = setup(vi.fn())
    act(() => result.current.setError('old error'))
    act(() => result.current.load({ job: { 'job:a': true } }))
    expect(result.current.map).toEqual({ company: {}, job: { 'job:a': true }, person: {} })
    expect(result.current.error).toBeNull()
  })

  it('applies a toggle optimistically, before the save resolves, and keeps it on success', async () => {
    const pending = deferred()
    const save = vi.fn(() => pending.promise)
    const { result } = setup(save)

    let done!: Promise<void>
    act(() => {
      done = result.current.toggle('company', 'company:acme', true)
    })
    expect(save).toHaveBeenCalledWith('company', 'company:acme', true)
    expect(result.current.map.company['company:acme']).toBe(true)

    await act(async () => {
      pending.resolve()
      await done
    })
    expect(result.current.map.company['company:acme']).toBe(true)
    expect(result.current.error).toBeNull()
  })

  it('only touches the toggled kind and key', async () => {
    const { result } = setup(vi.fn(async () => {}))
    act(() => result.current.load({ job: { 'job:a': true }, person: { 'person:a': true } }))
    await act(() => result.current.toggle('job', 'job:b', true))
    expect(result.current.map).toEqual({
      company: {},
      job: { 'job:a': true, 'job:b': true },
      person: { 'person:a': true },
    })
  })

  it('rolls back and reports the error when the save fails', async () => {
    const save = vi.fn(async () => {
      throw new Error('500')
    })
    const { result } = setup(save)
    act(() => result.current.load({ job: { 'job:a': true } }))

    await act(() => result.current.toggle('job', 'job:a', false))
    expect(result.current.map.job['job:a']).toBe(true)
    expect(result.current.error).toBe(FAIL)
    expect(console.error).toHaveBeenCalled()

    // Rolling back a never-set key restores "unpinned".
    await act(() => result.current.toggle('person', 'person:x', true))
    expect(result.current.map.person['person:x']).toBe(false)
  })

  it('a later successful save clears the error', async () => {
    const save = vi
      .fn<(kind: PinKind, key: string, on: boolean) => Promise<void>>()
      .mockRejectedValueOnce(new Error('500'))
      .mockResolvedValueOnce(undefined)
    const { result } = setup(save)

    await act(() => result.current.toggle('job', 'job:a', true))
    expect(result.current.error).toBe(FAIL)
    await act(() => result.current.toggle('job', 'job:a', true))
    expect(result.current.error).toBeNull()
    expect(result.current.map.job['job:a']).toBe(true)
  })

  it('a stale failure does not roll back a newer change to the same key', async () => {
    const first = deferred()
    const second = deferred()
    const save = vi
      .fn<(kind: PinKind, key: string, on: boolean) => Promise<void>>()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const { result } = setup(save)

    let firstDone!: Promise<void>
    let secondDone!: Promise<void>
    act(() => {
      firstDone = result.current.toggle('job', 'job:a', true)
    })
    act(() => {
      secondDone = result.current.toggle('job', 'job:a', false)
    })
    expect(result.current.map.job['job:a']).toBe(false)

    await act(async () => {
      first.reject(new Error('stale'))
      await firstDone
    })
    // The newer "unpin" stands and no error is shown for the superseded request.
    expect(result.current.map.job['job:a']).toBe(false)
    expect(result.current.error).toBeNull()

    await act(async () => {
      second.resolve()
      await secondDone
    })
    expect(result.current.map.job['job:a']).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('a failure of the latest change rolls back to the value before it', async () => {
    const first = deferred()
    const second = deferred()
    const save = vi
      .fn<(kind: PinKind, key: string, on: boolean) => Promise<void>>()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const { result } = setup(save)

    let firstDone!: Promise<void>
    let secondDone!: Promise<void>
    act(() => {
      firstDone = result.current.toggle('job', 'job:a', true)
    })
    act(() => {
      secondDone = result.current.toggle('job', 'job:a', false)
    })
    await act(async () => {
      first.resolve()
      second.reject(new Error('500'))
      await Promise.all([firstDone, secondDone])
    })
    expect(result.current.map.job['job:a']).toBe(true)
    expect(result.current.error).toBe(FAIL)
  })
})

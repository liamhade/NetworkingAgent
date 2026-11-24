import { describe, expect, it } from 'vitest'
import { job } from '@/test/fixtures'
import { countStatus } from '@/utils/count-status'

describe('countStatus', () => {
  const items = [job('A', 0), job('B', 1), job('C', 2)]

  it('counts entities whose status is on', () => {
    expect(countStatus(items, { 'job:a': true, 'job:c': true })).toEqual({ active: 2, total: 3 })
  })

  it('treats false and missing statuses as off', () => {
    expect(countStatus(items, { 'job:a': false })).toEqual({ active: 0, total: 3 })
  })

  it('ignores statuses for entities that are not listed', () => {
    expect(countStatus(items, { 'job:a': true, 'job:x': true, 'job:y': true })).toEqual({
      active: 1,
      total: 3,
    })
  })

  it('handles an empty list', () => {
    expect(countStatus([], { 'job:a': true })).toEqual({ active: 0, total: 0 })
  })
})

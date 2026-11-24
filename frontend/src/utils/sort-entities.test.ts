import { describe, expect, it } from 'vitest'
import type { EntityKind } from '@/api'
import { company, emptyPins, emptyStatuses, job, person } from '@/test/fixtures'
import { DEFAULT_SORT, SORT_OPTIONS, sortEntities, type SortContext } from '@/utils/sort-entities'

const KINDS = Object.keys(SORT_OPTIONS) as EntityKind[]

const ctx = (overrides: Partial<SortContext> = {}): SortContext => ({
  statuses: emptyStatuses(),
  pins: emptyPins(),
  ...overrides,
})

const keys = (items: readonly { key: string }[]) => items.map((item) => item.key)

describe('SORT_OPTIONS', () => {
  it.each(KINDS)('%s option ids are unique', (kind) => {
    const ids = SORT_OPTIONS[kind].map((option) => option.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it.each(KINDS)('%s starts with "Most recent" then "Pinned first"', (kind) => {
    const [first, second] = SORT_OPTIONS[kind]
    expect(first).toMatchObject({ id: DEFAULT_SORT, label: 'Most recent' })
    expect(second).toMatchObject({ id: 'pinned', label: 'Pinned first' })
  })

  it('lists the expected options per page', () => {
    const ids = (kind: EntityKind) => SORT_OPTIONS[kind].map((option) => option.id)
    expect(ids('companies')).toEqual(['recent', 'pinned', 'name', 'jobs', 'contacts'])
    expect(ids('jobs')).toEqual(['recent', 'pinned', 'applied', 'not-applied', 'title', 'company'])
    expect(ids('people')).toEqual([
      'recent',
      'pinned',
      'connected',
      'not-connected',
      'name',
      'company',
    ])
  })
})

describe('sortEntities', () => {
  it('"recent" orders by last_seen, newest first', () => {
    const items = [company('Old', 5), company('New', 0), company('Mid', 2)]
    expect(keys(sortEntities('companies', items, 'recent', ctx()))).toEqual([
      'company:new',
      'company:mid',
      'company:old',
    ])
  })

  it('falls back to the default sort for an unknown id', () => {
    const items = [company('Old', 5), company('New', 0)]
    expect(keys(sortEntities('companies', items, 'nope', ctx()))).toEqual([
      'company:new',
      'company:old',
    ])
  })

  it('returns a new array and does not mutate the input', () => {
    const items = [company('B', 1), company('A', 0)]
    const before = [...items]
    const sorted = sortEntities('companies', items, 'name', ctx())
    expect(sorted).not.toBe(items)
    expect(items).toEqual(before)
    expect(keys(sorted)).toEqual(['company:a', 'company:b'])
  })

  it('handles an empty list', () => {
    expect(sortEntities('jobs', [], 'pinned', ctx())).toEqual([])
  })

  describe('"Pinned first"', () => {
    it('companies: pinned first, each group keeps incoming (recency) order', () => {
      // Server order: most recent first.
      const items = [company('A', 0), company('B', 1), company('C', 2), company('D', 3)]
      const pins = { ...emptyPins(), company: { 'company:b': true, 'company:d': true } }
      expect(keys(sortEntities('companies', items, 'pinned', ctx({ pins })))).toEqual([
        'company:b',
        'company:d',
        'company:a',
        'company:c',
      ])
    })

    it('jobs: reads only the job slice of the pin map', () => {
      const items = [job('A', 0), job('B', 1), job('C', 2)]
      const pins = {
        company: { 'job:a': true }, // wrong kind: ignored
        job: { 'job:c': true },
        person: { 'job:b': true }, // wrong kind: ignored
      }
      expect(keys(sortEntities('jobs', items, 'pinned', ctx({ pins })))).toEqual([
        'job:c',
        'job:a',
        'job:b',
      ])
    })

    it('people: pinned first', () => {
      const items = [person('A', 0), person('B', 1), person('C', 2)]
      const pins = { ...emptyPins(), person: { 'person:c': true, 'person:b': true } }
      expect(keys(sortEntities('people', items, 'pinned', ctx({ pins })))).toEqual([
        'person:b',
        'person:c',
        'person:a',
      ])
    })

    it('treats pinned: false and missing pins as unpinned', () => {
      const items = [job('A', 0), job('B', 1), job('C', 2)]
      const pins = { ...emptyPins(), job: { 'job:a': false, 'job:c': true } }
      expect(keys(sortEntities('jobs', items, 'pinned', ctx({ pins })))).toEqual([
        'job:c',
        'job:a',
        'job:b',
      ])
    })

    it('keeps incoming order when nothing (or everything) is pinned', () => {
      const items = [job('B', 0), job('A', 1), job('C', 2)]
      expect(keys(sortEntities('jobs', items, 'pinned', ctx()))).toEqual(keys(items))
      const all = { ...emptyPins(), job: { 'job:a': true, 'job:b': true, 'job:c': true } }
      expect(keys(sortEntities('jobs', items, 'pinned', ctx({ pins: all })))).toEqual(keys(items))
    })

    it('ignores pins for keys that are not listed', () => {
      const items = [company('A', 0), company('B', 1)]
      const pins = { ...emptyPins(), company: { 'company:zzz': true } }
      expect(keys(sortEntities('companies', items, 'pinned', ctx({ pins })))).toEqual(keys(items))
    })
  })

  describe('status sorts', () => {
    const statuses = { job: { 'job:b': true, 'job:c': false }, person: { 'person:b': true } }

    it('"applied" puts applied jobs first, stable', () => {
      const items = [job('A', 0), job('B', 1), job('C', 2)]
      expect(keys(sortEntities('jobs', items, 'applied', ctx({ statuses })))).toEqual([
        'job:b',
        'job:a',
        'job:c',
      ])
    })

    it('"not-applied" puts unapplied (incl. missing) jobs first, stable', () => {
      const items = [job('B', 0), job('A', 1), job('C', 2)]
      expect(keys(sortEntities('jobs', items, 'not-applied', ctx({ statuses })))).toEqual([
        'job:a',
        'job:c',
        'job:b',
      ])
    })

    it('"connected" / "not-connected" use the person slice', () => {
      const items = [person('A', 0), person('B', 1)]
      expect(keys(sortEntities('people', items, 'connected', ctx({ statuses })))).toEqual([
        'person:b',
        'person:a',
      ])
      expect(keys(sortEntities('people', items, 'not-connected', ctx({ statuses })))).toEqual([
        'person:a',
        'person:b',
      ])
    })
  })

  describe('text sorts', () => {
    it('are case/accent-insensitive and numeric-aware', () => {
      const items = [
        company('beta', 0),
        company('Émile', 1),
        company('Alpha', 2),
        company('item 10', 3),
        company('item 9', 4),
      ]
      expect(sortEntities('companies', items, 'name', ctx()).map((c) => c.name)).toEqual([
        'Alpha',
        'beta',
        'Émile',
        'item 9',
        'item 10',
      ])
    })

    it('put blank values last, keeping their order', () => {
      const items = [
        job('X', 0, { company: '' }),
        job('Y', 1, { company: 'Zeta' }),
        job('Z', 2, { company: '  ' }),
        job('W', 3, { company: 'Acme' }),
      ]
      expect(keys(sortEntities('jobs', items, 'company', ctx()))).toEqual([
        'job:w',
        'job:y',
        'job:x',
        'job:z',
      ])
    })

    it('"title" sorts jobs; "name" / "company" sort people', () => {
      const jobs = [job('Zed', 0), job('alpha', 1)]
      expect(sortEntities('jobs', jobs, 'title', ctx()).map((j) => j.title)).toEqual([
        'alpha',
        'Zed',
      ])
      const people = [person('Bob', 0, { company: 'B' }), person('Al', 1, { company: 'A' })]
      expect(sortEntities('people', people, 'name', ctx()).map((p) => p.name)).toEqual([
        'Al',
        'Bob',
      ])
      expect(sortEntities('people', people, 'company', ctx()).map((p) => p.name)).toEqual([
        'Al',
        'Bob',
      ])
    })
  })

  describe('number sorts', () => {
    it('"jobs" and "contacts" sort largest first, ties stable', () => {
      const items = [
        company('A', 0, { job_count: 1, person_count: 5 }),
        company('B', 1, { job_count: 3, person_count: 5 }),
        company('C', 2, { job_count: 1, person_count: 9 }),
      ]
      expect(keys(sortEntities('companies', items, 'jobs', ctx()))).toEqual([
        'company:b',
        'company:a',
        'company:c',
      ])
      expect(keys(sortEntities('companies', items, 'contacts', ctx()))).toEqual([
        'company:c',
        'company:a',
        'company:b',
      ])
    })
  })
})

import { describe, expect, it } from 'vitest'
import type { CompanyResult, JobResult } from '@/api'
import { minYears, rankJobs } from '@/utils/job-list'

const job = (title: string, extra: Partial<JobResult> = {}): JobResult => ({
  title,
  url: '',
  location: '',
  salary: '',
  alignment: '',
  key: `job:${title}`,
  ...extra,
})

const company = (name: string, jobs: JobResult[]): CompanyResult => ({
  name,
  url: '',
  description: '',
  alignment: '',
  jobs,
  people: [],
})

describe('minYears', () => {
  it.each([
    ['3+ years', 3],
    ['3-5 years', 3],
    ['0-2 years', 0],
    ['at least 2.5 yrs', 2.5],
    ['entry level', null],
    ['', null],
    [null, null],
    [undefined, null],
  ])('reads %j as %j', (text, expected) => {
    expect(minYears(text)).toBe(expected)
  })
})

describe('rankJobs', () => {
  it('puts ranked jobs first in rank order, then unranked ones by score', () => {
    const entries = rankJobs([
      company('A', [job('a-unranked', { score: 99 }), job('a-two', { rank: 2 })]),
      company('B', [job('b-one', { rank: 1 }), job('b-unranked', { score: 10 })]),
    ])
    expect(entries.map((e) => e.job.title)).toEqual(['b-one', 'a-two', 'a-unranked', 'b-unranked'])
    expect(entries.map((e) => e.position)).toEqual([1, 2, 3, 4])
  })

  it('gives every job a unique id even when keys repeat', () => {
    const entries = rankJobs([company('A', [job('x'), job('x')])])
    expect(new Set(entries.map((e) => e.id)).size).toBe(2)
  })
})

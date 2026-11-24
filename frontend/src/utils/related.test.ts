import { describe, expect, it } from 'vitest'
import { entityDomId, groupByCompany, jobRelation, personRelation } from '@/utils/related'
import { job, person } from '@/test/fixtures'

describe('groupByCompany', () => {
  it('groups by company key and keeps list order', () => {
    const a = job('A', 0, { company_key: 'company:x' })
    const b = job('B', 1, { company_key: 'company:y' })
    const c = job('C', 2, { company_key: 'company:x' })
    const groups = groupByCompany([a, b, c])
    expect(groups.get('company:x')).toEqual([a, c])
    expect(groups.get('company:y')).toEqual([b])
    expect(groups.get('company:z')).toBeUndefined()
  })

  it('handles a list that has not loaded', () => {
    expect(groupByCompany(null).size).toBe(0)
  })
})

describe('relations', () => {
  it('points jobs at the jobs page and people at the people page', () => {
    expect(jobRelation(job('Engineer', 0))).toMatchObject({ kind: 'jobs', key: 'job:engineer' })
    expect(personRelation(person('Ann', 0))).toMatchObject({ kind: 'people', label: 'Ann' })
  })

  it('builds a DOM id from the key', () => {
    expect(entityDomId('job:x')).toBe('entity-job:x')
  })
})

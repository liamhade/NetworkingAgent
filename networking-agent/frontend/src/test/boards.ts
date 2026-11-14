import type { BoardInfo } from '@/api'

/** A trimmed board list shaped like `GET /api/search/boards`. */
export const BOARDS: BoardInfo[] = [
  {
    id: 'builtin_nyc',
    label: 'Built In NYC',
    description: 'New York City tech companies and their jobs.',
    available: true,
    unavailable_reason: '',
    default: { enabled: true, max_jobs: 45 },
    min_jobs: 1,
    max_jobs: 100,
  },
  {
    id: 'greenhouse',
    label: 'Greenhouse',
    description: 'Employer career boards on Greenhouse, found through Google.',
    available: true,
    unavailable_reason: '',
    default: { enabled: true, max_jobs: 8 },
    min_jobs: 1,
    max_jobs: 40,
  },
  {
    id: 'usajobs',
    label: 'USAJOBS',
    description: 'US federal government jobs.',
    available: false,
    unavailable_reason: 'Needs an API key (USAJOBS_API_KEY and USAJOBS_EMAIL)',
    default: { enabled: true, max_jobs: 20 },
    min_jobs: 1,
    max_jobs: 100,
  },
]

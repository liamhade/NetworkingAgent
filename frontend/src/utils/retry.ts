const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason)
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer)
        reject(signal.reason)
      },
      { once: true },
    )
  })

/**
 * Call `request` until it succeeds, backing off between attempts
 * (0.5s, 1s, 2s, 4s, 4s, ... ≈ 30s total by default). Useful on page load,
 * when the backend may still be starting or reloading.
 */
export async function withRetry<T>(
  request: (signal?: AbortSignal) => Promise<T>,
  signal?: AbortSignal,
  { attempts = 9, baseMs = 500, maxMs = 4000 } = {},
): Promise<T> {
  let lastError: unknown
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await request(signal)
    } catch (caught) {
      if (signal?.aborted) throw caught
      lastError = caught
      if (attempt < attempts - 1) await sleep(Math.min(baseMs * 2 ** attempt, maxMs), signal)
    }
  }
  throw lastError
}

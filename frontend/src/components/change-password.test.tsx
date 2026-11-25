import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChangePasswordDialog } from '@/components/change-password'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => vi.unstubAllGlobals())

async function fill(current: string, next: string, repeat = next) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Current password'), current)
  await user.type(screen.getByLabelText('New password'), next)
  await user.type(screen.getByLabelText('Repeat new password'), repeat)
  return user
}

describe('ChangePasswordDialog', () => {
  it('needs matching passwords of 8+ characters', async () => {
    render(<ChangePasswordDialog onClose={() => {}} />)
    const submit = screen.getByRole('button', { name: 'Change password' })
    await fill('old-password', 'short')
    expect(submit).toHaveProperty('disabled', true)
    await userEvent.type(screen.getByLabelText('New password'), '-but-longer')
    expect(screen.getByText(/don.t match/)).toBeTruthy()
  })

  it('sends both passwords and confirms', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    render(<ChangePasswordDialog onClose={() => {}} />)
    const user = await fill('old-password', 'new-password')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText(/Your password is changed/)).toBeTruthy()
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/account/password')
    expect(JSON.parse(String(init.body))).toEqual({
      current_password: 'old-password',
      new_password: 'new-password',
    })
  })

  it('shows the server error and closes on Escape', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => json({ detail: 'Your current password is wrong.' }, 400)),
    )
    const onClose = vi.fn()
    render(<ChangePasswordDialog onClose={onClose} />)
    const user = await fill('bad', 'new-password')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect((await screen.findByRole('alert')).textContent).toContain('current password is wrong')
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })
})

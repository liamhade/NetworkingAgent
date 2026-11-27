import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AboutPage } from '@/pages/about'

describe('AboutPage', () => {
  it('shows the overview and opens each FAQ answer on click', async () => {
    const user = userEvent.setup()
    render(<AboutPage />)
    expect(screen.getByRole('heading', { level: 1, name: 'About Enishi' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Overview' })).toBeInTheDocument()

    for (const question of [
      'How do I use this site?',
      'What does "enishi" mean?',
      'What do you do with my data?',
    ]) {
      const summary = screen.getByText(question)
      const details = summary.closest('details')!
      expect(details).not.toHaveAttribute('open')
      await user.click(summary)
      expect(details).toHaveAttribute('open')
    }
  })
})

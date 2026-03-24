import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PRInput from '../../components/PRInput'

const VALID_URL = 'https://github.com/owner/repo/pull/42'
const INVALID_URL = 'https://github.com/owner/repo'

function renderPR({ prUrl = '', disabled = false, onSubmit = vi.fn() } = {}) {
  const setPrUrl = vi.fn()
  render(
    <PRInput prUrl={prUrl} setPrUrl={setPrUrl} disabled={disabled} onSubmit={onSubmit} />,
  )
  return { onSubmit, setPrUrl }
}

describe('PRInput', () => {
  it('disables Analyze button when prUrl is empty', () => {
    renderPR({ prUrl: '' })
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('disables button and shows validation message for invalid URL', () => {
    renderPR({ prUrl: INVALID_URL })
    expect(screen.getByRole('button')).toBeDisabled()
    expect(
      screen.getByText(/Enter a valid GitHub PR URL ending in \/pull\/123/i),
    ).toBeInTheDocument()
  })

  it('enables button for valid PR URL', () => {
    renderPR({ prUrl: VALID_URL })
    expect(screen.getByRole('button')).not.toBeDisabled()
  })

  it('disables button when disabled prop is true (even with valid URL)', () => {
    renderPR({ prUrl: VALID_URL, disabled: true })
    expect(screen.getByRole('button')).toBeDisabled()
    expect(screen.getByRole('button')).toHaveTextContent('Analyzing...')
  })

  it('calls onSubmit when clicking with a valid URL', async () => {
    const onSubmit = vi.fn()
    renderPR({ prUrl: VALID_URL, onSubmit })
    await userEvent.click(screen.getByRole('button'))
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('does not call onSubmit when clicking with an invalid URL', async () => {
    const onSubmit = vi.fn()
    renderPR({ prUrl: INVALID_URL, onSubmit })
    await userEvent.click(screen.getByRole('button'))
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('does not show validation message when prUrl is empty', () => {
    renderPR({ prUrl: '' })
    expect(
      screen.queryByText(/Enter a valid GitHub PR URL/i),
    ).not.toBeInTheDocument()
  })
})

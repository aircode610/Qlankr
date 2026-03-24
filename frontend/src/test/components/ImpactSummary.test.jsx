import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ImpactSummary from '../../components/ImpactSummary'

const MOCK_RESULT = {
  pr_title: 'Refactor auth token refresh flow',
  pr_url: 'https://github.com/owner/repo/pull/42',
  pr_summary: 'This PR refactors token handling.',
  agent_steps: 5,
  affected_components: [
    {
      component: 'Authentication',
      confidence: 'high',
      files_changed: ['src/auth/tokens.py'],
      impact_summary: 'Token paths were changed.',
      risks: ['Refresh token may fail'],
      test_suggestions: { skip: [], run: ['Login regression'], deeper: [] },
    },
    {
      component: 'Session Management',
      confidence: 'medium',
      files_changed: ['src/session/store.py'],
      impact_summary: 'Sessions now depend on new token parsing.',
      risks: [],
      test_suggestions: { skip: [], run: [], deeper: [] },
    },
  ],
}

describe('ImpactSummary', () => {
  it('shows empty state when result is null', () => {
    render(<ImpactSummary result={null} onCopyMarkdown={vi.fn()} />)
    expect(
      screen.getByText('Run PR analysis to see results here.'),
    ).toBeInTheDocument()
  })

  it('disables copy button when result is null', () => {
    render(<ImpactSummary result={null} onCopyMarkdown={vi.fn()} />)
    expect(screen.getByRole('button', { name: /copy report/i })).toBeDisabled()
  })

  it('enables copy button when result is present', () => {
    render(<ImpactSummary result={MOCK_RESULT} onCopyMarkdown={vi.fn()} />)
    expect(screen.getByRole('button', { name: /copy report/i })).not.toBeDisabled()
  })

  it('renders pr_title', () => {
    render(<ImpactSummary result={MOCK_RESULT} onCopyMarkdown={vi.fn()} />)
    expect(
      screen.getByText('Refactor auth token refresh flow'),
    ).toBeInTheDocument()
  })

  it('renders both affected component names', () => {
    render(<ImpactSummary result={MOCK_RESULT} onCopyMarkdown={vi.fn()} />)
    expect(screen.getByText('Authentication')).toBeInTheDocument()
    expect(screen.getByText('Session Management')).toBeInTheDocument()
  })

  it('calls onCopyMarkdown when copy button is clicked', async () => {
    const onCopyMarkdown = vi.fn()
    render(<ImpactSummary result={MOCK_RESULT} onCopyMarkdown={onCopyMarkdown} />)
    await userEvent.click(screen.getByRole('button', { name: /copy report/i }))
    expect(onCopyMarkdown).toHaveBeenCalledTimes(1)
  })
})

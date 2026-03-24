import { render, screen } from '@testing-library/react'
import ComponentCard from '../../components/ComponentCard'

const FULL_ITEM = {
  component: 'Authentication',
  confidence: 'high',
  files_changed: ['src/auth/tokens.py', 'src/auth/middleware.py'],
  impact_summary: 'Token paths were changed.',
  risks: ['Refresh token rotation may reject valid sessions', 'Middleware order may bypass auth'],
  test_suggestions: {
    skip: ['Unrelated UI smoke tests'],
    run: ['Login/logout regression'],
    deeper: ['Expired token race conditions'],
  },
}

describe('ComponentCard', () => {
  it('renders component name and confidence badge', () => {
    render(<ComponentCard item={FULL_ITEM} />)
    expect(screen.getByText('Authentication')).toBeInTheDocument()
    expect(screen.getByText('high')).toBeInTheDocument()
  })

  it('renders files_changed as list items', () => {
    render(<ComponentCard item={FULL_ITEM} />)
    expect(screen.getByText('src/auth/tokens.py')).toBeInTheDocument()
    expect(screen.getByText('src/auth/middleware.py')).toBeInTheDocument()
  })

  it('renders risks as badges', () => {
    render(<ComponentCard item={FULL_ITEM} />)
    expect(
      screen.getByText('Refresh token rotation may reject valid sessions'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Middleware order may bypass auth'),
    ).toBeInTheDocument()
  })

  it('renders Skip, Run, Deeper test suggestion sections', () => {
    render(<ComponentCard item={FULL_ITEM} />)
    expect(screen.getByText('Skip')).toBeInTheDocument()
    expect(screen.getByText('Run')).toBeInTheDocument()
    expect(screen.getByText('Deeper')).toBeInTheDocument()
    expect(screen.getByText('Unrelated UI smoke tests')).toBeInTheDocument()
    expect(screen.getByText('Login/logout regression')).toBeInTheDocument()
    expect(screen.getByText('Expired token race conditions')).toBeInTheDocument()
  })

  it('handles empty arrays without crashing', () => {
    const emptyItem = {
      component: 'Empty',
      confidence: 'low',
      files_changed: [],
      impact_summary: 'Nothing changed.',
      risks: [],
      test_suggestions: { skip: [], run: [], deeper: [] },
    }
    render(<ComponentCard item={emptyItem} />)
    expect(screen.getByText('Empty')).toBeInTheDocument()
    expect(screen.getByText('Nothing changed.')).toBeInTheDocument()
  })
})

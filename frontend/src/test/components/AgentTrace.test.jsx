import { render, screen } from '@testing-library/react'
import AgentTrace from '../../components/AgentTrace'

describe('AgentTrace', () => {
  it('shows empty state when steps is empty', () => {
    render(<AgentTrace steps={[]} loading={false} />)
    expect(screen.getByText('No agent steps yet.')).toBeInTheDocument()
  })

  it('renders each step tool and summary', () => {
    const steps = [
      { tool: 'get_pull_request', summary: 'Reading PR metadata...' },
      { tool: 'impact', summary: 'Checking blast radius...' },
    ]
    render(<AgentTrace steps={steps} loading={false} />)
    // Tool name is in a <span>, summary is a sibling text node inside <li>
    expect(screen.getByText('get_pull_request')).toBeInTheDocument()
    expect(screen.getByText('impact')).toBeInTheDocument()
    const list = screen.getByRole('list')
    expect(list).toHaveTextContent('Reading PR metadata...')
    expect(list).toHaveTextContent('Checking blast radius...')
  })

  it('shows Running... indicator when loading is true', () => {
    render(<AgentTrace steps={[]} loading={true} />)
    expect(screen.getByText('Running...')).toBeInTheDocument()
  })

  it('hides Running... indicator when loading is false', () => {
    render(<AgentTrace steps={[]} loading={false} />)
    expect(screen.queryByText('Running...')).not.toBeInTheDocument()
  })
})

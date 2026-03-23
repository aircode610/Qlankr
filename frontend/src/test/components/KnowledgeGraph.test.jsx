import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import KnowledgeGraph from '../../components/KnowledgeGraph'

const SMALL_GRAPH = {
  nodes: [
    { id: 'n1', label: 'file1.py', type: 'file', cluster: 'auth' },
    { id: 'n2', label: 'file2.py', type: 'file', cluster: 'api' },
  ],
  edges: [{ source: 'n1', target: 'n2', type: 'CALLS' }],
  clusters: [
    { id: 'auth', label: 'Authentication Cluster', size: 1 },
    { id: 'api', label: 'API Cluster', size: 1 },
  ],
}

describe('KnowledgeGraph', () => {
  it('renders cluster filter buttons for each cluster', () => {
    render(<KnowledgeGraph graphData={SMALL_GRAPH} />)
    expect(screen.getByRole('button', { name: /Authentication Cluster/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /API Cluster/i })).toBeInTheDocument()
  })

  it('SVG has aria-label "Knowledge graph visualization"', () => {
    render(<KnowledgeGraph graphData={SMALL_GRAPH} />)
    expect(
      screen.getByRole('img', { name: 'Knowledge graph visualization' }),
    ).toBeInTheDocument()
  })

  it('switches to text mode and shows "Nodes by cluster"', async () => {
    render(<KnowledgeGraph graphData={SMALL_GRAPH} />)
    await userEvent.click(screen.getByRole('button', { name: /^text$/i }))
    expect(screen.getByText('Nodes by cluster')).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: 'Knowledge graph visualization' })).not.toBeInTheDocument()
  })

  it('clicking a cluster button activates it', async () => {
    render(<KnowledgeGraph graphData={SMALL_GRAPH} />)
    const btn = screen.getByRole('button', { name: /Authentication Cluster/i })
    await userEvent.click(btn)
    expect(btn).toHaveClass('bg-indigo-500/90')
  })

  it('clicking an active cluster button deactivates it', async () => {
    render(<KnowledgeGraph graphData={SMALL_GRAPH} />)
    const btn = screen.getByRole('button', { name: /Authentication Cluster/i })
    await userEvent.click(btn) // activate
    await userEvent.click(btn) // deactivate
    expect(btn).not.toHaveClass('bg-indigo-500/90')
  })

  it('shows amber hint when "Selected only" scope is active without a cluster selected', async () => {
    render(<KnowledgeGraph graphData={SMALL_GRAPH} />)
    await userEvent.click(screen.getByRole('button', { name: /selected only/i }))
    expect(screen.getByText(/Select a cluster above to isolate it/i)).toBeInTheDocument()
  })

  it('renders without crashing when graphData is empty', () => {
    render(<KnowledgeGraph graphData={{ nodes: [], edges: [], clusters: [] }} />)
    expect(screen.getByText('Knowledge graph')).toBeInTheDocument()
  })
})

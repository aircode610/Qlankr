import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RepoInput from '../../components/RepoInput'

function renderRepo({
  repoUrl = '',
  indexing = false,
  indexMessages = [],
  indexedRepo = null,
  onConnect = vi.fn(),
} = {}) {
  render(
    <RepoInput
      repoUrl={repoUrl}
      setRepoUrl={vi.fn()}
      indexing={indexing}
      indexMessages={indexMessages}
      onConnect={onConnect}
      indexedRepo={indexedRepo}
    />,
  )
  return { onConnect }
}

describe('RepoInput', () => {
  it('disables Connect button when repoUrl is empty', () => {
    renderRepo({ repoUrl: '' })
    expect(screen.getByRole('button', { name: /connect/i })).toBeDisabled()
  })

  it('disables button and shows "Indexing..." when indexing', () => {
    renderRepo({ repoUrl: 'https://github.com/owner/repo', indexing: true })
    const btn = screen.getByRole('button', { name: /indexing/i })
    expect(btn).toBeDisabled()
  })

  it('enables Connect button when repoUrl is non-empty and not indexing', () => {
    renderRepo({ repoUrl: 'https://github.com/owner/repo' })
    expect(screen.getByRole('button', { name: /connect/i })).not.toBeDisabled()
  })

  it('calls onConnect when clicking Connect', async () => {
    const onConnect = vi.fn()
    renderRepo({ repoUrl: 'https://github.com/owner/repo', onConnect })
    await userEvent.click(screen.getByRole('button', { name: /connect/i }))
    expect(onConnect).toHaveBeenCalledTimes(1)
  })

  it('shows "No progress events yet." when indexMessages is empty', () => {
    renderRepo()
    expect(screen.getByText('No progress events yet.')).toBeInTheDocument()
  })

  it('renders index progress messages', () => {
    renderRepo({
      indexMessages: [{ stage: 'clone', summary: 'Cloning owner/repo...' }],
    })
    expect(screen.getByText('Cloning owner/repo...')).toBeInTheDocument()
    expect(screen.getByText('[clone]')).toBeInTheDocument()
  })

  it('shows indexed repo summary when indexedRepo is set', () => {
    renderRepo({
      indexedRepo: { repo: 'owner/repo', files: 100, clusters: 5, symbols: 500 },
    })
    expect(screen.getByText(/Indexed owner\/repo/)).toBeInTheDocument()
    expect(screen.getByText(/files: 100/)).toBeInTheDocument()
  })
})

import { buildMarkdownReport, extractOwnerRepo } from '../App'

const MOCK_RESULT = {
  pr_title: 'Fix auth bug',
  pr_url: 'https://github.com/owner/repo/pull/5',
  pr_summary: 'Fixes a critical auth issue.',
  agent_steps: 3,
  affected_components: [
    {
      component: 'Authentication',
      confidence: 'high',
      files_changed: ['src/auth/tokens.py'],
      impact_summary: 'Token paths changed.',
      risks: ['Refresh token may fail'],
      test_suggestions: { skip: [], run: ['Login regression'], deeper: [] },
    },
    {
      component: 'Session Management',
      confidence: 'medium',
      files_changed: ['src/session/store.py'],
      impact_summary: 'Sessions affected.',
      risks: [],
      test_suggestions: { skip: [], run: [], deeper: [] },
    },
  ],
}

describe('extractOwnerRepo', () => {
  it('parses a standard GitHub URL', () => {
    expect(extractOwnerRepo('https://github.com/alice/myrepo')).toEqual({
      owner: 'alice',
      repo: 'myrepo',
    })
  })

  it('strips .git suffix', () => {
    expect(extractOwnerRepo('https://github.com/alice/myrepo.git')).toEqual({
      owner: 'alice',
      repo: 'myrepo',
    })
  })

  it('returns null for a non-URL string', () => {
    expect(extractOwnerRepo('not a url')).toBeNull()
  })

  it('returns null for a URL with only one path segment', () => {
    expect(extractOwnerRepo('https://github.com/alice')).toBeNull()
  })
})

describe('buildMarkdownReport', () => {
  it('returns empty string for null', () => {
    expect(buildMarkdownReport(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(buildMarkdownReport(undefined)).toBe('')
  })

  it('includes pr_title in the output', () => {
    const report = buildMarkdownReport(MOCK_RESULT)
    expect(report).toContain('Fix auth bug')
  })

  it('includes pr_url in the output', () => {
    const report = buildMarkdownReport(MOCK_RESULT)
    expect(report).toContain('https://github.com/owner/repo/pull/5')
  })

  it('includes all affected component names', () => {
    const report = buildMarkdownReport(MOCK_RESULT)
    expect(report).toContain('### Authentication')
    expect(report).toContain('### Session Management')
  })
})

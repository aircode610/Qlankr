import { mockAnalyzePR, mockGetGraph, mockIndexRepo } from '../../mock/mockApi'

describe('mockIndexRepo', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('fires onIndexStep 4 times with correct shape', async () => {
    const onIndexStep = vi.fn()
    const promise = mockIndexRepo('https://github.com/owner/repo', { onIndexStep })
    await vi.advanceTimersByTimeAsync(10000)
    await promise
    expect(onIndexStep).toHaveBeenCalledTimes(4)
    const firstCall = onIndexStep.mock.calls[0][0]
    expect(firstCall).toHaveProperty('stage')
    expect(firstCall).toHaveProperty('summary')
  })

  it('fires onIndexDone with correct shape', async () => {
    const onIndexDone = vi.fn()
    const promise = mockIndexRepo('https://github.com/owner/repo', { onIndexDone })
    await vi.advanceTimersByTimeAsync(10000)
    const result = await promise
    expect(onIndexDone).toHaveBeenCalledTimes(1)
    const payload = onIndexDone.mock.calls[0][0]
    expect(payload).toHaveProperty('repo')
    expect(payload).toHaveProperty('files')
    expect(payload).toHaveProperty('clusters')
    expect(payload).toHaveProperty('symbols')
    expect(result).toEqual(payload)
  })

  it('parses owner/repo from GitHub URL', async () => {
    const onIndexDone = vi.fn()
    const promise = mockIndexRepo('https://github.com/myorg/myapp', { onIndexDone })
    await vi.advanceTimersByTimeAsync(10000)
    await promise
    expect(onIndexDone.mock.calls[0][0].repo).toBe('myorg/myapp')
  })

  it('aborts mid-run when signal is aborted', async () => {
    const controller = new AbortController()
    const onIndexStep = vi.fn()
    const promise = mockIndexRepo('https://github.com/owner/repo', {
      signal: controller.signal,
      onIndexStep,
    })
    // Advance past first step only
    await vi.advanceTimersByTimeAsync(800)
    controller.abort()
    await expect(promise).rejects.toMatchObject({ name: 'AbortError' })
    expect(onIndexStep.mock.calls.length).toBeLessThan(4)
  })
})

describe('mockAnalyzePR', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('fires onAgentStep 5 times', async () => {
    const onAgentStep = vi.fn()
    const promise = mockAnalyzePR('https://github.com/owner/repo/pull/1', { onAgentStep })
    await vi.advanceTimersByTimeAsync(10000)
    await promise
    expect(onAgentStep).toHaveBeenCalledTimes(5)
  })

  it('fires onResult with full result object', async () => {
    const onResult = vi.fn()
    const promise = mockAnalyzePR('https://github.com/owner/repo/pull/1', { onResult })
    await vi.advanceTimersByTimeAsync(10000)
    await promise
    expect(onResult).toHaveBeenCalledTimes(1)
    const result = onResult.mock.calls[0][0]
    expect(result).toHaveProperty('pr_title')
    expect(result).toHaveProperty('pr_url')
    expect(result).toHaveProperty('affected_components')
    expect(result).toHaveProperty('agent_steps')
  })

  it('agent_steps matches step count', async () => {
    const onResult = vi.fn()
    const promise = mockAnalyzePR('https://github.com/owner/repo/pull/1', { onResult })
    await vi.advanceTimersByTimeAsync(10000)
    await promise
    const result = onResult.mock.calls[0][0]
    expect(result.agent_steps).toBe(5)
  })
})

describe('mockGetGraph', () => {
  it('returns a valid graph structure', async () => {
    const graph = await mockGetGraph('myorg', 'myapp')
    expect(graph).toHaveProperty('nodes')
    expect(graph).toHaveProperty('edges')
    expect(graph).toHaveProperty('clusters')
    expect(graph.nodes.length).toBeGreaterThan(0)
    expect(graph.clusters.length).toBeGreaterThan(0)
  })
})

// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { analyzePR, getGraph, indexRepo, isMockSseEnabled } from '../api'

function makeStreamResponse(sseText) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(sseText))
      controller.close()
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

beforeEach(() => {
  global.fetch = vi.fn()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('isMockSseEnabled', () => {
  it('returns false by default in test environment', () => {
    expect(isMockSseEnabled()).toBe(false)
  })
})

describe('indexRepo', () => {
  it('fires onIndexStep for index_step events', async () => {
    const sseBody =
      'event: index_step\ndata: {"stage":"clone","summary":"Cloning..."}\n\n'
    global.fetch = vi.fn().mockResolvedValue(makeStreamResponse(sseBody))

    const onIndexStep = vi.fn()
    await indexRepo('https://github.com/owner/repo', { onIndexStep })
    expect(onIndexStep).toHaveBeenCalledWith({ stage: 'clone', summary: 'Cloning...' })
  })

  it('fires onIndexDone for index_done events', async () => {
    const sseBody =
      'event: index_done\ndata: {"repo":"owner/repo","files":100,"clusters":5,"symbols":500}\n\n'
    global.fetch = vi.fn().mockResolvedValue(makeStreamResponse(sseBody))

    const onIndexDone = vi.fn()
    await indexRepo('https://github.com/owner/repo', { onIndexDone })
    expect(onIndexDone).toHaveBeenCalledWith({
      repo: 'owner/repo',
      files: 100,
      clusters: 5,
      symbols: 500,
    })
  })

  it('fires onError for error events', async () => {
    const sseBody = 'event: error\ndata: {"message":"Something went wrong"}\n\n'
    global.fetch = vi.fn().mockResolvedValue(makeStreamResponse(sseBody))

    const onError = vi.fn()
    await indexRepo('https://github.com/owner/repo', { onError })
    expect(onError).toHaveBeenCalledWith('Something went wrong')
  })

  it('throws when HTTP response is not ok', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response('Server Error', { status: 500 }),
    )
    await expect(
      indexRepo('https://github.com/owner/repo', {}),
    ).rejects.toThrow()
  })
})

describe('analyzePR', () => {
  it('fires onAgentStep for agent_step events', async () => {
    const sseBody =
      'event: agent_step\ndata: {"tool":"get_pull_request","summary":"Reading PR..."}\n\n'
    global.fetch = vi.fn().mockResolvedValue(makeStreamResponse(sseBody))

    const onAgentStep = vi.fn()
    await analyzePR('https://github.com/owner/repo/pull/1', { onAgentStep })
    expect(onAgentStep).toHaveBeenCalledWith({
      tool: 'get_pull_request',
      summary: 'Reading PR...',
    })
  })

  it('fires onResult for result events', async () => {
    const resultPayload = {
      pr_title: 'My PR',
      pr_url: 'https://github.com/owner/repo/pull/1',
      pr_summary: 'Summary',
      affected_components: [],
      agent_steps: 3,
    }
    const sseBody = `event: result\ndata: ${JSON.stringify(resultPayload)}\n\n`
    global.fetch = vi.fn().mockResolvedValue(makeStreamResponse(sseBody))

    const onResult = vi.fn()
    await analyzePR('https://github.com/owner/repo/pull/1', { onResult })
    expect(onResult).toHaveBeenCalledWith(resultPayload)
  })
})

describe('getGraph', () => {
  it('fetches the correct URL', async () => {
    const graphData = { nodes: [], edges: [], clusters: [] }
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(graphData), { status: 200 }))

    await getGraph('octocat', 'hello-world')

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/graph/octocat/hello-world',
      expect.any(Object),
    )
  })
})

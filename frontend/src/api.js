/**
 * Frontend API layer for Sprint 1.
 *
 * Connected backend endpoints:
 * - POST /index    (SSE stream: index_step, index_done, error)
 * - POST /analyze  (SSE stream: agent_step, result, error)
 * - GET  /graph/{owner}/{repo}
 *
 * Why this file exists:
 * - Keeps fetch/SSE parsing logic out of React components
 * - Exposes simple functions that UI components can call
 * - Provides optional callback hooks for each SSE event type
 */
import { mockAnalyzePR, mockGetGraph, mockIndexRepo } from "./mock/mockApi"

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"
const USE_MOCK_SSE = String(import.meta.env.VITE_USE_MOCK_SSE || "false") === "true"

function buildUrl(path) {
  return `${API_BASE_URL}${path}`
}

function safeJsonParse(value) {
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

function parseSseBlock(block) {
  const lines = block.split("\n")
  let event = "message"
  const dataLines = []

  for (const line of lines) {
    if (!line) continue
    if (line.startsWith("event:")) {
      event = line.slice(6).trim()
      continue
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim())
    }
  }

  return {
    event,
    data: safeJsonParse(dataLines.join("\n")),
  }
}

async function readErrorText(response) {
  try {
    const text = await response.text()
    return text || `HTTP ${response.status}`
  } catch {
    return `HTTP ${response.status}`
  }
}

async function streamSsePost(path, payload, { signal, onEvent } = {}) {
  // Using fetch streaming because EventSource supports only GET,
  // while our API contract uses POST for /index and /analyze.
  const response = await fetch(buildUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    throw new Error(await readErrorText(response))
  }

  if (!response.body) {
    throw new Error("Streaming is not available in this browser.")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split("\n\n")
    buffer = blocks.pop() || ""

    for (const block of blocks) {
      const trimmed = block.trim()
      if (!trimmed) continue
      const event = parseSseBlock(trimmed)
      if (onEvent) onEvent(event)
    }
  }

  if (buffer.trim()) {
    const event = parseSseBlock(buffer.trim())
    if (onEvent) onEvent(event)
  }
}

export function getApiBaseUrl() {
  return API_BASE_URL
}

export function isMockSseEnabled() {
  return USE_MOCK_SSE
}

export async function getGraph(owner, repo) {
  if (USE_MOCK_SSE) {
    return mockGetGraph(owner, repo)
  }

  const response = await fetch(buildUrl(`/graph/${owner}/${repo}`), {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(await readErrorText(response))
  }

  return response.json()
}

export async function indexRepo(
  repoUrl,
  { signal, onEvent, onIndexStep, onIndexDone, onError } = {},
) {
  if (USE_MOCK_SSE) {
    return mockIndexRepo(repoUrl, {
      signal,
      onEvent,
      onIndexStep,
      onIndexDone,
      onError,
    })
  }

  // Emits UI hooks as events arrive:
  // - index_step -> onIndexStep
  // - index_done -> onIndexDone (also returned)
  // - error -> onError
  let finalPayload = null

  try {
    await streamSsePost(
      "/index",
      { repo_url: repoUrl },
      {
        signal,
        onEvent: (evt) => {
          onEvent?.(evt)

          if (evt.event === "index_step") {
            onIndexStep?.(evt.data)
          } else if (evt.event === "index_done") {
            finalPayload = evt.data
            onIndexDone?.(evt.data)
          } else if (evt.event === "error") {
            const message =
              typeof evt.data === "object" && evt.data?.message
                ? evt.data.message
                : "Indexing failed."
            onError?.(message)
          }
        },
      },
    )

    return finalPayload
  } catch (error) {
    if (error?.name === "AbortError") throw error
    onError?.(error.message || "Indexing failed.")
    throw error
  }
}

export async function analyzePR(
  prUrl,
  { signal, onEvent, onAgentStep, onResult, onError } = {},
) {
  if (USE_MOCK_SSE) {
    return mockAnalyzePR(prUrl, {
      signal,
      onEvent,
      onAgentStep,
      onResult,
      onError,
    })
  }

  // Emits UI hooks as events arrive:
  // - agent_step -> onAgentStep
  // - result -> onResult (also returned)
  // - error -> onError
  let finalPayload = null

  try {
    await streamSsePost(
      "/analyze",
      { pr_url: prUrl },
      {
        signal,
        onEvent: (evt) => {
          onEvent?.(evt)

          if (evt.event === "agent_step") {
            onAgentStep?.(evt.data)
          } else if (evt.event === "result") {
            finalPayload = evt.data
            onResult?.(evt.data)
          } else if (evt.event === "error") {
            const message =
              typeof evt.data === "object" && evt.data?.message
                ? evt.data.message
                : "Analysis failed."
            onError?.(message)
          }
        },
      },
    )

    return finalPayload
  } catch (error) {
    if (error?.name === "AbortError") throw error
    onError?.(error.message || "Analysis failed.")
    throw error
  }
}

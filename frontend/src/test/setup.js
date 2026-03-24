import '@testing-library/jest-dom'

// jsdom does not implement scrollIntoView — stub it globally (not available in node env)
if (typeof window !== 'undefined') {
  window.Element.prototype.scrollIntoView = vi.fn()
}

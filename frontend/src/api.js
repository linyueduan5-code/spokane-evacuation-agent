const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed: ${response.status}`)
  }
  return response.json()
}

export const api = {
  bootstrap: () => request('/api/bootstrap'),
  health: () => request('/api/health'),
  geocode: (query) => request(`/api/geocode?q=${encodeURIComponent(query)}`),
  chat: (payload) => request('/api/chat', { method: 'POST', body: JSON.stringify(payload) }),
  missingPerson: (payload) => request('/api/missing-person', { method: 'POST', body: JSON.stringify(payload) }),
  runEvaluation: () => request('/api/evaluation/run', { method: 'POST' }),
  evaluationScenarios: () => request('/api/evaluation/scenarios'),
}

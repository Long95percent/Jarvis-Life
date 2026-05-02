export interface Scenario {
  id: string
  name: string
  name_en: string
  icon: string
  description: string
  agents: string[]
  agent_roster: 'jarvis' | 'brainstorm'
}

async function requestJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1/jarvis${path}`, init)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return await res.json() as T
}

export const jarvisScenarioApi = {
  listScenarios(): Promise<Scenario[]> {
    return requestJSON('/scenarios')
  },
}

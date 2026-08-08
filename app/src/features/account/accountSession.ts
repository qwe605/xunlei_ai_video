export interface DemoSession {
  displayName: string
  email: string
}

const SESSION_KEY = 'xunlei-ai-demo-session'

export function readDemoSession(): DemoSession | null {
  try {
    const value = localStorage.getItem(SESSION_KEY)
    return value ? (JSON.parse(value) as DemoSession) : null
  } catch {
    return null
  }
}

export const demoSessionStorageKey = SESSION_KEY

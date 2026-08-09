import { z } from 'zod'

const userSchema = z.object({
  id: z.string().min(1),
  email: z.string().min(1),
  displayName: z.string().min(1),
})

export type UserSession = z.infer<typeof userSchema>

async function parseAuthResponse(response: Response): Promise<UserSession> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? '账号服务暂不可用')
  }
  return userSchema.parse(await response.json())
}

export async function readCurrentUser(): Promise<UserSession | null> {
  const response = await fetch('/api/v1/auth/me')
  if (response.status === 401) return null
  return parseAuthResponse(response)
}

export async function registerAccount(
  displayName: string,
  email: string,
  password: string,
): Promise<UserSession> {
  return parseAuthResponse(
    await fetch('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ displayName, email, password }),
    }),
  )
}

export async function loginAccount(email: string, password: string): Promise<UserSession> {
  return parseAuthResponse(
    await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),
  )
}

export async function logoutAccount(): Promise<void> {
  const response = await fetch('/api/v1/auth/logout', { method: 'POST' })
  if (!response.ok && response.status !== 401) throw new Error('退出登录失败')
}

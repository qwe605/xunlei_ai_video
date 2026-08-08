import { describe, expect, it } from 'vitest'
import { derivePasswordHash } from './passwordHash'

describe('本地账号密码摘要', () => {
  it('公网 HTTP 环境缺少 Web Crypto 时仍能生成兼容的 PBKDF2-SHA256 摘要', async () => {
    const salt = Uint8Array.from({ length: 16 }, (_, index) => index)

    await expect(derivePasswordHash('review-pass-2026', salt, null)).resolves.toBe(
      'XWXtzLXv2LkD1vFSkWxvflpkSsI4o8Tgn0a/6VvqIMs=',
    )
  })
})

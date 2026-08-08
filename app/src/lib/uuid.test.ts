import { describe, expect, it } from 'vitest'
import { createUuid, type UuidCryptoSource } from './uuid'

describe('兼容 UUID 生成', () => {
  it('公网 HTTP 环境没有 randomUUID 时仍生成标准 UUID v4', () => {
    const source: UuidCryptoSource = {
      getRandomValues: (bytes) => {
        bytes.forEach((_, index) => {
          bytes[index] = index
        })
        return bytes
      },
    }

    expect(createUuid(source)).toBe('00010203-0405-4607-8809-0a0b0c0d0e0f')
  })
})

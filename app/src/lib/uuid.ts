export interface UuidCryptoSource {
  randomUUID?: () => string
  getRandomValues: (bytes: Uint8Array<ArrayBuffer>) => void
}

/**
 * 生成本地视频与任务使用的 UUID。
 * 公网 HTTP IP 中浏览器可能隐藏 randomUUID，但仍提供加密随机字节接口。
 */
export function createUuid(source?: UuidCryptoSource): string {
  const cryptoSource = source ?? {
    randomUUID: globalThis.crypto.randomUUID?.bind(globalThis.crypto),
    getRandomValues: (bytes: Uint8Array<ArrayBuffer>) => {
      globalThis.crypto.getRandomValues(bytes)
    },
  }
  if (typeof cryptoSource.randomUUID === 'function') return cryptoSource.randomUUID()

  const bytes = new Uint8Array(new ArrayBuffer(16))
  cryptoSource.getRandomValues(bytes)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

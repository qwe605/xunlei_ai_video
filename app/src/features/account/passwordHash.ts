import { pbkdf2Async } from '@noble/hashes/pbkdf2'
import { sha256 } from '@noble/hashes/sha256'

const PBKDF2_ITERATIONS = 120_000
const HASH_BYTES = 32

const bytesToBase64 = (bytes: Uint8Array) => {
  let binary = ''
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary)
}

/**
 * 派生浏览器本地体验账号的密码摘要。
 * 公网 HTTP IP 不属于安全上下文，浏览器会隐藏 Web Crypto；此时使用同参数的软件实现，
 * 确保本地开发、公网演示和既有账号得到完全一致的 PBKDF2-SHA256 结果。
 */
export async function derivePasswordHash(
  password: string,
  salt: Uint8Array,
  subtle: SubtleCrypto | null | undefined = globalThis.crypto?.subtle,
) {
  if (subtle) {
    const material = await subtle.importKey(
      'raw',
      new TextEncoder().encode(password),
      'PBKDF2',
      false,
      ['deriveBits'],
    )
    const bits = await subtle.deriveBits(
      {
        name: 'PBKDF2',
        salt: new Uint8Array(salt),
        iterations: PBKDF2_ITERATIONS,
        hash: 'SHA-256',
      },
      material,
      HASH_BYTES * 8,
    )
    return bytesToBase64(new Uint8Array(bits))
  }

  const bits = await pbkdf2Async(sha256, new TextEncoder().encode(password), salt, {
    c: PBKDF2_ITERATIONS,
    dkLen: HASH_BYTES,
  })
  return bytesToBase64(bits)
}

import { z } from 'zod'


const magnetResponseSchema = z.object({
  status: z.literal('opened'),
  detail: z.string().min(1),
})


export async function openMagnetInXunlei(magnet: string): Promise<string> {
  // 浏览器不能稳定唤起本地协议，因此统一交给 FastAPI 的 Windows Integration。
  const response = await fetch('/api/v1/system/magnet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ magnet }),
  })
  const body = (await response.json().catch(() => null)) as unknown
  if (!response.ok) {
    const detail = z.object({ detail: z.string() }).safeParse(body)
    throw new Error(detail.success ? detail.data.detail : '迅雷客户端启动失败')
  }
  return magnetResponseSchema.parse(body).detail
}

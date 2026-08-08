import { describe, expect, it } from 'vitest'
import { clampTime, formatDuration } from './time'

describe('播放器时间工具', () => {
  it('格式化分钟和小时', () => {
    expect(formatDuration(756)).toBe('12:36')
    expect(formatDuration(6420)).toBe('01:47:00')
  })

  it('把异常时间限制在视频范围内', () => {
    expect(clampTime(-12, 100)).toBe(0)
    expect(clampTime(120, 100)).toBe(100)
    expect(clampTime(Number.NaN, 100)).toBe(0)
  })
})


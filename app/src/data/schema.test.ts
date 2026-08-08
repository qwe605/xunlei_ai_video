import { describe, expect, it } from 'vitest'
import { demoLibrary } from './demoLibrary'
import { videoQaSchema, videoSchema } from './schema'

describe('演示数据契约', () => {
  it('全部视频均通过运行时校验', () => {
    expect(demoLibrary).toHaveLength(4)
    demoLibrary.forEach((video) => expect(videoSchema.safeParse(video).success).toBe(true))
  })

  it('中文样例已完成纯音频 AI 整理', () => {
    const sample = demoLibrary.find((video) => video.id === 'parsevideo-chinese-demo')

    expect(sample?.indexStatus).toBe('ready')
    expect(sample?.subtitleOrigin).toBe('ai-generated')
    expect(sample?.asrModel).toContain('stable-ts')
    expect(sample?.chapters).toHaveLength(6)
  })

  it('拒绝超出视频时长的章节', () => {
    const invalidVideo = {
      ...demoLibrary[0],
      chapters: [
        {
          ...demoLibrary[0].chapters[0],
          endSeconds: demoLibrary[0].durationSeconds + 1,
        },
      ],
    }

    expect(videoSchema.safeParse(invalidVideo).success).toBe(false)
  })

  it('有依据的回答必须提供引用片段', () => {
    const invalidAnswer = {
      ...demoLibrary[0].qa[0],
      citations: [],
      grounded: true,
    }

    expect(videoQaSchema.safeParse(invalidAnswer).success).toBe(false)
  })
})

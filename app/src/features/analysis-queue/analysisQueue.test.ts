import { describe, expect, it } from 'vitest'
import { chineseDemoVideos } from '../../data/chineseDemoLibrary'
import { getBundledAnalysis } from './analysisQueue'

describe('内置分析结果复用', () => {
  it('只回填 AI 产物，不覆盖用户本地媒体地址', () => {
    const imported = {
      ...chineseDemoVideos[0],
      id: 'local-upload',
      originalFilename: 'eternal-night-survival.mp4',
      videoUrl: 'blob:http://localhost/local-video',
      posterUrl: 'blob:http://localhost/local-poster',
    }

    const result = getBundledAnalysis(imported)

    expect(result?.summary).toBe(chineseDemoVideos[0].summary)
    expect(result).not.toHaveProperty('videoUrl')
    expect(result).not.toHaveProperty('posterUrl')
    expect(result).not.toHaveProperty('originalFilename')
  })
})

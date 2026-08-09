import { describe, expect, it } from 'vitest'
import { demoLibrary } from '../data/demoLibrary'
import { buildPromptSuggestions } from './promptSuggestions'
import { searchLibrary } from './search'

describe('buildPromptSuggestions', () => {
  it('优先根据当前片库的中文视频生成建议', () => {
    const suggestions = buildPromptSuggestions(demoLibrary)

    expect(suggestions).toHaveLength(3)
    expect(suggestions.every((item) => !item.includes('Python'))).toBe(true)
    expect(suggestions.some((item) => item.includes('永夜'))).toBe(true)
  })

  it('片库变化后不保留旧视频建议', () => {
    const onlyPython = demoLibrary.filter((video) => video.title.includes('Python'))

    const suggestions = buildPromptSuggestions(onlyPython)

    expect(suggestions).toHaveLength(3)
    expect(suggestions.some((item) => item.includes(onlyPython[0].title))).toBe(true)
    expect(suggestions.every((item) => !item.includes('永夜'))).toBe(true)
  })

  it('生成的每条建议都能在当前片库得到搜索结果', () => {
    const suggestions = buildPromptSuggestions(demoLibrary)

    for (const suggestion of suggestions) {
      expect(searchLibrary(suggestion, 'ai', demoLibrary).length).toBeGreaterThan(0)
    }
  })
})

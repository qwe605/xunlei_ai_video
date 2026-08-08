import { describe, expect, it } from 'vitest'
import { demoLibrary } from '../data/demoLibrary'
import { answerVideoQuestion, searchLibrary } from './search'

describe('片库搜索', () => {
  it('自然语言主查询定位到 Python 名字由来的真实章节', () => {
    const results = searchLibrary('找讲 Python 名字由来的视频', 'ai', demoLibrary)

    expect(results[0]?.video.id).toBe('python-as-a-language')
    expect(results[0]?.matchReasons.join('')).toContain('02:04')
    expect(results[0]?.evidence[0]?.startSeconds).toBe(124)
  })

  it('传统搜索可以直接命中真实原文件名', () => {
    const results = searchLibrary('永夜世界观-兽人清剿片段', 'filename', demoLibrary)

    expect(results[0]?.video.id).toBe('eternal-night-survival')
    expect(results[0]?.matchReasons).toContain('原文件名直接命中')
  })

  it('空搜索不返回任何结果', () => {
    expect(searchLibrary('   ', 'ai', demoLibrary)).toEqual([])
  })
})

describe('问视频', () => {
  const tutorial = demoLibrary.find((video) => video.id === 'python-as-a-language')!

  it('保留字问题返回 11:28 的字幕依据', () => {
    const answer = answerVideoQuestion(tutorial, '后面有没有讲保留字？')

    expect(answer?.grounded).toBe(true)
    expect(answer?.citations[0]?.startSeconds).toBe(688)
  })

  it('没有视频证据时返回 null，由界面明确拒答', () => {
    expect(answerVideoQuestion(tutorial, '老师有没有推荐北京餐厅？')).toBeNull()
  })
})

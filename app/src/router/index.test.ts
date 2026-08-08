import { describe, expect, it } from 'vitest'
import { parseRoute, routes } from './index'


describe('应用路由', () => {
  it('解析搜索、详情和播放器深链接', () => {
    expect(parseRoute(new URL('https://demo.test/search?q=永夜'))).toEqual({
      name: 'search',
      query: '永夜',
    })
    expect(parseRoute(new URL('https://demo.test/videos/video-1'))).toEqual({
      name: 'detail',
      videoId: 'video-1',
    })
    expect(parseRoute(new URL('https://demo.test/videos/video-1/play?t=12.5'))).toEqual({
      name: 'player',
      videoId: 'video-1',
      startSeconds: 12.5,
    })
  })

  it('生成的内部路径会编码用户输入', () => {
    expect(routes.search('烛龙 世界观')).toBe('/search?q=%E7%83%9B%E9%BE%99%20%E4%B8%96%E7%95%8C%E8%A7%82')
    expect(routes.detail('video/a')).toBe('/videos/video%2Fa')
  })
})

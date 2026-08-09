import type { Video } from '../data/schema'

const genericTags = new Set(['AI', '视频', '本地导入', '简体中文', '中文'])

const isChineseText = (value: string) => /[\u4e00-\u9fff]/.test(value)

export function buildPromptSuggestions(videos: Video[], limit = 3): string[] {
  const readyVideos = videos.filter((video) => video.indexStatus === 'ready')
  const chineseVideos = readyVideos.filter((video) => isChineseText(video.title))
  const candidates: string[] = []

  for (const video of chineseVideos) {
    const meaningfulTag = video.tags.find(
      (tag) => isChineseText(tag) && !genericTags.has(tag) && tag.length >= 2,
    )
    if (meaningfulTag) candidates.push(`找关于${meaningfulTag}的视频`)

    const chapter = video.chapters.find(
      (item) => isChineseText(item.title) && item.title.length >= 4,
    )
    if (chapter) candidates.push(`找讲“${chapter.title}”的片段`)

    candidates.push(`找视频“${video.title}”`)
  }

  for (const video of readyVideos.filter((video) => !chineseVideos.includes(video))) {
    candidates.push(`找视频“${video.title}”`)
  }

  return [...new Set(candidates)].slice(0, Math.max(0, limit))
}

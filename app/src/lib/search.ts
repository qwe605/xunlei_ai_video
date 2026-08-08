import type { EvidenceSegment, Video, VideoQa } from '../data/schema'

export type SearchMode = 'filename' | 'ai'

export interface SearchResult {
  video: Video
  score: number
  confidenceLabel: '高' | '中' | '低'
  matchReasons: string[]
  evidence: EvidenceSegment[]
}

const normalize = (value: string) =>
  value
    .toLocaleLowerCase('zh-CN')
    // 中文检索中“名字由来”和“名字的由来”表达同一意图，归一化结构助词后再做确定性匹配。
    .replace(/[的]/g, '')
    .replace(/\s+/g, '')

const queryTerms = (query: string) => {
  const withoutFillers = query
    .toLocaleLowerCase('zh-CN')
    .replace(/找我保存的|找|讲|那个|这部|视频|的/g, ' ')

  return withoutFillers
    .split(/[\s，。、“”‘’：；！？，./_\-[\]()]+/)
    // 去掉“的、找、讲”这类单字噪声，避免它们压过 Python、保留字等真正表达意图的词。
    .filter((term) => term.length > 1 || /^[a-z0-9]/.test(term))
}

const semanticAliases: Record<string, string[]> = {
  名字: ['命名', '由来', 'monty'],
  解释器: ['交互式', '终端', '提示符'],
  保留字: ['reserved', '词汇', '变量'],
  异常: ['exception', 'try-except', '捕获'],
  文件: ['读取', '文本', '多行'],
  python: ['编程', '开发', '前端', '后端'],
  教程: ['课程', '实战', '入门'],
}

function confidenceLabel(score: number): SearchResult['confidenceLabel'] {
  if (score >= 8) return '高'
  if (score >= 4) return '中'
  return '低'
}

function filenameSearch(query: string, videos: Video[]): SearchResult[] {
  const normalizedQuery = normalize(query)

  return videos
    .map((video) => {
      const title = normalize(video.title)
      const filename = normalize(video.originalFilename)
      const tags = normalize(video.tags.join(' '))
      let score = 0
      const matchReasons: string[] = []

      if (title.includes(normalizedQuery)) {
        score += 12
        matchReasons.push('展示名称与搜索词一致')
      }
      if (filename.includes(normalizedQuery)) {
        score += 10
        matchReasons.push('原文件名直接命中')
      }
      if (tags.includes(normalizedQuery)) {
        score += 5
        matchReasons.push('视频标签包含搜索词')
      }

      return {
        video,
        score,
        confidenceLabel: confidenceLabel(score),
        matchReasons,
        evidence: [],
      }
    })
    .filter((result) => result.score > 0)
    .sort((a, b) => b.score - a.score)
}

function aiSearch(query: string, videos: Video[]): SearchResult[] {
  const terms = queryTerms(query)

  return videos
    .map((video) => {
      const metadataText = normalize(
        [video.title, video.originalFilename, video.shortDescription, video.summary, ...video.tags].join(' '),
      )
      const chapterText = normalize(
        video.chapters.map((chapter) => `${chapter.title} ${chapter.summary}`).join(' '),
      )
      const expandedTerms = new Set(
        terms.flatMap((term) => [term, ...(semanticAliases[term] ?? [])]).map(normalize),
      )
      let keywordScore = 0
      let semanticScore = 0
      const matchReasons: string[] = []

      expandedTerms.forEach((term) => {
        if (metadataText.includes(term)) keywordScore += 1.8
        if (chapterText.includes(term)) semanticScore += 2.4
      })

      const matchingChapter = video.chapters
        .map((chapter) => {
          const title = normalize(chapter.title)
          const summary = normalize(chapter.summary)
          const score = [...expandedTerms].reduce((total, term) => {
            // 标题命中比摘要命中更能代表章节主题，因此给予更高权重。
            if (title.includes(term)) return total + 3
            if (summary.includes(term)) return total + 1
            return total
          }, 0)
          return { chapter, score }
        })
        .filter((candidate) => candidate.score > 0)
        .sort((left, right) => right.score - left.score)[0]?.chapter

      if (keywordScore > 0) {
        const matchedTags = video.tags.filter((tag) =>
          [...expandedTerms].some((term) => normalize(tag).includes(term)),
        )
        matchReasons.push(
          matchedTags.length > 0
            ? `内容标签命中：${matchedTags.slice(0, 3).join('、')}`
            : '标题、摘要或文件信息与描述相关',
        )
      }

      if (matchingChapter) {
        semanticScore += 3
        matchReasons.push(
          `相关章节位于 ${Math.floor(matchingChapter.startSeconds / 60)
            .toString()
            .padStart(2, '0')}:${Math.floor(matchingChapter.startSeconds % 60)
            .toString()
            .padStart(2, '0')}「${matchingChapter.title}」`,
        )
      }

      // Demo 使用 RRF 思想合并两路确定性得分；生产环境会替换为真实 BM25 与向量召回排名。
      const score = keywordScore + semanticScore + video.confidence * 1.5
      const evidence = matchingChapter
        ? [
            {
              id: `search-${video.id}-${matchingChapter.id}`,
              startSeconds: matchingChapter.startSeconds,
              endSeconds: matchingChapter.endSeconds,
              text: matchingChapter.summary,
              sourceType: 'summary' as const,
              confidence: matchingChapter.confidence,
            },
          ]
        : []

      return {
        video,
        score,
        confidenceLabel: confidenceLabel(score),
        matchReasons,
        evidence,
      }
    })
    .filter((result) => result.score >= 3)
    .sort((a, b) => b.score - a.score)
}

export function searchLibrary(query: string, mode: SearchMode, videos: Video[]): SearchResult[] {
  const trimmedQuery = query.trim()
  if (!trimmedQuery) return []
  return mode === 'filename'
    ? filenameSearch(trimmedQuery, videos)
    : aiSearch(trimmedQuery, videos)
}

export function answerVideoQuestion(video: Video, question: string): VideoQa | null {
  const normalizedQuestion = normalize(question)
  const candidates = video.qa
    .map((item) => ({
      item,
      matches: item.keywords.filter((keyword) => normalizedQuestion.includes(normalize(keyword))).length,
    }))
    .sort((a, b) => b.matches - a.matches)

  // 没有关键词证据就拒答，避免模型凭常识生成一个看似合理但无法跳转的答案。
  return candidates[0]?.matches > 0 ? candidates[0].item : null
}

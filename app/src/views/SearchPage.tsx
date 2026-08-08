import { ArrowLeft, CirclePlay, FileText, Play, Search, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { searchPersistedVideos } from '../api/search'
import { EmptyState } from '../components/EmptyState'
import { StatusBadge } from '../components/StatusBadge'
import { VideoThumbnail } from '../components/VideoThumbnail'
import type { Video } from '../data/schema'
import { searchLibrary, type SearchMode } from '../lib/search'
import { formatDuration } from '../lib/time'

interface SearchPageProps {
  query: string
  videos: Video[]
  onBack: () => void
  onOpen: (video: Video) => void
  onPlay: (video: Video, startSeconds?: number) => void
}

export function SearchPage({ query, videos, onBack, onOpen, onPlay }: SearchPageProps) {
  const [mode, setMode] = useState<SearchMode>('ai')
  const [backendResults, setBackendResults] = useState<ReturnType<typeof searchLibrary> | null>(null)
  const [searching, setSearching] = useState(false)
  const localResults = useMemo(() => searchLibrary(query, mode, videos), [mode, query, videos])
  const results = backendResults && backendResults.length > 0 ? backendResults : localResults

  useEffect(() => {
    const trimmedQuery = query.trim()
    if (!trimmedQuery) {
      setBackendResults([])
      return
    }

    let active = true
    setSearching(true)
    setBackendResults(null)
    // 后端搜索覆盖已持久化的视频字幕、章节和摘要；接口不可用时用本地规则兜底，避免打断演示。
    void searchPersistedVideos(trimmedQuery, mode, videos)
      .then((nextResults) => {
        if (active) setBackendResults(nextResults)
      })
      .catch(() => {
        if (active) setBackendResults([])
      })
      .finally(() => {
        if (active) setSearching(false)
      })

    return () => {
      active = false
    }
  }, [mode, query, videos])

  return (
    <main className="page search-page" id="main-content">
      <button type="button" className="back-button" onClick={onBack}>
        <ArrowLeft size={17} aria-hidden="true" />
        返回片库
      </button>

      <section className="search-summary">
        <div>
          <p className="eyebrow">搜索结果</p>
          <h1>“{query}”</h1>
          <p>
            {searching
              ? '正在检索服务端片库、字幕和章节'
              : mode === 'ai'
                ? `综合文件信息、字幕片段与章节，找到 ${results.length} 个相关结果`
                : `按原文件名与展示名称找到 ${results.length} 个结果`}
          </p>
        </div>
        <div className="search-mode-control" role="tablist" aria-label="搜索模式">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'filename'}
            className={mode === 'filename' ? 'active' : ''}
            onClick={() => setMode('filename')}
          >
            <FileText size={16} aria-hidden="true" />
            文件名结果
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'ai'}
            className={mode === 'ai' ? 'active' : ''}
            onClick={() => setMode('ai')}
          >
            <Sparkles size={16} aria-hidden="true" />
            AI 推荐
          </button>
        </div>
      </section>

      {results.length === 0 ? (
        <EmptyState
          title="没有找到足够相关的视频"
          description={
            mode === 'filename'
              ? '试试切换到 AI 推荐，用剧情、人物或知识点描述视频。'
              : '可以缩短描述，或切换到文件名结果检查尚未完成索引的视频。'
          }
          action={
            <button
              type="button"
              className="button button-primary"
              onClick={() => setMode(mode === 'ai' ? 'filename' : 'ai')}
            >
              <Search size={16} aria-hidden="true" />
              切换搜索方式
            </button>
          }
        />
      ) : (
        <section className="search-results" aria-label="搜索结果列表">
          {results.map((result, index) => {
            const primaryEvidence = result.evidence[0]
            return (
              <article className="search-result" key={result.video.id}>
                <div className="result-rank" aria-label={`第 ${index + 1} 名`}>
                  {index + 1}
                </div>
                <VideoThumbnail
                  cell={result.video.thumbnailCell}
                  alt={`${result.video.title}视频画面`}
                  className="result-thumbnail"
                />
                <div className="result-content">
                  <div className="result-title-row">
                    <div>
                      <h2>{result.video.title}</h2>
                      <p className="filename">{result.video.originalFilename}</p>
                    </div>
                    <StatusBadge status={result.video.indexStatus} />
                  </div>

                  <div className="match-explanation">
                    <Sparkles size={17} aria-hidden="true" />
                    <div>
                      <strong>为什么匹配</strong>
                      {result.matchReasons.map((reason) => (
                        <p key={reason}>{reason}</p>
                      ))}
                    </div>
                  </div>

                  {primaryEvidence && (
                    <button
                      type="button"
                      className="evidence-row"
                      onClick={() => onPlay(result.video, primaryEvidence.startSeconds)}
                    >
                      <CirclePlay size={20} aria-hidden="true" />
                      <span>
                        <strong>{formatDuration(primaryEvidence.startSeconds)} 相关片段</strong>
                        <small>{primaryEvidence.text}</small>
                      </span>
                    </button>
                  )}

                  <div className="result-footer">
                    <span>{formatDuration(result.video.durationSeconds)}</span>
                    <span>{result.video.resolution}</span>
                    <span>匹配置信度：{result.confidenceLabel}</span>
                    <div>
                      <button
                        type="button"
                        className="button button-secondary"
                        onClick={() => onOpen(result.video)}
                      >
                        查看详情
                      </button>
                      <button
                        type="button"
                        className="button button-primary"
                        onClick={() =>
                          onPlay(result.video, primaryEvidence?.startSeconds ?? result.video.watchProgressSeconds)
                        }
                      >
                        <Play size={15} fill="currentColor" aria-hidden="true" />
                        播放
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            )
          })}
        </section>
      )}
    </main>
  )
}

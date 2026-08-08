import {
  ArrowUpDown,
  Captions,
  Clock3,
  Film,
  Filter,
  Grid2X2,
  List,
  Search,
  Sparkles,
  Zap,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import type { Video } from '../data/schema'
import { VideoCard } from '../components/VideoCard'
import { AnalysisQueuePanel } from '../features/analysis-queue/AnalysisQueuePanel'
import type { AnalysisJob } from '../features/analysis-queue/analysisQueue'
import type { LibraryFilter } from '../types/library'

interface LibraryPageProps {
  videos: Video[]
  onOpen: (video: Video) => void
  onPlay: (video: Video, startSeconds?: number) => void
  onSearch: (query: string) => void
  filter: LibraryFilter
  onFilterChange: (filter: LibraryFilter) => void
  analysisJobs: AnalysisJob[]
  onRetryAnalysis: (videoId: string) => void
  onDismissAnalysis: (videoId: string) => void
}

const promptSuggestions = [
  '找讲 Python 名字由来的视频',
  '找演示 Python 交互式解释器的片段',
  '找讲保留字和变量的课程',
]

const filterLabels: Record<LibraryFilter, string> = {
  all: '全部视频',
  ready: 'AI 已整理',
  tutorial: '教程课程',
  attention: 'AI 整理队列',
}

export function LibraryPage({
  videos,
  onOpen,
  onPlay,
  onSearch,
  filter,
  onFilterChange,
  analysisJobs,
  onRetryAnalysis,
  onDismissAnalysis,
}: LibraryPageProps) {
  const [sort, setSort] = useState<'saved' | 'name' | 'progress'>('saved')
  const benefitMetrics = useMemo(() => {
    const readyVideos = videos.filter((video) => video.indexStatus === 'ready')
    const subtitleSeconds = readyVideos.reduce((total, video) => total + video.durationSeconds, 0)
    const chapterCount = readyVideos.reduce((total, video) => total + video.chapters.length, 0)
    // Demo 阶段用保守估算：有章节和搜索后，用户少拖动约 18% 的视频时长。
    const savedMinutes = Math.round((subtitleSeconds * 0.18) / 60)
    return {
      readyCount: readyVideos.length,
      subtitleHours: Math.max(0.1, subtitleSeconds / 3600).toFixed(1),
      chapterCount,
      savedMinutes,
    }
  }, [videos])

  const visibleVideos = useMemo(() => {
    const filtered = videos.filter((video) => {
      if (filter === 'all') return true
      if (filter === 'ready') return video.indexStatus === 'ready'
      if (filter === 'attention') return ['failed', 'pending', 'processing'].includes(video.indexStatus)
      return video.mediaType === filter
    })

    return [...filtered].sort((left, right) => {
      if (sort === 'name') return left.title.localeCompare(right.title, 'zh-CN')
      if (sort === 'progress') return right.watchProgressSeconds - left.watchProgressSeconds
      return Date.parse(right.savedAt) - Date.parse(left.savedAt)
    })
  }, [filter, sort, videos])

  return (
    <main className="page library-page" id="main-content">
      <section className="page-heading">
        <div>
          <p className="eyebrow">我的云盘视频</p>
          <h1>{filterLabels[filter]}</h1>
          <p>共 {videos.length} 个视频，AI 已完成 {videos.filter((video) => video.indexStatus === 'ready').length} 个</p>
        </div>
        <div className="page-heading-actions">
          <button type="button" className="icon-button active" title="海报视图" aria-label="切换到海报视图">
            <Grid2X2 size={18} />
          </button>
          <button type="button" className="icon-button" title="列表视图" aria-label="切换到列表视图">
            <List size={18} />
          </button>
        </div>
      </section>

      <section className="ai-discovery" aria-labelledby="ai-discovery-title">
        <div className="ai-discovery-heading">
          <span className="ai-icon">
            <Sparkles size={19} aria-hidden="true" />
          </span>
          <div>
            <h2 id="ai-discovery-title">记不住文件名？描述你想找的内容</h2>
            <p>AI 会同时理解文件名、字幕、摘要、章节和观看记录。</p>
          </div>
        </div>
        <div className="prompt-suggestions">
          {promptSuggestions.map((prompt) => (
            <button type="button" key={prompt} onClick={() => onSearch(prompt)}>
              <Search size={15} aria-hidden="true" />
              {prompt}
            </button>
          ))}
        </div>
      </section>

      <section className="benefit-strip" aria-label="AI 整理收益">
        <div>
          <Captions size={18} aria-hidden="true" />
          <span>
            <strong>{benefitMetrics.subtitleHours} 小时</strong>
            <small>已生成字幕时长</small>
          </span>
        </div>
        <div>
          <Zap size={18} aria-hidden="true" />
          <span>
            <strong>{benefitMetrics.chapterCount} 个</strong>
            <small>可直达章节</small>
          </span>
        </div>
        <div>
          <Clock3 size={18} aria-hidden="true" />
          <span>
            <strong>{benefitMetrics.savedMinutes} 分钟</strong>
            <small>预计少拖动时间</small>
          </span>
        </div>
        <div>
          <Sparkles size={18} aria-hidden="true" />
          <span>
            <strong>{benefitMetrics.readyCount} 个</strong>
            <small>精准整理权益</small>
          </span>
        </div>
      </section>

      <AnalysisQueuePanel
        jobs={analysisJobs}
        onRetry={onRetryAnalysis}
        onDismiss={onDismissAnalysis}
      />

      <section className="library-toolbar" aria-label="片库筛选和排序">
        <div className="filter-tabs">
          {[
            ['all', '全部'],
            ['ready', 'AI 已整理'],
            ['tutorial', '教程'],
            ['attention', '待处理'],
          ].map(([value, label]) => (
            <button
              type="button"
              className={filter === value ? 'active' : ''}
              onClick={() => onFilterChange(value as LibraryFilter)}
              key={value}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="toolbar-controls">
          <Filter size={16} aria-hidden="true" />
          <label>
            <span className="sr-only">排序方式</span>
            <select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}>
              <option value="saved">最近保存</option>
              <option value="name">按名称</option>
              <option value="progress">按观看进度</option>
            </select>
          </label>
          <ArrowUpDown size={15} aria-hidden="true" />
        </div>
      </section>

      <section className="video-grid" aria-label="视频列表">
        {visibleVideos.length > 0 ? (
          visibleVideos.map((video) => (
            <VideoCard video={video} onOpen={onOpen} onPlay={onPlay} key={video.id} />
          ))
        ) : (
          <div className="library-empty">
            <Film size={24} aria-hidden="true" />
            <strong>这个分类还没有视频</strong>
            <p>可使用右上角“导入视频”添加本机 MP4 或 WebM。</p>
          </div>
        )}
      </section>
    </main>
  )
}

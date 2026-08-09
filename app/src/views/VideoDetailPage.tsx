import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Edit3,
  Eye,
  EyeOff,
  Play,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { VideoThumbnail } from '../components/VideoThumbnail'
import type { Video } from '../data/schema'
import { formatDuration } from '../lib/time'
import { VideoCorrectionDialog } from '../features/video-correction/VideoCorrectionDialog'
import type { VideoInformationUpdate } from '../api/videos'

interface VideoDetailPageProps {
  video: Video
  onBack: () => void
  onPlay: (video: Video, startSeconds?: number) => void
  onDelete: (video: Video) => Promise<void>
  onCorrect: (video: Video, payload: VideoInformationUpdate) => Promise<void>
}

export function VideoDetailPage({ video, onBack, onPlay, onDelete, onCorrect }: VideoDetailPageProps) {
  const [spoilersVisible, setSpoilersVisible] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [correctionOpen, setCorrectionOpen] = useState(false)
  const progress = Math.round((video.watchProgressSeconds / video.durationSeconds) * 100)
  const deleteVideo = async () => {
    if (!window.confirm(`确定从片库删除《${video.title}》吗？`)) return
    setDeleting(true)
    setDeleteError('')
    try {
      await onDelete(video)
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : '删除失败，请稍后重试')
      setDeleting(false)
    }
  }

  return (
    <main className="page detail-page" id="main-content">
      <button type="button" className="back-button" onClick={onBack}>
        <ArrowLeft size={17} aria-hidden="true" />
        返回
      </button>

      <section className="detail-hero">
        <VideoThumbnail
          cell={video.thumbnailCell}
          imageUrl={video.thumbnailUrl}
          alt={`${video.title}视频画面`}
          className="detail-cover"
        />
        <div className="detail-primary">
          <div className="detail-status-row">
            <StatusBadge status={video.indexStatus} />
            <span>AI 分析层级 {video.indexLevel}</span>
            <span>内容置信度 {Math.round(video.confidence * 100)}%</span>
          </div>
          <h1>{video.title}</h1>
          <p className="detail-filename">{video.originalFilename}</p>
          <p className="detail-description">{video.shortDescription}</p>
          <div className="tag-list" aria-label="内容标签">
            {video.tags.map((tag) => (
              <span key={tag}>{tag}</span>
            ))}
          </div>
          <div className="detail-metadata">
            <span>{formatDuration(video.durationSeconds)}</span>
            <span>{video.resolution}</span>
            <span>{video.codec}</span>
            <span>{video.language}</span>
            <span>已观看 {progress}%</span>
          </div>
          {video.sourceAttribution ? (
            <p className="source-attribution">
              公开授权素材：{video.sourceAttribution.author} ·{' '}
              <a href={video.sourceAttribution.sourceUrl} target="_blank" rel="noreferrer">
                查看来源
              </a>{' '}
              ·{' '}
              <a href={video.sourceAttribution.licenseUrl} target="_blank" rel="noreferrer">
                {video.sourceAttribution.license}
              </a>
            </p>
          ) : (
            <p className="source-attribution">本地导入视频，源文件与 AI 结果已保存在服务端片库</p>
          )}
          <p className={`subtitle-origin ${video.subtitleOrigin}`}>
            {video.subtitleOrigin === 'provided' && '字幕来源：原视频英文字幕'}
            {video.subtitleOrigin === 'ai-generated' && `AI 自动字幕：${video.asrModel}`}
            {video.subtitleOrigin === 'processing' && 'AI 自动字幕：生成中'}
          </p>
          <div className="detail-actions">
            <button
              type="button"
              className="button button-primary button-large"
              onClick={() => onPlay(video, video.watchProgressSeconds)}
            >
              <Play size={18} fill="currentColor" aria-hidden="true" />
              {video.watchProgressSeconds > 0 ? '继续播放' : '开始播放'}
            </button>
            {video.importSource === 'local' && (
              <button type="button" className="button button-secondary" onClick={() => setCorrectionOpen(true)}>
                <Edit3 size={17} aria-hidden="true" />
                纠正信息
              </button>
            )}
            {video.importSource === 'local' && (
              <button
                type="button"
                className="button button-secondary"
                onClick={deleteVideo}
                disabled={deleting}
              >
                <Trash2 size={17} aria-hidden="true" />
                {deleting ? '正在删除' : '删除视频'}
              </button>
            )}
          </div>
          {deleteError && (
            <p className="field-error" role="alert">
              {deleteError}
            </p>
          )}
        </div>
      </section>

      {video.organizeHint && (
        <aside className="organize-notice">
          <CheckCircle2 size={18} aria-hidden="true" />
          <div>
            <strong>AI 整理说明</strong>
            <p>{video.organizeHint}</p>
          </div>
        </aside>
      )}

      <section className="summary-section" aria-labelledby="summary-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">AI 内容卡片</p>
            <h2 id="summary-title">打开前先看懂</h2>
          </div>
          {video.spoilerProtected && (
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setSpoilersVisible((visible) => !visible)}
            >
              {spoilersVisible ? <EyeOff size={16} /> : <Eye size={16} />}
              {spoilersVisible ? '隐藏剧透' : '显示完整摘要'}
            </button>
          )}
        </div>
        <div className={video.spoilerProtected && !spoilersVisible ? 'spoiler-summary' : ''}>
          <Sparkles size={19} aria-hidden="true" />
          <p>
            {video.spoilerProtected && !spoilersVisible
              ? `${video.shortDescription} 后续剧情已隐藏。`
              : video.summary}
          </p>
        </div>
      </section>

      <section className="chapters-section" aria-labelledby="chapters-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">智能章节</p>
            <h2 id="chapters-title">{video.chapters.length} 个内容节点</h2>
          </div>
          <span className="section-note">点击章节可直接跳转</span>
        </div>

        {video.chapters.length > 0 ? (
          <div className="chapter-list">
            {video.chapters.map((chapter) => {
              const hideTitle =
                video.spoilerProtected &&
                !spoilersVisible &&
                chapter.spoilerLevel === 'major' &&
                chapter.startSeconds > video.watchProgressSeconds

              return (
                <button
                  type="button"
                  className="chapter-row"
                  key={chapter.id}
                  onClick={() => onPlay(video, chapter.startSeconds)}
                >
                  <VideoThumbnail
                    cell={video.thumbnailCell}
                    imageUrl={video.thumbnailUrl}
                    alt={`${chapter.title}代表画面`}
                    className="chapter-thumbnail"
                  />
                  <time>{formatDuration(chapter.startSeconds)}</time>
                  <span className="chapter-copy">
                    <strong>{hideTitle ? '关键事件（继续观看后解锁）' : chapter.title}</strong>
                    <small>{hideTitle ? '为避免剧透，暂不展示本章内容。' : chapter.summary}</small>
                  </span>
                  <span className="chapter-confidence">{Math.round(chapter.confidence * 100)}%</span>
                  <ChevronRight size={18} aria-hidden="true" />
                </button>
              )
            })}
          </div>
        ) : (
          <div className="inline-empty">
            <AlertCircle size={20} aria-hidden="true" />
            <div>
              <strong>智能章节暂不可用</strong>
              <p>
                {video.indexStatus === 'processing'
                  ? '字幕已读取，正在生成语义章节。'
                  : '当前视频尚未完成深度分析，仍可正常播放。'}
              </p>
            </div>
          </div>
        )}
      </section>

      {video.duplicateHint && (
        <aside className="duplicate-notice">
          <Clock3 size={18} aria-hidden="true" />
          <span>{video.duplicateHint}</span>
          <button type="button">查看版本</button>
        </aside>
      )}
      {correctionOpen && (
        <VideoCorrectionDialog
          video={video}
          onClose={() => setCorrectionOpen(false)}
          onSave={(payload) => onCorrect(video, payload)}
        />
      )}
    </main>
  )
}

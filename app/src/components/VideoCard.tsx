import { CirclePlay, Clock3, HardDrive, Info, Play } from 'lucide-react'
import type { Video } from '../data/schema'
import { formatDuration } from '../lib/time'
import { StatusBadge } from './StatusBadge'
import { VideoThumbnail } from './VideoThumbnail'

interface VideoCardProps {
  video: Video
  onOpen: (video: Video) => void
  onPlay: (video: Video, startSeconds?: number) => void
}

export function VideoCard({ video, onOpen, onPlay }: VideoCardProps) {
  const progress = Math.round((video.watchProgressSeconds / video.durationSeconds) * 100)

  return (
    <article className="video-card">
      <button
        type="button"
        className="thumbnail-button"
        onClick={() => onOpen(video)}
        aria-label={`查看《${video.title}》详情`}
      >
        <VideoThumbnail
          cell={video.thumbnailCell}
          imageUrl={video.thumbnailUrl}
          alt={`${video.title}视频画面`}
        />
        <span className="duration-label">{formatDuration(video.durationSeconds)}</span>
        <span className="thumbnail-play" aria-hidden="true">
          <CirclePlay size={34} />
        </span>
      </button>

      <div className="video-card-body">
        <div className="video-card-heading">
          <div>
            <h3>{video.title}</h3>
            <p className="filename" title={video.originalFilename}>
              {video.originalFilename}
            </p>
          </div>
          <StatusBadge status={video.indexStatus} />
        </div>

        <div className="video-meta" aria-label="视频信息">
          <span>
            <HardDrive size={14} aria-hidden="true" />
            {video.resolution}
          </span>
          <span>
            <Clock3 size={14} aria-hidden="true" />
            已看 {progress}%
          </span>
          <span>{video.indexLevel}</span>
        </div>

        {(video.organizeHint || video.duplicateHint) && (
          <p className="ai-hint">
            <Info size={15} aria-hidden="true" />
            {video.organizeHint ?? video.duplicateHint}
          </p>
        )}

        <div className="video-card-actions">
          <button type="button" className="button button-secondary" onClick={() => onOpen(video)}>
            <Info size={16} aria-hidden="true" />
            查看详情
          </button>
          <button
            type="button"
            className="button button-primary"
            onClick={() => onPlay(video, video.watchProgressSeconds)}
          >
            <Play size={16} fill="currentColor" aria-hidden="true" />
            {video.watchProgressSeconds > 0 ? '继续播放' : '播放'}
          </button>
        </div>
      </div>
    </article>
  )
}

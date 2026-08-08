import { AlertCircle, CheckCircle2, Clock3, RefreshCw, Sparkles, X } from 'lucide-react'
import type { AnalysisJob } from './analysisQueue'

interface AnalysisQueueProps {
  jobs: AnalysisJob[]
  onRetry: (videoId: string) => void
  onDismiss: (videoId: string) => void
}

const statusLabel: Record<AnalysisJob['status'], string> = {
  queued: '排队中',
  processing: '整理中',
  completed: '整理完成',
  blocked: '需要处理',
}

export function AnalysisQueuePanel({ jobs, onRetry, onDismiss }: AnalysisQueueProps) {
  if (jobs.length === 0) return null

  const activeCount = jobs.filter((job) => job.status === 'queued' || job.status === 'processing').length

  return (
    <section className="analysis-queue" aria-labelledby="analysis-queue-title" aria-label="AI 整理队列">
      <header className="analysis-queue-header">
        <div>
          <span className="ai-icon">
            <Sparkles size={18} aria-hidden="true" />
          </span>
          <div>
            <h2 id="analysis-queue-title">AI 整理队列</h2>
            <p>{activeCount > 0 ? `${activeCount} 个任务正在排队或处理` : '当前没有运行中的任务'}</p>
          </div>
        </div>
        <span className="analysis-service-state">
          <span aria-hidden="true" />
          AI 服务已连接
        </span>
      </header>

      <div className="analysis-job-list" role="list">
        {jobs.map((job) => {
          const Icon =
            job.status === 'completed'
              ? CheckCircle2
              : job.status === 'blocked'
                ? AlertCircle
                : job.status === 'processing'
                  ? RefreshCw
                  : Clock3

          return (
            <div className={`analysis-job job-${job.status}`} role="listitem" key={job.videoId}>
              <Icon className={job.status === 'processing' ? 'spin' : ''} size={18} aria-hidden="true" />
              <div className="analysis-job-main">
                <div className="analysis-job-title">
                  <strong>{job.title}</strong>
                  <div className="analysis-job-state">
                    <span>
                      {job.analysisMode === 'api'
                        ? 'ASR API'
                        : job.analysisMode === 'precise'
                          ? '精准'
                          : '快速'}
                    </span>
                    <span>{statusLabel[job.status]}</span>
                  </div>
                </div>
                <div
                  className="analysis-progress"
                  role="progressbar"
                  aria-label={`${job.title}整理进度`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={job.progress}
                >
                  <span style={{ width: `${job.progress}%` }} />
                </div>
                <p>
                  <strong>{job.stage}</strong>
                  {job.detail}
                </p>
              </div>
              {job.status === 'blocked' && (
                <button type="button" className="button button-secondary" onClick={() => onRetry(job.videoId)}>
                  <RefreshCw size={15} aria-hidden="true" />
                  重试
                </button>
              )}
              {job.status === 'completed' && (
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => onDismiss(job.videoId)}
                  aria-label={`移除${job.title}的已完成任务`}
                  title="移除已完成任务"
                >
                  <X size={16} />
                </button>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

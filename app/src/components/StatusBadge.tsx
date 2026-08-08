import {
  Ban,
  CheckCircle2,
  CircleDashed,
  Clock3,
  RefreshCw,
  TriangleAlert,
} from 'lucide-react'
import type { IndexStatus } from '../data/schema'

const statusConfig = {
  ready: { label: 'AI 已整理', icon: CheckCircle2, tone: 'success' },
  processing: { label: 'AI 整理中', icon: RefreshCw, tone: 'info' },
  pending: { label: '已进入队列', icon: Clock3, tone: 'warning' },
  failed: { label: '等待 AI 服务', icon: TriangleAlert, tone: 'danger' },
  disabled: { label: 'AI 分析已关闭', icon: Ban, tone: 'neutral' },
} satisfies Record<IndexStatus, { label: string; icon: typeof CircleDashed; tone: string }>

export function StatusBadge({ status }: { status: IndexStatus }) {
  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <span className={`status-badge status-${config.tone}`}>
      <Icon size={14} aria-hidden="true" />
      {config.label}
    </span>
  )
}

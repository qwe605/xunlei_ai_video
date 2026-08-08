import { Film, Folder, ListVideo, Sparkles } from 'lucide-react'
import type { Video } from '../data/schema'
import type { LibraryFilter } from '../types/library'

interface AppSidebarProps {
  videos: Video[]
  activeFilter: LibraryFilter
  onFilterChange: (filter: LibraryFilter) => void
}

export function AppSidebar({ videos, activeFilter, onFilterChange }: AppSidebarProps) {
  const readyCount = videos.filter((video) => video.indexStatus === 'ready').length
  const pendingCount = videos.filter((video) =>
    ['pending', 'processing', 'failed'].includes(video.indexStatus),
  ).length
  const tutorialCount = videos.filter((video) => video.mediaType === 'tutorial').length

  const item = (
    filter: LibraryFilter,
    label: string,
    Icon: typeof Film,
    count?: number,
  ) => (
    <button
      type="button"
      className={`sidebar-item ${activeFilter === filter ? 'active' : ''}`}
      onClick={() => onFilterChange(filter)}
      aria-current={activeFilter === filter ? 'page' : undefined}
    >
      <Icon size={18} aria-hidden="true" />
      {label}
      {count !== undefined && <span>{count}</span>}
    </button>
  )

  return (
    <aside className="app-sidebar" aria-label="片库导航">
      <nav>
        <p className="sidebar-label">片库</p>
        {item('all', '全部视频', Film, videos.length)}
        {item('ready', 'AI 已整理', Sparkles, readyCount)}

        <p className="sidebar-label folders-label">分类</p>
        {item('tutorial', '教程课程', Folder, tutorialCount)}
        {item('attention', 'AI 整理队列', ListVideo, pendingCount)}
      </nav>
    </aside>
  )
}

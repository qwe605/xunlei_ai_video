import { ChevronDown, Search, Sparkles, Upload } from 'lucide-react'
import { useState, type FormEvent } from 'react'

interface AppHeaderProps {
  initialQuery?: string
  onSearch: (query: string) => void
  onGoHome: () => void
  onImport: () => void
  accountName: string
  onAccount: () => void
}

export function AppHeader({
  initialQuery = '',
  onSearch,
  onGoHome,
  onImport,
  accountName,
  onAccount,
}: AppHeaderProps) {
  const [query, setQuery] = useState(initialQuery)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (query.trim()) onSearch(query.trim())
  }

  return (
    <header className="app-header">
      <button type="button" className="brand" onClick={onGoHome} aria-label="返回迅雷 AI 片库首页">
        <span className="brand-mark">迅</span>
        <span>
          <strong>迅雷 AI 片库</strong>
          <small>云盘视频内容助手</small>
        </span>
      </button>

      <form className="global-search" onSubmit={submit} role="search">
        <Search size={18} aria-hidden="true" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="输入片名，或描述你想找的视频"
          aria-label="搜索整个视频片库"
        />
        <span className="ai-search-label">
          <Sparkles size={14} aria-hidden="true" />
          AI
        </span>
        <button type="submit" className="search-submit" aria-label="开始搜索">
          搜索
        </button>
      </form>

      <div className="header-actions">
        <button type="button" className="button button-primary header-import" onClick={onImport}>
          <Upload size={16} />
          导入视频
        </button>
        <button type="button" className="account-button" onClick={onAccount} aria-label="打开账号中心">
          <span className="avatar">{accountName.slice(0, 1).toUpperCase()}</span>
          <span className="account-name">{accountName}</span>
          <ChevronDown size={15} aria-hidden="true" />
        </button>
      </div>
    </header>
  )
}

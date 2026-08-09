import { AlertCircle, Save, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import type { Video } from '../../data/schema'
import type { VideoInformationUpdate } from '../../api/videos'

interface VideoCorrectionDialogProps {
  video: Video
  onClose: () => void
  onSave: (payload: VideoInformationUpdate) => Promise<void>
}

export function VideoCorrectionDialog({ video, onClose, onSave }: VideoCorrectionDialogProps) {
  const [title, setTitle] = useState(video.title)
  const [shortDescription, setShortDescription] = useState(video.shortDescription)
  const [summary, setSummary] = useState(video.summary)
  const [tags, setTags] = useState(video.tags.join('、'))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const normalizedTags = [...new Set(tags.split(/[，,、]/).map((tag) => tag.trim()).filter(Boolean))]
    if (!title.trim() || !shortDescription.trim() || !summary.trim()) {
      setError('标题、简介和摘要不能为空')
      return
    }
    if (normalizedTags.length === 0 || normalizedTags.length > 8) {
      setError('请填写 1 至 8 个标签')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave({
        title: title.trim(),
        shortDescription: shortDescription.trim(),
        summary: summary.trim(),
        tags: normalizedTags,
      })
      onClose()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '纠正信息保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="correction-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="correction-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="import-dialog-header">
          <div>
            <h2 id="correction-title">纠正视频信息</h2>
            <p>修改会保存到当前账号片库，并记录为一条 AI 纠错反馈。</p>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭纠正窗口">
            <X size={19} />
          </button>
        </header>
        <form className="correction-form" onSubmit={submit}>
          <label>
            标题
            <input value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            一句话简介
            <textarea
              value={shortDescription}
              maxLength={220}
              rows={2}
              onChange={(event) => setShortDescription(event.target.value)}
            />
          </label>
          <label>
            内容摘要
            <textarea value={summary} maxLength={1200} rows={6} onChange={(event) => setSummary(event.target.value)} />
          </label>
          <label>
            标签
            <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="使用逗号或顿号分隔，最多 8 个" />
          </label>
          {error && (
            <p className="import-error" role="alert">
              <AlertCircle size={16} />
              {error}
            </p>
          )}
          <footer className="correction-actions">
            <button type="button" className="button button-secondary" onClick={onClose}>取消</button>
            <button type="submit" className="button button-primary" disabled={saving}>
              <Save size={16} />
              {saving ? '保存中' : '保存纠正'}
            </button>
          </footer>
        </form>
      </section>
    </div>
  )
}

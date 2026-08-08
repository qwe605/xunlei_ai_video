import {
  AlertCircle,
  CheckCircle2,
  Copy,
  FileVideo,
  Link2,
  LoaderCircle,
  Gauge,
  Target,
  Upload,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { videoSchema, type Video } from '../../data/schema'
import { formatDuration } from '../../lib/time'
import { openMagnetInXunlei } from '../../api/system'
import { readAnalysisCapabilities, type AnalysisMode } from '../../api/analysis'

interface ImportVideoDialogProps {
  onClose: () => void
  onImport: (video: Video, file: File, analysisMode: AnalysisMode, posterFile: File) => void
}

interface LocalMedia {
  file: File
  objectUrl: string
  durationSeconds: number
  width: number
  height: number
  posterUrl: string
  posterFile: File
  mimeType: 'video/mp4' | 'video/webm'
}

const inferMimeType = (file: File): LocalMedia['mimeType'] | null => {
  if (file.type === 'video/mp4' || file.name.toLowerCase().endsWith('.mp4')) return 'video/mp4'
  if (file.type === 'video/webm' || file.name.toLowerCase().endsWith('.webm')) return 'video/webm'
  return null
}

const waitForEvent = (element: HTMLVideoElement, event: 'loadedmetadata' | 'seeked') =>
  new Promise<void>((resolve, reject) => {
    const onError = () => reject(new Error(element.error?.message ?? '浏览器无法读取该视频'))
    element.addEventListener(event, () => resolve(), { once: true })
    element.addEventListener('error', onError, { once: true })
  })

async function inspectLocalVideo(file: File): Promise<LocalMedia> {
  const mimeType = inferMimeType(file)
  if (!mimeType) throw new Error('当前支持 MP4 和 WebM，请选择浏览器可播放的视频')

  const objectUrl = URL.createObjectURL(file)
  const element = document.createElement('video')
  element.preload = 'metadata'
  element.muted = true

  try {
    const metadataReady = waitForEvent(element, 'loadedmetadata')
    element.src = objectUrl
    element.load()
    await metadataReady

    if (!Number.isFinite(element.duration) || element.duration <= 0) {
      throw new Error('没有读取到有效的视频时长')
    }

    const target = Math.min(2, Math.max(0.1, element.duration * 0.08))
    const seekReady = waitForEvent(element, 'seeked')
    element.currentTime = target
    await seekReady

    const canvas = document.createElement('canvas')
    canvas.width = 960
    canvas.height = 540
    const context = canvas.getContext('2d')
    if (!context) throw new Error('浏览器无法生成视频封面')

    context.fillStyle = '#080c12'
    context.fillRect(0, 0, canvas.width, canvas.height)
    const scale = Math.min(canvas.width / element.videoWidth, canvas.height / element.videoHeight)
    const width = element.videoWidth * scale
    const height = element.videoHeight * scale
    context.drawImage(element, (canvas.width - width) / 2, (canvas.height - height) / 2, width, height)

    const posterUrl = canvas.toDataURL('image/jpeg', 0.84)
    const posterBlob = await fetch(posterUrl).then((response) => response.blob())

    return {
      file,
      objectUrl,
      durationSeconds: element.duration,
      width: element.videoWidth,
      height: element.videoHeight,
      posterUrl,
      posterFile: new File([posterBlob], `${file.name.replace(/\.[^.]+$/, '') || 'poster'}.jpg`, {
        type: 'image/jpeg',
      }),
      mimeType,
    }
  } catch (error) {
    URL.revokeObjectURL(objectUrl)
    throw error
  } finally {
    element.removeAttribute('src')
    element.load()
  }
}

export function ImportVideoDialog({ onClose, onImport }: ImportVideoDialogProps) {
  const [mode, setMode] = useState<'local' | 'magnet'>('local')
  const [media, setMedia] = useState<LocalMedia | null>(null)
  const [loading, setLoading] = useState(false)
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>('fast')
  const [preciseModelReady, setPreciseModelReady] = useState<boolean | null>(null)
  const [error, setError] = useState('')
  const [magnet, setMagnet] = useState('')
  const [magnetLaunching, setMagnetLaunching] = useState(false)
  const [magnetStatus, setMagnetStatus] = useState<{
    tone: 'success' | 'error'
    detail: string
  } | null>(null)
  const committedUrl = useRef<string | null>(null)

  useEffect(() => {
    let active = true
    void readAnalysisCapabilities()
      .then((capabilities) => {
        if (active) setPreciseModelReady(capabilities.preciseModelReady)
      })
      .catch(() => {
        if (active) setPreciseModelReady(false)
      })
    return () => {
      active = false
    }
  }, [])

  const close = () => {
    if (media && committedUrl.current !== media.objectUrl) URL.revokeObjectURL(media.objectUrl)
    onClose()
  }

  const selectFile = async (file?: File) => {
    if (!file) return
    if (media) URL.revokeObjectURL(media.objectUrl)
    setMedia(null)
    setError('')
    setLoading(true)
    try {
      setMedia(await inspectLocalVideo(file))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '视频读取失败')
    } finally {
      setLoading(false)
    }
  }

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    void selectFile(event.target.files?.[0])
  }

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    void selectFile(event.dataTransfer.files[0])
  }

  const confirmLocalImport = () => {
    if (!media) return
    const title = media.file.name.replace(/\.[^.]+$/, '') || media.file.name
    const imported = videoSchema.parse({
      id: `local-${crypto.randomUUID()}`,
      title,
      originalFilename: media.file.name,
      mediaType: 'other',
      durationSeconds: Math.ceil(media.durationSeconds),
      resolution: `${media.width} × ${media.height}`,
      codec: media.mimeType === 'video/mp4' ? '本地 MP4' : '本地 WebM',
      language: '待 AI 识别',
      savedAt: new Date().toISOString(),
      watchProgressSeconds: 0,
      indexStatus: 'pending',
      indexLevel: 'L0',
      confidence: 1,
      shortDescription: '已从本机读取真实视频，等待 AI 整理队列处理。',
      summary: '本地导入成功。原始文件仅保留在当前浏览器会话，不会上传到演示服务器。',
      tags: ['本地导入', '待分析'],
      thumbnailCell: 0,
      thumbnailUrl: media.posterUrl,
      posterUrl: media.posterUrl,
      videoUrl: media.objectUrl,
      videoMimeType: media.mimeType,
      subtitleOrigin: 'processing',
      importSource: 'local',
      spoilerProtected: false,
      organizeHint: '媒体元数据和封面已提取，任务已加入 AI 整理队列',
      chapters: [],
      qa: [],
    })

    committedUrl.current = media.objectUrl
    onImport(imported, media.file, analysisMode, media.posterFile)
  }

  const validMagnet =
    /^magnet:\?xt=urn:btih:(?:[a-f0-9]{40}|[a-z2-7]{32})(?:&|$)/i.test(magnet.trim())

  const openMagnet = async () => {
    if (!validMagnet) return
    setMagnetLaunching(true)
    setMagnetStatus(null)
    try {
      const detail = await openMagnetInXunlei(magnet.trim())
      setMagnetStatus({ tone: 'success', detail })
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : '迅雷客户端启动失败'
      const offline = /fetch|network|Failed/i.test(message)
      setMagnetStatus({
        tone: 'error',
        detail: offline ? '本地服务未启动，无法调用迅雷客户端。' : message,
      })
    } finally {
      setMagnetLaunching(false)
    }
  }

  const copyMagnet = async () => {
    await navigator.clipboard.writeText(magnet.trim())
    setMagnetStatus({ tone: 'success', detail: '磁力链接已复制，可粘贴到迅雷新建任务。' })
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={close}>
      <section
        className="import-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="import-dialog-header">
          <div>
            <h2 id="import-title">导入真实视频</h2>
            <p>视频会安全上传到分析服务，任务结束后自动删除临时原文件。</p>
          </div>
          <button type="button" className="icon-button" onClick={close} aria-label="关闭导入窗口">
            <X size={19} />
          </button>
        </header>

        <div className="import-mode-tabs" role="tablist" aria-label="导入方式">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'local'}
            className={mode === 'local' ? 'active' : ''}
            onClick={() => setMode('local')}
          >
            <Upload size={17} />
            本地视频
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'magnet'}
            className={mode === 'magnet' ? 'active' : ''}
            onClick={() => setMode('magnet')}
          >
            <Link2 size={17} />
            磁力链接
          </button>
        </div>

        {mode === 'local' ? (
          <div className="local-import">
            <label
              className="file-dropzone"
              htmlFor="local-video-file"
              onDragOver={(event) => event.preventDefault()}
              onDrop={onDrop}
            >
              {loading ? <LoaderCircle className="spin" size={30} /> : <FileVideo size={30} />}
              <strong>{loading ? '正在读取媒体信息' : '选择或拖入 MP4 / WebM'}</strong>
              <span>文件只在当前会话中使用</span>
              <input
                id="local-video-file"
                type="file"
                accept="video/mp4,video/webm,.mp4,.webm"
                onChange={onFileChange}
                disabled={loading}
              />
            </label>

            {error && (
              <p className="import-error" role="alert">
                <AlertCircle size={16} />
                {error}
              </p>
            )}

            {media && (
              <div className="selected-media">
                <img src={media.posterUrl} alt="导入视频自动提取的封面" />
                <div>
                  <strong>{media.file.name}</strong>
                  <span>
                    {formatDuration(media.durationSeconds)} · {media.width} × {media.height} ·{' '}
                    {(media.file.size / 1024 / 1024).toFixed(1)} MB
                  </span>
                  <small>
                    <CheckCircle2 size={14} />
                    浏览器已读取真实媒体
                  </small>
                </div>
              </div>
            )}
            <fieldset className="analysis-mode-picker">
              <legend>字幕生成模式</legend>
              <div role="radiogroup" aria-label="字幕生成模式">
                <button
                  type="button"
                  role="radio"
                  aria-checked={analysisMode === 'fast'}
                  className={analysisMode === 'fast' ? 'active' : ''}
                  onClick={() => setAnalysisMode('fast')}
                >
                  <Gauge size={17} aria-hidden="true" />
                  <span><strong>快速</strong><small>Paraformer-zh</small></span>
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={analysisMode === 'precise'}
                  className={analysisMode === 'precise' ? 'active' : ''}
                  onClick={() => setAnalysisMode('precise')}
                  disabled={preciseModelReady !== true}
                >
                  <Target size={17} aria-hidden="true" />
                  <span><strong>精准</strong><small>Whisper large-v3</small></span>
                </button>
              </div>
              <p>
                {analysisMode === 'fast'
                  ? preciseModelReady === false
                    ? '精准模型尚未安装完成，当前仅开放快速模式。'
                    : '适合日常整理，优先缩短等待时间。'
                  : '适合口音、专名或嘈杂音轨；CPU 环境处理 9 分钟视频约需 17 分钟。'}
              </p>
            </fieldset>
            <div className="analysis-privacy-note">
              <AlertCircle size={16} />
              <p>
                视频仅用于生成字幕，处理完成后删除临时文件；MiniMax-M3 会在一次请求中保守
                校对低置信词并生成摘要。
              </p>
            </div>
          </div>
        ) : (
          <div className="magnet-import">
            <label htmlFor="magnet-url">迅雷磁力链接</label>
            <textarea
              id="magnet-url"
              value={magnet}
              onChange={(event) => {
                setMagnet(event.target.value)
                setMagnetStatus(null)
              }}
              placeholder="magnet:?xt=urn:btih:..."
              rows={4}
            />
            <div className="integration-notice">
              <AlertCircle size={18} />
              <div>
                <strong>云盘自动转存需要开放接口</strong>
                <p>
                  当前可调用系统中的迅雷客户端处理磁链；下载完成后再从“本地视频”导入。
                  云盘自动转存仍需账号鉴权和官方开放接口，本 Demo 不会伪造成功状态。
                </p>
              </div>
            </div>
            {magnet && !validMagnet && <p className="field-error">请输入有效的 BTIH 磁力链接</p>}
            {magnetStatus && (
              <p className={`magnet-status ${magnetStatus.tone}`} role="status">
                {magnetStatus.tone === 'success' ? (
                  <CheckCircle2 size={16} />
                ) : (
                  <AlertCircle size={16} />
                )}
                {magnetStatus.detail}
              </p>
            )}
          </div>
        )}

        <footer className="import-dialog-actions">
          <button type="button" className="button button-secondary" onClick={close}>
            取消
          </button>
          {mode === 'local' ? (
            <button
              type="button"
              className="button button-primary"
              onClick={confirmLocalImport}
              disabled={!media || loading}
            >
              <Upload size={16} />
              导入片库
            </button>
          ) : (
            <>
              {magnetStatus?.tone === 'error' && (
                <button type="button" className="button button-secondary" onClick={copyMagnet}>
                  <Copy size={16} />
                  复制链接
                </button>
              )}
              <button
                type="button"
                className="button button-primary"
                disabled={!validMagnet || magnetLaunching}
                onClick={openMagnet}
              >
                {magnetLaunching ? <LoaderCircle className="spin" size={16} /> : <Link2 size={16} />}
                {magnetLaunching ? '正在唤起' : '在迅雷中打开'}
              </button>
            </>
          )}
        </footer>
      </section>
    </div>
  )
}

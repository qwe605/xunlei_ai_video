import {
  ArrowLeft,
  Captions,
  Check,
  ChevronRight,
  CirclePlay,
  MessageSquareText,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react'
import Plyr from 'plyr'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import type { Video, VideoQa } from '../data/schema'
import { answerVideoQuestion } from '../lib/search'
import { clampTime, formatDuration } from '../lib/time'

interface PlayerPageProps {
  video: Video
  startSeconds: number
  onBack: () => void
}

interface TranscriptCue {
  id: string
  startSeconds: number
  endSeconds: number
  text: string
}

interface SubtitleTrackMeta {
  srcLang: string
  label: string
}

const getSubtitleTrackMeta = (video: Video): SubtitleTrackMeta => {
  const languageHint = `${video.language} ${video.subtitlesUrl ?? ''}`.toLowerCase()
  // 浏览器字幕菜单只看 <track> 元数据；这里用视频语言和 VTT 文件名兜底，避免中文样例显示成 English。
  if (
    languageHint.includes('zh') ||
    languageHint.includes('中文') ||
    languageHint.includes('简体')
  ) {
    return { srcLang: 'zh-CN', label: '简体中文' }
  }
  return { srcLang: 'en', label: 'English' }
}

const parseTimestamp = (value: string) => {
  const [hours, minutes, seconds] = value.split(':')
  return Number(hours) * 3600 + Number(minutes) * 60 + Number(seconds)
}

const parseVtt = (content: string): TranscriptCue[] =>
  content
    .replace(/^\uFEFF/, '')
    .split(/\r?\n\r?\n/)
    .flatMap((block, index) => {
      const lines = block.split(/\r?\n/).filter(Boolean)
      const timingIndex = lines.findIndex((line) => line.includes(' --> '))
      if (timingIndex < 0) return []
      const [start, end] = lines[timingIndex].split(' --> ')
      const text = lines.slice(timingIndex + 1).join(' ').replace(/<[^>]+>/g, '').trim()
      if (!text) return []
      return [
        {
          id: `cue-${index}`,
          startSeconds: parseTimestamp(start),
          endSeconds: parseTimestamp(end.split(' ')[0]),
          text,
        },
      ]
    })

export function PlayerPage({ video, startSeconds, onBack }: PlayerPageProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const playerRef = useRef<Plyr | null>(null)
  const [currentTime, setCurrentTime] = useState(startSeconds)
  const [activeTab, setActiveTab] = useState<'chapters' | 'transcript' | 'ask'>('chapters')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<VideoQa | null | 'no-evidence'>(null)
  const [transcript, setTranscript] = useState<TranscriptCue[]>([])

  useEffect(() => {
    let cancelled = false
    setTranscript([])
    if (!video.subtitlesUrl) return

    // VTT 只作为不可信模型/外部产物读取；解析失败时保持空状态，不向播放器注入 HTML。
    void fetch(video.subtitlesUrl)
      .then((response) => {
        if (!response.ok) throw new Error(`字幕加载失败：${response.status}`)
        return response.text()
      })
      .then((content) => {
        if (!cancelled) setTranscript(parseVtt(content))
      })
      .catch(() => {
        if (!cancelled) setTranscript([])
      })

    return () => {
      cancelled = true
    }
  }, [video.subtitlesUrl])

  useEffect(() => {
    const element = videoRef.current
    if (!element) return

    const player = new Plyr(element, {
      controls: [
        'play-large',
        'play',
        'progress',
        'current-time',
        'duration',
        'mute',
        'volume',
        'captions',
        'settings',
        'fullscreen',
      ],
      captions: { active: true, language: 'auto', update: true },
      settings: ['captions', 'speed'],
      keyboard: { focused: true, global: false },
      tooltips: { controls: true, seek: true },
    })
    playerRef.current = player

    let initialSeekApplied = false
    const seekWhenReady = () => {
      if (
        initialSeekApplied ||
        element.readyState < HTMLMediaElement.HAVE_METADATA ||
        !Number.isFinite(element.duration)
      ) {
        return
      }

      const target = clampTime(startSeconds, video.durationSeconds)
      // 初始化阶段只写原生媒体时间。Plyr 尚未 ready 时写 player.currentTime
      // 可能被内部初始化流程重置为 0；原生 timeupdate 会同步更新 Plyr 控制条。
      element.currentTime = target
      setCurrentTime(target)
      initialSeekApplied = true
    }
    const updateTime = () => setCurrentTime(player.currentTime)

    player.on('ready', seekWhenReady)
    player.on('timeupdate', updateTime)
    element.addEventListener('loadedmetadata', seekWhenReady)
    element.addEventListener('canplay', seekWhenReady)
    if (element.readyState >= HTMLMediaElement.HAVE_METADATA) {
      seekWhenReady()
    }

    return () => {
      player.off('ready', seekWhenReady)
      player.off('timeupdate', updateTime)
      element.removeEventListener('loadedmetadata', seekWhenReady)
      element.removeEventListener('canplay', seekWhenReady)
      player.destroy()
      playerRef.current = null
    }
  }, [startSeconds, video.durationSeconds, video.id])

  const currentChapter = useMemo(
    () =>
      video.chapters.find(
        (chapter) => currentTime >= chapter.startSeconds && currentTime < chapter.endSeconds,
      ),
    [currentTime, video.chapters],
  )
  const currentCue = useMemo(
    () =>
      transcript.find(
        (cue) => currentTime >= cue.startSeconds && currentTime < cue.endSeconds,
      ),
    [currentTime, transcript],
  )
  const recommendedQuestions = video.qa.map((item) => item.question)
  const subtitleTrackMeta = useMemo(() => getSubtitleTrackMeta(video), [video])

  const seekTo = (seconds: number) => {
    const target = clampTime(seconds, video.durationSeconds)
    if (videoRef.current) {
      videoRef.current.currentTime = target
    }
    if (playerRef.current) {
      playerRef.current.currentTime = target
      void playerRef.current.play()
    }
    setCurrentTime(target)
  }

  const ask = (event?: FormEvent, suggestedQuestion?: string) => {
    event?.preventDefault()
    const nextQuestion = (suggestedQuestion ?? question).trim()
    if (!nextQuestion) return
    setQuestion(nextQuestion)
    setActiveTab('ask')
    setAnswer(answerVideoQuestion(video, nextQuestion) ?? 'no-evidence')
  }

  return (
    <main className="player-page" id="main-content">
      <header className="player-header">
        <button type="button" className="back-button player-back" onClick={onBack}>
          <ArrowLeft size={17} aria-hidden="true" />
          返回详情
        </button>
        <div>
          <h1>{video.title}</h1>
          <p>{currentChapter ? `正在播放：${currentChapter.title}` : video.shortDescription}</p>
        </div>
        <span className="evidence-status">
          <Check size={15} aria-hidden="true" />
          回答仅使用当前视频
        </span>
      </header>

      <div className="player-workspace">
        <section className="player-stage" aria-label="视频播放器">
          <video
            ref={videoRef}
            controls
            playsInline
            poster={video.posterUrl}
            data-testid="demo-video"
          >
            <source src={video.videoUrl} type={video.videoMimeType} />
            {video.subtitlesUrl && (
              <track
                kind="subtitles"
                src={video.subtitlesUrl}
                srcLang={subtitleTrackMeta.srcLang}
                label={subtitleTrackMeta.label}
                default
              />
            )}
            您的浏览器暂不支持 HTML5 视频播放。
          </video>
          <div className="now-playing">
            <span>{formatDuration(currentTime)}</span>
            <div>
              <strong>{currentChapter?.title ?? '视频播放中'}</strong>
              <small>{currentChapter?.summary ?? '可从右侧章节或问答片段快速跳转'}</small>
            </div>
          </div>
        </section>

        <aside className="player-sidebar" aria-label="视频内容助手">
          <div className="player-tabs" role="tablist" aria-label="播放器侧栏">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'chapters'}
              className={activeTab === 'chapters' ? 'active' : ''}
              onClick={() => setActiveTab('chapters')}
            >
              <CirclePlay size={17} aria-hidden="true" />
              章节
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'transcript'}
              className={activeTab === 'transcript' ? 'active' : ''}
              onClick={() => setActiveTab('transcript')}
            >
              <Captions size={17} aria-hidden="true" />
              字幕
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'ask'}
              className={activeTab === 'ask' ? 'active' : ''}
              onClick={() => setActiveTab('ask')}
            >
              <MessageSquareText size={17} aria-hidden="true" />
              问视频
            </button>
          </div>

          {activeTab === 'chapters' ? (
            <div className="player-chapters">
              {video.chapters.map((chapter) => (
                <button
                  type="button"
                  className={currentChapter?.id === chapter.id ? 'active' : ''}
                  onClick={() => seekTo(chapter.startSeconds)}
                  key={chapter.id}
                >
                  <time>{formatDuration(chapter.startSeconds)}</time>
                  <span>
                    <strong>{chapter.title}</strong>
                    <small>{chapter.summary}</small>
                  </span>
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              ))}
            </div>
          ) : activeTab === 'transcript' ? (
            <div className="transcript-panel" aria-label="同步字幕">
              <div className="transcript-heading">
                <strong>
                  {video.subtitleOrigin === 'ai-generated' ? 'AI 自动生成字幕' : '原视频字幕'}
                </strong>
                <span>{video.asrModel ?? 'TimedText'}</span>
              </div>
              {transcript.length > 0 ? (
                <div className="transcript-list">
                  {transcript.map((cue) => (
                    <button
                      type="button"
                      className={currentCue?.id === cue.id ? 'active' : ''}
                      onClick={() => seekTo(cue.startSeconds)}
                      key={cue.id}
                    >
                      <time>{formatDuration(cue.startSeconds)}</time>
                      <span>{cue.text}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="transcript-empty" role="status">
                  <Captions size={22} aria-hidden="true" />
                  <strong>AI 字幕生成中</strong>
                  <p>音轨已进入转写队列，完成后会在这里显示可跳转字幕。</p>
                </div>
              )}
            </div>
          ) : (
            <div className="ask-panel">
              <div className="ask-intro">
                <Sparkles size={20} aria-hidden="true" />
                <div>
                  <strong>问问这个视频</strong>
                  <p>回答会附带字幕依据和可跳转片段。</p>
                </div>
              </div>

              {!answer && (
                <div className="question-suggestions">
                  {recommendedQuestions.map((suggestion) => (
                    <button type="button" key={suggestion} onClick={() => ask(undefined, suggestion)}>
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}

              {answer === 'no-evidence' && (
                <div className="answer-block no-evidence" role="status">
                  <strong>当前视频中没有找到相关内容</strong>
                  <p>AI 没有检索到可以核验的字幕或章节，因此不会使用常识补答。</p>
                </div>
              )}

              {answer && answer !== 'no-evidence' && (
                <div className="answer-block" role="status">
                  <div className="answer-label">
                    <Sparkles size={16} aria-hidden="true" />
                    AI 回答
                    <span>置信度 {Math.round(answer.confidence * 100)}%</span>
                  </div>
                  <p className="answer-text">{answer.answer}</p>
                  <p className="evidence-label">视频依据</p>
                  {answer.citations.map((citation) => (
                    <button
                      type="button"
                      className="citation"
                      onClick={() => seekTo(citation.startSeconds)}
                      key={citation.id}
                    >
                      <CirclePlay size={20} aria-hidden="true" />
                      <span>
                        <strong>
                          {formatDuration(citation.startSeconds)}—{formatDuration(citation.endSeconds)}
                        </strong>
                        <small>{citation.text}</small>
                      </span>
                    </button>
                  ))}
                  <div className="answer-feedback">
                    <span>这个回答有帮助吗？</span>
                    <button type="button" aria-label="有帮助" title="有帮助">
                      <ThumbsUp size={15} />
                    </button>
                    <button type="button" aria-label="不相关" title="不相关">
                      <ThumbsDown size={15} />
                    </button>
                  </div>
                </div>
              )}

              <form className="ask-form" onSubmit={(event) => ask(event)}>
                <label htmlFor="video-question" className="sr-only">
                  向当前视频提问
                </label>
                <textarea
                  id="video-question"
                  rows={2}
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="例如：后面有没有讲登录失效？"
                  maxLength={160}
                />
                <button type="submit" aria-label="发送问题" title="发送问题" disabled={!question.trim()}>
                  <Send size={18} />
                </button>
              </form>
            </div>
          )}
        </aside>
      </div>
    </main>
  )
}

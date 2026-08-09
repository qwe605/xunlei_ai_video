import { useCallback, useEffect, useRef, useState } from 'react'
import { AppHeader } from '../components/AppHeader'
import { AppSidebar } from '../components/AppSidebar'
import { demoLibrary } from '../data/demoLibrary'
import { videoSchema, type Video } from '../data/schema'
import { AccountDialog } from '../features/account/AccountDialog'
import type { DemoSession } from '../features/account/accountSession'
import { readCurrentUser } from '../api/auth'
import {
  createBlockedJob,
  createQueuedJob,
  getBundledAnalysis,
  type AnalysisJob,
} from '../features/analysis-queue/analysisQueue'
import { createLocalAnalysis, readLocalAnalysis, type AnalysisMode } from '../api/analysis'
import {
  deletePersistedVideo,
  readPersistedVideo,
  readPersistedVideos,
  saveWatchProgress,
  updateVideoInformation,
  type VideoInformationUpdate,
} from '../api/videos'
import { ImportVideoDialog } from '../features/import-video/ImportVideoDialog'
import { navigateTo, routes, useAppRoute } from '../router'
import type { LibraryFilter } from '../types/library'
import { LibraryPage } from '../views/LibraryPage'
import { PlayerPage } from '../views/PlayerPage'
import { SearchPage } from '../views/SearchPage'
import { VideoDetailPage } from '../views/VideoDetailPage'

export function App() {
  const route = useAppRoute()
  const [videos, setVideos] = useState<Video[]>(demoLibrary)
  const [libraryFilter, setLibraryFilter] = useState<LibraryFilter>('all')
  const [importOpen, setImportOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [session, setSession] = useState<DemoSession | null>(null)
  const [sessionLoading, setSessionLoading] = useState(true)
  const [analysisJobs, setAnalysisJobs] = useState<AnalysisJob[]>(() =>
    demoLibrary
      .filter((video) => video.indexStatus !== 'ready')
      .map((video) => createBlockedJob(video)),
  )
  const localObjectUrls = useRef<string[]>([])
  const localFiles = useRef<Map<string, File>>(new Map())
  const localPosters = useRef<Map<string, File>>(new Map())
  const localAnalysisModes = useRef<Map<string, AnalysisMode>>(new Map())
  const analysisTimers = useRef<number[]>([])
  const activeAnalysisId = useRef<string | null>(null)

  const selectedVideo =
    'videoId' in route ? videos.find((video) => video.id === route.videoId) : undefined
  const handleSessionChange = (nextSession: DemoSession | null) => {
    localObjectUrls.current.forEach((url) => URL.revokeObjectURL(url))
    localObjectUrls.current = []
    localFiles.current.clear()
    localPosters.current.clear()
    localAnalysisModes.current.clear()
    setVideos(demoLibrary)
    setAnalysisJobs(
      demoLibrary
        .filter((video) => video.indexStatus !== 'ready')
        .map((video) => createBlockedJob(video)),
    )
    setSession(nextSession)
    if (nextSession && route.name !== 'library') {
      navigateTo(routes.library(), { replace: true })
    }
    if (!nextSession) {
      setAccountOpen(false)
      setImportOpen(false)
      navigateTo(routes.library(), { replace: true })
    }
  }

  useEffect(() => {
    let active = true
    void readCurrentUser()
      .then((current) => {
        if (active) setSession(current)
      })
      .catch(() => {
        if (active) setSession(null)
      })
      .finally(() => {
        if (active) setSessionLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    // 深链接里的视频 ID 可能已失效，回到片库而不是留下空白主内容。
    if ('videoId' in route && !selectedVideo) navigateTo(routes.library(), { replace: true })
  }, [route, selectedVideo])

  useEffect(() => {
    // 视图切换后把焦点交回主内容，键盘和读屏用户不必重新穿过整个导航栏。
    requestAnimationFrame(() => {
      document.getElementById('main-content')?.focus({ preventScroll: true })
    })
  }, [route])

  useEffect(
    () => () => {
      localObjectUrls.current.forEach((url) => URL.revokeObjectURL(url))
      analysisTimers.current.forEach((timer) => window.clearTimeout(timer))
    },
    [],
  )

  useEffect(() => {
    if (!session) return
    let active = true
    // 服务端片库是本地导入内容的事实来源；内置样例只在没有同名持久化记录时补充展示。
    void readPersistedVideos()
      .then((persistedVideos) => {
        if (!active || persistedVideos.length === 0) return
        setVideos([
          ...persistedVideos,
          ...demoLibrary.filter(
            (demo) => !persistedVideos.some((video) => video.id === demo.id),
          ),
        ])
      })
      .catch(() => {
        if (active) setVideos(demoLibrary)
      })
    return () => {
      active = false
    }
  }, [session])

  useEffect(() => {
    if (activeAnalysisId.current) return
    // 队列严格单任务执行，避免同一浏览器同时上传多个大视频拖垮本地模型服务。
    const nextJob = analysisJobs.find((job) => job.status === 'queued')
    if (!nextJob) return
    const video = videos.find((item) => item.id === nextJob.videoId)
    if (!video) return

    activeAnalysisId.current = nextJob.videoId
    const updateJob = (patch: Partial<AnalysisJob>) => {
      setAnalysisJobs((current) =>
        current.map((job) => (job.videoId === nextJob.videoId ? { ...job, ...patch } : job)),
      )
    }
    const schedule = (delay: number, callback: () => void) => {
      analysisTimers.current.push(window.setTimeout(callback, delay))
    }

    updateJob({
      status: 'processing',
      stage: '读取媒体',
      progress: 12,
      detail: '正在确认音轨、时长和已提取的封面。',
    })

    // 精准模式必须真实运行 large-v3，不能因为文件名命中内置样例而复用旧 FunASR 结果。
    const bundledAnalysis = nextJob.analysisMode === 'fast' ? getBundledAnalysis(video) : null
    if (!bundledAnalysis) {
      const runLocalAnalysis = async () => {
        try {
          let file = localFiles.current.get(video.id)
          if (!file && video.importSource === 'demo-public') {
            const response = await fetch(video.videoUrl)
            if (!response.ok) throw new Error('无法读取演示视频')
            file = new File([await response.blob()], video.originalFilename, {
              type: video.videoMimeType,
            })
          }
          if (!file) throw new Error('当前会话已丢失本地视频，请重新导入')

          updateJob({
            stage: '上传到 AI 分析服务',
            progress: 8,
            detail: '正在安全上传视频，分析完成后会写入服务端片库。',
          })
          const analysisMode = localAnalysisModes.current.get(video.id) ?? nextJob.analysisMode
          let remoteJob = await createLocalAnalysis(
            video.id,
            video.durationSeconds,
            file,
            analysisMode,
            {
              title: video.title,
              resolution: video.resolution,
              codec: video.codec,
              poster: localPosters.current.get(video.id),
            },
          )
          while (remoteJob.status === 'queued' || remoteJob.status === 'processing') {
            updateJob({
              status: 'processing',
              stage: remoteJob.stage,
              progress: remoteJob.progress,
              detail: remoteJob.detail,
            })
            await new Promise((resolve) => window.setTimeout(resolve, 750))
            remoteJob = await readLocalAnalysis(remoteJob.id)
          }

          if (remoteJob.status === 'failed' || !remoteJob.result) {
            throw new Error(remoteJob.detail)
          }

          const persistedVideo = await readPersistedVideo(video.id)
          setVideos((current) =>
            current.map((item) =>
              item.id === video.id
                ? videoSchema.parse({
                    ...persistedVideo,
                    thumbnailUrl: item.thumbnailUrl ?? persistedVideo.thumbnailUrl,
                    posterUrl: item.posterUrl,
                  })
                : item,
            ),
          )
          updateJob({
            status: 'completed',
            stage: '整理完成',
            progress: 100,
            detail: remoteJob.detail,
          })
        } catch (error) {
          const rawMessage = error instanceof Error ? error.message : 'AI 分析失败'
          const offline = /fetch|network|连接|Failed/i.test(rawMessage)
          const detail = offline
            ? 'AI 分析服务暂时不可用，请稍后重试。'
            : rawMessage
          updateJob({
            status: 'blocked',
            stage: offline ? 'AI 分析服务离线' : '整理失败',
            progress: 0,
            detail,
          })
          setVideos((current) =>
            current.map((item) =>
              item.id === video.id
                ? {
                    ...item,
                    indexStatus: 'failed',
                    organizeHint: detail,
                  }
                : item,
            ),
          )
        } finally {
          activeAnalysisId.current = null
        }
      }
      void runLocalAnalysis()
      return
    }

    schedule(650, () =>
      updateJob({
        stage: '生成字幕',
        progress: 45,
        detail: '正在载入该真实样例已生成的 34 段 faster-whisper 字幕。',
      }),
    )
    schedule(1_300, () =>
      updateJob({
        stage: '生成摘要与章节',
        progress: 76,
        detail: '正在校验摘要、关键词和章节时间范围。',
      }),
    )
    schedule(2_000, () => {
      setVideos((current) =>
        current.map((item) =>
          item.id === nextJob.videoId
            ? videoSchema.parse({ ...item, ...bundledAnalysis })
            : item,
        ),
      )
      updateJob({
        status: 'completed',
        stage: '整理完成',
        progress: 100,
        detail: '字幕、摘要、关键词和 3 个可跳转章节已经写入片库。',
      })
      activeAnalysisId.current = null
    })
  }, [analysisJobs, videos])

  const openVideo = (video: Video) => navigateTo(routes.detail(video.id))
  const playVideo = (video: Video, startSeconds = 0) =>
    navigateTo(routes.player(video.id, startSeconds))
  const updateWatchProgress = useCallback((targetVideo: Video, positionSeconds: number) => {
    setVideos((current) =>
      current.map((video) =>
        video.id === targetVideo.id
          ? { ...video, watchProgressSeconds: positionSeconds }
          : video,
      ),
    )
    void saveWatchProgress(targetVideo, positionSeconds).catch(() => undefined)
  }, [])
  const deleteVideo = useCallback(async (targetVideo: Video) => {
    await deletePersistedVideo(targetVideo.id)
    setVideos((current) => current.filter((video) => video.id !== targetVideo.id))
    setAnalysisJobs((current) => current.filter((job) => job.videoId !== targetVideo.id))
    navigateTo(routes.library())
  }, [])
  const correctVideo = useCallback(async (targetVideo: Video, payload: VideoInformationUpdate) => {
    const updated = await updateVideoInformation(targetVideo.id, payload)
    setVideos((current) => current.map((video) => (video.id === targetVideo.id ? updated : video)))
  }, [])
  const retryAnalysis = (videoId: string) => {
    setVideos((current) =>
      current.map((video) =>
        video.id === videoId
          ? {
              ...video,
              indexStatus: 'pending',
              organizeHint: '已重新加入 AI 整理队列',
            }
          : video,
      ),
    )
    setAnalysisJobs((current) =>
      current.map((job) =>
        job.videoId === videoId
          ? { ...job, status: 'queued', stage: '等待整理', progress: 0, detail: '已重新进入队列。' }
          : job,
      ),
    )
  }

  if (sessionLoading) {
    return <main className="auth-page" aria-busy="true" aria-label="正在确认登录状态" />
  }

  if (!session) {
    return (
      <main className="auth-page" id="main-content" tabIndex={-1}>
        <section className="auth-intro" aria-labelledby="auth-page-title">
          <div className="brand-mark" aria-hidden="true">
            迅雷
          </div>
          <div>
            <h1 id="auth-page-title">迅雷 AI 片库</h1>
            <p>请先登录或注册账号，再进入自己的片库、导入视频和播放页面。</p>
          </div>
        </section>
        <AccountDialog
          session={null}
          onSessionChange={handleSessionChange}
          variant="page"
        />
      </main>
    )
  }

  if (route.name === 'player' && selectedVideo) {
    return (
      <PlayerPage
        video={selectedVideo}
        startSeconds={route.startSeconds}
        onBack={() => navigateTo(routes.detail(selectedVideo.id))}
        onProgress={(positionSeconds) => updateWatchProgress(selectedVideo, positionSeconds)}
      />
    )
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <AppHeader
        initialQuery={route.name === 'search' ? route.query : ''}
        onSearch={(query) => navigateTo(routes.search(query))}
        onGoHome={() => navigateTo(routes.library())}
        onImport={() => setImportOpen(true)}
        accountName={session?.displayName ?? '登录 / 注册'}
        onAccount={() => setAccountOpen(true)}
      />
      <AppSidebar
        videos={videos}
        activeFilter={libraryFilter}
        onFilterChange={(filter) => {
          setLibraryFilter(filter)
          navigateTo(routes.library())
        }}
      />
      <div className="app-content">
        {route.name === 'library' && (
          <LibraryPage
            videos={videos}
            onOpen={openVideo}
            onPlay={playVideo}
            onSearch={(query) => navigateTo(routes.search(query))}
            filter={libraryFilter}
            onFilterChange={setLibraryFilter}
            analysisJobs={analysisJobs}
            onRetryAnalysis={retryAnalysis}
            onDismissAnalysis={(videoId) =>
              setAnalysisJobs((current) => current.filter((job) => job.videoId !== videoId))
            }
          />
        )}
        {route.name === 'search' && (
          <SearchPage
            query={route.query}
            videos={videos}
            onBack={() => navigateTo(routes.library())}
            onOpen={openVideo}
            onPlay={playVideo}
          />
        )}
        {route.name === 'detail' && selectedVideo && (
          <VideoDetailPage
            video={selectedVideo}
            onBack={() => navigateTo(routes.library())}
            onPlay={playVideo}
            onDelete={deleteVideo}
            onCorrect={correctVideo}
          />
        )}
      </div>
      {importOpen && (
        <ImportVideoDialog
          onClose={() => setImportOpen(false)}
          onImport={(video, file, analysisMode, posterFile) => {
            localObjectUrls.current.push(video.videoUrl)
            localFiles.current.set(video.id, file)
            localPosters.current.set(video.id, posterFile)
            localAnalysisModes.current.set(video.id, analysisMode)
            setVideos((current) => [video, ...current])
            setAnalysisJobs((current) => [createQueuedJob(video, analysisMode), ...current])
            setLibraryFilter('all')
            navigateTo(routes.library())
            setImportOpen(false)
          }}
        />
      )}
      {accountOpen && (
        <AccountDialog
          session={session}
          onSessionChange={handleSessionChange}
          onClose={() => setAccountOpen(false)}
        />
      )}
    </div>
  )
}

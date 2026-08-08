import { useSyncExternalStore } from 'react'

export type AppRoute =
  | { name: 'library' }
  | { name: 'search'; query: string }
  | { name: 'detail'; videoId: string }
  | { name: 'player'; videoId: string; startSeconds: number }

const ROUTE_EVENT = 'xunlei:route-change'

const decodeSegment = (value: string) => {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

export function parseRoute(url: URL): AppRoute {
  if (url.pathname === '/search') {
    return { name: 'search', query: url.searchParams.get('q')?.trim() ?? '' }
  }

  const player = url.pathname.match(/^\/videos\/([^/]+)\/play$/)
  if (player) {
    const requestedTime = Number(url.searchParams.get('t') ?? 0)
    return {
      name: 'player',
      videoId: decodeSegment(player[1]),
      startSeconds: Number.isFinite(requestedTime) ? Math.max(0, requestedTime) : 0,
    }
  }

  const detail = url.pathname.match(/^\/videos\/([^/]+)$/)
  if (detail) return { name: 'detail', videoId: decodeSegment(detail[1]) }
  return { name: 'library' }
}

let cachedHref = ''
let cachedRoute: AppRoute = { name: 'library' }

const currentRoute = () => {
  // useSyncExternalStore 要求未导航时返回同一引用，否则 React 会误判为持续更新。
  if (cachedHref !== window.location.href) {
    cachedHref = window.location.href
    cachedRoute = parseRoute(new URL(cachedHref))
  }
  return cachedRoute
}

const serverRoute: AppRoute = { name: 'library' }

const subscribe = (onStoreChange: () => void) => {
  window.addEventListener('popstate', onStoreChange)
  window.addEventListener(ROUTE_EVENT, onStoreChange)
  return () => {
    window.removeEventListener('popstate', onStoreChange)
    window.removeEventListener(ROUTE_EVENT, onStoreChange)
  }
}

export function useAppRoute(): AppRoute {
  return useSyncExternalStore(subscribe, currentRoute, () => serverRoute)
}

export function navigateTo(path: string, options?: { replace?: boolean }) {
  const next = new URL(path, window.location.origin)
  if (next.origin !== window.location.origin) throw new Error('只允许应用内导航')
  window.history[options?.replace ? 'replaceState' : 'pushState']({}, '', next)
  window.dispatchEvent(new Event(ROUTE_EVENT))
}

export const routes = {
  library: () => '/',
  search: (query: string) => `/search?q=${encodeURIComponent(query)}`,
  detail: (videoId: string) => `/videos/${encodeURIComponent(videoId)}`,
  player: (videoId: string, startSeconds = 0) =>
    `/videos/${encodeURIComponent(videoId)}/play?t=${Math.max(0, startSeconds)}`,
}

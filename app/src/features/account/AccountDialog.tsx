import {
  AlertCircle,
  LogIn,
  LogOut,
  ShieldCheck,
  UserPlus,
  X,
} from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { demoSessionStorageKey, type DemoSession } from './accountSession'

interface StoredAccount extends DemoSession {
  salt: string
  passwordHash: string
}

interface AccountDialogProps {
  session: DemoSession | null
  onSessionChange: (session: DemoSession | null) => void
  onClose?: () => void
  variant?: 'modal' | 'page'
}

const ACCOUNT_KEY = 'xunlei-ai-demo-account'

const bytesToBase64 = (bytes: Uint8Array) => {
  let binary = ''
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary)
}

const derivePasswordHash = async (password: string, salt: Uint8Array) => {
  const material = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveBits'],
  )
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt: new Uint8Array(salt), iterations: 120_000, hash: 'SHA-256' },
    material,
    256,
  )
  return bytesToBase64(new Uint8Array(bits))
}

const base64ToBytes = (value: string) =>
  Uint8Array.from(atob(value), (character) => character.charCodeAt(0))

export function AccountDialog({
  session,
  onSessionChange,
  onClose,
  variant = 'modal',
}: AccountDialogProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const isPageGate = variant === 'page'

  const register = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (displayName.trim().length < 2) {
      setError('昵称至少需要 2 个字符')
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('请输入有效邮箱')
      return
    }
    if (password.length < 8) {
      setError('密码至少需要 8 个字符')
      return
    }

    setSubmitting(true)
    try {
      const salt = crypto.getRandomValues(new Uint8Array(16))
      const account: StoredAccount = {
        displayName: displayName.trim(),
        email: email.trim().toLowerCase(),
        salt: bytesToBase64(salt),
        passwordHash: await derivePasswordHash(password, salt),
      }
      const nextSession = { displayName: account.displayName, email: account.email }
      localStorage.setItem(ACCOUNT_KEY, JSON.stringify(account))
      localStorage.setItem(demoSessionStorageKey, JSON.stringify(nextSession))
      onSessionChange(nextSession)
    } finally {
      setSubmitting(false)
    }
  }

  const login = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const value = localStorage.getItem(ACCOUNT_KEY)
      if (!value) {
        setError('本机还没有 Demo 账号，请先注册')
        return
      }
      const account = JSON.parse(value) as StoredAccount
      const passwordHash = await derivePasswordHash(password, base64ToBytes(account.salt))
      if (account.email !== email.trim().toLowerCase() || account.passwordHash !== passwordHash) {
        setError('邮箱或密码不正确')
        return
      }
      const nextSession = { displayName: account.displayName, email: account.email }
      localStorage.setItem(demoSessionStorageKey, JSON.stringify(nextSession))
      onSessionChange(nextSession)
    } finally {
      setSubmitting(false)
    }
  }

  const logout = () => {
    localStorage.removeItem(demoSessionStorageKey)
    setMode('login')
    setPassword('')
    setError('')
    onSessionChange(null)
  }

  return (
    <div
      className={isPageGate ? 'account-page-panel' : 'modal-backdrop'}
      role="presentation"
      onMouseDown={onClose}
    >
      <section
        className={isPageGate ? 'account-dialog account-dialog-page' : 'account-dialog'}
        role="dialog"
        aria-modal={!isPageGate}
        aria-labelledby="account-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="import-dialog-header">
          <div>
            <h2 id="account-title">{session ? '我的片库账号' : '登录迅雷 AI 片库'}</h2>
            <p>{session ? '管理当前浏览器中的本地会话' : '建立仅用于体验 Demo 的本地账号'}</p>
          </div>
          {onClose && (
            <button type="button" className="icon-button" onClick={onClose} aria-label="关闭账号窗口">
              <X size={19} />
            </button>
          )}
        </header>

        {session ? (
          <div className="account-profile">
            <section className="local-account-summary">
              <span className="profile-avatar">{session.displayName.slice(0, 1).toUpperCase()}</span>
              <div>
                <strong>{session.displayName}</strong>
                <span>{session.email}</span>
                <small>
                  <ShieldCheck size={14} />
                  Demo 本地账号
                </small>
              </div>
              <button type="button" className="button button-secondary" onClick={logout}>
                <LogOut size={15} />
                退出
              </button>
            </section>
            <p className="local-auth-note account-profile-note">
              此账号不会连接迅雷账号或读取云盘。正式产品应由迅雷内部账号体系直接提供当前用户身份与文件权限。
            </p>
          </div>
        ) : (
          <>
            <div className="import-mode-tabs account-tabs" role="tablist" aria-label="账号操作">
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'login'}
                className={mode === 'login' ? 'active' : ''}
                onClick={() => {
                  setMode('login')
                  setError('')
                }}
              >
                <LogIn size={17} />
                登录
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'register'}
                className={mode === 'register' ? 'active' : ''}
                onClick={() => {
                  setMode('register')
                  setError('')
                }}
              >
                <UserPlus size={17} />
                注册
              </button>
            </div>

            <form className="account-form" onSubmit={mode === 'register' ? register : login}>
              {mode === 'register' && (
                <label>
                  昵称
                  <input
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    autoComplete="nickname"
                    placeholder="用于片库显示"
                  />
                </label>
              )}
              <label>
                邮箱
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  placeholder="name@example.com"
                />
              </label>
              <label>
                密码
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                  placeholder="至少 8 个字符"
                />
              </label>
              {error && (
                <p className="import-error" role="alert">
                  <AlertCircle size={16} />
                  {error}
                </p>
              )}
              <button type="submit" className="button button-primary account-submit" disabled={submitting}>
                {mode === 'register' ? <UserPlus size={16} /> : <LogIn size={16} />}
                {submitting ? '处理中' : mode === 'register' ? '创建并登录' : '登录'}
              </button>
              <p className="local-auth-note">
                Demo 账号仅保存在当前浏览器；密码使用 PBKDF2-SHA256 派生后存储，不会发送到服务器。
              </p>
            </form>
          </>
        )}
      </section>
    </div>
  )
}

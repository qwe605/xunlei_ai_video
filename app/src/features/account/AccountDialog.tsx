import { AlertCircle, LogIn, LogOut, ShieldCheck, UserPlus, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { loginAccount, logoutAccount, registerAccount } from '../../api/auth'
import type { DemoSession } from './accountSession'

interface AccountDialogProps {
  session: DemoSession | null
  onSessionChange: (session: DemoSession | null) => void
  onClose?: () => void
  variant?: 'modal' | 'page'
}

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
      const nextSession = await registerAccount(
        displayName.trim(),
        email.trim().toLowerCase(),
        password,
      )
      onSessionChange(nextSession)
    } catch (registerError) {
      setError(registerError instanceof Error ? registerError.message : '注册失败，请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  const login = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const nextSession = await loginAccount(email.trim().toLowerCase(), password)
      onSessionChange(nextSession)
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : '登录失败，请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  const logout = async () => {
    setSubmitting(true)
    setError('')
    try {
      await logoutAccount()
      setMode('login')
      setPassword('')
      onSessionChange(null)
    } catch (logoutError) {
      setError(logoutError instanceof Error ? logoutError.message : '退出登录失败')
    } finally {
      setSubmitting(false)
    }
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
            <p>{session ? '管理当前登录账号' : '登录后进入自己的视频片库'}</p>
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
                  服务端安全会话
                </small>
              </div>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => void logout()}
                disabled={submitting}
              >
                <LogOut size={15} />
                退出
              </button>
            </section>
            <p className="local-auth-note account-profile-note">
              本地导入视频、AI 结果和观看进度仅对当前账号可见。
            </p>
            {error && <p className="import-error" role="alert">{error}</p>}
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
            </form>
          </>
        )}
      </section>
    </div>
  )
}

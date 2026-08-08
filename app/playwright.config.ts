import { defineConfig, devices } from '@playwright/test'

const externalBaseUrl = process.env.DEMO_BASE_URL
const browserChannel = process.env.CI ? undefined : 'chrome'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  // 视觉截图会同时等待字体和整页布局稳定；限制并发可避免 CI/普通笔记本资源争用。
  // 真实视频解码会占用更多内存；双并发可避免桌面与移动项目同时加载 WebM 时页面崩溃。
  workers: 2,
  reporter: [['list'], ['html', { open: 'never' }]],
  expect: {
    timeout: 15_000,
    toHaveScreenshot: {
      animations: 'disabled',
      caret: 'hide',
      maxDiffPixels: 300,
      threshold: 0.2,
    },
  },
  use: {
    baseURL: externalBaseUrl ?? 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  // 设置 DEMO_BASE_URL 时直接验收离线包或部署地址，不再额外启动 Vite。
  webServer: externalBaseUrl
    ? undefined
    : {
        command: 'npm.cmd run preview -- --host 127.0.0.1',
        url: 'http://127.0.0.1:4173',
        reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === '1',
      },
  projects: [
    {
      name: 'desktop',
      use: {
        ...devices['Desktop Chrome'],
        channel: browserChannel,
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: 'mobile',
      use: { ...devices['Pixel 7'], channel: browserChannel },
    },
  ],
})

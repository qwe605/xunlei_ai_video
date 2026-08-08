import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'

async function registerDemoAccount(page: import('@playwright/test').Page, suffix = 'e2e') {
  await page.getByRole('tab', { name: '注册' }).click()
  await page.getByLabel('昵称').fill(`评审账号${suffix}`)
  await page.getByLabel('邮箱').fill(`judge-${suffix}@example.com`)
  await page.getByLabel('密码').fill('review-pass-2026')
  await page.getByRole('button', { name: '创建并登录' }).click()
  await expect(page.getByRole('heading', { name: '全部视频' })).toBeVisible()
}

async function openLibraryAsLoggedInUser(page: import('@playwright/test').Page, path = '/', suffix = 'e2e') {
  await page.goto(path)
  await expect(page.getByRole('heading', { name: '登录迅雷 AI 片库' })).toBeVisible()
  await registerDemoAccount(page, suffix)
}

test('从自然语言搜索到视频片段跳转形成完整闭环', async ({ page }) => {
  const browserErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text())
  })

  await openLibraryAsLoggedInUser(page, '/', 'search-flow')
  await expect(page.getByRole('heading', { name: '全部视频' })).toBeVisible()
  await expect(page.getByRole('article')).toHaveCount(4)

  await page.getByRole('button', { name: /找讲 Python 名字由来的视频/ }).click()
  await expect(page.getByRole('heading', { name: '“找讲 Python 名字由来的视频”' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Python 入门：语言、语法与保留字' })).toBeVisible()
  await expect(page.getByText(/相关章节位于 02:04/)).toBeVisible()

  await page.getByRole('button', { name: '查看详情' }).first().click()
  await expect(page.getByRole('heading', { name: '打开前先看懂' })).toBeVisible()
  await page.getByRole('button', { name: /Python 名字的由来/ }).click()

  await expect(page.getByRole('heading', { name: 'Python 入门：语言、语法与保留字' })).toBeVisible()
  await expect(page.locator('.now-playing > span')).toHaveText('02:04')
  await expect
    .poll(() => page.getByTestId('demo-video').evaluate((element) => (element as HTMLVideoElement).currentTime))
    .toBeGreaterThanOrEqual(124)
  await page.getByRole('tab', { name: '问视频' }).click()
  await page.getByRole('button', { name: '后面有没有讲保留字？' }).click()
  await page.getByRole('button', { name: /11:28—11:40/ }).click()

  await expect(page.locator('.now-playing > span')).toHaveText('11:28')
  await expect
    .poll(() => page.getByTestId('demo-video').evaluate((element) => (element as HTMLVideoElement).currentTime))
    .toBeGreaterThanOrEqual(688)
  expect(browserErrors).toEqual([])
})

test('无证据问题会明确拒答', async ({ page }) => {
  await openLibraryAsLoggedInUser(page, '/', 'no-evidence')
  await page.getByRole('button', { name: /查看《Python 入门/ }).click()
  await page.getByRole('button', { name: /开始播放/ }).click()
  await page.getByRole('tab', { name: '问视频' }).click()

  await page.getByLabel('向当前视频提问').fill('老师有没有推荐北京餐厅？')
  await page.getByRole('button', { name: '发送问题' }).click()

  await expect(page.getByText('当前视频中没有找到相关内容')).toBeVisible()
  await expect(page.getByRole('button', { name: /00:.*—/ })).toHaveCount(0)
})

test('详情与播放器深链接支持刷新和浏览器返回', async ({ page }) => {
  await openLibraryAsLoggedInUser(page, '/videos/python-as-a-language', 'deep-link')
  await page.goto('/videos/python-as-a-language')
  await expect(page.getByRole('heading', { name: 'Python 入门：语言、语法与保留字' })).toBeVisible()

  await page.getByRole('button', { name: /Python 名字的由来/ }).click()
  await expect(page).toHaveURL(/\/videos\/python-as-a-language\/play\?t=124$/)
  await expect(page.locator('.now-playing > span')).toHaveText('02:04')

  await page.goBack()
  await expect(page).toHaveURL(/\/videos\/python-as-a-language$/)
  await expect(page.getByRole('heading', { name: '打开前先看懂' })).toBeVisible()
})

test('中文内置视频展示精准处理后的字幕结果', async ({ page }) => {
  await openLibraryAsLoggedInUser(page, '/', 'subtitle')
  await page.getByRole('button', { name: /查看《永夜生存/ }).click()
  await expect(page.getByText(/AI 自动字幕：faster-whisper large-v3 \+ stable-ts/)).toBeVisible()
  await page.getByRole('button', { name: '开始播放' }).click()
  await page.getByRole('tab', { name: '字幕' }).click()

  await expect(page.getByText('AI 自动生成字幕')).toBeVisible()
  await expect(page.getByText('faster-whisper large-v3 + stable-ts · CPU int8 + MiniMax-M3')).toBeVisible()
  await expect(page.getByText(/驻军进入城镇后立刻行动/)).toBeVisible()
  await expect(page.getByText('乱世用重典')).toBeVisible()
  await expect(page.getByText('一位士兵命途的超凡者')).toBeVisible()
  await expect(page.getByText('乱世用重点没有')).toHaveCount(0)
  await expect(page.getByText('一位士兵命途的迎接')).toHaveCount(0)
  await expect(page.locator('button[data-plyr="captions"]')).toBeVisible()
  await expect(page.getByRole('tab', { name: '精修' })).toHaveCount(0)
})

test('本地视频导入后进入 AI 整理队列并通过 Blob URL 播放', async ({ page }) => {
  await page.route('**/api/v1/health', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'ok',
        model: 'funasr:paraformer-zh',
        device: 'cpu',
        version: '2.0.0',
        preciseModel: 'faster-whisper:large-v3',
        preciseModelReady: true,
      }),
    })
  })
  await openLibraryAsLoggedInUser(page, '/', 'import-fast')
  await page.getByRole('button', { name: '导入视频' }).click()
  await page
    .locator('#local-video-file')
    .setInputFiles(resolve('public/demo/eternal-night-survival.mp4'))

  const importDialog = page.getByRole('dialog')
  await expect(importDialog.getByText(/1280 × 720/)).toBeVisible()
  await expect(page.getByText('浏览器已读取真实媒体')).toBeVisible()
  await expect(importDialog.getByRole('radio', { name: /快速/ })).toHaveAttribute('aria-checked', 'true')
  await importDialog.getByRole('radio', { name: /精准/ }).click()
  await expect(importDialog.getByRole('radio', { name: /精准/ })).toHaveAttribute('aria-checked', 'true')
  await importDialog.getByRole('radio', { name: /快速/ }).click()
  await page.getByRole('button', { name: '导入片库' }).click()

  await expect(page.getByRole('article')).toHaveCount(5)
  const queue = page.getByRole('region', { name: 'AI 整理队列' })
  await expect(queue).toBeVisible()
  await expect(queue.getByText('eternal-night-survival')).toBeVisible()
  await expect(queue.getByText('整理完成', { exact: true }).first()).toBeVisible({ timeout: 10_000 })

  const importedCard = page.getByRole('article').filter({
    hasText: 'eternal-night-survival.mp4',
  })
  await expect(importedCard.getByRole('heading', { name: 'eternal-night-survival' })).toBeVisible()
  await expect(importedCard.getByText('AI 已整理')).toBeVisible()
  await importedCard.getByRole('button', { name: '播放' }).click()

  await expect(page.getByRole('heading', { name: 'eternal-night-survival' })).toBeVisible()
  await expect
    .poll(() =>
      page
        .getByTestId('demo-video')
        .evaluate((element) => (element as HTMLVideoElement).currentSrc),
    )
    .toMatch(/^blob:/)
})

test('本地 AI 服务结果会回填字幕摘要和章节', async ({ page }) => {
  let submittedAnalysis = ''
  await page.route('**/api/v1/health', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'ok',
        model: 'funasr:paraformer-zh',
        device: 'cpu',
        version: '2.0.0',
        preciseModel: 'faster-whisper:large-v3',
        preciseModelReady: true,
      }),
    })
  })
  await page.route('**/api/v1/analyses', async (route) => {
    submittedAnalysis = route.request().postData() ?? ''
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'job-e2e',
        videoId: 'placeholder',
        status: 'queued',
        stage: '等待本地模型',
        progress: 5,
        detail: '任务已进入本地 AI 队列。',
        result: null,
        errorCode: null,
      }),
    })
  })
  await page.route('**/api/v1/analyses/job-e2e', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'job-e2e',
        videoId: 'placeholder',
        status: 'completed',
        stage: '整理完成',
        progress: 100,
        detail: '已生成 46 段字幕和 3 个章节。',
        errorCode: null,
        result: {
          language: '中文（简体）',
          confidence: 0.96,
          shortDescription: '本地 AI 已从音轨识别出 46 段字幕，并生成内容结构。',
          summary: '四族通过共享情报与研发低光作物应对永夜饥荒。',
          tags: ['永夜', '四族', '饥荒'],
          subtitlesVtt: 'WEBVTT\n\n1\n00:00:00.000 --> 00:00:04.000\n四族共享末日情报。',
          asrModel: 'FunASR Paraformer-zh · CPU + MiniMax-M3',
          chapters: [
            {
              id: 'chapter-1',
              title: '四族共享末日情报',
              startSeconds: 0,
              endSeconds: 135,
              summary: '四族联合应对永夜危机。',
              source: 'subtitle',
              confidence: 0.96,
              spoilerLevel: 'none',
            },
          ],
        },
      }),
    })
  })

  await openLibraryAsLoggedInUser(page, '/', 'import-ai')
  await page.getByRole('button', { name: '导入视频' }).click()
  await page
    .locator('#local-video-file')
    .setInputFiles({
      name: 'civilization-upload.mp4',
      mimeType: 'video/mp4',
      buffer: await readFile(resolve('public/demo/eternal-night-civilization.mp4')),
    })
  await page.getByRole('radio', { name: /精准/ }).click()
  await page.getByRole('button', { name: '导入片库' }).click()

  const queue = page.getByRole('region', { name: 'AI 整理队列' })
  const job = queue.getByRole('listitem').filter({ hasText: 'civilization-upload' })
  await expect(job.locator('.analysis-job-state span').first()).toHaveText('精准')
  await expect(job.getByText('整理完成', { exact: true }).first()).toBeVisible({ timeout: 10_000 })
  expect(submittedAnalysis).toContain('name="analysis_mode"')
  expect(submittedAnalysis).toContain('precise')
  const importedCard = page.getByRole('article').filter({
    has: page.getByRole('heading', { name: 'civilization-upload', exact: true }),
  })
  await expect(importedCard.getByText('AI 已整理')).toBeVisible()
  await importedCard.getByRole('button', { name: '查看详情' }).click()
  await expect(page.getByText('四族通过共享情报与研发低光作物应对永夜饥荒。')).toBeVisible()
  await expect(page.getByRole('button', { name: /四族共享末日情报/ })).toBeVisible()
})

test('精准模型未安装时不允许提交精准任务', async ({ page }) => {
  await page.route('**/api/v1/health', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'ok',
        model: 'funasr:paraformer-zh',
        device: 'cpu',
        version: '2.0.0',
        preciseModel: 'faster-whisper:large-v3',
        preciseModelReady: false,
      }),
    })
  })

  await openLibraryAsLoggedInUser(page, '/', 'precise-disabled')
  await page.getByRole('button', { name: '导入视频' }).click()

  await expect(page.getByRole('radio', { name: /精准/ })).toBeDisabled()
  await expect(page.getByText('精准模型尚未安装完成，当前仅开放快速模式。')).toBeVisible()
})

test('侧栏只保留可用筛选，磁力入口不伪造下载成功', async ({ page }) => {
  await page.route('**/api/v1/system/magnet', async (route) => {
    const body = route.request().postDataJSON() as { magnet: string }
    expect(body.magnet).toMatch(/^magnet:\?xt=urn:btih:/)
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ status: 'opened', detail: '已交给迅雷客户端处理' }),
    })
  })
  await openLibraryAsLoggedInUser(page, '/', 'magnet')
  await expect(page.getByText('云盘空间')).toHaveCount(0)

  await page.locator('.filter-tabs').getByRole('button', { name: 'AI 已整理', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'AI 已整理' })).toBeVisible()
  await expect(page.getByRole('article')).toHaveCount(4)

  await page.locator('.filter-tabs').getByRole('button', { name: '待处理', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'AI 整理队列', level: 1 })).toBeVisible()
  await expect(page.getByRole('article')).toHaveCount(0)
  await expect(page.getByText('这个分类还没有视频')).toBeVisible()

  await page.getByRole('button', { name: '导入视频' }).click()
  await page.getByRole('tab', { name: '磁力链接' }).click()
  await page
    .getByLabel('迅雷磁力链接')
    .fill('magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567')
  await expect(page.getByText('云盘自动转存需要开放接口')).toBeVisible()
  const openButton = page.getByRole('button', { name: '在迅雷中打开' })
  await expect(openButton).toBeEnabled()
  await openButton.click()
  await expect(page.getByText('已交给迅雷客户端处理')).toBeVisible()
})

test('默认进入登录页，深链未登录时不能绕过片库门禁', async ({ page }) => {
  await page.goto('/videos/python-as-a-language/play?t=124')
  await expect(page.getByRole('heading', { name: '登录迅雷 AI 片库' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Python 入门：语言、语法与保留字' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '导入视频' })).toHaveCount(0)
  await registerDemoAccount(page, 'gate')
})

test('我的片库支持本地注册登录、退出再登录，且不展示不可用的迅雷授权入口', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '登录迅雷 AI 片库' })).toBeVisible()
  await page.getByRole('tab', { name: '注册' }).click()
  await page.getByLabel('昵称').fill('评审账号')
  await page.getByLabel('邮箱').fill('judge@example.com')
  await page.getByLabel('密码').fill('review-pass-2026')
  await page.getByRole('button', { name: '创建并登录' }).click()

  await page.getByRole('button', { name: '打开账号中心' }).click()
  await expect(page.getByText('Demo 本地账号')).toBeVisible()
  await expect(page.getByText('迅雷开放平台 AppID')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '前往迅雷授权' })).toHaveCount(0)

  await page.getByRole('button', { name: '退出' }).click()
  await expect(page.getByRole('heading', { name: '登录迅雷 AI 片库' })).toBeVisible()
  await page.getByLabel('邮箱').fill('judge@example.com')
  await page.getByLabel('密码').fill('review-pass-2026')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('button', { name: '打开账号中心' }).click()
  await expect(page.getByText('judge@example.com')).toBeVisible()
})

test('首页没有严重可访问性问题', async ({ page }) => {
  await openLibraryAsLoggedInUser(page, '/', 'a11y')
  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter((item) => ['critical', 'serious'].includes(item.impact ?? ''))).toEqual([])
})

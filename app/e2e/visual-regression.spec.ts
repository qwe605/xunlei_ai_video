import { expect, test } from '@playwright/test'

async function openLibraryAsLoggedInUser(page: import('@playwright/test').Page, suffix = 'visual') {
  await page.goto('/')
  await page.getByRole('tab', { name: '注册' }).click()
  await page.getByLabel('昵称').fill(`评审账号${suffix}`)
  await page.getByLabel('邮箱').fill(`judge-${suffix}@example.com`)
  await page.getByLabel('密码').fill('review-pass-2026')
  await page.getByRole('button', { name: '创建并登录' }).click()
  await expect(page.getByRole('heading', { name: '全部视频' })).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  // 视觉基线固定使用“精准模型已部署”能力，避免依赖本机后端是否正在运行。
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
})

test('默认登录页保持视觉稳定', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '登录迅雷 AI 片库' })).toBeVisible()
  await expect(page).toHaveScreenshot('auth-login-page.png', { fullPage: true })
})

test('片库首页和自然语言搜索结果保持视觉稳定', async ({ page }) => {
  await openLibraryAsLoggedInUser(page, 'library')
  await expect(page.getByRole('heading', { name: '全部视频' })).toBeVisible()
  await expect(page).toHaveScreenshot('library.png', { fullPage: true })

  await page.getByRole('button', { name: /找讲 Python 名字由来的视频/ }).click()
  await expect(page.getByRole('heading', { name: /语言、语法与保留字/ })).toBeVisible()
  await expect(page).toHaveScreenshot('search-results.png', { fullPage: true })
})

test('详情和有依据问答保持视觉稳定', async ({ page }) => {
  await openLibraryAsLoggedInUser(page, 'detail')
  await page.getByRole('button', { name: /找讲 Python 名字由来的视频/ }).click()
  await page.getByRole('button', { name: '查看详情' }).first().click()
  await expect(page.getByRole('heading', { name: '打开前先看懂' })).toBeVisible()
  const mainContent = page.getByRole('main')
  // 移动端对长元素截图时 sticky 顶栏可能处于两种等价滚动位置；隐藏顶栏只比较详情内容。
  await page.locator('.app-header').evaluate((element) => {
    element.style.visibility = 'hidden'
  })
  await expect(mainContent).toHaveScreenshot('video-detail.png')

  await page.getByRole('button', { name: /Python 名字的由来/ }).click()
  await page.getByRole('tab', { name: '问视频' }).click()
  await page.getByRole('button', { name: '后面有没有讲保留字？' }).click()
  await expect(page.getByRole('button', { name: /11:28—11:40/ })).toBeVisible()

  // 视频帧由解码时序决定；遮罩后仍能检测播放器布局、证据卡片和控制区回归。
  await expect(mainContent).toHaveScreenshot('grounded-answer.png', {
    mask: [page.getByTestId('demo-video')],
    maskColor: '#172033',
  })
})

test('真实视频导入入口保持视觉稳定', async ({ page }) => {
  await openLibraryAsLoggedInUser(page, 'import')
  await page.getByRole('button', { name: '导入视频' }).click()
  const dialog = page.getByRole('dialog', { name: '导入真实视频' })
  await expect(dialog).toHaveScreenshot('local-import-dialog.png')

  await page.getByRole('tab', { name: '磁力链接' }).click()
  await expect(dialog).toHaveScreenshot('magnet-import-dialog.png')
})

test('本地账号注册入口和资料页保持视觉稳定', async ({ page }) => {
  await page.goto('/')
  const dialog = page.getByRole('dialog', { name: '登录迅雷 AI 片库' })
  await expect(dialog).toHaveScreenshot('account-login-dialog.png')

  await page.getByRole('tab', { name: '注册' }).click()
  await page.getByLabel('昵称').fill('Judge')
  await page.getByLabel('邮箱').fill('judge@example.com')
  await page.getByLabel('密码').fill('review-pass-2026')
  await page.getByRole('button', { name: '创建并登录' }).click()
  await page.getByRole('button', { name: '打开账号中心' }).click()
  await expect(page.getByRole('dialog', { name: '我的片库账号' })).toHaveScreenshot(
    'account-profile.png',
  )
})

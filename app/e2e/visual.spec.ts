import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { expect, test } from '@playwright/test'

const outputDir = resolve('..', 'output', 'qa')

async function openLibraryAsLoggedInUser(page: import('@playwright/test').Page, suffix = 'capture') {
  const uniqueSuffix = `${suffix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
  await page.goto('/')
  await page.getByRole('tab', { name: '注册' }).click()
  await page.getByLabel('昵称').fill(`评审账号${suffix}`)
  await page.getByLabel('邮箱').fill(`judge-${uniqueSuffix}@example.com`)
  await page.getByLabel('密码').fill('review-pass-2026')
  await page.getByRole('button', { name: '创建并登录' }).click()
  await expect(page.getByRole('heading', { name: '全部视频' })).toBeVisible()
}

test('保存核心视图的验收截图', { tag: '@capture' }, async ({ page }, testInfo) => {
  await mkdir(outputDir, { recursive: true })
  const suffix = testInfo.project.name

  await openLibraryAsLoggedInUser(page, suffix)
  await expect(page.getByRole('heading', { name: '全部视频' })).toBeVisible()
  await page.screenshot({
    path: resolve(outputDir, `demo-library-${suffix}.png`),
    fullPage: true,
  })

  await page.getByRole('button', { name: /找讲 Python 名字由来的视频/ }).click()
  await expect(page.getByRole('heading', { name: /语言、语法与保留字/ })).toBeVisible()
  await page.screenshot({
    path: resolve(outputDir, `demo-search-${suffix}.png`),
    fullPage: true,
  })

  await page.getByRole('button', { name: '查看详情' }).first().click()
  await expect(page.getByRole('heading', { name: '打开前先看懂' })).toBeVisible()
  await page.screenshot({
    path: resolve(outputDir, `demo-detail-${suffix}.png`),
    fullPage: true,
  })

  await page.getByRole('button', { name: /Python 名字的由来/ }).click()
  await page.getByRole('tab', { name: '问视频' }).click()
  await page.getByRole('button', { name: '后面有没有讲保留字？' }).click()
  await expect(page.getByRole('button', { name: /11:28—11:40/ })).toBeVisible()
  await page.screenshot({
    path: resolve(outputDir, `demo-player-${suffix}.png`),
    fullPage: true,
  })

  await page.goto('/')
  await page.getByRole('button', { name: /查看《永夜生存/ }).click()
  await page.getByRole('button', { name: '开始播放' }).click()
  await page.getByRole('tab', { name: '字幕' }).click()
  await expect(page.getByText('AI 自动生成字幕')).toBeVisible()
  await page.screenshot({
    path: resolve(outputDir, `demo-ai-subtitles-${suffix}.png`),
    fullPage: true,
  })
})

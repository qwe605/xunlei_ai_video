import { mkdir, copyFile, rm } from 'node:fs/promises'
import { resolve } from 'node:path'
import { chromium } from 'playwright'

const baseUrl = process.env.DEMO_URL ?? 'http://127.0.0.1:5173'
const recordingDir = resolve('..', 'tmp', 'recording', 'playwright')
const rawVideoPath = resolve('..', 'tmp', 'recording', 'xunlei-ai-library-demo.webm')

// 录制目录只存放本脚本生成的临时视频，运行前清空可避免误取上一次的随机文件名。
await rm(recordingDir, { recursive: true, force: true })
await mkdir(recordingDir, { recursive: true })

const browser = await chromium.launch({
  channel: 'chrome',
  headless: true,
  args: ['--hide-scrollbars', '--autoplay-policy=no-user-gesture-required'],
})
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  recordVideo: {
    dir: recordingDir,
    size: { width: 1440, height: 900 },
  },
})
const page = await context.newPage()
let recordedVideo

const sleep = (milliseconds) => page.waitForTimeout(milliseconds)

async function installPresentationLayer() {
  await page.evaluate(() => {
    const style = document.createElement('style')
    style.textContent = `
      #submission-caption {
        position: fixed;
        left: 50%;
        bottom: 34px;
        z-index: 2147483646;
        width: min(760px, calc(100vw - 56px));
        padding: 16px 22px;
        color: #fff;
        background: rgba(6, 18, 35, .94);
        border: 1px solid rgba(112, 174, 255, .55);
        border-radius: 7px;
        box-shadow: 0 16px 40px rgba(0, 0, 0, .28);
        transform: translate(-50%, 18px);
        opacity: 0;
        pointer-events: none;
        transition: opacity .25s ease, transform .25s ease;
        font-family: "Microsoft YaHei", system-ui, sans-serif;
      }
      #submission-caption.visible {
        transform: translate(-50%, 0);
        opacity: 1;
      }
      #submission-caption strong {
        display: block;
        margin-bottom: 4px;
        color: #70aeff;
        font-size: 20px;
        line-height: 1.4;
      }
      #submission-caption span {
        display: block;
        font-size: 15px;
        line-height: 1.55;
      }
      #submission-cursor {
        position: fixed;
        z-index: 2147483647;
        width: 24px;
        height: 24px;
        margin: -12px 0 0 -12px;
        border: 3px solid #1473e6;
        border-radius: 50%;
        background: rgba(255, 255, 255, .88);
        box-shadow: 0 0 0 6px rgba(20, 115, 230, .24);
        pointer-events: none;
        transition: left .65s cubic-bezier(.2,.8,.2,1), top .65s cubic-bezier(.2,.8,.2,1), transform .15s ease;
      }
      #submission-cursor.clicking {
        transform: scale(.72);
      }
      #submission-watermark {
        position: fixed;
        right: 18px;
        bottom: 12px;
        z-index: 2147483645;
        color: rgba(255,255,255,.78);
        padding: 4px 8px;
        border-radius: 4px;
        background: rgba(6,18,35,.72);
        font: 12px/1.4 "Microsoft YaHei", system-ui, sans-serif;
        pointer-events: none;
      }
    `
    document.head.appendChild(style)

    const caption = document.createElement('div')
    caption.id = 'submission-caption'
    caption.innerHTML = '<strong></strong><span></span>'
    document.body.appendChild(caption)

    const cursor = document.createElement('div')
    cursor.id = 'submission-cursor'
    cursor.style.left = '720px'
    cursor.style.top = '450px'
    document.body.appendChild(cursor)

    const watermark = document.createElement('div')
    watermark.id = 'submission-watermark'
    watermark.textContent = '迅雷 AI 片库 · 产品 Demo'
    document.body.appendChild(watermark)
  })
}

async function showCaption(title, body, visibleMilliseconds = 4200) {
  await page.evaluate(
    ({ nextTitle, nextBody }) => {
      const caption = document.querySelector('#submission-caption')
      caption.querySelector('strong').textContent = nextTitle
      caption.querySelector('span').textContent = nextBody
      caption.classList.add('visible')
    },
    { nextTitle: title, nextBody: body },
  )
  await sleep(visibleMilliseconds)
  await page.evaluate(() => document.querySelector('#submission-caption').classList.remove('visible'))
  await sleep(900)
}

async function clickWithCursor(locator) {
  await locator.scrollIntoViewIfNeeded()
  const box = await locator.boundingBox()
  if (!box) throw new Error('目标控件不可见，无法录制点击。')
  await page.evaluate(
    ({ x, y }) => {
      const cursor = document.querySelector('#submission-cursor')
      cursor.style.left = `${x}px`
      cursor.style.top = `${y}px`
    },
    { x: box.x + box.width / 2, y: box.y + box.height / 2 },
  )
  await sleep(750)
  await page.evaluate(() => document.querySelector('#submission-cursor').classList.add('clicking'))
  await locator.click()
  await sleep(180)
  await page.evaluate(() => document.querySelector('#submission-cursor').classList.remove('clicking'))
}

try {
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: '全部视频' }).waitFor()
  await installPresentationLayer()

  await showCaption(
    '迅雷 AI 片库',
    '面向海量云端视频，用一句自然语言找到目标内容，并直接跳转到关键片段。',
    5600,
  )
  await showCaption(
    '真实用户问题',
    '用户只记得场景或知识点，却记不住复杂文件名；找到以后还要反复试播和拖动进度条。',
    5200,
  )

  await clickWithCursor(page.locator('.header-import'))
  await page
    .locator('#local-video-file')
    .setInputFiles(resolve('public/demo/eternal-night-survival.mp4'))
  await page.locator('.selected-media').waitFor()
  await showCaption(
    '评委可导入自己的视频',
    '系统真实读取本机文件的时长、分辨率和大小，并从视频抽取封面，不替换成内置素材。',
    6000,
  )
  await clickWithCursor(page.locator('.import-dialog-actions .button-primary'))
  await page.getByRole('article').first().waitFor()

  const searchSuggestion = page.getByRole('button', {
    name: /找讲 Python 名字由来的视频/,
  })
  await clickWithCursor(searchSuggestion)
  await page.getByRole('heading', { name: '“找讲 Python 名字由来的视频”' }).waitFor()
  await showCaption(
    '一句话搜索',
    'AI 同时理解文件名、摘要、标签和章节，并说明为什么匹配以及最相关的时间点。',
    6000,
  )

  await showCaption(
    '结果可解释',
    '第一条结果命中 Python 和名字由来，并给出 02:04“Python 名字的由来”相关片段。',
    5200,
  )

  const detailButton = page.getByRole('button', { name: '查看详情' }).first()
  await clickWithCursor(detailButton)
  await page.getByRole('heading', { name: '打开前先看懂' }).waitFor()
  await showCaption(
    '打开前先看懂',
    '整片摘要帮助判断内容是否相关，六个智能章节让用户选择准确的观看起点。',
    6200,
  )

  const chapterButton = page.getByRole('button', { name: /Python 名字的由来/ })
  await clickWithCursor(chapterButton)
  await page.getByRole('heading', { name: 'Python 入门：语言、语法与保留字' }).waitFor()
  // 录屏必须等待真实媒体 Seek 完成，不能只依赖界面上的章节状态。
  await page.waitForFunction(
    () => document.querySelector('[data-testid="demo-video"]')?.currentTime >= 124,
    undefined,
    { timeout: 15000 },
  )
  await showCaption(
    '章节直接跳转',
    '播放器从 02:04 开始，并播放公开授权原片的真实画面和声音。',
    5600,
  )

  const askTab = page.getByRole('tab', { name: '问视频' })
  await clickWithCursor(askTab)
  const recommendedQuestion = page.getByRole('button', { name: '后面有没有讲保留字？' })
  await clickWithCursor(recommendedQuestion)
  await page.getByRole('button', { name: /11:28—11:40/ }).waitFor()
  await showCaption(
    '问视频，回答必须带证据',
    '回答引用 11:28—11:40 的字幕内容，用户可以点击证据独立核验。',
    6200,
  )

  const evidenceButton = page.getByRole('button', { name: /11:28—11:40/ })
  await clickWithCursor(evidenceButton)
  await page.locator('.now-playing > span').filter({ hasText: '11:28' }).waitFor()
  await page.waitForFunction(
    () => document.querySelector('[data-testid="demo-video"]')?.currentTime >= 688,
    undefined,
    { timeout: 15000 },
  )
  await showCaption(
    '从答案抵达内容',
    '点击证据后，视频时间轴实际跳到 11:28，完成“搜索—理解—问答—播放”闭环。',
    6000,
  )

  await page.goto(baseUrl)
  await installPresentationLayer()
  await clickWithCursor(page.getByRole('button', { name: /查看《永夜生存/ }))
  await clickWithCursor(page.getByRole('button', { name: '开始播放' }))
  await clickWithCursor(page.getByRole('tab', { name: '字幕' }))
  await page.getByText('AI 自动生成字幕').waitFor()
  await showCaption(
    '无字幕视频自动转写',
    '这段真实教程没有现成字幕，Demo 已用 faster-whisper 生成 34 段可跳转英文字幕。',
    6500,
  )

  await clickWithCursor(page.getByRole('tab', { name: '问视频' }))
  const questionInput = page.getByLabel('向当前视频提问')
  await questionInput.fill('老师有没有推荐北京餐厅？')
  await clickWithCursor(page.getByRole('button', { name: '发送问题' }))
  await page.getByText('当前视频中没有找到相关内容').waitFor()
  await showCaption(
    '没有依据就明确拒答',
    '系统只使用当前视频字幕；找不到证据时不调用模型常识生成看似正确的答案。',
    6500,
  )

  await showCaption(
    '海量视频，一句话找到',
    '迅雷 AI 片库把“找文件”升级为“找到可验证的内容”。',
    5600,
  )
} finally {
  recordedVideo = page.video()
  await context.close()
  await browser.close()
}

if (!recordedVideo) throw new Error('Playwright 没有生成录屏文件。')
await copyFile(await recordedVideo.path(), rawVideoPath)
console.log(rawVideoPath)

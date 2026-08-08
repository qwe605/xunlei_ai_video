"""生成迅雷 AI 片库评委版产品说明 PDF 与独立产品流程图。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
QA_DIR = ROOT / "output" / "qa"
OUTPUT_DIR = ROOT / "output" / "submission"
PDF_PATH = OUTPUT_DIR / "迅雷AI片库-产品说明书.pdf"
FLOW_PATH = OUTPUT_DIR / "迅雷AI片库-产品闭环流程图.png"

FONT_REGULAR_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD_PATH = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_REGULAR = "MicrosoftYaHei"
FONT_BOLD = "MicrosoftYaHeiBold"

PAGE_W, PAGE_H = A4
MARGIN = 42

NAVY = colors.HexColor("#0B1F3A")
BLUE = colors.HexColor("#1473E6")
LIGHT_BLUE = colors.HexColor("#EAF3FF")
PALE = colors.HexColor("#F4F7FB")
LINE = colors.HexColor("#D8E1EC")
TEXT = colors.HexColor("#172033")
MUTED = colors.HexColor("#64748B")
GREEN = colors.HexColor("#138A66")
WHITE = colors.white


def register_fonts() -> None:
    """注册中文字体，避免 PDF 中出现方框或字符替换。"""
    if not FONT_REGULAR_PATH.exists() or not FONT_BOLD_PATH.exists():
        raise FileNotFoundError("缺少微软雅黑字体，无法生成可靠的中文 PDF。")
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(FONT_REGULAR_PATH)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_BOLD_PATH)))


def style(
    size: float,
    *,
    bold: bool = False,
    color: colors.Color = TEXT,
    leading: float | None = None,
    alignment: int = TA_LEFT,
) -> ParagraphStyle:
    return ParagraphStyle(
        name=f"style-{size}-{bold}-{alignment}",
        fontName=FONT_BOLD if bold else FONT_REGULAR,
        fontSize=size,
        leading=leading or size * 1.55,
        textColor=color,
        alignment=alignment,
        wordWrap="CJK",
        splitLongWords=True,
        spaceAfter=0,
        spaceBefore=0,
    )


def paragraph(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y_top: float,
    width: float,
    *,
    size: float = 10,
    bold: bool = False,
    color: colors.Color = TEXT,
    leading: float | None = None,
    alignment: int = TA_LEFT,
) -> float:
    """从顶部坐标开始绘制自动换行段落，并返回段落底部 y 坐标。"""
    block = Paragraph(
        text,
        style(
            size,
            bold=bold,
            color=color,
            leading=leading,
            alignment=alignment,
        ),
    )
    _, height = block.wrap(width, PAGE_H)
    block.drawOn(pdf, x, y_top - height)
    return y_top - height


def draw_page_header(pdf: canvas.Canvas, section: str, page_number: int) -> None:
    pdf.setFillColor(BLUE)
    pdf.roundRect(MARGIN, PAGE_H - 45, 23, 23, 5, fill=1, stroke=0)
    pdf.setFillColor(WHITE)
    pdf.setFont(FONT_BOLD, 12)
    pdf.drawCentredString(MARGIN + 11.5, PAGE_H - 38, "迅")
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, 10)
    pdf.drawString(MARGIN + 31, PAGE_H - 38, "迅雷 AI 片库")
    pdf.setFillColor(MUTED)
    pdf.setFont(FONT_REGULAR, 8)
    pdf.drawRightString(PAGE_W - MARGIN, PAGE_H - 38, section)

    pdf.setStrokeColor(LINE)
    pdf.line(MARGIN, 34, PAGE_W - MARGIN, 34)
    pdf.setFillColor(MUTED)
    pdf.setFont(FONT_REGULAR, 7.5)
    pdf.drawString(MARGIN, 20, "迅雷校园 AI 产品创造营 · 产品 Demo")
    pdf.drawRightString(PAGE_W - MARGIN, 20, f"{page_number:02d}")


def draw_title(pdf: canvas.Canvas, title: str, subtitle: str | None = None) -> float:
    y = PAGE_H - 78
    y = paragraph(pdf, title, MARGIN, y, PAGE_W - 2 * MARGIN, size=24, bold=True, color=NAVY)
    if subtitle:
        y -= 8
        y = paragraph(pdf, subtitle, MARGIN, y, PAGE_W - 2 * MARGIN, size=10, color=MUTED)
    return y


def draw_screenshot(
    pdf: canvas.Canvas,
    image_path: Path,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """按 contain 方式放置截图，保留完整产品界面，不裁掉关键信息。"""
    if not image_path.exists():
        raise FileNotFoundError(f"缺少界面截图：{image_path}")
    with Image.open(image_path) as image:
        image_w, image_h = image.size
    scale = min(width / image_w, height / image_h)
    draw_w = image_w * scale
    draw_h = image_h * scale
    draw_x = x + (width - draw_w) / 2
    draw_y = y + (height - draw_h) / 2

    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(LINE)
    pdf.roundRect(x, y, width, height, 5, fill=1, stroke=1)
    pdf.drawImage(
        ImageReader(str(image_path)),
        draw_x,
        draw_y,
        draw_w,
        draw_h,
        preserveAspectRatio=True,
        mask="auto",
    )


def draw_feature_list(
    pdf: canvas.Canvas,
    items: list[tuple[str, str]],
    x: float,
    y_top: float,
    width: float,
) -> float:
    y = y_top
    for index, (title, body) in enumerate(items, start=1):
        pdf.setFillColor(LIGHT_BLUE)
        pdf.circle(x + 10, y - 10, 10, fill=1, stroke=0)
        pdf.setFillColor(BLUE)
        pdf.setFont(FONT_BOLD, 8.5)
        pdf.drawCentredString(x + 10, y - 13, str(index))
        paragraph(pdf, title, x + 28, y, width - 28, size=10, bold=True, color=NAVY)
        y = paragraph(pdf, body, x + 28, y - 18, width - 28, size=8.5, color=MUTED)
        y -= 16
    return y


def draw_flow_image() -> None:
    """生成可独立提交和复用的高分辨率产品闭环流程图。"""
    width, height = 2400, 900
    image = Image.new("RGB", (width, height), "#F4F7FB")
    draw = ImageDraw.Draw(image)
    regular = ImageFont.truetype(str(FONT_REGULAR_PATH), 34)
    small = ImageFont.truetype(str(FONT_REGULAR_PATH), 25)
    bold = ImageFont.truetype(str(FONT_BOLD_PATH), 40)
    title_font = ImageFont.truetype(str(FONT_BOLD_PATH), 58)

    draw.text((100, 70), "迅雷 AI 片库：从视频文件到可跳转知识", fill="#0B1F3A", font=title_font)
    draw.text(
        (100, 150),
        "同一套内容索引贯穿整理、搜索、理解、问答与播放，不制造孤立的 AI 聊天入口。",
        fill="#64748B",
        font=regular,
    )

    steps = [
        ("01", "云端视频", "保留原文件与权限"),
        ("02", "AI 自动整理", "字幕 · 摘要 · 标签"),
        ("03", "一句话搜索", "文件名 + 内容混合召回"),
        ("04", "打开前看懂", "整片摘要 + 智能章节"),
        ("05", "问视频", "回答绑定字幕证据"),
        ("06", "跳转片段", "从答案直达时间点"),
    ]
    card_w = 330
    card_h = 270
    gap = 45
    start_x = 75
    y = 330

    for index, (number, title, body) in enumerate(steps):
        x = start_x + index * (card_w + gap)
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=24, fill="#FFFFFF", outline="#D8E1EC", width=3)
        draw.rounded_rectangle((x + 24, y + 24, x + 86, y + 86), radius=14, fill="#1473E6")
        number_box = draw.textbbox((0, 0), number, font=small)
        number_w = number_box[2] - number_box[0]
        draw.text((x + 55 - number_w / 2, y + 38), number, fill="#FFFFFF", font=small)
        draw.text((x + 24, y + 120), title, fill="#0B1F3A", font=bold)
        draw.text((x + 24, y + 185), body, fill="#64748B", font=small)

        if index < len(steps) - 1:
            arrow_start = x + card_w + 8
            arrow_y = y + card_h / 2
            arrow_end = x + card_w + gap - 8
            draw.line((arrow_start, arrow_y, arrow_end, arrow_y), fill="#1473E6", width=8)
            draw.polygon(
                [
                    (arrow_end, arrow_y),
                    (arrow_end - 22, arrow_y - 16),
                    (arrow_end - 22, arrow_y + 16),
                ],
                fill="#1473E6",
            )

    draw.rounded_rectangle((675, 690, 1725, 800), radius=22, fill="#E8F7F1")
    draw.text((740, 718), "可信原则：找不到视频证据时明确拒答", fill="#138A66", font=bold)
    image.save(FLOW_PATH, quality=95)


def build_pdf() -> None:
    register_fonts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    draw_flow_image()

    pdf = canvas.Canvas(str(PDF_PATH), pagesize=A4, pageCompression=1)
    pdf.setTitle("迅雷 AI 片库 - 产品说明书")
    pdf.setAuthor("迅雷校园 AI 产品创造营参赛作品")
    pdf.setSubject("云盘视频自然语言搜索、摘要、章节与证据问答产品 Demo")

    # 第 1 页：封面直接呈现产品本体，避免营销式空页。
    pdf.setFillColor(NAVY)
    pdf.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    pdf.setFillColor(BLUE)
    pdf.roundRect(MARGIN, PAGE_H - 88, 34, 34, 7, fill=1, stroke=0)
    pdf.setFillColor(WHITE)
    pdf.setFont(FONT_BOLD, 17)
    pdf.drawCentredString(MARGIN + 17, PAGE_H - 78, "迅")
    pdf.setFont(FONT_BOLD, 29)
    pdf.drawString(MARGIN, PAGE_H - 150, "迅雷 AI 片库")
    pdf.setFont(FONT_REGULAR, 13)
    pdf.setFillColor(colors.HexColor("#C9D7E8"))
    pdf.drawString(MARGIN, PAGE_H - 181, "海量视频，一句话找到")
    paragraph(
        pdf,
        "让 AI 自动理解云端视频，通过摘要、智能章节和证据问答，"
        "把“翻目录、猜文件名、反复试播”变成一次准确跳转。",
        MARGIN,
        PAGE_H - 220,
        PAGE_W - 2 * MARGIN,
        size=10.5,
        color=colors.HexColor("#E5EDF7"),
        leading=17,
    )
    draw_screenshot(
        pdf,
        QA_DIR / "demo-library-desktop.png",
        MARGIN,
        92,
        PAGE_W - 2 * MARGIN,
        465,
    )
    pdf.setFillColor(colors.HexColor("#91A5BC"))
    pdf.setFont(FONT_REGULAR, 8)
    pdf.drawString(MARGIN, 54, "迅雷校园 AI 产品创造营 · 产品 Demo 说明书")
    pdf.drawRightString(PAGE_W - MARGIN, 54, "2026.07")
    pdf.showPage()

    # 第 2 页：真实需求。
    draw_page_header(pdf, "01 · 用户需求", 2)
    y = draw_title(
        pdf,
        "从“我明明存过”开始",
        "当云盘进入 TB 级规模，文件存在不等于内容可被找到。",
    )
    y -= 22
    pain_points = [
        ("找不到", "只记得演员、场景或知识点，记不住发布组和编码组成的原文件名。"),
        ("看不懂", "搜索结果只有文件名和封面，必须逐个打开才能判断是不是目标视频。"),
        ("跳不准", "长视频里目标内容只占几分钟，用户仍要反复拖动进度条。"),
    ]
    card_w = (PAGE_W - 2 * MARGIN - 18) / 3
    for index, (title, body) in enumerate(pain_points):
        x = MARGIN + index * (card_w + 9)
        pdf.setFillColor(PALE)
        pdf.setStrokeColor(LINE)
        pdf.roundRect(x, y - 175, card_w, 175, 6, fill=1, stroke=1)
        pdf.setFillColor(BLUE)
        pdf.setFont(FONT_BOLD, 22)
        pdf.drawString(x + 16, y - 36, f"0{index + 1}")
        paragraph(pdf, title, x + 16, y - 63, card_w - 32, size=15, bold=True, color=NAVY)
        paragraph(pdf, body, x + 16, y - 96, card_w - 32, size=9, color=MUTED, leading=15)

    quote_y = y - 215
    pdf.setFillColor(LIGHT_BLUE)
    pdf.roundRect(MARGIN, quote_y - 135, PAGE_W - 2 * MARGIN, 135, 7, fill=1, stroke=0)
    pdf.setFillColor(BLUE)
    pdf.setFont(FONT_BOLD, 36)
    pdf.drawString(MARGIN + 20, quote_y - 42, "“")
    paragraph(
        pdf,
        "我记得存过一个讲 Python 名字由来的视频，后面好像还讲了保留字，"
        "但我完全不记得文件名。",
        MARGIN + 52,
        quote_y - 27,
        PAGE_W - 2 * MARGIN - 78,
        size=13,
        bold=True,
        color=NAVY,
        leading=21,
    )
    paragraph(
        pdf,
        "这是本 Demo 选取的核心用户任务：不是“让 AI 聊天”，而是让用户从模糊记忆直接抵达视频证据。",
        MARGIN,
        quote_y - 176,
        PAGE_W - 2 * MARGIN,
        size=10,
        color=TEXT,
    )
    pdf.showPage()

    # 第 3 页：产品闭环。
    draw_page_header(pdf, "02 · 产品闭环", 3)
    y = draw_title(
        pdf,
        "一套索引，贯穿完整任务",
        "AI 整理不是终点，最终价值是减少用户寻找和确认内容的操作成本。",
    )
    draw_screenshot(pdf, FLOW_PATH, MARGIN, y - 285, PAGE_W - 2 * MARGIN, 250)
    draw_feature_list(
        pdf,
        [
            ("真实入口", "评委可注册登录、导入自己的 MP4/WebM，并查看迅雷官方授权入口。"),
            ("统一内容资产", "文件名、字幕、摘要、标签和章节进入同一检索结构。"),
            ("结果可解释", "告诉用户命中了什么内容，以及最相关章节位于哪个时间点。"),
            ("回答可验证", "每个回答都附带字幕证据；点击证据直接跳到视频片段。"),
        ],
        MARGIN,
        y - 330,
        PAGE_W - 2 * MARGIN,
    )
    pdf.showPage()

    # 第 4 页：搜索。
    draw_page_header(pdf, "03 · 一句话搜索", 4)
    y = draw_title(
        pdf,
        "用户描述记忆，AI 返回可行动结果",
        "示例问题：找讲 Python 名字由来的视频。",
    )
    draw_screenshot(
        pdf,
        QA_DIR / "demo-search-desktop.png",
        MARGIN,
        y - 345,
        PAGE_W - 2 * MARGIN,
        320,
    )
    draw_feature_list(
        pdf,
        [
            ("混合理解", "同时检索标题、原文件名、标签、摘要和章节，而非只匹配文件名。"),
            ("解释匹配", "第一条结果明确展示命中的 Python、名字由来以及 02:04 章节。"),
            ("保留传统能力", "用户可随时切换“文件名结果”，AI 是增强而不是替换。"),
        ],
        MARGIN,
        y - 378,
        PAGE_W - 2 * MARGIN,
    )
    pdf.showPage()

    # 第 5 页：摘要与章节。
    draw_page_header(pdf, "04 · 打开前先看懂", 5)
    y = draw_title(
        pdf,
        "摘要负责判断，章节负责行动",
        "在播放前就回答“是不是目标视频”和“应该从哪里开始看”。",
    )
    draw_screenshot(
        pdf,
        QA_DIR / "demo-detail-desktop.png",
        MARGIN,
        y - 395,
        PAGE_W - 2 * MARGIN,
        370,
    )
    draw_feature_list(
        pdf,
        [
            ("整片摘要", "用一段话交代课程目标、主要内容和结论，降低错误试播。"),
            ("自动章节", "以 00:00、02:04、03:00、06:18、09:10、11:14 等时间点组织视频。"),
            ("内容策略", "教程默认展示摘要；影视内容默认开启防剧透，尊重不同观看场景。"),
        ],
        MARGIN,
        y - 428,
        PAGE_W - 2 * MARGIN,
    )
    pdf.showPage()

    # 第 6 页：视频问答。
    draw_page_header(pdf, "05 · 问视频", 6)
    y = draw_title(
        pdf,
        "答案不是终点，证据片段才是",
        "追问“后面有没有讲保留字？”，回答引用 11:28—11:40 并支持跳转。",
    )
    draw_screenshot(
        pdf,
        QA_DIR / "demo-player-desktop.png",
        MARGIN,
        y - 365,
        PAGE_W - 2 * MARGIN,
        340,
    )
    draw_feature_list(
        pdf,
        [
            ("当前视频约束", "问答只使用正在播放的视频，不跨文件混入相似内容。"),
            ("字幕证据", "答案展示对应时间范围和字幕摘录，用户可以独立核验。"),
            ("真实跳转", "点击证据后，HTML 视频时间轴实际跳到 11:28，而非视觉模拟。"),
        ],
        MARGIN,
        y - 398,
        PAGE_W - 2 * MARGIN,
    )
    pdf.showPage()

    # 第 7 页：技术与可信机制。
    draw_page_header(pdf, "06 · 技术落地", 7)
    y = draw_title(
        pdf,
        "用成熟组件构建可落地的视频知识层",
        "Demo 已对真实无字幕视频运行 faster-whisper；其余索引预生成以保证评审稳定。",
    )
    y -= 20
    pipeline = [
        ("媒体解析", "FFprobe", "时长、分辨率、编码"),
        ("字幕生成", "faster-whisper", "无字幕视频转写"),
        ("镜头候选", "PySceneDetect", "辅助章节边界"),
        ("中文向量", "BGE-M3", "语义检索与重排"),
        ("索引存储", "PostgreSQL + pgvector", "权限内保存元数据"),
    ]
    row_h = 58
    for index, (stage, component, output) in enumerate(pipeline):
        row_y = y - index * row_h
        pdf.setFillColor(PALE if index % 2 == 0 else WHITE)
        pdf.roundRect(MARGIN, row_y - 46, PAGE_W - 2 * MARGIN, 48, 4, fill=1, stroke=0)
        pdf.setFillColor(BLUE)
        pdf.setFont(FONT_BOLD, 9)
        pdf.drawString(MARGIN + 14, row_y - 27, stage)
        pdf.setFillColor(NAVY)
        pdf.drawString(MARGIN + 115, row_y - 27, component)
        pdf.setFillColor(MUTED)
        pdf.setFont(FONT_REGULAR, 8.5)
        pdf.drawString(MARGIN + 300, row_y - 27, output)

    y2 = y - len(pipeline) * row_h - 10
    pdf.setFillColor(colors.HexColor("#E8F7F1"))
    pdf.roundRect(MARGIN, y2 - 132, PAGE_W - 2 * MARGIN, 132, 7, fill=1, stroke=0)
    paragraph(pdf, "可信与安全边界", MARGIN + 18, y2 - 17, PAGE_W - 2 * MARGIN - 36, size=12, bold=True, color=GREEN)
    paragraph(
        pdf,
        "• 回答必须引用当前视频字幕；无证据时明确拒答。<br/>"
        "• 用户视频、字幕与向量索引继承原文件权限，不用于公共推荐。<br/>"
        "• Demo 不展示无法证明云盘权限的第三方账号关联入口。<br/>"
        "• 本地导入不上传原片；磁力云盘自动转存等待迅雷官方开放接口。<br/>"
        "• Demo 使用 CC BY 3.0 公开授权真实媒体，不包含真实用户数据。",
        MARGIN + 18,
        y2 - 47,
        PAGE_W - 2 * MARGIN - 36,
        size=9,
        color=TEXT,
        leading=17,
    )
    pdf.showPage()

    # 第 8 页：评审演示与价值。
    draw_page_header(pdf, "07 · 评审指引", 8)
    y = draw_title(
        pdf,
        "90 秒看懂产品价值",
        "从模糊记忆出发，以可验证的视频片段结束。",
    )
    y -= 14
    steps = [
        "打开“登录 / 注册”，创建仅保存在当前浏览器的 Demo 账号。",
        "点击“导入视频”，确认真实元数据，并查看 AI 整理队列的阶段与结果。",
        "点击推荐问题“找讲 Python 名字由来的视频”。",
        "查看第一条结果的匹配原因与 02:04 相关片段。",
        "进入详情页，浏览整片摘要和 6 个智能章节。",
        "点击“Python 名字的由来”进入播放器并确认真实声音。",
        "询问“后面有没有讲保留字？”。",
        "点击 11:28—11:40 的证据片段，观察时间轴跳转。",
        "输入不存在的问题，展示无依据拒答。",
    ]
    for index, step_text in enumerate(steps, start=1):
        step_y = y - (index - 1) * 48
        pdf.setFillColor(BLUE)
        pdf.circle(MARGIN + 13, step_y - 12, 13, fill=1, stroke=0)
        pdf.setFillColor(WHITE)
        pdf.setFont(FONT_BOLD, 9)
        pdf.drawCentredString(MARGIN + 13, step_y - 15, str(index))
        paragraph(pdf, step_text, MARGIN + 38, step_y - 2, PAGE_W - 2 * MARGIN - 38, size=10, color=TEXT)

    value_y = y - len(steps) * 48 - 10
    pdf.setFillColor(NAVY)
    pdf.roundRect(MARGIN, value_y - 137, PAGE_W - 2 * MARGIN, 137, 7, fill=1, stroke=0)
    paragraph(pdf, "产品价值假设", MARGIN + 18, value_y - 18, PAGE_W - 2 * MARGIN - 36, size=12, bold=True, color=WHITE)
    paragraph(
        pdf,
        "把一次视频寻找任务，从“翻目录 → 猜文件名 → 多次试播 → 手动拖动”"
        "压缩为“一句话搜索 → 查看解释 → 跳转证据”。上线后重点验证搜索成功率、"
        "首次命中时间、错误试播次数和证据跳转使用率。",
        MARGIN + 18,
        value_y - 50,
        PAGE_W - 2 * MARGIN - 36,
        size=9.5,
        color=colors.HexColor("#E5EDF7"),
        leading=17,
    )
    pdf.showPage()

    pdf.save()


if __name__ == "__main__":
    build_pdf()
    print(PDF_PATH)
    print(FLOW_PATH)

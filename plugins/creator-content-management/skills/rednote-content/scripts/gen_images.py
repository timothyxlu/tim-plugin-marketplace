#!/usr/bin/env python3
"""
gen_images.py — Generate Rednote (小红书) post images (cover + content pages).

Usage:
    python gen_images.py --title "AI时代的未来" --keyword "AI Future" \
        --pages '[{"title":"什么是AI","body":"人工智能是..."}]' \
        --output ./output

    python gen_images.py --config post.json --output ./output

Environment:
    Requires Pillow:  pip install Pillow --break-system-packages

Font strategy:
    - Chinese text → CJK font (Noto Sans CJK > Droid Sans Fallback > system fallback)
    - English text → Serif / Sans font (DejaVu Serif, Lato, Liberation Serif, etc.)
    The script auto-detects available fonts and picks the best option.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 1242, 1660
MARGIN = 100

# Cover page colours
COVER_BG_LOWER = "#FFFFFF"
COVER_TITLE_COLOR = "#1A1A1A"
COVER_AUTHOR_COLOR = "#666666"
GRADIENT_COLORS = ["#FF9A56", "#E87CBB", "#C77DBA", "#8CC5E8", "#A8D86C"]

# Content page colours
CONTENT_BG = "#F5E6D3"
CONTENT_NUM_COLOR = "#7A3B10"
CONTENT_TITLE_COLOR = "#7A3B10"
CONTENT_BODY_COLOR = "#8B4513"
CONTENT_SEP_COLOR = "#A0785A"

AUTHOR = "碳基补完计划"


# ---------------------------------------------------------------------------
# Font resolver
# ---------------------------------------------------------------------------
@dataclass
class FontSet:
    """Resolved font paths for CJK and Latin."""
    cjk_regular: str = ""
    cjk_bold: str = ""
    latin_serif: str = ""
    latin_serif_bold: str = ""
    latin_sans: str = ""
    latin_sans_bold: str = ""

    # Cached ImageFont objects
    _cache: dict = field(default_factory=dict, repr=False)

    def get(self, name: str, size: int) -> ImageFont.FreeTypeFont:
        key = (name, size)
        if key not in self._cache:
            path = getattr(self, name, "") or self.cjk_regular
            self._cache[key] = ImageFont.truetype(path, size)
        return self._cache[key]


def _find_font(patterns: list[str]) -> str:
    """Return the first existing font path from *patterns*."""
    for p in patterns:
        if os.path.isfile(p):
            return p
    return ""


def resolve_fonts() -> FontSet:
    fs = FontSet()

    # CJK fonts — prefer Noto Sans/Serif CJK, then Droid fallback
    cjk_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/System/Library/Fonts/PingFang.ttc",           # macOS
        "/System/Library/Fonts/STHeiti Medium.ttc",      # macOS
        "C:\\Windows\\Fonts\\msyh.ttc",                  # Windows
    ]
    cjk_bold_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "C:\\Windows\\Fonts\\msyhbd.ttc",
    ]
    cjk_serif_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
    ]

    fs.cjk_regular = _find_font(cjk_candidates)
    fs.cjk_bold = _find_font(cjk_bold_candidates) or fs.cjk_regular

    # CJK serif for cover title
    cjk_serif = _find_font(cjk_serif_candidates)
    if cjk_serif:
        fs.cjk_bold = cjk_serif  # prefer serif for cover title look

    # Latin serif
    latin_serif_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    ]
    latin_serif_bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ]
    fs.latin_serif = _find_font(latin_serif_candidates)
    fs.latin_serif_bold = _find_font(latin_serif_bold_candidates) or fs.latin_serif

    # Latin sans
    latin_sans_candidates = [
        "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    latin_sans_bold_candidates = [
        "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
        "/usr/share/fonts/truetype/lato/Lato-Black.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    fs.latin_sans = _find_font(latin_sans_candidates)
    fs.latin_sans_bold = _find_font(latin_sans_bold_candidates) or fs.latin_sans

    # Validation
    if not fs.cjk_regular:
        print("WARNING: No CJK font found. Install fonts-noto-cjk or provide a CJK font.", file=sys.stderr)
        print("  apt-get install -y fonts-noto-cjk   (Linux)", file=sys.stderr)

    return fs


# ---------------------------------------------------------------------------
# Text rendering helpers
# ---------------------------------------------------------------------------
CJK_RANGES = [
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0x3400, 0x4DBF),    # CJK Extension A
    (0x3000, 0x303F),    # CJK Punctuation
    (0xFF00, 0xFFEF),    # Fullwidth Forms
    (0x2E80, 0x2EFF),    # CJK Radicals
    (0xFE30, 0xFE4F),    # CJK Compatibility Forms
]


def is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in CJK_RANGES)


def segment_text(text: str) -> list[tuple[str, bool]]:
    """Split text into segments of (text, is_cjk)."""
    if not text:
        return []
    segments: list[tuple[str, bool]] = []
    current = text[0]
    current_is_cjk = is_cjk(text[0])
    for ch in text[1:]:
        ch_cjk = is_cjk(ch)
        if ch_cjk == current_is_cjk:
            current += ch
        else:
            segments.append((current, current_is_cjk))
            current = ch
            current_is_cjk = ch_cjk
    segments.append((current, current_is_cjk))
    return segments


def draw_mixed_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    cjk_font: ImageFont.FreeTypeFont,
    latin_font: ImageFont.FreeTypeFont,
    fill: str,
) -> int:
    """Draw text with different fonts for CJK vs Latin. Returns total width."""
    x, y = xy
    total_w = 0
    for seg, seg_is_cjk in segment_text(text):
        font = cjk_font if seg_is_cjk else latin_font
        bbox = font.getbbox(seg)
        w = bbox[2] - bbox[0]
        draw.text((x + total_w, y), seg, font=font, fill=fill)
        total_w += w
    return total_w


def measure_mixed_text(
    text: str,
    cjk_font: ImageFont.FreeTypeFont,
    latin_font: ImageFont.FreeTypeFont,
) -> int:
    """Measure total width of mixed CJK/Latin text."""
    total = 0
    for seg, seg_is_cjk in segment_text(text):
        font = cjk_font if seg_is_cjk else latin_font
        bbox = font.getbbox(seg)
        total += bbox[2] - bbox[0]
    return total


def wrap_mixed_text(
    text: str,
    max_width: int,
    cjk_font: ImageFont.FreeTypeFont,
    latin_font: ImageFont.FreeTypeFont,
) -> list[str]:
    """Word-wrap mixed CJK/Latin text to fit max_width pixels."""
    lines: list[str] = []
    current_line = ""
    current_width = 0

    i = 0
    chars = list(text)
    while i < len(chars):
        ch = chars[i]
        if ch == "\n":
            lines.append(current_line)
            current_line = ""
            current_width = 0
            i += 1
            continue

        # For Latin words, grab the whole word
        if not is_cjk(ch) and ch not in " \t":
            word = ch
            j = i + 1
            while j < len(chars) and not is_cjk(chars[j]) and chars[j] not in " \t\n":
                word += chars[j]
                j += 1
            font = latin_font
            w = font.getbbox(word)[2] - font.getbbox(word)[0]
            if current_width + w > max_width and current_line:
                lines.append(current_line)
                current_line = word
                current_width = w
            else:
                current_line += word
                current_width += w
            i = j
            continue

        # CJK or space
        font = cjk_font if is_cjk(ch) else latin_font
        w = font.getbbox(ch)[2] - font.getbbox(ch)[0]
        if current_width + w > max_width and current_line:
            lines.append(current_line)
            current_line = ch
            current_width = w
        else:
            current_line += ch
            current_width += w
        i += 1

    if current_line:
        lines.append(current_line)
    return lines


# ---------------------------------------------------------------------------
# Cover page generation
# ---------------------------------------------------------------------------
def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def generate_gradient_upper(width: int, height: int) -> Image.Image:
    """Create an abstract gradient for the cover upper zone."""
    img = Image.new("RGB", (width, height))
    colors = [hex_to_rgb(c) for c in GRADIENT_COLORS]
    random.shuffle(colors)

    # Multi-point radial gradient
    pixels = img.load()
    # Create several "blobs"
    n_blobs = 5
    blobs = []
    for i in range(n_blobs):
        cx = random.randint(0, width)
        cy = random.randint(0, height)
        radius = random.randint(min(width, height) // 3, min(width, height))
        color = colors[i % len(colors)]
        blobs.append((cx, cy, radius, color))

    base_color = hex_to_rgb(GRADIENT_COLORS[0])
    for y in range(height):
        for x in range(width):
            r, g, b = base_color
            for cx, cy, radius, color in blobs:
                dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                if dist < radius:
                    t = 1 - (dist / radius)
                    t = t ** 1.5  # soften falloff
                    r = int(r * (1 - t) + color[0] * t)
                    g = int(g * (1 - t) + color[1] * t)
                    b = int(b * (1 - t) + color[2] * t)
            pixels[x, y] = (min(r, 255), min(g, 255), min(b, 255))

    # Apply slight gaussian blur for smoothness
    from PIL import ImageFilter
    img = img.filter(ImageFilter.GaussianBlur(radius=30))
    return img


def draw_pill_badge(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    text: str,
    center_xy: tuple[int, int],
    cjk_font: ImageFont.FreeTypeFont,
    latin_font: ImageFont.FreeTypeFont,
):
    """Draw a white rounded-rectangle pill with centered text."""
    text_w = measure_mixed_text(text, cjk_font, latin_font)
    bbox_h = cjk_font.getbbox("测试Ag")[3] - cjk_font.getbbox("测试Ag")[1]
    pad_x, pad_y = 50, 25
    pill_w = text_w + pad_x * 2
    pill_h = bbox_h + pad_y * 2
    x1 = center_xy[0] - pill_w // 2
    y1 = center_xy[1] - pill_h // 2
    x2 = x1 + pill_w
    y2 = y1 + pill_h

    # Draw shadow
    shadow_offset = 4
    draw.rounded_rectangle(
        [x1 + shadow_offset, y1 + shadow_offset, x2 + shadow_offset, y2 + shadow_offset],
        radius=pill_h // 2,
        fill=(0, 0, 0, 40),
    )
    # Draw pill
    draw.rounded_rectangle(
        [x1, y1, x2, y2],
        radius=pill_h // 2,
        fill="white",
    )
    # Draw text
    text_x = x1 + pad_x
    text_y = y1 + pad_y
    draw_mixed_text(draw, (text_x, text_y), text, cjk_font, latin_font, fill="#1A1A1A")


def generate_cover(
    title: str,
    keyword: str,
    fonts: FontSet,
    output_path: str,
):
    """Generate the cover page image."""
    upper_h = int(HEIGHT * 0.6)
    divider_h = 4
    lower_h = HEIGHT - upper_h - divider_h

    img = Image.new("RGB", (WIDTH, HEIGHT), COVER_BG_LOWER)
    # --- Upper zone: gradient ---
    gradient = generate_gradient_upper(WIDTH, upper_h)
    img.paste(gradient, (0, 0))

    # --- Divider ---
    div_img = Image.new("RGB", (WIDTH, divider_h))
    for x in range(WIDTH):
        t = x / WIDTH
        idx = int(t * (len(GRADIENT_COLORS) - 1))
        idx = min(idx, len(GRADIENT_COLORS) - 2)
        local_t = (t * (len(GRADIENT_COLORS) - 1)) - idx
        c = _lerp_color(hex_to_rgb(GRADIENT_COLORS[idx]), hex_to_rgb(GRADIENT_COLORS[idx + 1]), local_t)
        for y in range(divider_h):
            div_img.putpixel((x, y), c)
    img.paste(div_img, (0, upper_h))

    draw = ImageDraw.Draw(img)

    # --- Pill badge in upper zone ---
    pill_cjk = fonts.get("cjk_regular", 44)
    pill_latin = fonts.get("latin_sans_bold", 44)
    draw_pill_badge(draw, img, keyword, (WIDTH // 2, upper_h // 2), pill_cjk, pill_latin)

    # --- Lower zone: title + author ---
    lower_top = upper_h + divider_h
    title_font_cjk = fonts.get("cjk_bold", 76)
    title_font_latin = fonts.get("latin_serif_bold", 76)
    max_text_w = WIDTH - MARGIN * 2
    title_lines = wrap_mixed_text(title, max_text_w, title_font_cjk, title_font_latin)

    line_h = title_font_cjk.getbbox("测试")[3] - title_font_cjk.getbbox("测试")[1]
    line_spacing = int(line_h * 0.4)
    total_title_h = len(title_lines) * line_h + (len(title_lines) - 1) * line_spacing

    # Author line
    author_font_cjk = fonts.get("cjk_regular", 36)
    author_font_latin = fonts.get("latin_sans", 36)
    author_text = f"丨作者：{AUTHOR}"
    author_h = author_font_cjk.getbbox("测试")[3] - author_font_cjk.getbbox("测试")[1]

    # Vertical centering in lower zone
    content_h = total_title_h + 40 + author_h
    start_y = lower_top + (lower_h - content_h) // 2

    y = start_y
    for line in title_lines:
        draw_mixed_text(draw, (MARGIN, y), line, title_font_cjk, title_font_latin, COVER_TITLE_COLOR)
        y += line_h + line_spacing

    y += 20
    draw_mixed_text(draw, (MARGIN, y), author_text, author_font_cjk, author_font_latin, COVER_AUTHOR_COLOR)

    img.save(output_path, "PNG")
    print(f"  ✓ Cover saved: {output_path}")


# ---------------------------------------------------------------------------
# Content page generation
# ---------------------------------------------------------------------------
def generate_content_page(
    page_num: int,
    total_pages: int,
    section_title: str,
    body_text: str,
    fonts: FontSet,
    output_path: str,
):
    """Generate a single content page image."""
    bg = hex_to_rgb(CONTENT_BG)
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)

    max_text_w = WIDTH - MARGIN * 2
    y = MARGIN

    # --- Page number ---
    num_font_cjk = fonts.get("cjk_bold", 110)
    num_font_latin = fonts.get("latin_serif_bold", 110)
    num_str = f"{page_num:02d}"
    draw_mixed_text(draw, (MARGIN, y), num_str, num_font_cjk, num_font_latin, CONTENT_NUM_COLOR)
    num_h = num_font_latin.getbbox("00")[3] - num_font_latin.getbbox("00")[1]
    y += num_h + 50

    # --- Section title ---
    title_font_cjk = fonts.get("cjk_bold", 52)
    title_font_latin = fonts.get("latin_serif_bold", 52)
    title_lines = wrap_mixed_text(section_title, max_text_w, title_font_cjk, title_font_latin)
    title_line_h = title_font_cjk.getbbox("测试")[3] - title_font_cjk.getbbox("测试")[1]

    for line in title_lines:
        draw_mixed_text(draw, (MARGIN, y), line, title_font_cjk, title_font_latin, CONTENT_TITLE_COLOR)
        y += title_line_h + 10
    y += 30

    # --- Separator ---
    sep_color_rgb = hex_to_rgb(CONTENT_SEP_COLOR)
    line_y = y + 15
    draw.line([(MARGIN, line_y), (MARGIN + 120, line_y)], fill=sep_color_rgb, width=3)
    y += 40

    # --- Body text ---
    body_font_cjk = fonts.get("cjk_regular", 40)
    body_font_latin = fonts.get("latin_serif", 40)
    body_line_h = body_font_cjk.getbbox("测试")[3] - body_font_cjk.getbbox("测试")[1]
    line_spacing = int(body_line_h * 0.7)  # 1.7x line height

    # Split body by paragraphs, then wrap each
    paragraphs = body_text.split("\n")
    for para in paragraphs:
        para = para.strip()
        if not para:
            y += line_spacing
            continue
        lines = wrap_mixed_text(para, max_text_w, body_font_cjk, body_font_latin)
        for line in lines:
            if y + body_line_h > HEIGHT - MARGIN - 60:
                break  # don't overflow
            draw_mixed_text(draw, (MARGIN, y), line, body_font_cjk, body_font_latin, CONTENT_BODY_COLOR)
            y += body_line_h + line_spacing

    # --- Page indicator (bottom-right) ---
    indicator = f"{page_num}/{total_pages}"
    ind_font = fonts.get("latin_sans", 30)
    ind_w = ind_font.getbbox(indicator)[2] - ind_font.getbbox(indicator)[0]
    draw.text((WIDTH - MARGIN - ind_w, HEIGHT - MARGIN), indicator, font=ind_font, fill=CONTENT_SEP_COLOR)

    img.save(output_path, "PNG")
    print(f"  ✓ Page {page_num:02d} saved: {output_path}")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
@dataclass
class ContentPage:
    title: str
    body: str


@dataclass
class PostConfig:
    title: str                       # Cover title (Chinese)
    keyword: str                     # Pill badge text
    pages: list[ContentPage]         # Content pages
    author: str = AUTHOR


def generate_post(config: PostConfig, output_dir: str) -> list[str]:
    """Generate all images for a post. Returns list of file paths."""
    os.makedirs(output_dir, exist_ok=True)

    fonts = resolve_fonts()
    if not fonts.cjk_regular:
        print("ERROR: No CJK font available. Cannot generate images.", file=sys.stderr)
        sys.exit(1)

    paths: list[str] = []

    # Cover
    cover_path = os.path.join(output_dir, "cover.png")
    generate_cover(config.title, config.keyword, fonts, cover_path)
    paths.append(cover_path)

    # Content pages
    total = len(config.pages)
    for i, page in enumerate(config.pages, 1):
        page_path = os.path.join(output_dir, f"page_{i:02d}.png")
        generate_content_page(i, total, page.title, page.body, fonts, page_path)
        paths.append(page_path)

    print(f"\nGenerated {len(paths)} image(s) in {output_dir}")
    return paths


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate Rednote post images")
    parser.add_argument("--title", help="Cover page title (Chinese)")
    parser.add_argument("--keyword", help="Pill badge keyword")
    parser.add_argument(
        "--pages",
        help='JSON array: [{"title":"...", "body":"..."},...]',
    )
    parser.add_argument(
        "--config",
        help="Path to JSON config file (alternative to --title/--keyword/--pages)",
    )
    parser.add_argument(
        "--output", default="./output",
        help="Output directory (default: ./output)",
    )
    args = parser.parse_args()

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = PostConfig(
            title=data["title"],
            keyword=data["keyword"],
            pages=[ContentPage(**p) for p in data["pages"]],
            author=data.get("author", AUTHOR),
        )
    elif args.title and args.keyword and args.pages:
        pages_data = json.loads(args.pages)
        config = PostConfig(
            title=args.title,
            keyword=args.keyword,
            pages=[ContentPage(**p) for p in pages_data],
        )
    else:
        parser.error("Provide either --config or all of --title, --keyword, --pages")

    generate_post(config, args.output)


if __name__ == "__main__":
    main()

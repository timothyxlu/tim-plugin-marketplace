---
description: Extract and summarize TLDR newsletter articles from Gmail
argument-hint: <category|"ai","tech","dev","marketing","fintech","infosec","product","design">
---

Extract and summarize a TLDR newsletter. Follow these steps precisely:

## Step 1: Load TLDR Skill & Environment

1. Read the TLDR skill at `${CLAUDE_PLUGIN_ROOT}/skills/tldr-scraper/SKILL.md`.
2. Load environment variables from `${CLAUDE_PLUGIN_ROOT}/.env`:
   ```python
   from dotenv import load_dotenv
   load_dotenv(os.path.join(os.environ.get("CLAUDE_PLUGIN_ROOT", "."), ".env"))
   ```

## Step 2: Determine Category & Language

The user's argument is: $ARGUMENTS

- If a category is specified (e.g., "ai", "dev"), use it to filter Gmail search.
- If no category, search for the most recent TLDR email and let the user pick, or process the most recent one.
- Determine the output language per the skill's Step 0 rules.

## Step 3: Extract & Summarize

Follow the skill's extraction workflow (Steps 1-4): search Gmail → parse email → fetch all articles in parallel → generate summaries.

## Step 4: Save Locally

Save the assembled Markdown file to the user's workspace:

- Save to: `{workspace}/outputs/tldr-{category}-news-YYYY-MM-DD.md`
- Create the directory if it doesn't exist
- Present the local file path to the user

## Step 5: Save to Notion

Search Notion for the “原始资源” data source. Create a new empty page under it with these properties first:

- **名称**: Newsletter name and date (e.g., “TLDR AI - 2026-03-10”)
- **来源**: “View Online” URL from the email
- **类别**: “业界新闻”

Then update the page using one tool call per news following below rules:

**Notion formatting rules:**

When saving to Notion, adjust the Markdown format:
- **短摘要**: Plain paragraph text with `📋` prefix — do NOT wrap in blocks
- **详细摘要**: Wrap in block with `<summary>📖 详细摘要</summary>`
- **Reserving Content**: Do not compact content when upload to Notion.

## Step 6: Generate Podcast TTS Script

Convert the Markdown summaries into a TTS-ready podcast script for "今日AI":

**Podcast profile:**
- Name: 今日AI
- Format: 单人播报，每日一期
- Target audience: 喜欢科技行业的普通读者
- Tone: 36氪等科技媒体的口吻——专业但不晦涩，有节奏感，适度口语化
- Total length: 不超过30分钟（约6000-8000字）

**Script structure:**
1. **开场白**: 简短问候 + 日期 + 今日亮点预告（2-3句）
2. **正文**: 逐条播报新闻，每条包含：
   - 过渡语（自然衔接，避免机械的"第一条、第二条"）
   - 新闻标题和核心内容（用口语化方式复述，不要照念原文）
   - 简短点评或背景补充（帮助听众理解新闻的意义）
3. **结尾**: 总结今日要点 + 固定结束语

**TTS formatting rules:**
- 纯文本，不使用 Markdown 格式符号
- 使用自然的中文标点断句，方便 TTS 引擎正确停顿
- 英文专有名词首次出现时标注中文释义，之后可直接使用英文
- 避免过长句子，每句控制在30字以内
- 段落之间用空行分隔，表示较长停顿

Save the script to: `{workspace}/outputs/tldr-{category}-podcast-YYYY-MM-DD.txt`

## Step 7: Save Podcast Script to Notion

Search Notion for the "Podcasts" database. Create a new page under it with these properties:

- **Name/Title**: "今日AI - YYYY-MM-DD"(use the actual date)

Then update the page content with the full TTS script from Step 6, preserving plain text formatting with paragraph breaks.

## Step 8: Generate Podcast Audio

Run the TTS script to convert the podcast text from Step 6 into an audio file:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/tts_minimax.py \
  --input {workspace}/outputs/tldr-{category}-podcast-YYYY-MM-DD.txt \
  --output {workspace}/outputs/tldr-{category}-podcast-YYYY-MM-DD.mp3 \
  --voice_id "Chinese (Mandarin)_Radio_Host"
```

The script will submit the task, poll for completion, and download the MP3 automatically. Present the output file path to the user when done.
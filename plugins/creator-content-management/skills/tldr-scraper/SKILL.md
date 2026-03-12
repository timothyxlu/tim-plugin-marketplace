---
name: tldr-scraper
description: Extract TLDR newsletter articles from Gmail, fetch originals, and generate bilingual summaries in Markdown.
---
 
# TLDR Newsletter Scraper (Gmail-based)
 
A skill for extracting tech news from TLDR newsletters **via Gmail** and converting them into well-structured Markdown files with categorized links and **AI-generated summaries** for each article.
 
## Overview
 
This skill enables Claude to:
1. **Search Gmail** for the latest TLDR newsletter email (from `dan@tldrnewsletter.com`)
2. **Read the full email body** and parse all article sections
3. Extract article titles, URLs, categories, read times, and TLDR's own blurbs
4. **Fetch each article's original content** via `web_fetch`
5. **Generate a short summary (<100 words) and a detailed summary (<1000 words, scaled to content length)** for each article
6. Output summaries in **foldable `<details>` blocks** in Markdown
 
## Step 0: Determine Output Language (MUST DO FIRST)
 
Before fetching any content, determine whether the output Markdown file should be in **English** or **Chinese (中文)**. This affects all summaries, section headers, and UI text in the final file.
 
**Detection rules (in order of priority):**
1. **Explicit request** — If the user specifies a language (e.g., "用中文", "in English", "中文摘要"), use that.
2. **Conversation language** — If the user's message is written in Chinese, default to Chinese output. If in English, default to English.
3. **Memory/context** — Check if user preferences (e.g., from memory or past conversations) indicate a preferred language.
4. **When in doubt — ASK.**
 
**What changes by language:**
 
| Element | English | Chinese |
|---------|---------|---------|
| File header / intro | English | 中文 |
| Section headers (🚀 Headlines, etc.) | English labels | 中文标签 (e.g., 🚀 头条新闻) |
| 短摘要 / Short summary | English | 中文 |
| 详细摘要 / Detailed summary | English | 中文 |
| Article titles & links | Original (unchanged) | Original (unchanged) |
| Category & read time labels | English | English (keep original) |
| Footer / generation note | English | 中文 |
 
---
 
## Extraction Workflow
 
### Step 1: Search Gmail for the Latest TLDR Newsletter
 
Use the Gmail MCP tool to find the most recent TLDR newsletter email.
 
⚠️ **IMPORTANT: Match BOTH sender name AND email address.** All TLDR newsletters share the same email address `dan@tldrnewsletter.com`, but each category has a distinct sender display name (e.g., `TLDR AI`, `TLDR Dev`, `TLDR Fintech`). You MUST use `from:"<Sender Name>"` combined with `from:dan@tldrnewsletter.com` to correctly filter by category.
 
**For a specific category** (e.g., TLDR AI):
```
gmail_search_messages(q='from:"TLDR AI" from:dan@tldrnewsletter.com', maxResults=1)
```
 
**For any/all TLDR newsletters:**
```
gmail_search_messages(q="from:dan@tldrnewsletter.com", maxResults=5)
```
 
**Category-specific search queries (use sender display name for precise filtering):**
 
| Category | Sender Display Name | Search query |
|----------|-------------------|-------------|
| AI | `TLDR AI` | `from:"TLDR AI" from:dan@tldrnewsletter.com` |
| Tech (main) | `TLDR` | `from:"TLDR" from:dan@tldrnewsletter.com` (note: may also match other TLDR variants; verify the `From` header in results) |
| Dev | `TLDR Dev` | `from:"TLDR Dev" from:dan@tldrnewsletter.com` |
| Marketing | `TLDR Marketing` | `from:"TLDR Marketing" from:dan@tldrnewsletter.com` |
| Fintech | `TLDR Fintech` | `from:"TLDR Fintech" from:dan@tldrnewsletter.com` |
| InfoSec | `TLDR InfoSec` | `from:"TLDR InfoSec" from:dan@tldrnewsletter.com` |
| Product | `TLDR Product` | `from:"TLDR Product" from:dan@tldrnewsletter.com` |
| Design | `TLDR Design` | `from:"TLDR Design" from:dan@tldrnewsletter.com` |
 
**Verification step**: After getting search results, always check the `From` header in the returned message to confirm it matches the expected sender name (e.g., `TLDR AI <dan@tldrnewsletter.com>`). If results contain a different sender name, refine the query or pick the correct message.
 
If the user just says "TLDR" without specifying a category, search for the most recent emails from `dan@tldrnewsletter.com` and let them pick, or process the most recent one.
 
### Step 2: Read the Full Email Body
 
```
gmail_read_message(messageId="<message_id_from_step_1>")
```
 
The email body is plain text with a well-defined structure. Key parsing rules:
 
#### Email Body Structure
 
The TLDR newsletter email body follows this general pattern:
 
```
TLDR AI 2026-03-10            ← Newsletter name and date
 
SPONSOR SECTION (skip)        ← Starts after "TOGETHER WITH [sponsor]"
                                 Ends before first section header
 
🚀
HEADLINES & LAUNCHES          ← START extraction here
 
 ARTICLE TITLE (X MINUTE READ) [N]
 
 TLDR's blurb paragraph...
 
 ANOTHER ARTICLE TITLE (X MINUTE READ) [N]
 
 TLDR's blurb...
 
🧠
DEEP DIVES & ANALYSIS
 
 ARTICLE TITLE (X MINUTE READ) [N]
 ...
 
🧑‍💻
ENGINEERING & RESEARCH
 
 DEBUG WITH AI... (SPONSOR) [N]  ← Skip any line with "(SPONSOR)"
 
 ARTICLE TITLE (X MINUTE READ) [N]
 ...
 
🎁
MISCELLANEOUS
 
 ARTICLE TITLE (X MINUTE READ) [N]
 ...
 
⚡
QUICK LINKS                   ← STOP extraction here
 
 ...                          ← Do NOT process Quick Links
 
Links:
------
[1] https://...
[2] https://...
...
```
 
#### Parsing Rules
 
1. **Start extraction** at the first section header after the sponsor block. Section headers are marked by emoji icons followed by section names: `🚀 HEADLINES & LAUNCHES`, `🧠 DEEP DIVES & ANALYSIS`, `🧑‍💻 ENGINEERING & RESEARCH`, `🎁 MISCELLANEOUS`, etc.
 
2. **Stop extraction** at `⚡ QUICK LINKS`. Do NOT process Quick Links — they are short one-liners without enough substance for summaries.
 
3. **Skip SPONSOR entries**: Any article title containing `(SPONSOR)` must be skipped entirely (both title and blurb).
 
4. **Extract for each article:**
   - **Title**: ALL CAPS text followed by `(X MINUTE READ)` — convert to Title Case in output
   - **Read time**: The `(X MINUTE READ)` part
   - **URL**: Found in the `Links:` section at the bottom of the email, referenced by `[N]` numbers. Match the `[N]` after each title to the corresponding URL.
   - **TLDR blurb**: The paragraph(s) following the title, before the next title
   - **Category/section**: Determined by which section header the article falls under
 
5. **URL resolution**: The email body uses `[N]` reference-style links. The actual URLs are listed at the bottom under `Links:` like:
   ```
   Links:
   ------
   [5] https://www.promptfoo.dev/blog/promptfoo-joining-openai/?utm_source=tldrai
   [6] https://techcrunch.com/2026/03/09/...
   ```
   Map each article's `[N]` to the corresponding URL.
 
### Step 3: Fetch Each Article's Original Content
 
⚠️ **MANDATORY — NO EXCEPTIONS: You MUST call `web_fetch` on EVERY article URL.**
 
This is the most important step. **Do NOT skip any article.** Do NOT use TLDR's email blurb as a substitute for fetching the original. Do NOT cite "原文无法访问" unless you have actually attempted the fetch and it genuinely failed.
 
**Compliance checklist (enforce strictly):**
1. For EVERY article extracted in Step 2, call `web_fetch` with the article's URL
2. Only after a `web_fetch` call returns an actual error (403, 404, timeout, empty body) may you fall back to TLDR's blurb
3. If you find yourself writing "原文无法访问" for more than 3 articles in a single run, stop and re-examine — you are likely skipping fetches
4. Never batch-skip articles to "save tool calls" — thoroughness is more important than speed
 
```
web_fetch url="<article_url>" html_extraction_method="markdown" text_content_token_limit=4000
```
 
**Fetch rules:**
- Fetch articles **in parallel** — launch multiple `web_fetch` calls concurrently since they are independent. Do not skip any.
- If a fetch genuinely fails (timeout, 403, paywall), try `web_search` with the article title to find alternative coverage or cached content. If web search also fails, fall back to TLDR's own blurb for the short summary and note the failure in the detailed summary. Use the output language from Step 0 — e.g., Chinese: "⚠️ 原文无法访问（已尝试抓取及搜索，返回错误：[具体错误]）", English: "⚠️ Original article unavailable (fetch and search attempted, error: [specific error])"
- For paywalled sites, use whatever preview content is available from `web_fetch`, or search for alternative coverage via `web_search`
- Set a reasonable token limit: `text_content_token_limit=8000`
 
### Step 4: Generate Summaries
 
For each article, generate **two summaries** from the fetched content:
 
#### Short Summary (短摘要)
- **Max 100 words**
- One paragraph, no bullet points
- Capture the single most important takeaway
- Language determined by Step 0
 
#### Detailed Summary (详细摘要)
- **Scaled to original content length, max 1000 words**
- Scaling guide:
  - 1-2 min read (~500 words original) → ~150-200 word summary
  - 3-5 min read (~1000-1500 words original) → ~300-500 word summary
  - 5-10 min read (~2000-3000 words original) → ~600-800 word summary
  - 10+ min read (3000+ words original) → up to 1000 word summary
- Structured paragraphs covering: main thesis, key evidence/data, implications, and context
- May include brief bullet points for listing multiple findings or features
- Maintain factual accuracy — do not hallucinate details not in the source
 
### Step 5: Assemble Markdown with Foldable Blocks
 
Use the section headers from the email as category groupings:
 
```markdown
# TLDR AI News - 2026-03-10
 
> 自动从 TLDR AI Newsletter (via Gmail) 提取的科技新闻摘要（含 AI 生成的短摘要与详细摘要）
 
---
 
## 🚀 头条新闻 / Headlines & Launches
 
### [Article Title](https://link-to-article)
**X minute read**
 
📋 Short summary here (plain text, no block)...
 
<details>
<summary>📖 详细摘要</summary>
 
Detailed summary here...
 
</details>
 
---
 
## 🧠 深度分析 / Deep Dives & Analysis
 
### [Article Title](https://link)
**X minute read**
 
📋 Short summary here...
 
<details>
<summary>📖 详细摘要</summary>
 
...
 
</details>
 
---
 
## 🧑‍💻 工程与研究 / Engineering & Research
 
...
 
---
 
## 🎁 杂项 / Miscellaneous
 
...
 
---
 
*生成于 [DATE] · 数据来源: TLDR AI Newsletter*
```
 
#### Section Header Mapping

| Email Section | Output Header (Chinese) | Output Header (English) |
|---------------|------------------------|------------------------|
| HEADLINES & LAUNCHES | 🚀 头条新闻 | 🚀 Headlines & Launches |
| DEEP DIVES & ANALYSIS | 🧠 深度分析 | 🧠 Deep Dives & Analysis |
| ENGINEERING & RESEARCH | 🧑‍💻 工程与研究 | 🧑‍💻 Engineering & Research |
| MISCELLANEOUS | 🎁 杂项 | 🎁 Miscellaneous |

**Formatting notes:**
- Always include a blank line after `<summary>` closing tag and before content
- Always include a blank line before `</details>` closing tag

## Error Handling
 
- If Gmail search returns no results, inform the user and suggest checking their subscriptions
- If `gmail_read_message` returns an empty body, try the next most recent email
- If an **individual article fetch fails** (and ONLY after actually attempting the fetch):
  - Try `web_search` with the article title to find alternative coverage
  - If search finds usable content, summarize from that source and note it
  - If both fetch and search fail, use TLDR's own blurb as the short summary
  - In the detailed summary block, note the failure in the output language from Step 0 — e.g., Chinese: "⚠️ 原文无法访问（已尝试抓取及搜索）— 仅使用 TLDR 提供的简介", English: "⚠️ Original article unavailable (fetch and search attempted) — using TLDR blurb only"
- **NEVER write a fetch-failure notice without having actually called `web_fetch` and `web_search` first**
- If the email body structure doesn't match expected format, fall back to best-effort parsing and note any issues
 

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

Automatically save the digest to the notion “原始资料”data source, category field is “业界新闻”

**Properties:**
- **标题**: Newsletter name and date (e.g., "TLDR AI - 2026-03-10")
- **类别**: Newsletter category (e.g., "AI", "Tech")
- **日期**: Newsletter date (YYYY-MM-DD)

**Notion formatting rules:**

When saving to Notion, adjust the Markdown format:
- **短摘要**: Plain paragraph text with `📋` prefix — do NOT wrap in `<details>` blocks
- **详细摘要**: Wrap in `<details>` block with `<summary>📖 详细摘要</summary>`

```markdown
### [Article Title](https://link)
**X minute read**

📋 短摘要内容直接显示在这里，不折叠...

<details>
<summary>📖 详细摘要</summary>

详细摘要内容...

</details>

---
```

**Forbidden formats** (even if used in the past):
- ❌ Short summary with `**📋 短摘要**` bold text on its own line
- ❌ Short summary wrapped in `<details>` block
- ✅ Short summary = plain paragraph text starting with `📋`

**Important**: Always include a blank line after `<summary>` tag and before content, and a blank line before `</details>` tag.

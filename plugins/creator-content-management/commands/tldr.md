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

Then start to update the page gradually following below rules:

**Notion formatting rules:**

When saving to Notion, adjust the Markdown format:
- **短摘要**: Plain paragraph text with `📋` prefix — do NOT wrap in blocks
- **详细摘要**: Wrap in block with `<summary>📖 详细摘要</summary>`
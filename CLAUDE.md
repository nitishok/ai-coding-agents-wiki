# CLAUDE.md — AI Coding Agents Wiki Website

## Project Overview

This project builds a **personal Wikipedia-style website** that serves as a frontend for the AI Coding Agents knowledge base stored in an Obsidian vault.

---

## Directory Structure

```
/projects/ai-coding-agents/ai-coding-agents/   ← Obsidian vault (SOURCE — READ ONLY)
/projects/vibe-coding/ai-coding-agents-wiki/   ← Website project (ALL CODE GOES HERE)
```

---

## ⚠️ CRITICAL RULES — Read Before Every Task

### Rule 1: NEVER touch the Obsidian vault
- The Obsidian vault at `/projects/ai-coding-agents/ai-coding-agents/` is the **source of truth**
- **Read it. Never write to it. Never create files in it. Never modify files in it.**
- Treat it as a read-only external data source
- This includes `.obsidian/` config, any `.md` files, any attachments

### Rule 2: All code lives in the wiki project folder
- Every file you create — HTML, CSS, JS, config, scripts, README — goes inside `/projects/vibe-coding/ai-coding-agents-wiki/`
- Never place code, build artifacts, or config files outside this folder

### Rule 3: Wikipedia UI style
- The website must look and feel like Wikipedia — see UI spec below
- No modern SaaS aesthetics, no gradient cards, no dark mode dashboards
- The reference is: https://en.wikipedia.org — classic, encyclopedic, content-first

---

## Obsidian Vault — How to Read Content

The vault at `/projects/ai-coding-agents/ai-coding-agents/` contains Markdown files (`.md`).

**Reading strategy:**
1. List all `.md` files to discover available pages
2. Parse Obsidian-flavored Markdown: `[[WikiLinks]]`, `#tags`, YAML frontmatter
3. Convert `[[Page Name]]` links to internal website URLs
4. Treat the filename (without `.md`) as the article title if no frontmatter title exists
5. Ignore `.obsidian/` folder entirely — it is internal Obsidian config

**Frontmatter fields to use:**
- `title:` → Article title
- `tags:` → Article categories
- `aliases:` → Alternate titles / redirects
- `date:` or `created:` → Article date

---

## Suggested Project Structure

```
/projects/vibe-coding/ai-coding-agents-wiki/
├── CLAUDE.md                  ← This file (copy here too so Claude Code can find it)
├── README.md                  ← Project documentation
├── package.json               ← If using Node-based build tools
├── scripts/
│   └── build.py / build.js   ← Script to read vault and generate HTML
├── src/
│   ├── templates/
│   │   ├── article.html       ← Article page template
│   │   ├── index.html         ← Main page / portal template
│   │   └── category.html      ← Category listing template
│   ├── static/
│   │   ├── css/
│   │   │   └── wiki.css       ← Wikipedia-style CSS
│   │   ├── js/
│   │   │   └── wiki.js        ← Search, TOC, navigation
│   │   └── images/
│   │       └── logo.png       ← Personal wiki logo
│   └── partials/
│       ├── sidebar.html       ← Left nav sidebar
│       ├── header.html        ← Top navigation
│       └── footer.html        ← Footer with metadata
└── dist/                      ← Built/generated HTML output
    ├── index.html
    ├── articles/
    └── categories/
```

---

## Wikipedia UI Specification

### Visual Style
- **Background**: `#f8f9fa` (page background), `#ffffff` (content area)
- **Text**: `#202122` (body), `#0645ad` (links), `#a2a9b1` (borders)
- **Font**: Linux Libertine, Georgia, Times, serif — for body text
- **Headings**: Same serif stack, clear hierarchy (h1 > h2 > h3)
- **Link style**: Blue underline, visited links turn purple (`#551a8b`)
- **No rounded corners on major elements** — Wikipedia uses sharp rectangular boxes

### Layout — Classic Two-Column
```
┌─────────────────────────────────────────────────────────┐
│  [Logo] Personal Wiki: AI Coding Agents      [Search]   │  ← Header
├──────────────┬──────────────────────────────────────────┤
│              │  Article Title                           │
│  Navigation  │  ─────────────────────────────────────  │
│  sidebar     │  [TOC box — top right or top of content] │
│              │                                          │
│  • Main Page │  Body content in serif font...           │
│  • Topics    │                                          │
│  • Tags      │  == Section Heading ==                   │
│  • Recent    │  Content...                              │
│              │                                          │
│              │  === Sub-section ===                     │
│              │  Content...                              │
│              │                                          │
└──────────────┴──────────────────────────────────────────┘
│  Footer: last modified · categories · page info         │
└─────────────────────────────────────────────────────────┘
```

### Required UI Components

**1. Header bar**
- Left: wiki logo + site title ("AI Coding Agents — Personal Wiki")
- Right: search box (search across all articles)
- Thin blue-gray border at bottom

**2. Left sidebar (Navigation)**
- "Navigation" section: Main Page, All Topics, All Tags, Recent Changes
- "Tools" section: What links here, Printable version
- "Categories" section: dynamically generated from vault tags
- Thin right border separating sidebar from content

**3. Article content area**
- Article title as `<h1>` — large, serif, no top margin
- Byline: last modified date (from file mtime or frontmatter)
- Infobox (if article has frontmatter metadata worth displaying) — right-aligned table, bordered, light gray header
- Table of Contents box — auto-generated from `## Heading` sections, shown if article has 3+ headings
- Body content — parsed Markdown rendered to HTML
- `[[WikiLink]]` links converted to internal `<a href="/articles/page-name">` links
- Section edit hints are optional (can be `[edit]` placeholders)
- Category footer: "Categories: tag1 · tag2 · tag3"

**4. Footer**
- "This page was last modified on [date]"
- "Content source: Obsidian vault"
- "Personal wiki · AI Coding Agents KB"

### CSS Rules
```css
/* Core variables */
:root {
  --bg: #f8f9fa;
  --content-bg: #ffffff;
  --text: #202122;
  --link: #0645ad;
  --link-visited: #551a8b;
  --border: #a2a9b1;
  --sidebar-width: 160px;
  --content-max: 960px;
  --font-body: 'Linux Libertine', 'Georgia', 'Times', serif;
  --font-sans: -apple-system, 'Helvetica Neue', Arial, sans-serif;
}

/* No border-radius on Wikipedia-style components */
/* Tables use collapse borders */
/* TOC has light gray background, solid border */
/* Infoboxes float right, max 320px wide */
/* Content links always underlined */
```

### TOC Box Style
```
┌─────────────────────────┐
│ Contents [hide]         │
│ 1 Introduction          │
│ 2 Tools & Agents        │
│   2.1 Claude Code       │
│   2.2 Cursor            │
│ 3 Patterns              │
│ 4 References            │
└─────────────────────────┘
```

### Search
- Top-right search box (Wikipedia style — plain input with "Search" button)
- Search should scan article titles first, then full content
- Can be implemented as: client-side JS search over a pre-built search index JSON, OR a simple query-string filter if static
- Results page shows matching article titles + excerpt snippets

---

## Build Approach Options

Choose the simplest option that works for local use:

### Option A — Pure Static (Recommended for simplicity)
- Python script reads all `.md` files from the vault
- Converts Markdown → HTML using a library (e.g. `python-markdown`, `mistune`)
- Writes static HTML files into `dist/`
- No server needed — open `dist/index.html` in browser
- Search via pre-built JSON index + client-side JS (lunr.js or fuse.js)

### Option B — Local Dev Server (Better DX)
- Use a lightweight Python Flask or Node Express server
- Reads vault files at request time (no build step needed)
- Supports live reload when vault files change
- Run: `python app.py` or `node server.js` then visit `http://localhost:5000`

### Option C — Static Site Generator
- Use Eleventy (11ty) or Jekyll with custom templates
- Configure vault path as content source
- Outputs to `dist/`

**Default recommendation:** Start with Option A (Python static generator) — minimal dependencies, runs anywhere, no server needed.

---

## Markdown Parsing Rules

When converting Obsidian Markdown to HTML:

| Obsidian syntax         | HTML output                                      |
|-------------------------|--------------------------------------------------|
| `[[Page Name]]`         | `<a href="/articles/page-name">Page Name</a>`   |
| `[[Page\|Display]]`     | `<a href="/articles/page">Display</a>`           |
| `#tag`                  | `<a href="/categories/tag" class="tag">#tag</a>` |
| `![[image.png]]`        | `<img src="/static/images/image.png">`           |
| `==highlighted==`       | `<mark>highlighted</mark>`                       |
| `---` (frontmatter)     | Parse as metadata, do not render                 |
| `> [!NOTE]`             | Render as Wikipedia-style hatnote or info box    |
| `- [ ] task`            | Render as `☐ task` (no interactive checkbox)    |

---

## Article URL Convention

- Filename: `my article name.md` → URL: `/articles/my-article-name`
- Spaces → hyphens, lowercase, strip special characters
- Index page: `/` → Main Page (like Wikipedia's Main Page)
- Category pages: `/categories/tag-name`
- All articles: `/articles/` (full index)

---

## Main Page Design

The main page (`index.html`) should mimic Wikipedia's Main Page layout:

```
┌──────────────────────────────────────────────────────────┐
│  Welcome to AI Coding Agents — Personal Wiki             │
│  [nn] articles · last updated [date]                     │
├────────────────────────┬─────────────────────────────────┤
│  Featured Article      │  Topics & Categories            │
│  ─────────────────     │  ─────────────────────          │
│  [excerpt of a key     │  • Agentic Engineering          │
│   article, auto-       │  • Spec-Driven Dev              │
│   selected or pinned]  │  • Prompting                    │
│                        │  • Evals                        │
│                        │  • MCP                          │
│                        │  • Tools & Agents               │
│                        │  • Enterprise Patterns          │
├────────────────────────┴─────────────────────────────────┤
│  Recent Articles (last 10 modified files from vault)     │
│  Article title · [date]                                  │
└──────────────────────────────────────────────────────────┘
```

---

## What NOT to Build

- Do not build a fancy modern UI (no Tailwind dark-mode dashboards)
- Do not add user accounts, login, or editing via the website
- Do not write back to the Obsidian vault in any way
- Do not add unnecessary dependencies — keep it lean
- Do not use React or heavy JS frameworks unless the user explicitly asks
- Do not style with purple gradients or rounded card grids

---

## Testing Checklist

Before considering the site complete:

- [ ] All vault `.md` files are parsed and have a corresponding HTML page
- [ ] `[[WikiLinks]]` resolve correctly to internal pages
- [ ] Broken links (links to pages that don't exist in vault) show gracefully (red link style like Wikipedia)
- [ ] TOC is auto-generated for articles with 3+ headings
- [ ] Search returns results across all articles
- [ ] Categories page lists all tags found in vault
- [ ] Left sidebar navigation works on every page
- [ ] Site renders correctly in Chrome/Firefox/Safari
- [ ] No files have been created or modified inside the Obsidian vault path

---

## Running the Site (Expected Commands)

After build:

```bash
# Option A — Static build
cd /projects/vibe-coding/ai-coding-agents-wiki
python scripts/build.py
open dist/index.html

# Option B — Dev server
cd /projects/vibe-coding/ai-coding-agents-wiki
python app.py
# → Visit http://localhost:5000

# Option C — 11ty
cd /projects/vibe-coding/ai-coding-agents-wiki
npm run build   # or npm run dev for live server
```

---

## Session Start Checklist

At the start of every Claude Code session on this project:

1. Re-read this CLAUDE.md
2. Confirm you are working inside `/projects/vibe-coding/ai-coding-agents-wiki/`
3. Do a quick `ls` of the Obsidian vault to understand available content — **do not write to it**
4. Check `dist/` to understand what has already been built
5. Ask the user which task to tackle if not specified

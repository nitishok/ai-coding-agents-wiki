#!/usr/bin/env python3
"""
Static site generator for the AI Coding Agents Wiki.
Reads Obsidian vault markdown files and generates Wikipedia-style HTML pages.
"""

import os
import re
import json
import shutil
import datetime
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlparse

try:
    import markdown
    from markdown.extensions.toc import TocExtension
except ImportError:
    print("Installing python-markdown...")
    os.system("pip3 install markdown")
    import markdown
    from markdown.extensions.toc import TocExtension

# Paths — configurable via env vars for CI/GitHub Pages
_default_vault = os.path.expanduser("~/Projects/obsidian-vaults/ai-coding-agents/ai-coding-agents")
VAULT_PATH = Path(os.environ.get("VAULT_PATH", _default_vault))
PROJECT_PATH = Path(os.environ.get("PROJECT_PATH", os.path.expanduser("~/Projects/vibe-coding/ai-coding-agents-wiki")))

# URL prefix for GitHub Pages project sites (e.g. "/ai-coding-agents-wiki").
# Empty string for local dev (served from root).
BASE_PATH = os.environ.get("GITHUB_PAGES_BASE", "").rstrip("/")
DIST_PATH = PROJECT_PATH / "dist"
STATIC_SRC = PROJECT_PATH / "src" / "static"

# Cache-buster for static asset URLs (regenerated each build).
BUILD_VERSION = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

# Files to skip entirely
SKIP_FILES = {"CLAUDE.md", "raw/Untitled.md"}
SKIP_NAMES = {"CLAUDE.md", "Untitled.md"}

# Files that are meta/index — include but mark as such
META_FILES = {"_index.md", "_summaries.md"}

# Topic portals — shared by main page and topic pages
TOPIC_PORTALS = [
    {"id": "context-engineering", "title": "Context Engineering",
     "tags": {"context-engineering", "context-windows", "memory", "prompting", "rag"}},
    {"id": "agentic-coding", "title": "Agentic Coding",
     "tags": {"agentic-coding", "patterns", "workflow", "workflows", "vibe-coding",
              "autonomy", "orchestration", "multi-agent"}},
    {"id": "harness-engineering", "title": "Harness Engineering",
     "tags": {"harness", "scaffolding", "agent-design", "hooks", "long-running"}},
    {"id": "evals", "title": "Evals &amp; Quality",
     "tags": {"evals", "testing", "code-quality", "quality", "benchmarks",
              "safeguards", "ai-readiness", "empirical"}},
    {"id": "sdd", "title": "Spec-Driven Dev",
     "tags": {"sdd", "spec-driven-development", "spec-driven", "planning"}},
    {"id": "enterprise", "title": "Enterprise &amp; Regulated",
     "tags": {"enterprise", "regulated", "gxp", "validation", "compliance",
              "production", "landscape", "comparison"}},
]
CURATED_TYPES = {'concept', 'paper', 'tool', 'mental-model', 'note'}
TYPE_ORDER = {'concept': 0, 'paper': 1, 'tool': 2, 'mental-model': 3, 'note': 4}


def slugify(name):
    """Convert a page name to a URL slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def parse_frontmatter(content):
    """Extract YAML frontmatter from markdown content."""
    metadata = {}
    body = content
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            fm = parts[1].strip()
            body = parts[2].strip()
            for line in fm.split('\n'):
                if ':' in line:
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    if val.startswith('[') and val.endswith(']'):
                        val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(',')]
                    elif (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    metadata[key] = val
    return metadata, body


def extract_wikilink_targets(text):
    """Extract all wikilink targets from markdown text (for backlinks)."""
    targets = []
    for match in re.finditer(r'\[\[([^\]]+)\]\]', text):
        full = match.group(1)
        if '|' in full:
            target = full.split('|', 0)[0]
        else:
            target = full
        target_name = target.split('/')[-1]
        targets.append(slugify(target_name))
    return targets


def convert_wikilinks(text, all_slugs, pdf_to_summary=None):
    """Convert [[WikiLink]] and [[Page|Display]] to HTML links.
    PDF references are mapped to their paper summary if available."""
    pdf_to_summary = pdf_to_summary or {}

    def replace_link(match):
        full = match.group(1)
        if '|' in full:
            target, display = full.split('|', 1)
        else:
            target = full
            display = full

        target_name = target.split('/')[-1]

        # PDF reference: map to paper summary if known, else render as italic citation
        if target_name.lower().endswith('.pdf'):
            pdf_slug = slugify(target_name.rsplit('.', 1)[0])
            mapping = pdf_to_summary.get(pdf_slug)
            if mapping:
                summary_slug, summary_title = mapping
                label = display if display != full else summary_title
                return f'<a href="{BASE_PATH}/articles/{summary_slug}.html" class="paper-ref" title="Summary: {summary_title}">{label}</a>'
            label = display if display != full else target_name
            return f'<cite class="citation">{label}</cite>'

        slug = slugify(target_name)
        if slug in all_slugs:
            return f'<a href="{BASE_PATH}/articles/{slug}.html">{display}</a>'
        else:
            return f'<a href="{BASE_PATH}/articles/{slug}.html" class="redlink" title="This page does not exist yet">{display}</a>'

    return re.sub(r'\[\[([^\]]+)\]\]', replace_link, text)


def auto_link_first_mentions(text, term_map, current_slug):
    """Auto-link the first occurrence of each known concept term to its wiki page.

    Wikipedia convention: link the first mention only. Skip code blocks, existing
    links (markdown or wikilink), and headings. Don't link a term to its own article.
    """
    if not term_map:
        return text

    # Split out fenced code blocks so we don't auto-link inside code
    parts = re.split(r'(```[\s\S]*?```)', text)

    # Sort terms longest-first to prefer specific matches (e.g., "Spec-Driven Development" over "Development")
    sorted_terms = sorted(term_map.keys(), key=len, reverse=True)

    linked = set()  # terms already linked anywhere in this article

    def process_segment(segment):
        # Split out inline code spans
        inline_parts = re.split(r'(`[^`\n]+`)', segment)
        for i, ip in enumerate(inline_parts):
            if ip.startswith('`') and ip.endswith('`'):
                continue  # skip inline code
            inline_parts[i] = process_text(ip)
        return ''.join(inline_parts)

    def process_text(s):
        # Process line by line so we can skip heading lines
        lines = s.split('\n')
        for li, line in enumerate(lines):
            if line.lstrip().startswith('#'):
                continue
            for term in sorted_terms:
                if term in linked:
                    continue
                slug, display = term_map[term]
                if slug == current_slug:
                    continue
                # Word-boundary, case-insensitive search for term in this line
                pattern = re.compile(r'(?<![\w\[/])(' + re.escape(term) + r')(?![\w\]])', re.IGNORECASE)

                # Replace first occurrence outside existing markdown links/wikilinks
                def safe_replace(m, _slug=slug):
                    # Check if match is inside a markdown link or wikilink by scanning the line
                    start = m.start()
                    before = line[:start]
                    # If preceding part has unclosed [ or [[, skip
                    open_brackets = before.count('[') - before.count(']')
                    if open_brackets > 0:
                        return m.group(0)
                    linked.add(term)
                    return f'[{m.group(0)}]({BASE_PATH}/articles/{_slug}.html)'

                new_line, n = pattern.subn(safe_replace, line, count=1)
                if n > 0:
                    lines[li] = new_line
                    line = new_line  # in case more terms match this line
        return '\n'.join(lines)

    for i, part in enumerate(parts):
        if part.startswith('```'):
            continue  # skip fenced code blocks
        parts[i] = process_segment(part)

    return ''.join(parts)


def convert_highlights(text):
    """Convert ==highlight== to <mark>."""
    return re.sub(r'==([^=]+)==', r'<mark>\1</mark>', text)


def convert_callouts(text):
    """Convert > [!NOTE] style callouts to styled divs."""
    lines = text.split('\n')
    result = []
    in_callout = False
    for line in lines:
        if re.match(r'>\s*\[!(NOTE|TIP|WARNING|INFO)\]', line):
            in_callout = True
            callout_type = re.search(r'\[!(\w+)\]', line).group(1).lower()
            result.append(f'<div class="callout callout-{callout_type}"><strong>{callout_type.title()}:</strong> ')
        elif in_callout and line.startswith('>'):
            result.append(line[1:].strip())
        elif in_callout:
            in_callout = False
            result.append('</div>')
            result.append(line)
        else:
            result.append(line)
    if in_callout:
        result.append('</div>')
    return '\n'.join(result)


def generate_toc(html_content):
    """Generate table of contents from h2 and h3 tags."""
    headings = re.findall(r'<h([23])[^>]*id="([^"]*)"[^>]*>(.*?)</h[23]>', html_content)
    if len(headings) < 3:
        return ""

    toc_html = '<div class="toc"><div class="toc-title">Contents <span class="toc-toggle">[hide]</span></div><ul>'
    counter = [0, 0]
    for level, id_, text in headings:
        level = int(level)
        clean_text = re.sub(r'<[^>]+>', '', text)
        if level == 2:
            counter[0] += 1
            counter[1] = 0
            toc_html += f'<li><a href="#{id_}">{counter[0]} {clean_text}</a></li>'
        elif level == 3:
            counter[1] += 1
            toc_html += f'<li style="margin-left:16px"><a href="#{id_}">{counter[0]}.{counter[1]} {clean_text}</a></li>'
    toc_html += '</ul></div>'
    return toc_html


def render_markdown(text):
    """Convert markdown to HTML with TOC extension for heading IDs."""
    md = markdown.Markdown(extensions=[
        'tables',
        'fenced_code',
        TocExtension(permalink=False, slugify=lambda value, separator: slugify(value)),
    ])
    return md.convert(text)


def build_infobox(metadata):
    """Build an infobox table from metadata."""
    rows = ""
    if 'created' in metadata:
        rows += f'<tr><th>Created</th><td>{metadata["created"]}</td></tr>'
    if 'updated' in metadata:
        rows += f'<tr><th>Updated</th><td>{metadata["updated"]}</td></tr>'
    if 'tags' in metadata:
        tags = metadata['tags']
        if isinstance(tags, list):
            tag_links = ' · '.join(f'<a href="{BASE_PATH}/categories/{slugify(t)}.html">{t}</a>' for t in tags)
            rows += f'<tr><th>Tags</th><td>{tag_links}</td></tr>'
    if 'sources' in metadata:
        sources = metadata['sources']
        if isinstance(sources, list):
            source_links = '<br>'.join(sources)
            rows += f'<tr><th>Sources</th><td>{len(sources)} source(s)</td></tr>'

    if not rows:
        return ""

    return f'''<table class="infobox">
<tr class="infobox-title"><td colspan="2">Article Info</td></tr>
{rows}
</table>'''


def classify_article(path):
    """Classify an article by its vault location."""
    if 'wiki/concepts' in path:
        return 'concept'
    elif 'wiki/papers' in path:
        return 'paper'
    elif 'wiki/tools' in path:
        return 'tool'
    elif 'wiki/mental-models' in path:
        return 'mental-model'
    elif 'raw/articles' in path:
        return 'source'
    elif 'raw/written-notes' in path:
        return 'note'
    elif 'outputs/reports' in path:
        return 'report'
    else:
        return 'page'


def page_template(title, content, all_categories, current_slug=None):
    """Wrap content in the full page HTML template."""
    cat_links = ""
    for cat in sorted(all_categories)[:15]:
        cat_links += f'<li><a href="{BASE_PATH}/categories/{slugify(cat)}.html">{cat}</a></li>'

    # "What links here" in tools section — link to backlinks page if we have a slug
    tools_links = ""
    if current_slug:
        tools_links = f'<li><a href="{BASE_PATH}/backlinks/{current_slug}.html">What links here</a></li>'
    tools_links += f'<li><a href="{BASE_PATH}/articles/index.html">All articles</a></li>'

    sidebar = f'''<nav class="wiki-sidebar">
<h3>Navigation</h3>
<ul>
<li><a href="{BASE_PATH}/index.html">Main Page</a></li>
<li><a href="{BASE_PATH}/articles/index.html">All Articles</a></li>
<li><a href="{BASE_PATH}/categories/index.html">All Categories</a></li>
</ul>
<h3>Categories</h3>
<ul>
{cat_links}
</ul>
<h3>Tools</h3>
<ul>
{tools_links}
</ul>
</nav>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — AI Coding Agents Wiki</title>
<link rel="stylesheet" href="{BASE_PATH}/static/css/wiki.css?v={BUILD_VERSION}">
</head>
<body>
<header class="wiki-header">
<div class="wiki-header-left">
<a href="{BASE_PATH}/index.html" class="site-title">AI Coding Agents — Personal Wiki</a>
</div>
<div class="wiki-header-right">
<form class="search-box" onsubmit="return handleSearch(event)">
<input type="text" placeholder="Search wiki..." id="search-input">
<button type="submit">Search</button>
</form>
</div>
</header>
<div class="wiki-layout">
{sidebar}
<main class="wiki-content">
{content}
</main>
</div>
<footer class="wiki-footer">
Content source: Obsidian vault · Personal wiki · AI Coding Agents KB
</footer>
<script src="{BASE_PATH}/static/js/wiki.js?v={BUILD_VERSION}"></script>
<script>
function handleSearch(e) {{
  e.preventDefault();
  var q = document.getElementById('search-input').value.trim();
  if (q) performSearch(q);
  return false;
}}
</script>
</body>
</html>'''


def build_article_page(title, metadata, body_html, toc_html, infobox_html, backlinks, all_categories, slug, article_type):
    """Build a complete article page."""
    meta_line = ""
    if metadata.get('updated'):
        meta_line = f'<div class="article-meta">Last updated: {metadata["updated"]}</div>'
    elif metadata.get('created'):
        meta_line = f'<div class="article-meta">Created: {metadata["created"]}</div>'

    # Type badge
    type_labels = {
        'concept': 'Concept',
        'paper': 'Paper Summary',
        'tool': 'Tool',
        'mental-model': 'Mental Model',
        'source': 'Source Article',
        'note': 'Written Note',
        'report': 'Report',
        'page': 'Page',
    }
    type_label = type_labels.get(article_type, '')
    if type_label and article_type != 'page':
        meta_line += f' <span class="article-type-badge">{type_label}</span>'

    # Source URL hatnote (top) and External Links section (bottom)
    hatnote_html = ""
    external_links_html = ""
    source_url = metadata.get('source')
    if source_url and isinstance(source_url, str) and source_url.startswith(('http://', 'https://')):
        try:
            domain = urlparse(source_url).netloc.replace('www.', '')
        except Exception:
            domain = 'source'
        hatnote_html = (
            f'<div class="hatnote">From <a href="{source_url}" rel="nofollow noopener" target="_blank">{domain}</a> '
            f'— <a href="{source_url}" rel="nofollow noopener" target="_blank">View original</a></div>'
        )
        external_links_html = (
            f'<div class="external-links">\n'
            f'<h2 id="external-links">External links</h2>\n'
            f'<ul><li><a href="{source_url}" rel="nofollow noopener" target="_blank">Original article on {domain}</a></li></ul>\n'
            f'</div>'
        )

    cat_footer = ""
    if metadata.get('tags') and isinstance(metadata['tags'], list):
        tags_html = ' · '.join(f'<a href="{BASE_PATH}/categories/{slugify(t)}.html">{t}</a>' for t in metadata['tags'])
        cat_footer = f'<div class="category-footer">Categories: {tags_html}</div>'

    # Backlinks section
    backlinks_html = ""
    if backlinks:
        bl_items = ""
        for bl_slug, bl_title in sorted(backlinks, key=lambda x: x[1]):
            bl_items += f'<li><a href="{BASE_PATH}/articles/{bl_slug}.html">{bl_title}</a></li>'
        backlinks_html = f'''<div class="backlinks-section">
<h2 id="backlinks">Pages that link here</h2>
<ul>{bl_items}</ul>
</div>'''

    content = f'''<h1>{title}</h1>
{meta_line}
{hatnote_html}
{infobox_html}
{toc_html}
{body_html}
{external_links_html}
{backlinks_html}
{cat_footer}'''

    return page_template(title, content, all_categories, current_slug=slug)


def build_backlinks_page(slug, title, backlinks, all_categories):
    """Build a 'What links here' page for a given article."""
    if backlinks:
        items = ""
        for bl_slug, bl_title in sorted(backlinks, key=lambda x: x[1]):
            items += f'<li><a href="{BASE_PATH}/articles/{bl_slug}.html">{bl_title}</a></li>'
        listing = f'<ul class="category-list">{items}</ul>'
    else:
        listing = '<p>No other pages link to this article.</p>'

    content = f'''<h1>Pages that link to "{title}"</h1>
<p class="article-meta"><a href="{BASE_PATH}/articles/{slug}.html">← Back to {title}</a></p>
{listing}'''

    return page_template(f"What links here: {title}", content, all_categories)


def build_main_page(articles, all_categories):
    """Build the main/index page."""
    SHOW_N = 4

    def portal_articles(portal):
        matched = [
            a for a in articles
            if a.get('type') in CURATED_TYPES
            and set(a.get('tags') or []) & portal['tags']
        ]
        matched.sort(key=lambda a: (TYPE_ORDER.get(a.get('type'), 9), a['title']))
        return matched

    def render_portal(portal):
        matched = portal_articles(portal)
        show = matched[:SHOW_N]
        remainder = len(matched) - SHOW_N
        items = ''.join(
            f'<li><a href="{BASE_PATH}/articles/{a["slug"]}.html">{a["title"]}</a></li>'
            for a in show
        )
        more = (f'<li class="portal-more"><a href="{BASE_PATH}/topics/{portal["id"]}.html">'
                f'{remainder} more &rarr;</a></li>') if remainder > 0 else ''
        empty = '<li><em>No articles tagged yet.</em></li>' if not show else ''
        return (f'<div class="portal-box">'
                f'<h3 class="portal-heading"><a href="{BASE_PATH}/topics/{portal["id"]}.html">{portal["title"]}</a></h3>'
                f'<ul class="portal-list">{items}{more}{empty}</ul>'
                f'</div>')

    portal_boxes = ''.join(render_portal(p) for p in TOPIC_PORTALS)
    portal_grid_html = f'<div class="portal-grid">{portal_boxes}</div>'

    # My Writing section — concepts/mental-models + papers
    my_concepts = sorted(
        [a for a in articles if a.get('type') in ('concept', 'mental-model')],
        key=lambda a: a['title']
    )
    my_papers = sorted(
        [a for a in articles if a.get('type') == 'paper'],
        key=lambda a: a['title']
    )

    def writing_list(items):
        return ''.join(
            f'<li><a href="{BASE_PATH}/articles/{a["slug"]}.html">{a["title"]}</a>'
            f' <span class="article-type-badge">{a["type"]}</span></li>'
            for a in items
        )

    my_writing_html = f'''<div class="main-page-section">
<h2>My Writing</h2>
<div class="my-writing-columns">
<div>
<h3>Concepts &amp; Mental Models</h3>
<ul class="portal-list">{writing_list(my_concepts)}</ul>
</div>
<div>
<h3>Paper Summaries</h3>
<ul class="portal-list">{writing_list(my_papers)}</ul>
</div>
</div>
</div>'''

    # Recently Updated
    sorted_articles = sorted(articles, key=lambda a: a.get('updated', a.get('created', '')), reverse=True)
    recent_html = '<div class="main-page-section recent-articles"><h2>Recently Updated</h2><ul>'
    for a in sorted_articles[:15]:
        date = a.get('updated', a.get('created', ''))
        type_badge = f' <span class="article-type-badge">{a.get("type", "")}</span>' if a.get('type') else ''
        recent_html += f'<li><a href="{BASE_PATH}/articles/{a["slug"]}.html">{a["title"]}</a>{type_badge}<span class="date">{date}</span></li>'
    recent_html += '</ul></div>'

    # Source articles
    source_articles = sorted(
        [a for a in articles if a.get('type') == 'source'],
        key=lambda a: a['title']
    )
    source_items = ''.join(
        f'<li><a href="{BASE_PATH}/articles/{a["slug"]}.html">{a["title"]}</a></li>'
        for a in source_articles
    )
    source_html = f'''<div class="main-page-section">
<h2>Source Articles <span class="section-count">({len(source_articles)})</span></h2>
<p class="section-desc">Saved web clippings and reference material.</p>
<ul class="portal-list source-list">{source_items}</ul>
</div>'''

    content = f'''<h1>AI Coding Agents — Personal Wiki</h1>
<div class="main-page-welcome">
Welcome to the <strong>AI Coding Agents</strong> knowledge base — a personal Wikipedia-style wiki compiling research, patterns, and tools for agentic AI-assisted software development.<br>
<strong>{len(articles)}</strong> articles · Last updated: {datetime.date.today().isoformat()}
</div>
{portal_grid_html}
<div class="main-page-two-col">
<div class="main-page-col-wide">{my_writing_html}</div>
<div class="main-page-col-narrow">{recent_html}</div>
</div>
{source_html}'''

    return page_template("Main Page", content, all_categories)


def build_category_page(category, articles, all_categories):
    """Build a category listing page."""
    matching = [a for a in articles if category in (a.get('tags') or [])]
    items = ""
    for a in sorted(matching, key=lambda x: x['title']):
        type_badge = f' <span class="article-type-badge">{a.get("type", "")}</span>'
        items += f'<li><a href="{BASE_PATH}/articles/{a["slug"]}.html">{a["title"]}</a>{type_badge}</li>'

    content = f'''<h1>Category: {category}</h1>
<p class="article-meta">{len(matching)} article(s) in this category.</p>
<ul class="category-list">{items}</ul>'''

    return page_template(f"Category: {category}", content, all_categories)


def build_categories_index(all_categories, articles):
    """Build the categories index page."""
    items = ""
    for cat in sorted(all_categories):
        count = sum(1 for a in articles if cat in (a.get('tags') or []))
        items += f'<li><a href="{BASE_PATH}/categories/{slugify(cat)}.html">{cat}</a> ({count} articles)</li>'

    content = f'''<h1>All Categories</h1>
<p class="article-meta">{len(all_categories)} categories.</p>
<ul class="category-list">{items}</ul>'''
    return page_template("All Categories", content, all_categories)


def build_topic_page(portal, articles, all_categories):
    """Build a topic page listing all articles matching a portal's tag set."""
    matched = [
        a for a in articles
        if a.get('type') in CURATED_TYPES
        and set(a.get('tags') or []) & portal['tags']
    ]
    matched.sort(key=lambda a: (TYPE_ORDER.get(a.get('type'), 9), a['title']))

    # Also collect source articles that match
    sources = [
        a for a in articles
        if a.get('type') == 'source'
        and set(a.get('tags') or []) & portal['tags']
    ]
    sources.sort(key=lambda a: a['title'])

    def render_list(items):
        return ''.join(
            f'<li><a href="{BASE_PATH}/articles/{a["slug"]}.html">{a["title"]}</a>'
            f' <span class="article-type-badge">{a.get("type","")}</span></li>'
            for a in items
        )

    curated_section = f'<ul class="category-list">{render_list(matched)}</ul>' if matched else '<p>No articles yet.</p>'
    source_section = (f'<h2>Source Articles ({len(sources)})</h2>'
                      f'<ul class="category-list">{render_list(sources)}</ul>') if sources else ''

    content = (f'<h1>Topic: {portal["title"]}</h1>'
               f'<p class="article-meta"><a href="{BASE_PATH}/">← Main Page</a></p>'
               f'<p class="article-meta">{len(matched)} curated articles · {len(sources)} source articles</p>'
               f'{curated_section}'
               f'{source_section}')

    return page_template(f'Topic: {portal["title"]}', content, all_categories)


def build_articles_index(articles, all_categories):
    """Build the all-articles index page."""
    # Group by type
    by_type = defaultdict(list)
    for a in articles:
        by_type[a.get('type', 'page')].append(a)

    type_order = [
        ('concept', 'Concepts'),
        ('paper', 'Paper Summaries'),
        ('tool', 'Tools'),
        ('mental-model', 'Mental Models'),
        ('source', 'Source Articles'),
        ('note', 'Written Notes'),
        ('report', 'Reports'),
        ('page', 'Other Pages'),
    ]

    sections = ""
    for type_key, type_label in type_order:
        group = by_type.get(type_key, [])
        if not group:
            continue
        items = ""
        for a in sorted(group, key=lambda x: x['title']):
            items += f'<li><a href="{BASE_PATH}/articles/{a["slug"]}.html">{a["title"]}</a></li>'
        sections += f'<h2>{type_label} ({len(group)})</h2><ul class="category-list">{items}</ul>'

    content = f'''<h1>All Articles</h1>
<p class="article-meta">{len(articles)} articles in this wiki.</p>
{sections}'''
    return page_template("All Articles", content, all_categories)


def main():
    print("Building AI Coding Agents Wiki...")
    print(f"Vault: {VAULT_PATH}")
    print(f"Output: {DIST_PATH}")

    # Clean dist
    if DIST_PATH.exists():
        shutil.rmtree(DIST_PATH)
    DIST_PATH.mkdir(parents=True)

    # Collect ALL markdown files from the vault
    md_files = []
    for fpath in VAULT_PATH.rglob("*.md"):
        # Skip .obsidian directory
        if '.obsidian' in fpath.parts:
            continue
        # Skip specific files
        if fpath.name in SKIP_NAMES:
            continue
        # Skip empty files (no content or only whitespace)
        try:
            if not fpath.read_text(encoding='utf-8').strip():
                print(f"  Skipping empty file: {fpath.relative_to(VAULT_PATH)}")
                continue
        except (OSError, UnicodeDecodeError):
            continue
        md_files.append(fpath)

    print(f"Found {len(md_files)} articles to process.")

    # Priority order — lower number = higher priority (keeps the clean slug)
    type_priority = {
        'concept': 0,
        'paper': 1,
        'tool': 2,
        'mental-model': 3,
        'page': 4,
        'report': 5,
        'source': 6,
        'note': 7,
    }

    # Sort files by priority so high-priority files claim the clean slug first
    def file_priority(fp):
        rel = str(fp.relative_to(VAULT_PATH))
        return type_priority.get(classify_article(rel), 99)

    md_files.sort(key=file_priority)

    # First pass: collect all articles and slugs (with collision handling)
    all_slugs = set()
    articles = []
    slug_to_idx = {}

    for fpath in md_files:
        raw_content = fpath.read_text(encoding='utf-8')
        metadata, body = parse_frontmatter(raw_content)

        # Title: from h1 in body, or filename
        title_match = re.match(r'^#\s+(.+)$', body, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
        else:
            title = fpath.stem.replace('-', ' ').replace('_', ' ').title()

        base_slug = slugify(fpath.stem)
        rel_path = str(fpath.relative_to(VAULT_PATH))
        article_type = classify_article(rel_path)

        # Handle slug collisions: prefix with parent directory name
        slug = base_slug
        if slug in all_slugs:
            parent_name = slugify(fpath.parent.name)
            slug = f"{parent_name}-{base_slug}"
            # If still colliding, append a counter
            counter = 2
            while slug in all_slugs:
                slug = f"{parent_name}-{base_slug}-{counter}"
                counter += 1
            print(f"  Slug collision: {rel_path} -> {slug}")

        all_slugs.add(slug)

        idx = len(articles)
        articles.append({
            'path': rel_path,
            'title': title,
            'slug': slug,
            'metadata': metadata,
            'body': body,
            'tags': metadata.get('tags', []),
            'created': metadata.get('created', ''),
            'updated': metadata.get('updated', ''),
            'type': article_type,
        })
        slug_to_idx[slug] = idx

    # Build backlinks map: target_slug -> [(source_slug, source_title), ...]
    backlinks_map = defaultdict(list)
    for article in articles:
        targets = extract_wikilink_targets(article['body'])
        for target_slug in set(targets):  # deduplicate
            if target_slug != article['slug']:  # don't self-link
                backlinks_map[target_slug].append((article['slug'], article['title']))

    print(f"  Backlinks computed: {sum(len(v) for v in backlinks_map.values())} total links across {len(backlinks_map)} targets")

    # Build PDF → paper-summary map: read 'sources' frontmatter on each wiki/papers article.
    pdf_to_summary = {}
    for a in articles:
        if a['type'] != 'paper':
            continue
        for src in (a['metadata'].get('sources') or []):
            if isinstance(src, str) and src.lower().endswith('.pdf'):
                pdf_name = src.rsplit('/', 1)[-1]
                pdf_to_summary[slugify(pdf_name.rsplit('.', 1)[0])] = (a['slug'], a['title'])
                pdf_to_summary[slugify(pdf_name)] = (a['slug'], a['title'])
        # Also map by 'arxiv' frontmatter (e.g., "2603.09619v2")
        arxiv_id = a['metadata'].get('arxiv')
        if arxiv_id and isinstance(arxiv_id, str):
            pdf_to_summary[slugify(arxiv_id)] = (a['slug'], a['title'])
    print(f"  PDF→summary mappings: {len(pdf_to_summary)} keys for {len(set(v[0] for v in pdf_to_summary.values()))} papers")

    # Build term map for auto-linking first mentions of curated concepts.
    # Only curated articles (concept/paper/tool/mental-model) are linkable targets.
    term_map = {}
    for a in articles:
        if a['type'] not in ('concept', 'paper', 'tool', 'mental-model'):
            continue
        title = a['title']
        # Only register reasonably specific terms (skip 1-2 char titles)
        if len(title) >= 3:
            term_map[title.lower()] = (a['slug'], title)
        for alias in (a['metadata'].get('aliases') or []):
            if isinstance(alias, str) and len(alias) >= 3:
                term_map[alias.lower()] = (a['slug'], alias)
    print(f"  Auto-link terms: {len(term_map)}")

    # Collect all categories
    all_categories = set()
    for a in articles:
        tags = a.get('tags', [])
        if isinstance(tags, list):
            all_categories.update(tags)

    # Create output directories
    (DIST_PATH / "articles").mkdir(parents=True, exist_ok=True)
    (DIST_PATH / "categories").mkdir(parents=True, exist_ok=True)
    (DIST_PATH / "backlinks").mkdir(parents=True, exist_ok=True)
    (DIST_PATH / "topics").mkdir(parents=True, exist_ok=True)
    (DIST_PATH / "static" / "css").mkdir(parents=True, exist_ok=True)
    (DIST_PATH / "static" / "js").mkdir(parents=True, exist_ok=True)

    # Copy static files
    shutil.copy2(STATIC_SRC / "css" / "wiki.css", DIST_PATH / "static" / "css" / "wiki.css")
    shutil.copy2(STATIC_SRC / "js" / "wiki.js", DIST_PATH / "static" / "js" / "wiki.js")

    # Build search index
    search_index = []

    for article in articles:
        body = article['body']

        # Auto-link first mentions of known concepts (operates on raw markdown
        # before wikilinks are converted, so the resulting [text](url) renders cleanly).
        body = auto_link_first_mentions(body, term_map, article['slug'])

        # Convert obsidian syntax
        body = convert_wikilinks(body, all_slugs, pdf_to_summary)
        body = convert_highlights(body)
        body = convert_callouts(body)

        # Render markdown to HTML
        html_body = render_markdown(body)

        # Generate TOC
        toc_html = generate_toc(html_body)

        # Infobox
        infobox_html = build_infobox(article['metadata'])

        # Get backlinks for this article
        backlinks = backlinks_map.get(article['slug'], [])

        # Build article page
        page_html = build_article_page(
            article['title'], article['metadata'], html_body, toc_html, infobox_html,
            backlinks, all_categories, article['slug'], article['type']
        )

        # Write article page
        out_path = DIST_PATH / "articles" / f"{article['slug']}.html"
        out_path.write_text(page_html, encoding='utf-8')

        # Build backlinks page ("What links here")
        bl_page_html = build_backlinks_page(article['slug'], article['title'], backlinks, all_categories)
        (DIST_PATH / "backlinks" / f"{article['slug']}.html").write_text(bl_page_html, encoding='utf-8')

        # Add to search index
        plain_body = re.sub(r'<[^>]+>', '', html_body)
        search_index.append({
            'title': article['title'],
            'url': f"{BASE_PATH}/articles/{article['slug']}.html",
            'content': plain_body[:1000],
            'tags': article.get('tags', []),
        })

    # Build main page
    main_html = build_main_page(articles, all_categories)
    (DIST_PATH / "index.html").write_text(main_html, encoding='utf-8')

    # Build topic pages
    for portal in TOPIC_PORTALS:
        topic_html = build_topic_page(portal, articles, all_categories)
        (DIST_PATH / "topics" / f"{portal['id']}.html").write_text(topic_html, encoding='utf-8')

    # Build category pages
    for cat in all_categories:
        cat_html = build_category_page(cat, articles, all_categories)
        (DIST_PATH / "categories" / f"{slugify(cat)}.html").write_text(cat_html, encoding='utf-8')

    # Categories index
    cat_index_html = build_categories_index(all_categories, articles)
    (DIST_PATH / "categories" / "index.html").write_text(cat_index_html, encoding='utf-8')

    # Articles index
    articles_index_html = build_articles_index(articles, all_categories)
    (DIST_PATH / "articles" / "index.html").write_text(articles_index_html, encoding='utf-8')

    # Write search index JSON
    (DIST_PATH / "search-index.json").write_text(json.dumps(search_index, indent=None), encoding='utf-8')

    # Summary
    by_type = defaultdict(int)
    for a in articles:
        by_type[a.get('type', 'page')] += 1

    print(f"\nBuild complete!")
    print(f"  Total articles: {len(articles)}")
    for t, c in sorted(by_type.items()):
        print(f"    {t}: {c}")
    print(f"  Categories: {len(all_categories)}")
    print(f"  Backlink pages: {len(backlinks_map)}")
    print(f"  Output: {DIST_PATH}")
    print(f"\nTo view: open {DIST_PATH / 'index.html'}")
    print(f"Or serve: python3 -m http.server 8000 -d {DIST_PATH}")


if __name__ == '__main__':
    main()

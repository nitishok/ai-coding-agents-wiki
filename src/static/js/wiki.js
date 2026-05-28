// Search functionality
let searchIndex = [];

document.addEventListener('DOMContentLoaded', function() {
  // Load search index
  fetch('/search-index.json')
    .then(r => r.json())
    .then(data => { searchIndex = data; })
    .catch(() => {
      fetch('./search-index.json')
        .then(r => r.json())
        .then(data => { searchIndex = data; })
        .catch(() => {});
    });

  // Wire up live autocomplete on the search input
  const input = document.getElementById('search-input');
  const searchForm = document.querySelector('.search-box');
  if (input && searchForm) {
    const dropdown = document.createElement('div');
    dropdown.className = 'search-dropdown';
    dropdown.setAttribute('role', 'listbox');
    searchForm.appendChild(dropdown);

    let activeIndex = -1;

    function renderDropdown(matches, q) {
      if (!matches.length) {
        dropdown.innerHTML = '<div class="search-empty">No matches</div>';
      } else {
        dropdown.innerHTML = matches.map((m, i) =>
          `<a class="search-suggest" role="option" data-index="${i}" href="${m.url}">${highlight(m.title, q)}</a>`
        ).join('');
      }
      dropdown.style.display = 'block';
      activeIndex = -1;
    }

    function hideDropdown() {
      dropdown.style.display = 'none';
      activeIndex = -1;
    }

    function setActive(idx) {
      const items = dropdown.querySelectorAll('.search-suggest');
      items.forEach(it => it.classList.remove('active'));
      if (idx >= 0 && idx < items.length) {
        items[idx].classList.add('active');
        items[idx].scrollIntoView({ block: 'nearest' });
      }
      activeIndex = idx;
    }

    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      if (q.length < 2) { hideDropdown(); return; }
      const matches = searchIndex
        .map(i => ({ ...i, score: scoreItem(i, q) }))
        .filter(i => i.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, 8);
      renderDropdown(matches, q);
    });

    input.addEventListener('keydown', (e) => {
      const items = dropdown.querySelectorAll('.search-suggest');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (items.length) setActive(Math.min(activeIndex + 1, items.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (items.length) setActive(Math.max(activeIndex - 1, 0));
      } else if (e.key === 'Enter') {
        if (activeIndex >= 0 && items[activeIndex]) {
          e.preventDefault();
          window.location.href = items[activeIndex].getAttribute('href');
        }
      } else if (e.key === 'Escape') {
        hideDropdown();
      }
    });

    // Hide dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!searchForm.contains(e.target)) hideDropdown();
    });

    // Submit handler still works as a fallback (full results page)
    searchForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const query = input.value.trim();
      if (query) {
        hideDropdown();
        performSearch(query);
      }
    });
  }

  // TOC toggle
  const tocToggle = document.querySelector('.toc-toggle');
  if (tocToggle) {
    tocToggle.addEventListener('click', function() {
      const tocList = document.querySelector('.toc ul');
      if (tocList.style.display === 'none') {
        tocList.style.display = '';
        tocToggle.textContent = '[hide]';
      } else {
        tocList.style.display = 'none';
        tocToggle.textContent = '[show]';
      }
    });
  }
});

function scoreItem(item, q) {
  let score = 0;
  const titleLower = item.title.toLowerCase();
  const contentLower = (item.content || '').toLowerCase();

  if (titleLower === q) score += 100;
  else if (titleLower.startsWith(q)) score += 60;
  else if (titleLower.includes(q)) score += 40;

  const words = q.split(/\s+/);
  words.forEach(word => {
    if (titleLower.includes(word)) score += 10;
    if (contentLower.includes(word)) score += 2;
  });
  return score;
}

function highlight(title, q) {
  const escaped = escapeHtml(title);
  if (!q) return escaped;
  const re = new RegExp('(' + escapeRegex(q) + ')', 'ig');
  return escaped.replace(re, '<mark>$1</mark>');
}

function performSearch(query) {
  const resultsContainer = document.querySelector('.wiki-content');
  if (!resultsContainer) return;

  const q = query.toLowerCase();
  const results = searchIndex
    .map(item => ({ ...item, score: scoreItem(item, q) }))
    .filter(item => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 20);

  let html = `<h1>Search results</h1>`;
  html += `<p class="article-meta">Results for: <strong>${escapeHtml(query)}</strong></p>`;

  if (results.length === 0) {
    html += `<p>No results found for "${escapeHtml(query)}".</p>`;
  } else {
    html += `<div class="search-results">`;
    results.forEach(item => {
      const snippet = getSnippet(item.content || '', query);
      html += `<div class="search-result-item">`;
      html += `<h3><a href="${item.url}">${escapeHtml(item.title)}</a></h3>`;
      html += `<div class="snippet">${snippet}</div>`;
      html += `</div>`;
    });
    html += `</div>`;
  }

  resultsContainer.innerHTML = html;
  document.title = `Search: ${query} — AI Coding Agents Wiki`;
}

function getSnippet(content, query) {
  const words = query.toLowerCase().split(/\s+/);
  const plainText = content.replace(/[#*_\[\]`]/g, '').substring(0, 2000);
  const idx = plainText.toLowerCase().indexOf(words[0]);
  const start = Math.max(0, idx - 60);
  const end = Math.min(plainText.length, idx + 200);
  let snippet = (start > 0 ? '...' : '') + plainText.substring(start, end) + (end < plainText.length ? '...' : '');

  words.forEach(word => {
    const re = new RegExp(`(${escapeRegex(word)})`, 'gi');
    snippet = snippet.replace(re, '<mark>$1</mark>');
  });

  return snippet;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

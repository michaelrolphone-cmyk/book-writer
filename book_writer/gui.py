"""Neumorphic GUI template for the Book Writer project."""
from __future__ import annotations

from pathlib import Path

GUI_TITLE = "Book Writer Catalogue"


def get_gui_html() -> str:
    """Return the HTML for the neumorphic book catalogue GUI."""
    html = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>__TITLE__</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #e6ebf1;
        --shadow-light: #ffffff;
        --shadow-dark: #c8ced8;
        --accent: #1f6feb;
        --text: #1f2430;
        --muted: #6c7485;
        --surface: #f3f6fb;
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        font-family: "SF Pro Display", "Segoe UI", system-ui, -apple-system, sans-serif;
        background: var(--bg);
        color: var(--text);
      }

      .app {
        max-width: 1280px;
        margin: 0 auto;
        padding: 40px 32px 72px;
      }

      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        margin-bottom: 32px;
      }

      .header-title {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .header-title h1 {
        margin: 0;
        font-size: 32px;
        font-weight: 600;
        letter-spacing: -0.02em;
      }

      .header-title p {
        margin: 0;
        color: var(--muted);
      }

      .pill-button {
        border: none;
        padding: 12px 20px;
        border-radius: 999px;
        background: var(--bg);
        color: var(--text);
        font-weight: 600;
        box-shadow: 8px 8px 16px var(--shadow-dark), -8px -8px 16px var(--shadow-light);
        cursor: pointer;
      }

      .pill-button.primary {
        color: white;
        background: var(--accent);
        box-shadow: 8px 8px 16px rgba(31, 111, 235, 0.35), -8px -8px 16px var(--shadow-light);
      }

      .search-bar {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 28px;
        padding: 16px 20px;
        border-radius: 24px;
        background: var(--bg);
        box-shadow: inset 6px 6px 12px var(--shadow-dark), inset -6px -6px 12px var(--shadow-light);
      }

      .search-bar input {
        border: none;
        background: transparent;
        font-size: 16px;
        flex: 1;
        outline: none;
      }

      .layout {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 340px;
        gap: 28px;
      }

      .shelf {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 20px;
      }

      .book-card {
        padding: 22px;
        border-radius: 24px;
        background: var(--bg);
        box-shadow: 12px 12px 24px var(--shadow-dark), -12px -12px 24px var(--shadow-light);
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .shelf-section {
        margin-bottom: 28px;
      }

      .book-cover {
        border-radius: 18px;
        padding: 20px;
        background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
        color: #1c1c1c;
        font-weight: 600;
        height: 150px;
        display: flex;
        align-items: flex-end;
        box-shadow: inset 4px 4px 10px rgba(255, 255, 255, 0.4),
          inset -4px -4px 12px rgba(0, 0, 0, 0.1);
      }

      .book-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
      }

      .tag {
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(31, 111, 235, 0.12);
        color: var(--accent);
        font-size: 12px;
        font-weight: 600;
      }

      .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        gap: 16px;
      }

      .section-header h2 {
        margin: 0 0 4px;
        font-size: 20px;
      }

      .section-header p {
        margin: 0;
        color: var(--muted);
        font-size: 13px;
      }

      .count-pill {
        padding: 6px 12px;
        border-radius: 999px;
        background: var(--surface);
        color: var(--muted);
        font-size: 12px;
        font-weight: 600;
        box-shadow: inset 2px 2px 6px rgba(200, 206, 216, 0.8),
          inset -2px -2px 6px rgba(255, 255, 255, 0.7);
      }

      .empty-state {
        padding: 18px;
        border-radius: 18px;
        background: var(--surface);
        color: var(--muted);
        text-align: center;
        box-shadow: inset 4px 4px 8px rgba(200, 206, 216, 0.8),
          inset -4px -4px 8px rgba(255, 255, 255, 0.7);
      }

      .meta-line {
        color: var(--muted);
        font-size: 13px;
        margin: 4px 0 0;
      }

      .progress {
        height: 8px;
        border-radius: 999px;
        background: #d5dbe4;
        overflow: hidden;
      }

      .progress span {
        display: block;
        height: 100%;
        border-radius: inherit;
        background: var(--accent);
      }

      .panel {
        padding: 22px;
        border-radius: 24px;
        background: var(--bg);
        box-shadow: 10px 10px 20px var(--shadow-dark), -10px -10px 20px var(--shadow-light);
      }

      .panel + .panel {
        margin-top: 20px;
      }

      .panel h3 {
        margin: 0 0 12px;
      }

      .panel label {
        font-size: 12px;
        color: var(--muted);
        display: block;
        margin-bottom: 6px;
      }

      .panel input,
      .panel select,
      .panel textarea {
        width: 100%;
        border: none;
        border-radius: 14px;
        padding: 10px 12px;
        background: var(--surface);
        box-shadow: inset 4px 4px 8px rgba(200, 206, 216, 0.8),
          inset -4px -4px 8px rgba(255, 255, 255, 0.7);
        font-size: 14px;
        margin-bottom: 12px;
        outline: none;
      }

      .panel .row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }

      .status-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(31, 111, 235, 0.12);
        color: var(--accent);
        font-size: 12px;
        font-weight: 600;
      }

      .footer-panel {
        margin-top: 32px;
        padding: 24px 32px;
        border-radius: 28px;
        background: var(--bg);
        box-shadow: 10px 10px 20px var(--shadow-dark), -10px -10px 20px var(--shadow-light);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
      }

      .footer-panel h3 {
        margin: 0 0 6px;
      }

      .footer-panel p {
        margin: 0;
        color: var(--muted);
      }

      .action-log {
        font-size: 12px;
        color: var(--muted);
        background: var(--surface);
        border-radius: 16px;
        padding: 12px;
        min-height: 90px;
      }

      @media (max-width: 1024px) {
        .layout {
          grid-template-columns: 1fr;
        }
      }
    </style>
  </head>
  <body>
    <div class="app">
      <header class="header">
        <div class="header-title">
          <h1>Book Writer Studio</h1>
          <p>Curate outlines, drafts, and finished books in a soft, tactile shelf view.</p>
        </div>
        <div class="status-chip">● API Connected</div>
      </header>

      <section class="search-bar">
        <span>🔍</span>
        <input type="text" placeholder="Search by title, genre, or status" />
        <button class="pill-button">Filters</button>
      </section>

      <div class="layout">
        <section>
          <div class="catalog">
            <section class="shelf-section">
              <div class="section-header">
                <div>
                  <h2>Active outlines</h2>
                  <p>Ready-to-generate drafts pulled from the outlines directory.</p>
                </div>
                <span class="count-pill" id="outlineCount">0 outlines</span>
              </div>
              <div class="shelf" id="outlineShelf"></div>
            </section>

            <section class="shelf-section">
              <div class="section-header">
                <div>
                  <h2>Completed outlines</h2>
                  <p>Archived outlines already moved to completed_outlines.</p>
                </div>
                <span class="count-pill" id="completedOutlineCount">0 outlines</span>
              </div>
              <div class="shelf" id="completedOutlineShelf"></div>
            </section>

            <section class="shelf-section">
              <div class="section-header">
                <div>
                  <h2>Books</h2>
                  <p>Books tracked from the books directory, including media outputs.</p>
                </div>
                <span class="count-pill" id="bookCount">0 books</span>
              </div>
              <div class="shelf" id="bookShelf"></div>
            </section>
          </div>
        </section>

        <aside>
          <div class="panel">
            <h3>Generate from outline</h3>
            <label>Outline path</label>
            <input id="outlinePath" placeholder="OUTLINE.md" />
            <label>Output directory</label>
            <input id="outputDir" placeholder="output" />
            <div class="row">
              <div>
                <label>Model</label>
                <input id="modelName" placeholder="local-model" />
              </div>
              <div>
                <label>Base URL</label>
                <input id="baseUrl" placeholder="http://localhost:1234" />
              </div>
            </div>
            <label>Tone</label>
            <input id="tone" placeholder="instructive self help guide" />
            <label>Byline</label>
            <input id="byline" placeholder="Marissa Bard" />
            <button class="pill-button primary" id="generateBook">Generate Book</button>
          </div>

          <div class="panel">
            <h3>Expand or compile</h3>
            <label>Book directory</label>
            <input id="bookDir" placeholder="books/my-book" />
            <div class="row">
              <div>
                <label>Expand passes</label>
                <input id="expandPasses" placeholder="1" />
              </div>
              <div>
                <label>Expand only</label>
                <input id="expandOnly" placeholder="1,3-4" />
              </div>
            </div>
            <button class="pill-button" id="expandBook">Expand</button>
            <button class="pill-button" id="compileBook">Compile PDF</button>
          </div>

          <div class="panel">
            <h3>Audio + video</h3>
            <label>Audio output dir</label>
            <input id="audioDir" placeholder="audio" />
            <label>Video output dir</label>
            <input id="videoDir" placeholder="video" />
            <label>Background video path</label>
            <input id="backgroundVideo" placeholder="/path/to/background.mp4" />
            <button class="pill-button" id="generateAudio">Generate Audio</button>
            <button class="pill-button" id="generateVideo">Generate Video</button>
          </div>

          <div class="panel">
            <h3>Activity log</h3>
            <div class="action-log" id="actionLog">Waiting for actions...</div>
          </div>
        </aside>
      </div>

      <section class="footer-panel">
        <div>
          <h3>Weekly focus</h3>
          <p>Schedule two writing sessions and review outlines with your personas.</p>
        </div>
        <button class="pill-button">Open Planner</button>
      </section>
    </div>

    <script>
      const log = (message) => {
        const logEl = document.getElementById('actionLog');
        const timestamp = new Date().toLocaleTimeString();
        logEl.textContent = `[${timestamp}] ${message}\n` + logEl.textContent;
      };

      const postJson = async (path, payload) => {
        const response = await fetch(path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(errorText || 'Request failed');
        }
        return response.json();
      };

      const fetchJson = async (path) => {
        const response = await fetch(path);
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        return response.json();
      };

      const gradients = [
        ['#f6d365', '#fda085'],
        ['#a1c4fd', '#c2e9fb'],
        ['#fbc2eb', '#a6c1ee'],
        ['#fdcbf1', '#e6dee9'],
        ['#84fab0', '#8fd3f4'],
        ['#fccb90', '#d57eeb'],
      ];

      const gradientFor = (seed) => {
        let hash = 0;
        for (let i = 0; i < seed.length; i += 1) {
          hash = (hash << 5) - hash + seed.charCodeAt(i);
          hash |= 0;
        }
        const [start, end] = gradients[Math.abs(hash) % gradients.length];
        return `linear-gradient(135deg, ${start} 0%, ${end} 100%)`;
      };

      const createCard = (title, status, detail, tag, accentLabel, progress) => {
        const card = document.createElement('article');
        card.className = 'book-card';

        const cover = document.createElement('div');
        cover.className = 'book-cover';
        cover.style.background = gradientFor(title);
        cover.textContent = title;

        const content = document.createElement('div');
        const heading = document.createElement('h2');
        heading.textContent = status;
        const meta = document.createElement('p');
        meta.className = 'meta-line';
        meta.textContent = detail;
        content.appendChild(heading);
        content.appendChild(meta);

        card.appendChild(cover);
        card.appendChild(content);

        if (typeof progress === 'number') {
          const progressWrap = document.createElement('div');
          progressWrap.className = 'progress';
          const progressFill = document.createElement('span');
          progressFill.style.width = `${Math.min(Math.max(progress, 0), 100)}%`;
          progressWrap.appendChild(progressFill);
          card.appendChild(progressWrap);
        }

        const metaRow = document.createElement('div');
        metaRow.className = 'book-meta';
        const tagEl = document.createElement('span');
        tagEl.className = 'tag';
        tagEl.textContent = tag;
        const accent = document.createElement('strong');
        accent.textContent = accentLabel;
        metaRow.appendChild(tagEl);
        metaRow.appendChild(accent);
        card.appendChild(metaRow);

        return card;
      };

      const renderEmpty = (container, message) => {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.textContent = message;
        container.appendChild(empty);
      };

      const loadCatalog = async () => {
        try {
          const [outlineResponse, completedResponse, booksResponse] = await Promise.all([
            fetchJson('/api/outlines'),
            fetchJson('/api/completed-outlines'),
            fetchJson('/api/books'),
          ]);

          const outlines = outlineResponse.outlines || [];
          const completed = completedResponse.outlines || [];
          const books = booksResponse.books || [];

          const outlineShelf = document.getElementById('outlineShelf');
          const completedShelf = document.getElementById('completedOutlineShelf');
          const bookShelf = document.getElementById('bookShelf');

          outlineShelf.innerHTML = '';
          completedShelf.innerHTML = '';
          bookShelf.innerHTML = '';

          document.getElementById('outlineCount').textContent = `${outlines.length} outlines`;
          document.getElementById('completedOutlineCount').textContent = `${completed.length} outlines`;
          document.getElementById('bookCount').textContent = `${books.length} books`;

          if (!outlines.length) {
            renderEmpty(outlineShelf, 'No outlines found in the outlines directory.');
          } else {
            outlines.forEach((outline) => {
              const title = outline.title || outline.path.split('/').pop();
              const detail = `${outline.item_count || 0} sections • ${outline.preview || 'No preview available.'}`;
              outlineShelf.appendChild(
                createCard(
                  title,
                  'Outline ready',
                  detail,
                  'Outline',
                  'Next: Generate book',
                  15,
                ),
              );
            });
          }

          if (!completed.length) {
            renderEmpty(completedShelf, 'No completed outlines archived yet.');
          } else {
            completed.forEach((outline) => {
              const title = outline.title || outline.path.split('/').pop();
              const detail = `${outline.item_count || 0} sections • ${outline.preview || 'No preview available.'}`;
              completedShelf.appendChild(
                createCard(
                  title,
                  'Archived outline',
                  detail,
                  'Completed',
                  'Stored in completed_outlines',
                  100,
                ),
              );
            });
          }

          if (!books.length) {
            renderEmpty(bookShelf, 'No books found in the books directory.');
          } else {
            books.forEach((book) => {
              const statusFlags = [];
              if (book.has_text) statusFlags.push('Text');
              if (book.has_audio) statusFlags.push('Audio');
              if (book.has_video) statusFlags.push('Video');
              if (book.has_compilation) statusFlags.push('Compiled');
              const status = book.has_compilation ? 'Compiled' : book.has_text ? 'Drafting' : 'No chapters';
              const detail = `${book.chapter_count || 0} chapters • ${statusFlags.join(' • ') || 'No media yet'}`;
              const progress = (statusFlags.length / 4) * 100;
              bookShelf.appendChild(
                createCard(
                  book.title,
                  status,
                  detail,
                  'Book',
                  book.path.split('/').pop(),
                  progress,
                ),
              );
            });
          }

          log('Catalog loaded from disk.');
        } catch (error) {
          log(`Catalog load failed: ${error.message}`);
        }
      };

      document.getElementById('generateBook').addEventListener('click', async () => {
        try {
          const payload = {
            outline_path: document.getElementById('outlinePath').value || 'OUTLINE.md',
            output_dir: document.getElementById('outputDir').value || 'output',
            base_url: document.getElementById('baseUrl').value || 'http://localhost:1234',
            model: document.getElementById('modelName').value || 'local-model',
            tone: document.getElementById('tone').value || 'instructive self help guide',
            byline: document.getElementById('byline').value || 'Marissa Bard',
          };
          const result = await postJson('/api/generate-book', payload);
          log(`Generated book with ${result.written_files.length} files.`);
        } catch (error) {
          log(`Generate failed: ${error.message}`);
        }
      });

      document.getElementById('expandBook').addEventListener('click', async () => {
        try {
          const payload = {
            expand_book: document.getElementById('bookDir').value,
            expand_passes: Number(document.getElementById('expandPasses').value || 1),
            expand_only: document.getElementById('expandOnly').value || null,
          };
          await postJson('/api/expand-book', payload);
          log('Expansion complete.');
        } catch (error) {
          log(`Expand failed: ${error.message}`);
        }
      });

      document.getElementById('compileBook').addEventListener('click', async () => {
        try {
          const payload = {
            book_dir: document.getElementById('bookDir').value,
          };
          await postJson('/api/compile-book', payload);
          log('Compilation complete.');
        } catch (error) {
          log(`Compile failed: ${error.message}`);
        }
      });

      document.getElementById('generateAudio').addEventListener('click', async () => {
        try {
          const payload = {
            book_dir: document.getElementById('bookDir').value,
            tts_settings: { audio_dirname: document.getElementById('audioDir').value || 'audio' },
          };
          await postJson('/api/generate-audio', payload);
          log('Audio generation complete.');
        } catch (error) {
          log(`Audio failed: ${error.message}`);
        }
      });

      document.getElementById('generateVideo').addEventListener('click', async () => {
        try {
          const payload = {
            book_dir: document.getElementById('bookDir').value,
            audio_dirname: document.getElementById('audioDir').value || 'audio',
            video_settings: {
              video_dirname: document.getElementById('videoDir').value || 'video',
              background_video: document.getElementById('backgroundVideo').value || null,
              enabled: true,
            },
          };
          await postJson('/api/generate-videos', payload);
          log('Video generation complete.');
        } catch (error) {
          log(`Video failed: ${error.message}`);
        }
      });

      loadCatalog();
    </script>
  </body>
</html>
"""
    return html.replace("__TITLE__", GUI_TITLE)


def save_gui_html(output_path: str | Path) -> Path:
    """Write the GUI HTML to the provided path and return it."""
    path = Path(output_path)
    path.write_text(get_gui_html(), encoding="utf-8")
    return path


__all__ = ["get_gui_html", "save_gui_html", "GUI_TITLE"]

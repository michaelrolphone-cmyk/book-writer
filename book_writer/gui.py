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
        --page-padding: 32px;
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
        min-height: 100vh;
        padding: 36px var(--page-padding) 72px;
      }

      .home-view {
        max-width: 1280px;
        margin: 0 auto;
      }

      .detail-view {
        width: 100%;
      }

      .outline-view {
        width: 100%;
      }

      .chapter-view {
        width: 100%;
      }

      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        margin-bottom: 32px;
      }

      .header-actions {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .now-playing {
        max-width: 1280px;
        margin: 0 auto 28px;
        padding: 18px 22px;
        border-radius: 24px;
        background: var(--bg);
        box-shadow: 10px 10px 20px var(--shadow-dark), -10px -10px 20px var(--shadow-light);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
        position: relative;
        overflow: hidden;
      }

      .now-playing.hidden {
        display: none;
      }

      .now-playing.with-cover {
        color: rgba(255, 255, 255, 0.95);
      }

      .now-playing::before,
      .now-playing::after {
        content: '';
        position: absolute;
        inset: 0;
        opacity: 0;
        transition: opacity 0.3s ease;
      }

      .now-playing::before {
        background: var(--now-playing-cover, var(--bg));
        background-size: cover;
        background-position: center;
        transform: scale(1.05);
      }

      .now-playing::after {
        background: linear-gradient(135deg, rgba(10, 16, 26, 0.25), rgba(10, 16, 26, 0.55));
      }

      .now-playing.with-cover::before,
      .now-playing.with-cover::after {
        opacity: 1;
      }

      .now-playing > * {
        position: relative;
        z-index: 2;
      }

      .now-playing-info {
        display: flex;
        align-items: center;
        gap: 14px;
      }

      .now-playing-info h2 {
        margin: 0;
        font-size: 18px;
      }

      .now-playing-info p {
        margin: 4px 0 0;
        color: var(--muted);
        font-size: 13px;
      }

      .now-playing.with-cover .now-playing-info h2 {
        color: rgba(255, 255, 255, 0.98);
      }

      .now-playing.with-cover .now-playing-info p {
        color: rgba(255, 255, 255, 0.82);
      }

      .now-playing.with-cover .tag {
        background: rgba(8, 12, 20, 0.55);
        color: rgba(255, 255, 255, 0.95);
        border: 1px solid rgba(255, 255, 255, 0.35);
      }

      .now-playing-controls {
        flex: 1;
        min-width: 240px;
      }

      .now-playing-controls audio {
        width: 100%;
      }

      .now-playing-settings {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 13px;
        color: var(--muted);
        white-space: nowrap;
      }

      .now-playing-settings input[type='checkbox'] {
        accent-color: var(--accent);
      }

      .now-playing.with-cover .now-playing-settings {
        color: rgba(255, 255, 255, 0.82);
      }

      .now-playing-close {
        position: absolute;
        top: 12px;
        right: 12px;
        border: none;
        background: transparent;
        color: var(--muted);
        font-size: 18px;
        cursor: pointer;
      }

      .now-playing.with-cover .now-playing-close {
        color: rgba(255, 255, 255, 0.8);
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

      .pill-button.ghost {
        background: transparent;
        box-shadow: none;
        border: 1px solid rgba(31, 111, 235, 0.2);
        color: var(--accent);
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

      .detail-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 24px;
      }

      .detail-heading h2 {
        margin: 0;
        font-size: 26px;
      }

      .detail-heading p {
        margin: 4px 0 0;
        color: var(--muted);
      }

      .detail-layout {
        display: grid;
        gap: 20px;
      }

      .chapter-layout {
        display: grid;
        gap: 20px;
      }

      .home-utilities {
        display: grid;
        gap: 20px;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      }

      .home-utilities.is-collapsed {
        display: none;
      }

      .utilities-section {
        margin-top: 32px;
      }

      .shelf {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 20px;
      }

      .scroll-shelf {
        display: grid;
        grid-auto-flow: column;
        grid-auto-columns: minmax(220px, 1fr);
        gap: 20px;
        overflow-x: auto;
        overflow-y: visible;
        padding: 6px 0 16px;
        padding-inline: calc(50vw - 50% + var(--page-padding));
        scroll-behavior: smooth;
        scroll-snap-type: none;
        scrollbar-width: none;
        -ms-overflow-style: none;
        background: transparent;
        margin-inline: calc(50% - 50vw);
        scroll-padding-inline: calc(50vw - 50% + var(--page-padding));
      }

      .scroll-shelf::-webkit-scrollbar {
        display: none;
      }

      .scroll-shelf .book-card {
        scroll-snap-align: start;
      }

      .chapter-shelf {
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      }

      .book-card {
        padding: 22px;
        border-radius: 24px;
        background: transparent;
        box-shadow: 12px 12px 24px var(--shadow-dark), -12px -12px 24px var(--shadow-light);
        display: flex;
        flex-direction: column;
        gap: 16px;
        height: 360px;
        overflow: hidden;
        position: relative;
        color: var(--card-text, var(--text));
      }

      .card-body {
        display: flex;
        flex-direction: column;
        gap: 12px;
        flex: 1;
        padding-top: 4px;
      }

      .card-body h2 {
        margin: 0;
        line-height: 1.3;
      }

      .card-description {
        position: relative;
        max-height: 96px;
        min-height: 96px;
        overflow: hidden;
      }

      .card-description::after {
        content: '';
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 32px;
        background: linear-gradient(
          180deg,
          rgba(8, 12, 20, 0) 0%,
          var(--card-fade, rgba(8, 12, 20, 0.6)) 100%
        );
      }

      .card-footer {
        margin-top: auto;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .book-card.cover-filled::before {
        content: '';
        position: absolute;
        inset: 0;
        background: var(--card-cover, var(--bg));
        background-size: cover;
        background-position: center;
        z-index: 0;
        transform: scale(1.02);
      }

      .book-card.cover-filled::after {
        content: '';
        position: absolute;
        inset: 0;
        background: var(--card-overlay, rgba(255, 255, 255, 0.7));
        z-index: 1;
      }

      .book-card.cover-filled > * {
        position: relative;
        z-index: 2;
      }

      .book-card.selectable {
        cursor: pointer;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
      }

      .book-card.selectable:hover {
        transform: translateY(-4px);
        box-shadow: 14px 14px 26px var(--shadow-dark), -14px -14px 26px var(--shadow-light);
      }

      .book-card.selected {
        box-shadow: inset 4px 4px 12px rgba(31, 111, 235, 0.2),
          inset -4px -4px 12px rgba(255, 255, 255, 0.7);
        border: 1px solid rgba(31, 111, 235, 0.2);
      }

      .shelf-section {
        margin-bottom: 28px;
      }

      .shelf-heading {
        margin: 0 0 12px;
        font-size: 16px;
        font-weight: 600;
        color: var(--text);
        letter-spacing: 0.02em;
      }

      .book-cover {
        border-radius: 24px 24px 0 0;
        margin: -22px -22px 0;
        padding: 20px;
        background: rgba(12, 16, 24, 0.4);
        color: inherit;
        font-weight: 600;
        height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        align-items: flex-start;
        overflow: hidden;
        position: relative;
        box-shadow: inset 4px 4px 10px rgba(255, 255, 255, 0.08),
          inset -4px -4px 12px rgba(0, 0, 0, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(6px);
      }

      .cover-header {
        border-radius: 24px 24px 0 0;
        margin: -22px -22px 18px;
        padding: 24px;
        min-height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        align-items: flex-start;
        overflow: hidden;
        position: relative;
        color: var(--card-text, var(--text));
        box-shadow: inset 4px 4px 10px rgba(255, 255, 255, 0.08),
          inset -4px -4px 12px rgba(0, 0, 0, 0.25);
      }

      .cover-header::before {
        content: '';
        position: absolute;
        inset: 0;
        background: var(--card-cover, var(--bg));
        background-size: cover;
        background-position: center;
        z-index: 0;
        transform: scale(1.02);
      }

      .cover-header::after {
        content: '';
        position: absolute;
        inset: 0;
        background: var(--card-overlay, rgba(255, 255, 255, 0.7));
        z-index: 1;
      }

      .cover-header > * {
        position: relative;
        z-index: 2;
      }

      .cover-header-content {
        display: flex;
        flex-direction: column;
        gap: 12px;
        width: 100%;
      }

      .cover-header .cover-title {
        font-size: 20px;
        font-weight: 600;
        text-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
      }

      .workspace-cover {
        margin-bottom: 18px;
      }

      .reader-cover {
        min-height: 130px;
        margin-bottom: 16px;
      }

      .cover-header .media-block {
        background: rgba(8, 12, 20, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.2);
      }

      .cover-header .media-block label {
        color: rgba(248, 249, 251, 0.82);
      }

      .visually-hidden {
        display: none;
      }

      .book-cover.has-image {
        padding: 20px;
      }

      .book-cover-title {
        position: relative;
        z-index: 2;
        text-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
      }

      .chapter-card .book-cover {
        height: 110px;
        font-size: 14px;
        padding: 16px;
      }

      .book-card.cover-filled .meta-line {
        color: rgba(248, 249, 251, 0.78);
      }

      .book-card.cover-filled h2 {
        color: rgba(255, 255, 255, 0.96);
      }

      .book-card.cover-filled .tag {
        background: rgba(8, 12, 20, 0.35);
        color: rgba(255, 255, 255, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.25);
      }

      .book-card.cover-filled .book-meta strong {
        color: rgba(255, 255, 255, 0.92);
      }

      .book-card.cover-filled .progress {
        background: rgba(255, 255, 255, 0.2);
      }

      .chapter-card h2 {
        font-size: 16px;
        margin-bottom: 6px;
      }

      .chapter-card {
        height: 300px;
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

      .section-actions {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
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
        white-space: pre-wrap;
      }

      .meta-line.markdown p {
        margin: 0 0 6px;
      }

      .meta-line.markdown p:last-child {
        margin-bottom: 0;
      }

      .meta-line.markdown ul,
      .meta-line.markdown ol {
        margin: 6px 0 6px 18px;
        padding: 0;
      }

      .meta-line.markdown li {
        margin-bottom: 4px;
      }

      .meta-line.markdown h1,
      .meta-line.markdown h2,
      .meta-line.markdown h3,
      .meta-line.markdown h4,
      .meta-line.markdown h5 {
        margin: 8px 0 4px;
        font-size: 13px;
        color: var(--text);
      }

      .meta-line.markdown hr {
        border: none;
        border-top: 1px solid rgba(148, 163, 184, 0.6);
        margin: 8px 0;
      }

      .meta-line.markdown table {
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0;
        font-size: 12px;
      }

      .meta-line.markdown th,
      .meta-line.markdown td {
        border: 1px solid rgba(148, 163, 184, 0.4);
        padding: 6px 8px;
        text-align: left;
      }

      .meta-line.markdown th {
        background: rgba(225, 232, 242, 0.6);
        font-weight: 600;
      }

      .reader-panel {
        display: none;
        margin-top: 12px;
        padding: 14px;
        border-radius: 18px;
        background: var(--surface);
        box-shadow: inset 4px 4px 8px rgba(200, 206, 216, 0.8),
          inset -4px -4px 8px rgba(255, 255, 255, 0.7);
        font-size: 13px;
        color: var(--text);
      }

      .reader-panel.active {
        display: block;
      }

      .reader-panel .reader-body {
        margin-top: 10px;
        white-space: normal;
      }

      .reader-panel .reader-body p {
        margin: 0 0 10px;
      }

      .reader-panel .reader-body ul,
      .reader-panel .reader-body ol {
        margin: 6px 0 10px 18px;
        padding: 0;
      }

      .reader-panel .reader-body li {
        margin-bottom: 6px;
      }

      .reader-panel .reader-body pre {
        background: #dde3ec;
        padding: 10px;
        border-radius: 10px;
        overflow-x: auto;
      }

      .reader-panel .reader-body code {
        background: #dde3ec;
        padding: 2px 4px;
        border-radius: 6px;
      }

      .reader-panel .reader-body hr {
        border: none;
        border-top: 1px solid rgba(148, 163, 184, 0.6);
        margin: 12px 0;
      }

      .reader-panel .reader-body table {
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 12px;
      }

      .reader-panel .reader-body th,
      .reader-panel .reader-body td {
        border: 1px solid rgba(148, 163, 184, 0.4);
        padding: 6px 8px;
        text-align: left;
      }

      .reader-panel .reader-body th {
        background: rgba(225, 232, 242, 0.6);
        font-weight: 600;
      }

      .reader-panel .close-reader {
        border: none;
        background: transparent;
        color: var(--muted);
        font-size: 12px;
        cursor: pointer;
      }

      .media-panel {
        margin-top: 16px;
        display: grid;
        gap: 12px;
      }

      .card-media {
        margin-top: 12px;
      }

      .card-media audio {
        width: 100%;
      }

      .media-block {
        background: #dde3ec;
        border-radius: 14px;
        padding: 12px;
      }

      .media-block.hidden {
        display: none;
      }

      .media-block label {
        display: block;
        font-size: 12px;
        color: var(--muted);
        margin-bottom: 6px;
      }

      .media-block audio,
      .media-block video {
        width: 100%;
        border-radius: 10px;
      }

      .media-block img {
        width: 100%;
        height: auto;
        max-height: 66vh;
        object-fit: contain;
        border-radius: 10px;
        display: block;
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

      .cover-progress {
        margin-top: 16px;
        padding: 12px 14px;
        border-radius: 16px;
        background: var(--surface);
        box-shadow: inset 4px 4px 10px var(--shadow-dark),
          inset -4px -4px 10px var(--shadow-light);
      }

      .cover-progress.hidden {
        display: none;
      }

      .cover-progress-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 14px;
        margin-bottom: 10px;
        color: var(--muted);
      }

      .cover-progress-bar {
        position: relative;
        height: 8px;
        border-radius: 999px;
        background: rgba(31, 111, 235, 0.12);
        overflow: hidden;
      }

      .cover-progress-bar span {
        position: absolute;
        top: 0;
        left: -40%;
        height: 100%;
        width: 40%;
        background: var(--accent);
        border-radius: 999px;
        animation: cover-progress 1.2s ease-in-out infinite;
      }

      @keyframes cover-progress {
        0% {
          left: -40%;
        }
        50% {
          left: 30%;
        }
        100% {
          left: 100%;
        }
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

      .workspace-empty {
        font-size: 13px;
        color: var(--muted);
        background: var(--surface);
        padding: 14px;
        border-radius: 14px;
        box-shadow: inset 3px 3px 8px rgba(200, 206, 216, 0.7),
          inset -3px -3px 8px rgba(255, 255, 255, 0.7);
      }

      .workspace-view.is-hidden {
        display: none;
      }

      .is-hidden {
        display: none;
      }

      .workspace-meta {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 8px;
      }

      .detail-section {
        margin-top: 16px;
      }

      .detail-section h4 {
        margin: 0 0 8px;
        font-size: 14px;
      }

      .detail-actions {
        margin: 0;
        padding: 0 0 0 18px;
        color: var(--muted);
        font-size: 13px;
      }

      .detail-content {
        background: var(--surface);
        border-radius: 14px;
        padding: 12px;
        max-height: 260px;
        overflow: auto;
        font-size: 13px;
        color: var(--text);
        box-shadow: inset 3px 3px 8px rgba(200, 206, 216, 0.7),
          inset -3px -3px 8px rgba(255, 255, 255, 0.7);
      }

      .detail-content p {
        margin: 0 0 8px;
      }

      .detail-content p:last-child {
        margin-bottom: 0;
      }

      .detail-content ul,
      .detail-content ol {
        margin: 6px 0 10px 18px;
        padding: 0;
      }

      .detail-content li {
        margin-bottom: 6px;
      }

      .detail-content pre {
        background: #dde3ec;
        padding: 10px;
        border-radius: 10px;
        overflow-x: auto;
      }

      .detail-content code {
        background: #dde3ec;
        padding: 2px 4px;
        border-radius: 6px;
      }

      .workspace-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
      }

      .workspace-actions .row {
        flex: 1 1 100%;
      }

      .workspace-actions .pill-button {
        width: auto;
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

      .outline-editor {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .outline-editor textarea {
        min-height: 220px;
        resize: vertical;
        border: none;
        border-radius: 16px;
        padding: 14px 16px;
        font-family: "SF Mono", "Courier New", monospace;
        font-size: 14px;
        background: var(--surface);
        box-shadow: inset 6px 6px 12px var(--shadow-dark),
          inset -6px -6px 12px var(--shadow-light);
        outline: none;
      }

      @media (max-width: 1024px) {
        .detail-header {
          flex-direction: column;
          align-items: flex-start;
        }
      }

      @media (max-width: 768px) {
        .now-playing {
          flex-direction: column;
          align-items: stretch;
          gap: 14px;
        }

        .scroll-shelf {
          grid-auto-columns: minmax(220px, 66vw);
          scroll-snap-type: x mandatory;
          scroll-padding-inline: calc(50vw - 50% + var(--page-padding));
        }

        .book-card {
          height: 340px;
        }

        .now-playing-info {
          width: 100%;
        }

        .now-playing-controls {
          width: 100%;
          min-width: 100%;
        }

        .now-playing-settings {
          width: 100%;
          white-space: normal;
        }
      }
    </style>
  </head>
  <body>
    <div class="app">
      <main class="home-view" id="homeView">
        <header class="header">
          <div class="header-title">
            <h1>Book Writer Studio</h1>
            <p>Plan outlines, generate drafts, and manage finished books from one workspace.</p>
          </div>
          <div class="header-actions">
            <button class="pill-button ghost" id="viewOutlines">View outlines</button>
          </div>
        </header>

        <section class="search-bar">
          <span>🔍</span>
          <input id="searchInput" type="text" placeholder="Search by title or file name" />
        </section>

        <div id="nowPlayingHomeSlot">
          <section class="now-playing hidden" id="nowPlaying">
            <button class="now-playing-close" id="nowPlayingClose" aria-label="Close now playing">
              ×
            </button>
            <div class="now-playing-info">
              <span class="tag">Now playing</span>
              <div>
                <h2 id="nowPlayingTitle">Nothing playing</h2>
                <p id="nowPlayingSubtitle">Select a chapter to start listening.</p>
              </div>
            </div>
            <div class="now-playing-controls" id="nowPlayingControls"></div>
            <div class="now-playing-settings">
              <label>
                <input type="checkbox" id="nowPlayingAutoplay" checked />
                Autoplay next chapter
              </label>
            </div>
          </section>
        </div>

        <section class="catalog">
          <section class="shelf-section">
            <div class="section-header">
              <div>
                <h2>Newest books</h2>
                <p>Latest 10 books based on folder activity.</p>
              </div>
              <button class="pill-button ghost" id="viewAllBooks">View all</button>
            </div>
            <div class="scroll-shelf" id="latestShelf"></div>
          </section>

          <section class="shelf-section">
            <div class="section-header">
              <div>
                <h2>Browse by genre</h2>
                <p>Scroll through each genre to discover more reads.</p>
              </div>
              <div class="section-actions">
                <span class="count-pill" id="bookCount">0 books</span>
                <button class="pill-button ghost" id="viewAllBooksSecondary">View all</button>
              </div>
            </div>
            <div id="genreShelves"></div>
          </section>

          <section class="shelf-section is-hidden" id="allBooksSection">
            <div class="section-header">
              <div>
                <h2>All books</h2>
                <p>The full library in one place.</p>
              </div>
            </div>
            <div class="shelf" id="bookShelf"></div>
          </section>

        </section>

        <section class="utilities-section">
          <div class="section-header">
            <div>
              <h2>Workspace tools</h2>
              <p>Expand books, generate assets, and create new outlines when you need them.</p>
            </div>
            <button class="pill-button ghost" id="toggleUtilities" aria-expanded="false">
              Show tools
            </button>
          </div>
          <section class="home-utilities is-collapsed" id="homeUtilities">
          <div class="panel">
            <h3>Create outline wizard</h3>
            <label>Outline prompt</label>
            <textarea
              id="outlinePrompt"
              placeholder="Describe the book you want to outline"
            ></textarea>
            <label>Revision prompts (one per line)</label>
            <textarea
              id="outlineRevisions"
              placeholder="Add a stronger hook&#10;Refine the chapter arc"
            ></textarea>
            <div class="row">
              <div>
                <label>Outline filename</label>
                <input id="outlineName" placeholder="my-outline.md" />
              </div>
              <div>
                <label>Outlines directory</label>
                <input id="outlineDir" placeholder="outlines" />
              </div>
            </div>
            <div class="row">
              <div>
                <label>Model</label>
                <input id="outlineModel" placeholder="local-model" />
              </div>
              <div>
                <label>Base URL</label>
                <input id="outlineBaseUrl" placeholder="http://localhost:1234" />
              </div>
            </div>
            <button class="pill-button primary" id="generateOutline">
              Generate outline
            </button>
          </div>

          <div class="panel">
            <h3>Generate from outline</h3>
            <label>Outline</label>
            <select id="outlineSelect"></select>
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
            <label>Book</label>
            <select id="bookSelect"></select>
            <label>Chapter selection</label>
            <select id="chapterSelect" disabled></select>
            <button class="pill-button" id="openReader" disabled>Open reader</button>
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
            <label class="checkbox">
              <input type="checkbox" id="audioOverwrite" />
              Overwrite existing audio
            </label>
            <label class="checkbox">
              <input type="checkbox" id="audioBookOnly" />
              Only generate full book audio
            </label>
            <label>Video output dir</label>
            <input id="videoDir" placeholder="video" />
            <label>Background video path</label>
            <input id="backgroundVideo" placeholder="/path/to/background.mp4" />
            <button class="pill-button" id="generateAudio">Generate Audio</button>
            <button class="pill-button" id="generateVideo">Generate Video</button>
          </div>

          <div class="panel">
            <h3>Cover generation</h3>
            <label>Cover prompt override</label>
            <textarea id="coverPrompt" placeholder="Leave blank for auto-generated prompts"></textarea>
            <label>Negative prompt</label>
            <textarea id="coverNegativePrompt" placeholder="Avoid unwanted elements"></textarea>
            <label>Core ML model path</label>
            <input id="coverModelPath" placeholder="/path/to/model" />
            <label>python_coreml_stable_diffusion module path</label>
            <input id="coverModulePath" placeholder="../ml-stable-diffusion" />
            <div class="row">
              <div>
                <label>Inference steps</label>
                <input id="coverSteps" placeholder="30" />
              </div>
              <div>
                <label>Guidance scale</label>
                <input id="coverGuidanceScale" placeholder="7.5" />
              </div>
            </div>
            <div class="row">
              <div>
                <label>Seed</label>
                <input id="coverSeed" placeholder="Optional" />
              </div>
              <div>
                <label>Output filename</label>
                <input id="coverOutputName" placeholder="cover.png" />
              </div>
            </div>
            <div class="row">
              <div>
                <label>Image width</label>
                <input id="coverWidth" placeholder="768" />
              </div>
              <div>
                <label>Image height</label>
                <input id="coverHeight" placeholder="1024" />
              </div>
            </div>
            <label>Cover command template</label>
            <input id="coverCommand" placeholder="swift run StableDiffusionSample {prompt} ..." />
            <label>Chapter cover output dir</label>
            <input id="chapterCoverDir" placeholder="chapter_covers" />
            <label class="checkbox">
              <input type="checkbox" id="coverOverwrite" />
              Overwrite existing cover images
            </label>
            <div class="workspace-actions">
              <button class="pill-button" id="generateBookCover">Generate Book Cover</button>
              <button class="pill-button" id="generateChapterCovers">Generate Chapter Covers</button>
            </div>
            <div class="cover-progress hidden" id="coverProgress">
              <div class="cover-progress-header">
                <strong id="coverProgressLabel">Generating cover art</strong>
                <span>In progress</span>
              </div>
              <div class="cover-progress-bar">
                <span></span>
              </div>
            </div>
          </div>

          <div class="panel">
            <h3>Activity log</h3>
            <div class="action-log" id="actionLog">Waiting for actions...</div>
          </div>
          </section>
        </section>
      </main>

      <main class="detail-view outline-view is-hidden" id="outlineView">
        <div class="detail-header">
          <button class="pill-button" id="outlineBack">← Back to library</button>
          <div class="detail-heading">
            <h2>Outlines</h2>
            <p>Review active outlines and archived drafts in one place.</p>
          </div>
        </div>
        <div id="nowPlayingOutlineSlot"></div>
        <section class="catalog">
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
        </section>
      </main>

      <main class="detail-view is-hidden" id="detailView">
        <div class="detail-header">
          <button class="pill-button" id="detailBack">← Back to library</button>
          <div class="detail-heading">
            <h2 id="detailHeading">Workspace</h2>
            <p id="detailSubheading">Open a book or outline to focus on.</p>
            <p class="meta-line is-hidden" id="detailSummary"></p>
          </div>
        </div>
        <div id="nowPlayingDetailSlot"></div>

        <div class="detail-layout">
          <div class="panel" id="workspacePanel">
            <div class="workspace-empty" id="workspaceEmpty">
              Select a book or outline to open its workspace view.
            </div>
            <div class="workspace-view is-hidden" id="outlineWorkspace">
              <h3>Workspace</h3>
              <div class="workspace-meta">
                <span class="tag">Outline</span>
                <span class="status-chip" id="outlineWorkspaceState"></span>
              </div>
              <strong id="outlineWorkspaceTitle">Outline title</strong>
              <p class="meta-line" id="outlineWorkspacePath"></p>
              <p class="meta-line" id="outlineWorkspaceSummary"></p>
              <div class="detail-section">
                <h4>Outline actions</h4>
                <div class="workspace-actions">
                  <div class="row">
                    <div>
                      <label>Author</label>
                      <select id="outlineWorkspaceAuthor"></select>
                    </div>
                    <div>
                      <label>Tone</label>
                      <select id="outlineWorkspaceTone"></select>
                    </div>
                  </div>
                  <button class="pill-button primary" id="outlineWorkspaceGenerate">
                    Generate book from outline
                  </button>
                </div>
              </div>
              <div class="detail-section">
                <h4>Outline editor</h4>
                <div class="outline-editor">
                  <textarea id="outlineEditor" placeholder="Edit outline markdown here"></textarea>
                  <div class="workspace-actions">
                    <button class="pill-button" id="outlineReload">Reload outline</button>
                    <button class="pill-button primary" id="outlineSave">Save outline</button>
                  </div>
                </div>
              </div>
              <div class="detail-section">
                <h4>Outline preview</h4>
                <div class="detail-content markdown" id="outlineWorkspaceContent"></div>
              </div>
            </div>
            <div class="workspace-view is-hidden" id="bookWorkspace">
              <div class="cover-header workspace-cover" id="bookWorkspaceCoverHeader">
                <div class="cover-header-content">
                  <span class="cover-title" id="bookWorkspaceTitle">Book title</span>
                  <div class="media-block hidden" id="bookAudioBlock">
                    <label>Full book audio</label>
                    <audio controls id="bookAudio"></audio>
                  </div>
                </div>
              </div>
              <img id="bookCoverImage" class="visually-hidden" alt="Book cover" />
              <div class="workspace-meta">
                <span class="tag">Book</span>
                <span class="status-chip" id="bookWorkspaceState"></span>
              </div>
              <p class="meta-line" id="bookWorkspacePath"></p>
              <p class="meta-line" id="bookWorkspacePages"></p>
              <div class="detail-section">
                <h4>Book actions</h4>
                <div class="workspace-actions">
                  <button class="pill-button" id="bookWorkspaceReader">Open reader</button>
                  <button class="pill-button" id="bookWorkspaceExpand">Expand chapters</button>
                  <button class="pill-button" id="bookWorkspaceCompile">Compile PDF</button>
                  <button class="pill-button" id="bookWorkspaceAudio">Generate audio</button>
                  <button class="pill-button" id="bookWorkspaceVideo">Generate video</button>
                  <button class="pill-button" id="bookWorkspaceCover">Generate cover</button>
                  <button class="pill-button" id="bookWorkspaceChapterCovers">
                    Generate chapter covers
                  </button>
                </div>
              </div>
              <div class="detail-section">
                <div class="section-header">
                  <div>
                    <h4>Chapters</h4>
                    <p>Navigate deeper by selecting a chapter card.</p>
                  </div>
                  <span class="count-pill" id="chapterCount">0 chapters</span>
                </div>
                <div class="shelf chapter-shelf" id="chapterShelf"></div>
              </div>
              <div class="detail-section">
                <h4 id="bookContentHeading">Book content</h4>
                <div class="detail-content markdown" id="bookWorkspaceContent"></div>
              </div>
              <div class="detail-section">
                <div class="reader-panel" id="readerPanel">
                  <div class="book-meta">
                    <strong id="readerTitle">Chapter preview</strong>
                    <button class="close-reader" id="closeReader">Close</button>
                  </div>
                  <div class="media-panel" id="mediaPanel">
                    <div class="media-block hidden" id="audioBlock">
                      <label>Audio narration</label>
                      <audio controls id="chapterAudio"></audio>
                    </div>
                    <div class="media-block hidden" id="videoBlock">
                      <label>Chapter video</label>
                      <video controls id="chapterVideo"></video>
                    </div>
                  </div>
                  <div class="reader-body" id="readerBody"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <main class="chapter-view is-hidden" id="chapterView">
        <div class="detail-header">
          <button class="pill-button" id="chapterBack">← Back to book</button>
          <div class="detail-heading">
            <h2 id="chapterHeading">Chapter view</h2>
            <p id="chapterSubheading">Select a chapter to read and play media.</p>
            <p class="meta-line is-hidden" id="chapterSummary"></p>
            <p class="meta-line" id="chapterPageCount"></p>
          </div>
        </div>
        <div id="nowPlayingChapterSlot"></div>

        <div class="chapter-layout">
          <div class="panel">
            <h3>Chapter controls</h3>
            <div class="workspace-actions">
              <button class="pill-button" id="chapterExpand">Expand chapter</button>
              <button class="pill-button" id="chapterGenerateAudio">Generate audio</button>
              <button class="pill-button" id="chapterGenerateVideo">Generate video</button>
              <button class="pill-button" id="chapterGenerateCover">Generate cover</button>
            </div>
          </div>
          <div class="panel reader-panel active" id="chapterReaderPanel">
            <div class="cover-header reader-cover" id="chapterReaderCover">
              <div class="cover-header-content">
                <span class="cover-title" id="chapterReaderTitle">Chapter preview</span>
                <div class="media-block hidden" id="chapterViewAudioBlock">
                  <label>Chapter audio</label>
                  <audio controls id="chapterViewAudio"></audio>
                </div>
              </div>
            </div>
            <img id="chapterCoverImage" class="visually-hidden" alt="Chapter cover" />
            <div class="media-panel" id="chapterMediaPanel">
              <div class="media-block hidden" id="chapterViewVideoBlock">
                <label>Chapter video</label>
                <video controls id="chapterViewVideo"></video>
              </div>
            </div>
            <div class="reader-body" id="chapterReaderBody"></div>
          </div>
        </div>
      </main>
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

      const buildSummaryParams = () => {
        const baseUrl = document.getElementById('baseUrl').value || 'http://localhost:1234';
        const model = document.getElementById('modelName').value || 'local-model';
        const params = new URLSearchParams({
          base_url: baseUrl,
          model,
        });
        return params.toString();
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

      const createCard = (
        title,
        status,
        detail,
        tag,
        accentLabel,
        progress,
        coverUrl = null,
        displayTitle = null,
      ) => {
        const card = document.createElement('article');
        card.className = 'book-card cover-filled';
        const resolvedTitle = displayTitle || title;
        const coverBackground = coverUrl ? `url("${coverUrl}")` : gradientFor(resolvedTitle);
        const overlayBackground = coverUrl
          ? 'linear-gradient(180deg, rgba(8, 12, 20, 0.1) 0%, rgba(8, 12, 20, 0.78) 100%)'
          : 'linear-gradient(180deg, rgba(8, 12, 20, 0.05) 0%, rgba(8, 12, 20, 0.45) 100%)';

        card.style.setProperty('--card-cover', coverBackground);
        card.style.setProperty('--card-overlay', overlayBackground);
        card.style.setProperty('--card-text', '#f8f9fb');
        card.style.setProperty(
          '--card-fade',
          coverUrl ? 'rgba(8, 12, 20, 0.55)' : 'rgba(243, 246, 251, 0.85)',
        );

        const cover = document.createElement('div');
        cover.className = 'book-cover';
        if (coverUrl) {
          cover.classList.add('has-image');
        }
        const coverTitle = document.createElement('span');
        coverTitle.className = 'book-cover-title';
        coverTitle.textContent = resolvedTitle;
        cover.appendChild(coverTitle);

        const content = document.createElement('div');
        content.className = 'card-body';
        const heading = document.createElement('h2');
        heading.textContent = status;
        const meta = document.createElement('div');
        meta.className = 'card-description meta-line markdown';
        meta.innerHTML = renderMarkdown(detail);
        content.appendChild(heading);
        content.appendChild(meta);

        card.appendChild(cover);
        card.appendChild(content);

        const footer = document.createElement('div');
        footer.className = 'card-footer';
        if (typeof progress === 'number') {
          const progressWrap = document.createElement('div');
          progressWrap.className = 'progress';
          const progressFill = document.createElement('span');
          progressFill.style.width = `${Math.min(Math.max(progress, 0), 100)}%`;
          progressWrap.appendChild(progressFill);
          footer.appendChild(progressWrap);
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
        footer.appendChild(metaRow);
        card.appendChild(footer);

        return card;
      };

      const renderEmpty = (container, message) => {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.textContent = message;
        container.appendChild(empty);
      };

      const enableShelfWheelScroll = (shelf) => {
        if (!shelf || shelf.dataset.wheelBound === 'true') {
          return;
        }
        shelf.dataset.wheelBound = 'true';
        shelf.addEventListener(
          'wheel',
          (event) => {
            if (event.deltaY === 0 || Math.abs(event.deltaX) > Math.abs(event.deltaY)) {
              return;
            }
            if (shelf.scrollWidth <= shelf.clientWidth) {
              return;
            }
            event.preventDefault();
            shelf.scrollBy({ left: event.deltaY, behavior: 'smooth' });
          },
          { passive: false },
        );
      };

      const bindShelfWheelScroll = () => {
        document.querySelectorAll('.scroll-shelf').forEach((shelf) => {
          enableShelfWheelScroll(shelf);
        });
      };

      const escapeHtml = (value) =>
        value
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/\"/g, '&quot;')
          .replace(/'/g, '&#39;');

      const formatInlineMarkdown = (value) => {
        if (!value) return '';
        let formatted = value;
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        formatted = formatted.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/__([^_]+)__/g, '<strong>$1</strong>');
        formatted = formatted.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
        formatted = formatted.replace(/_([^_]+)_/g, '<em>$1</em>');
        formatted = formatted.replace(
          /\\[([^\\]]+)\\]\\(([^)]+)\\)/g,
          '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
        );
        return formatted;
      };

      const renderMarkdown = (value) => {
        if (!value) return '';
        const safe = escapeHtml(value);
        const lines = safe.split('\\n');
        let html = '';
        let listType = null;
        const closeList = () => {
          if (listType) {
            html += `</${listType}>`;
            listType = null;
          }
        };
        const isHorizontalRule = (line) => line.trim() === '---';
        const isTableSeparator = (line) => {
          const trimmed = line.trim();
          if (!trimmed.includes('-')) return false;
          const segments = trimmed.split('|').map((segment) => segment.trim());
          const cells = segments.filter((segment) => segment.length);
          if (!cells.length) return false;
          return cells.every((cell) => /^:?-+:?$/.test(cell));
        };
        const parseTableCells = (line) => {
          if (!line.includes('|')) return null;
          const segments = line.split('|').map((segment) => segment.trim());
          if (segments.length <= 1) return null;
          if (!segments[0]) segments.shift();
          if (!segments[segments.length - 1]) segments.pop();
          if (!segments.length) return null;
          return segments.map((segment) => formatInlineMarkdown(segment));
        };
        let index = 0;
        while (index < lines.length) {
          const line = lines[index];
          const trimmed = line.trim();
          if (!trimmed) {
            closeList();
            html += '<p></p>';
            index += 1;
            continue;
          }
          if (isHorizontalRule(trimmed)) {
            closeList();
            html += '<hr />';
            index += 1;
            continue;
          }
          const nextLine = lines[index + 1];
          const headerCells = parseTableCells(trimmed);
          if (headerCells && nextLine && isTableSeparator(nextLine)) {
            closeList();
            let tableHtml = '<table><thead><tr>';
            tableHtml += headerCells.map((cell) => `<th>${cell}</th>`).join('');
            tableHtml += '</tr></thead><tbody>';
            index += 2;
            while (index < lines.length) {
              const rowLine = lines[index];
              const rowTrimmed = rowLine.trim();
              const rowCells = rowTrimmed ? parseTableCells(rowTrimmed) : null;
              if (!rowCells) break;
              tableHtml += '<tr>';
              tableHtml += rowCells.map((cell) => `<td>${cell}</td>`).join('');
              tableHtml += '</tr>';
              index += 1;
            }
            tableHtml += '</tbody></table>';
            html += tableHtml;
            continue;
          }
          const unorderedMatch = /^[-*]\\s+(.+)/.exec(trimmed);
          const orderedMatch = /^(\\d+)\\.\\s+(.+)/.exec(trimmed);
          if (unorderedMatch) {
            if (listType !== 'ul') {
              closeList();
              listType = 'ul';
              html += '<ul>';
            }
            html += `<li>${formatInlineMarkdown(unorderedMatch[1])}</li>`;
            index += 1;
            continue;
          }
          if (orderedMatch) {
            if (listType !== 'ol') {
              closeList();
              listType = 'ol';
              html += '<ol>';
            }
            html += `<li>${formatInlineMarkdown(orderedMatch[2])}</li>`;
            index += 1;
            continue;
          }
          closeList();
          const headingMatch = /^(#{1,6})\\s+(.+)/.exec(trimmed);
          if (headingMatch) {
            const level = headingMatch[1].length;
            html += `<h${level}>${formatInlineMarkdown(headingMatch[2])}</h${level}>`;
            index += 1;
            continue;
          }
          html += `<p>${formatInlineMarkdown(trimmed)}</p>`;
          index += 1;
        }
        closeList();
        return html;
      };

      const setSummaryText = (element, summary) => {
        if (!element) return;
        const cleaned = (summary || '').trim();
        if (!cleaned) {
          element.textContent = '';
          element.classList.add('is-hidden');
          return;
        }
        element.textContent = cleaned;
        element.classList.remove('is-hidden');
      };

      const stripMarkdownSymbols = (value) => {
        if (!value) return '';
        let cleaned = String(value);
        cleaned = cleaned.replace(/!\\[([^\\]]*)\\]\\([^)]+\\)/g, '$1');
        cleaned = cleaned.replace(/\\[([^\\]]+)\\]\\([^)]+\\)/g, '$1');
        cleaned = cleaned.replace(/[`*_~>#]/g, '');
        cleaned = cleaned.replace(/[()[\\]]/g, '');
        cleaned = cleaned.replace(/\\s+/g, ' ').trim();
        return cleaned;
      };

      const sanitizeTitleForDisplay = (value, type) => {
        const base = stripMarkdownSymbols(value);
        if (!base) return '';
        let cleaned = base;
        if (type === 'book') {
          cleaned = cleaned.replace(/^(book\\s+)?title\\b\\s*[:\\-–]?\\s*/i, '');
          cleaned = cleaned.replace(/\\btitle\\b/gi, '').replace(/\\s+/g, ' ').trim();
        }
        if (type === 'chapter') {
          cleaned = cleaned.replace(/^chapter\\s+\\d+\\s*[:\\-–]?\\s*/i, '');
          cleaned = cleaned.replace(/^[\\-–—]+\\s*/, '');
        }
        cleaned = cleaned.replace(/\\s+/g, ' ').trim();
        return cleaned || base;
      };

      const displayBookTitle = (title) => sanitizeTitleForDisplay(title, 'book');

      const displayChapterTitle = (title) => sanitizeTitleForDisplay(title, 'chapter');

      const formatPageCount = (count) => {
        const resolved = Number(count);
        const safeCount = Number.isFinite(resolved) ? resolved : 0;
        return `${safeCount} page${safeCount === 1 ? '' : 's'}`;
      };

      const sumChapterPages = (chapters) =>
        (chapters || []).reduce((total, chapter) => {
          const resolved = Number(chapter?.page_count);
          const safeCount = Number.isFinite(resolved) ? resolved : 0;
          return total + safeCount;
        }, 0);

      const searchInput = document.getElementById('searchInput');
      const outlineSelect = document.getElementById('outlineSelect');
      const bookSelect = document.getElementById('bookSelect');
      const chapterSelect = document.getElementById('chapterSelect');
      const openReader = document.getElementById('openReader');
      const readerPanel = document.getElementById('readerPanel');
      const readerTitle = document.getElementById('readerTitle');
      const readerBody = document.getElementById('readerBody');
      const closeReader = document.getElementById('closeReader');
      const audioBlock = document.getElementById('audioBlock');
      const videoBlock = document.getElementById('videoBlock');
      const chapterAudio = document.getElementById('chapterAudio');
      const chapterVideo = document.getElementById('chapterVideo');
      const bookAudioBlock = document.getElementById('bookAudioBlock');
      const bookAudio = document.getElementById('bookAudio');
      const bookCoverImage = document.getElementById('bookCoverImage');
      const homeView = document.getElementById('homeView');
      const detailView = document.getElementById('detailView');
      const detailBack = document.getElementById('detailBack');
      const outlineView = document.getElementById('outlineView');
      const outlineBack = document.getElementById('outlineBack');
      const detailHeading = document.getElementById('detailHeading');
      const detailSubheading = document.getElementById('detailSubheading');
      const detailSummary = document.getElementById('detailSummary');
      const chapterView = document.getElementById('chapterView');
      const chapterBack = document.getElementById('chapterBack');
      const chapterHeading = document.getElementById('chapterHeading');
      const chapterSubheading = document.getElementById('chapterSubheading');
      const chapterSummary = document.getElementById('chapterSummary');
      const chapterPageCount = document.getElementById('chapterPageCount');
      const chapterReaderTitle = document.getElementById('chapterReaderTitle');
      const chapterReaderBody = document.getElementById('chapterReaderBody');
      const chapterViewAudioBlock = document.getElementById('chapterViewAudioBlock');
      const chapterViewVideoBlock = document.getElementById('chapterViewVideoBlock');
      const chapterViewAudio = document.getElementById('chapterViewAudio');
      const chapterViewVideo = document.getElementById('chapterViewVideo');
      const chapterCoverImage = document.getElementById('chapterCoverImage');
      const chapterReaderCover = document.getElementById('chapterReaderCover');
      const chapterExpand = document.getElementById('chapterExpand');
      const chapterGenerateAudio = document.getElementById('chapterGenerateAudio');
      const chapterGenerateVideo = document.getElementById('chapterGenerateVideo');
      const chapterGenerateCover = document.getElementById('chapterGenerateCover');
      const workspaceEmpty = document.getElementById('workspaceEmpty');
      const outlineWorkspace = document.getElementById('outlineWorkspace');
      const outlineWorkspaceState = document.getElementById('outlineWorkspaceState');
      const outlineWorkspaceTitle = document.getElementById('outlineWorkspaceTitle');
      const outlineWorkspacePath = document.getElementById('outlineWorkspacePath');
      const outlineWorkspaceSummary = document.getElementById('outlineWorkspaceSummary');
      const outlineWorkspaceContent = document.getElementById('outlineWorkspaceContent');
      const outlineWorkspaceGenerate = document.getElementById('outlineWorkspaceGenerate');
      const outlineWorkspaceAuthor = document.getElementById('outlineWorkspaceAuthor');
      const outlineWorkspaceTone = document.getElementById('outlineWorkspaceTone');
      const outlineEditor = document.getElementById('outlineEditor');
      const outlineSave = document.getElementById('outlineSave');
      const outlineReload = document.getElementById('outlineReload');
      const outlinePrompt = document.getElementById('outlinePrompt');
      const outlineRevisions = document.getElementById('outlineRevisions');
      const outlineName = document.getElementById('outlineName');
      const outlineDir = document.getElementById('outlineDir');
      const outlineModel = document.getElementById('outlineModel');
      const outlineBaseUrl = document.getElementById('outlineBaseUrl');
      const generateOutline = document.getElementById('generateOutline');
      const bookWorkspace = document.getElementById('bookWorkspace');
      const bookWorkspaceState = document.getElementById('bookWorkspaceState');
      const bookWorkspaceTitle = document.getElementById('bookWorkspaceTitle');
      const bookWorkspaceCoverHeader = document.getElementById('bookWorkspaceCoverHeader');
      const bookWorkspacePath = document.getElementById('bookWorkspacePath');
      const bookWorkspacePages = document.getElementById('bookWorkspacePages');
      const bookContentHeading = document.getElementById('bookContentHeading');
      const bookWorkspaceContent = document.getElementById('bookWorkspaceContent');
      const chapterShelf = document.getElementById('chapterShelf');
      const chapterCount = document.getElementById('chapterCount');
      const bookWorkspaceReader = document.getElementById('bookWorkspaceReader');
      const bookWorkspaceExpand = document.getElementById('bookWorkspaceExpand');
      const bookWorkspaceCompile = document.getElementById('bookWorkspaceCompile');
      const bookWorkspaceAudio = document.getElementById('bookWorkspaceAudio');
      const bookWorkspaceVideo = document.getElementById('bookWorkspaceVideo');
      const bookWorkspaceCover = document.getElementById('bookWorkspaceCover');
      const bookWorkspaceChapterCovers = document.getElementById('bookWorkspaceChapterCovers');
      const coverProgress = document.getElementById('coverProgress');
      const coverProgressLabel = document.getElementById('coverProgressLabel');
      const nowPlaying = document.getElementById('nowPlaying');
      const nowPlayingTitle = document.getElementById('nowPlayingTitle');
      const nowPlayingSubtitle = document.getElementById('nowPlayingSubtitle');
      const nowPlayingControls = document.getElementById('nowPlayingControls');
      const nowPlayingClose = document.getElementById('nowPlayingClose');
      const nowPlayingAutoplay = document.getElementById('nowPlayingAutoplay');
      const nowPlayingHomeSlot = document.getElementById('nowPlayingHomeSlot');
      const nowPlayingOutlineSlot = document.getElementById('nowPlayingOutlineSlot');
      const nowPlayingDetailSlot = document.getElementById('nowPlayingDetailSlot');
      const nowPlayingChapterSlot = document.getElementById('nowPlayingChapterSlot');
      const latestShelf = document.getElementById('latestShelf');
      const genreShelves = document.getElementById('genreShelves');
      const allBooksSection = document.getElementById('allBooksSection');
      const viewAllBooks = document.getElementById('viewAllBooks');
      const viewAllBooksSecondary = document.getElementById('viewAllBooksSecondary');
      const viewOutlines = document.getElementById('viewOutlines');
      const toggleUtilities = document.getElementById('toggleUtilities');
      const homeUtilities = document.getElementById('homeUtilities');

      const setSelectOptions = (select, options, placeholder) => {
        select.innerHTML = '';
        const placeholderOption = document.createElement('option');
        placeholderOption.value = '';
        placeholderOption.textContent = placeholder;
        select.appendChild(placeholderOption);
        options.forEach((option) => {
          const optionEl = document.createElement('option');
          optionEl.value = option.value;
          optionEl.textContent = option.label;
          select.appendChild(optionEl);
        });
      };

      const outlineLabel = (outline) =>
        `${outline.title || outline.path.split('/').pop()} (${outline.item_count || 0} sections)`;

      const bookLabel = (book) =>
        `${displayBookTitle(book.title)} (${book.chapter_count || 0} chapters)`;

      const catalogState = {
        outlines: [],
        completedOutlines: [],
        books: [],
        authors: [],
        tones: [],
      };

      let showAllBooks = false;

      const getSearchTerm = () => (searchInput?.value || '').trim().toLowerCase();

      const filterEntries = (entries, getFields) => {
        const term = getSearchTerm();
        if (!term) return entries;
        return entries.filter((entry) =>
          getFields(entry).some((field) => String(field || '').toLowerCase().includes(term)),
        );
      };

      const normalizeGenres = (genres) => {
        if (!Array.isArray(genres)) return [];
        const unique = [];
        const seen = new Set();
        genres.forEach((genre) => {
          const cleaned = String(genre || '').trim().replace(/[.,;]+$/, '');
          if (!cleaned) return;
          const key = cleaned.toLowerCase();
          if (seen.has(key)) return;
          seen.add(key);
          unique.push(cleaned);
        });
        return unique;
      };

      const getPrimaryGenre = (book) => {
        const genres = normalizeGenres(book.genres);
        return genres.length ? genres[0] : 'Uncategorized';
      };

      const getBookFolderTimestamp = (book) => {
        const value = Number(book?.folder_mtime);
        return Number.isFinite(value) ? value : 0;
      };

      const getGenreLine = (book) => {
        const genres = normalizeGenres(book.genres);
        if (!genres.length) return 'Genre: Uncategorized';
        return `Genres: ${genres.join(', ')}`;
      };

      const groupBooksByGenre = (books) => {
        const groups = new Map();
        books.forEach((book) => {
          const genre = getPrimaryGenre(book);
          if (!groups.has(genre)) {
            groups.set(genre, []);
          }
          groups.get(genre).push(book);
        });
        return groups;
      };

      const sortGenreKeys = (keys) => {
        const sorted = [...keys].sort((a, b) => a.localeCompare(b));
        const uncategorizedIndex = sorted.findIndex(
          (genre) => genre.toLowerCase() === 'uncategorized',
        );
        if (uncategorizedIndex > -1) {
          const [uncategorized] = sorted.splice(uncategorizedIndex, 1);
          sorted.push(uncategorized);
        }
        return sorted;
      };

      let currentSelection = {
        type: null,
        path: null,
      };
      let currentChapters = [];
      let currentChapter = null;
      let chapterAudioHandoff = null;
      let activeChapterAudio = chapterViewAudio;
      let activePlayback = null;
      let autoplayEnabled = true;
      let currentBookSynopsis = '';
      const autoplayState = {
        session: null,
        chapters: [],
      };

      const showHomeView = () => {
        detailView.classList.add('is-hidden');
        outlineView.classList.add('is-hidden');
        chapterView.classList.add('is-hidden');
        homeView.classList.remove('is-hidden');
        updateNowPlayingPlacement();
      };

      const showDetailView = () => {
        homeView.classList.add('is-hidden');
        outlineView.classList.add('is-hidden');
        chapterView.classList.add('is-hidden');
        detailView.classList.remove('is-hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        updateNowPlayingPlacement();
      };

      const showOutlineView = () => {
        homeView.classList.add('is-hidden');
        detailView.classList.add('is-hidden');
        chapterView.classList.add('is-hidden');
        outlineView.classList.remove('is-hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        updateNowPlayingPlacement();
      };

      const showChapterView = () => {
        homeView.classList.add('is-hidden');
        detailView.classList.add('is-hidden');
        outlineView.classList.add('is-hidden');
        chapterView.classList.remove('is-hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        updateNowPlayingPlacement();
      };

      const setSelectedCard = (cardElement) => {
        document.querySelectorAll('.book-card.selected').forEach((card) => {
          card.classList.remove('selected');
        });
        if (cardElement) {
          cardElement.classList.add('selected');
        }
      };

      const findCardByPath = (type, path) => {
        const cards = Array.from(document.querySelectorAll('.book-card.selectable'));
        return (
          cards.find((card) => card.dataset.type === type && card.dataset.path === path) || null
        );
      };

      const showWorkspace = (type) => {
        workspaceEmpty.classList.add('is-hidden');
        outlineWorkspace.classList.toggle('is-hidden', type !== 'outline');
        bookWorkspace.classList.toggle('is-hidden', type !== 'book');
        if (type === 'outline') {
          detailHeading.textContent = 'Outline workspace';
        } else if (type === 'book') {
          detailHeading.textContent = 'Book workspace';
        }
      };

      const updateOutlinePreview = (content) => {
        outlineWorkspaceContent.innerHTML = renderMarkdown(
          content || 'No outline content available.',
        );
      };

      const setOutlineContent = (content) => {
        outlineEditor.value = content || '';
        updateOutlinePreview(content);
      };

      const setBookContent = (content) => {
        bookWorkspaceContent.innerHTML = renderMarkdown(content || 'No chapter content available.');
      };

      const setBookSynopsis = (synopsis) => {
        currentBookSynopsis = synopsis || '';
        if (bookContentHeading) {
          bookContentHeading.textContent = currentBookSynopsis
            ? 'Book synopsis'
            : 'Book content';
        }
        if (currentBookSynopsis) {
          setBookContent(currentBookSynopsis);
        }
      };

      const setChapterSelection = (chapterIndex) => {
        document.querySelectorAll('.chapter-card.selected').forEach((card) => {
          card.classList.remove('selected');
        });
        if (!chapterIndex) return;
        const activeCard = chapterShelf.querySelector(`article[data-chapter="${chapterIndex}"]`);
        if (activeCard) {
          activeCard.classList.add('selected');
        }
      };

      const getChapterCardAudio = (chapterIndex) => {
        const card = chapterShelf.querySelector(`article[data-chapter="${chapterIndex}"]`);
        if (!card) return null;
        return card.querySelector('audio');
      };

      const restoreChapterAudioToDetail = () => {
        if (!chapterViewAudioBlock.contains(chapterViewAudio)) {
          chapterViewAudioBlock.replaceChildren(chapterViewAudio);
        }
        activeChapterAudio = chapterViewAudio;
      };

      const handoffChapterAudioToDetail = (cardAudio, url) => {
        if (!cardAudio || !url) {
          chapterAudioHandoff = null;
          restoreChapterAudioToDetail();
          return;
        }
        if (cardAudio.dataset.audioUrl !== url) {
          chapterAudioHandoff = null;
          restoreChapterAudioToDetail();
          return;
        }
        if (
          chapterAudioHandoff &&
          chapterAudioHandoff.cardAudio &&
          chapterAudioHandoff.cardAudio !== cardAudio
        ) {
          restoreChapterAudioToCard();
        }
        const cardContainer = cardAudio.parentElement;
        if (!cardContainer) {
          chapterAudioHandoff = null;
          restoreChapterAudioToDetail();
          return;
        }
        chapterAudioHandoff = { cardAudio, cardContainer, url };
        cardAudio.dataset.mediaUrl = url;
        chapterViewAudioBlock.classList.remove('hidden');
        chapterViewAudioBlock.replaceChildren(cardAudio);
        activeChapterAudio = cardAudio;
      };

      const restoreChapterAudioToCard = () => {
        if (!chapterAudioHandoff || !chapterAudioHandoff.cardAudio) {
          restoreChapterAudioToDetail();
          return;
        }
        const { cardAudio, cardContainer } = chapterAudioHandoff;
        if (cardContainer && !cardContainer.contains(cardAudio)) {
          cardContainer.replaceChildren(cardAudio);
        }
        chapterAudioHandoff = null;
        restoreChapterAudioToDetail();
      };

      const hydrateAudioSource = (audio, mediaUrl) => {
        if (!audio) return;
        if (!mediaUrl) return;
        if (audio.src !== mediaUrl) {
          audio.src = mediaUrl;
        }
        audio.preload = 'metadata';
        audio.load();
      };

      const getAudioLabel = (audio) => {
        if (!audio) return 'Audio';
        if (audio === bookAudio) {
          return bookWorkspaceTitle.textContent || 'Book audio';
        }
        if (audio === chapterAudio || audio === chapterViewAudio) {
          return readerTitle.textContent || chapterReaderTitle.textContent || 'Chapter audio';
        }
        return audio.dataset.mediaTitle || 'Audio playback';
      };

      const getBookMetadata = (bookDir) => {
        if (!bookDir) {
          return { title: '', coverUrl: '' };
        }
        const match = catalogState.books.find((book) => book.path === bookDir);
        if (match) {
          const title = displayBookTitle(match.title || '') || match.path.split('/').pop();
          return { title, coverUrl: match.cover_url || '' };
        }
        return { title: bookDir.split('/').pop(), coverUrl: '' };
      };

      const setBookAudioMetadata = (audio, bookDir, title, coverUrl) => {
        if (!audio) return;
        audio.dataset.playbackType = 'book';
        audio.dataset.bookDir = bookDir || '';
        audio.dataset.bookTitle = title || '';
        audio.dataset.coverUrl = coverUrl || '';
      };

      const setChapterAudioMetadata = (audio, details) => {
        if (!audio || !details) return;
        audio.dataset.playbackType = 'chapter';
        audio.dataset.bookDir = details.bookDir || '';
        audio.dataset.chapterIndex = details.chapterIndex ? String(details.chapterIndex) : '';
        audio.dataset.bookTitle = details.bookTitle || '';
        audio.dataset.coverUrl = details.coverUrl || '';
        audio.dataset.bookCoverUrl = details.bookCoverUrl || '';
        if (details.mediaTitle) {
          audio.dataset.mediaTitle = details.mediaTitle;
        }
      };

      const getPlaybackMetadata = (audio) => {
        if (!audio) return {};
        const chapterIndexValue = audio.dataset.chapterIndex;
        const chapterIndex = chapterIndexValue ? Number(chapterIndexValue) : null;
        return {
          playbackType: audio.dataset.playbackType || null,
          bookDir: audio.dataset.bookDir || null,
          chapterIndex,
          coverUrl: audio.dataset.coverUrl || audio.dataset.bookCoverUrl || null,
          bookTitle: audio.dataset.bookTitle || '',
        };
      };

      const updateNowPlayingBackground = (coverUrl) => {
        if (!nowPlaying) return;
        if (coverUrl) {
          nowPlaying.style.setProperty('--now-playing-cover', `url("${coverUrl}")`);
          nowPlaying.classList.add('with-cover');
          return;
        }
        nowPlaying.style.removeProperty('--now-playing-cover');
        nowPlaying.classList.remove('with-cover');
      };

      const updateNowPlayingUI = () => {
        if (!nowPlaying) return;
        if (!activePlayback || !activePlayback.audio) {
          nowPlaying.classList.add('hidden');
          updateNowPlayingBackground(null);
          return;
        }
        nowPlayingTitle.textContent = activePlayback.title || 'Audio playback';
        if (nowPlayingSubtitle) {
          nowPlayingSubtitle.textContent = activePlayback.subtitle || '';
        }
        nowPlaying.classList.remove('hidden');
        updateNowPlayingBackground(activePlayback.coverUrl || null);
      };

      const restoreAudioToOrigin = (origin, audio) => {
        if (!origin || !origin.parent || !audio) return;
        if (origin.parent.contains(audio)) return;
        if (origin.nextSibling && origin.nextSibling.parentElement === origin.parent) {
          origin.parent.insertBefore(audio, origin.nextSibling);
        } else {
          origin.parent.appendChild(audio);
        }
      };

      const moveAudioToNowPlaying = (audio) => {
        if (!nowPlayingControls || !audio) return;
        if (nowPlayingControls.contains(audio)) return;
        nowPlayingControls.replaceChildren(audio);
      };

      const getActiveViewSlot = () => {
        if (!homeView.classList.contains('is-hidden')) return nowPlayingHomeSlot;
        if (!outlineView.classList.contains('is-hidden')) return nowPlayingOutlineSlot;
        if (!detailView.classList.contains('is-hidden')) return nowPlayingDetailSlot;
        if (!chapterView.classList.contains('is-hidden')) return nowPlayingChapterSlot;
        return nowPlayingHomeSlot;
      };

      const updateNowPlayingPlacement = () => {
        if (!nowPlaying) return;
        const slot = getActiveViewSlot();
        if (slot && nowPlaying.parentElement !== slot) {
          slot.appendChild(nowPlaying);
        }
        if (!activePlayback || !activePlayback.audio) {
          updateNowPlayingUI();
          return;
        }
        moveAudioToNowPlaying(activePlayback.audio);
        updateNowPlayingUI();
      };

      const resolveBookEntry = async (bookDir) => {
        if (!bookDir) return null;
        let book = catalogState.books.find((entry) => entry.path === bookDir);
        if (book) {
          return book;
        }
        try {
          await loadCatalog({ selectCurrent: false, refreshMode: 'books' });
        } catch (error) {
          log(`Catalog refresh failed: ${error.message}`);
        }
        book = catalogState.books.find((entry) => entry.path === bookDir);
        return book || null;
      };

      const navigateToBookDetail = async (bookDir) => {
        const book = await resolveBookEntry(bookDir);
        if (!book) {
          return;
        }
        await selectEntry('book', book);
      };

      const navigateToChapterDetail = async (bookDir, chapterIndex) => {
        if (!bookDir || chapterIndex === null || chapterIndex === undefined) return;
        const book = await resolveBookEntry(bookDir);
        if (!book) {
          return;
        }
        if (currentSelection.type !== 'book' || currentSelection.path !== bookDir) {
          await selectEntry('book', book);
        }
        const chapters = await loadChapters(bookDir);
        const chapter = chapters.find(
          (entry) => Number(entry.index) === Number(chapterIndex),
        );
        if (!chapter) {
          return;
        }
        await openChapterView(bookDir, chapter);
      };

      const shouldIgnoreNowPlayingClick = (event) => {
        if (!event || !event.target) return false;
        if (nowPlayingControls && nowPlayingControls.contains(event.target)) return true;
        if (nowPlayingClose && nowPlayingClose.contains(event.target)) return true;
        if (nowPlayingAutoplay && nowPlayingAutoplay.contains(event.target)) return true;
        return false;
      };

      const stopActivePlayback = () => {
        if (!activePlayback || !activePlayback.audio) return;
        const { audio, origin } = activePlayback;
        audio.pause();
        restoreAudioToOrigin(origin, audio);
        activePlayback = null;
        updateNowPlayingUI();
      };

      const findNextPlayableChapter = (chapters, currentIndex) => {
        if (!chapters || currentIndex === null || currentIndex === undefined) return null;
        const startIndex = chapters.findIndex(
          (chapter) => Number(chapter.index) === Number(currentIndex),
        );
        if (startIndex === -1) return null;
        for (let i = startIndex + 1; i < chapters.length; i += 1) {
          if (chapters[i].audio_url) {
            return chapters[i];
          }
        }
        return null;
      };

      const startAutoplaySession = async (bookDir) => {
        if (!bookDir) return;
        if (autoplayState.session && autoplayState.session.bookDir === bookDir) return;
        let chapters = [];
        if (currentSelection.type === 'book' && currentSelection.path === bookDir) {
          chapters = currentChapters;
        }
        if (!chapters || !chapters.length) {
          chapters = await fetchChapters(bookDir);
        }
        autoplayState.session = {
          bookDir,
          initialCount: chapters.length,
          knownCount: chapters.length,
        };
        autoplayState.chapters = chapters;
      };

      const refreshAutoplayChapters = async (bookDir) => {
        const chapters = await fetchChapters(bookDir);
        if (autoplayState.session && autoplayState.session.bookDir === bookDir) {
          autoplayState.session.knownCount = chapters.length;
          autoplayState.chapters = chapters;
        }
        if (currentSelection.type === 'book' && currentSelection.path === bookDir) {
          currentChapters = chapters;
          updateChaptersInDetailView(bookDir, chapters);
        }
        return chapters;
      };

      const playAutoplayChapter = async (bookDir, chapter) => {
        if (!chapter || !chapter.audio_url) return false;
        currentChapter = { ...chapter, bookDir };
        if (currentSelection.type === 'book' && currentSelection.path === bookDir) {
          chapterSelect.value = String(chapter.index);
          setChapterSelection(String(chapter.index));
        }
        if (
          !chapterView.classList.contains('is-hidden') &&
          currentChapter.bookDir === bookDir
        ) {
          await openChapterView(bookDir, chapter);
          if (chapterViewAudio) {
            await chapterViewAudio.play();
            return true;
          }
        }
        const cardAudio = getChapterCardAudio(String(chapter.index));
        if (cardAudio) {
          const { coverUrl: bookCoverUrl, title: bookTitle } = getBookMetadata(bookDir);
          setChapterAudioMetadata(cardAudio, {
            bookDir,
            chapterIndex: chapter.index,
            bookTitle,
            coverUrl: chapter.cover_url || '',
            bookCoverUrl,
            mediaTitle: displayChapterTitle(chapter.title || `Chapter ${chapter.index}`),
          });
          hydrateAudioSource(cardAudio, chapter.audio_url);
          await cardAudio.play();
          return true;
        }
        const { coverUrl: bookCoverUrl, title: bookTitle } = getBookMetadata(bookDir);
        const fallbackAudio = chapterAudio;
        setMediaSource(audioBlock, fallbackAudio, chapter.audio_url);
        setChapterAudioMetadata(fallbackAudio, {
          bookDir,
          chapterIndex: chapter.index,
          bookTitle,
          coverUrl: chapter.cover_url || '',
          bookCoverUrl,
          mediaTitle: displayChapterTitle(chapter.title || `Chapter ${chapter.index}`),
        });
        await fallbackAudio.play();
        return true;
      };

      const trackPlayback = (audio, titleProvider) => {
        if (!audio) return;
        audio.addEventListener('play', async () => {
          if (activePlayback?.audio && activePlayback.audio !== audio) {
            stopActivePlayback();
          }
          const origin =
            activePlayback?.audio === audio && activePlayback.origin
              ? activePlayback.origin
              : {
                  parent: audio.parentElement,
                  nextSibling: audio.nextSibling,
                };
          const metadata = getPlaybackMetadata(audio);
          activePlayback = {
            audio,
            title: titleProvider ? titleProvider() : getAudioLabel(audio),
            subtitle: metadata.bookTitle ? `Book: ${metadata.bookTitle}` : '',
            coverUrl: metadata.coverUrl || null,
            playbackType: metadata.playbackType,
            bookDir: metadata.bookDir,
            chapterIndex: metadata.chapterIndex,
            origin,
          };
          if (metadata.playbackType === 'chapter' && metadata.bookDir) {
            try {
              await startAutoplaySession(metadata.bookDir);
            } catch (error) {
              log(`Autoplay setup failed: ${error.message}`);
            }
          }
          moveAudioToNowPlaying(audio);
          updateNowPlayingPlacement();
        });
        audio.addEventListener('ended', async () => {
          if (activePlayback?.audio !== audio) {
            return;
          }
          if (
            autoplayEnabled &&
            activePlayback.playbackType === 'chapter' &&
            activePlayback.bookDir
          ) {
            const bookDir = activePlayback.bookDir;
            await startAutoplaySession(bookDir);
            let chapters = autoplayState.chapters;
            let nextChapter = findNextPlayableChapter(chapters, activePlayback.chapterIndex);
            if (!nextChapter) {
              try {
                const refreshed = await refreshAutoplayChapters(bookDir);
                const baseline = autoplayState.session?.initialCount ?? 0;
                if (refreshed.length > baseline) {
                  chapters = refreshed;
                  nextChapter = findNextPlayableChapter(chapters, activePlayback.chapterIndex);
                }
              } catch (error) {
                log(`Autoplay refresh failed: ${error.message}`);
              }
            }
            if (nextChapter) {
              const played = await playAutoplayChapter(bookDir, nextChapter);
              if (played) {
                return;
              }
            }
          }
          stopActivePlayback();
        });
      };

      const createChapterCard = (bookDir, chapter, bookCoverUrl, bookTitle) => {
        const title = chapter.title || `Chapter ${chapter.index}`;
        const displayTitle = displayChapterTitle(title);
        const detail = `${
          chapter.summary || 'Select to preview chapter content.'
        }\n${formatPageCount(chapter.page_count)}`;
        const card = createCard(
          title,
          `Chapter ${chapter.index}`,
          detail,
          'Chapter',
          'Preview',
          null,
          chapter.cover_url || null,
          displayTitle,
        );
        card.classList.add('selectable', 'chapter-card');
        card.dataset.chapter = String(chapter.index);
        if (chapter.audio_url) {
          const media = document.createElement('div');
          media.className = 'card-media';
          const audio = document.createElement('audio');
          audio.controls = true;
          audio.dataset.audioUrl = chapter.audio_url;
          audio.dataset.mediaUrl = chapter.audio_url;
          audio.dataset.mediaTitle = displayTitle;
          setChapterAudioMetadata(audio, {
            bookDir,
            chapterIndex: chapter.index,
            bookTitle,
            coverUrl: chapter.cover_url || '',
            bookCoverUrl,
            mediaTitle: displayTitle,
          });
          hydrateAudioSource(audio, chapter.audio_url);
          trackPlayback(audio, () => displayTitle);
          audio.addEventListener('click', (event) => {
            event.stopPropagation();
          });
          audio.addEventListener('play', (event) => {
            event.stopPropagation();
          });
          media.addEventListener('click', (event) => {
            event.stopPropagation();
          });
          media.appendChild(audio);
          card.appendChild(media);
        }
        return card;
      };

      const renderChapterShelf = (bookDir, chapters) => {
        updateNowPlayingPlacement();
        chapterShelf.innerHTML = '';
        chapterCount.textContent = `${chapters.length} chapters`;
        if (bookWorkspacePages) {
          bookWorkspacePages.textContent = formatPageCount(sumChapterPages(chapters));
        }
        if (!chapters.length) {
          renderEmpty(chapterShelf, 'No chapters found for this book yet.');
          return;
        }
        const { coverUrl: bookCoverUrl, title: bookTitle } = getBookMetadata(bookDir);
        chapters.forEach((chapter) => {
          const card = createChapterCard(bookDir, chapter, bookCoverUrl, bookTitle);
          card.addEventListener('click', async () => {
            await openChapterView(bookDir, chapter);
          });
          chapterShelf.appendChild(card);
        });
      };

      const updateChaptersInDetailView = (bookDir, chapters) => {
        if (
          currentSelection.type !== 'book' ||
          currentSelection.path !== bookDir ||
          detailView.classList.contains('is-hidden')
        ) {
          return;
        }
        const previousSelection = chapterSelect.value;
        const options = chapters.map((chapter) => {
          const title = chapter.title || `Chapter ${chapter.index}`;
          return {
            value: String(chapter.index),
            label: `${chapter.index}. ${displayChapterTitle(title)}`,
          };
        });
        setSelectOptions(chapterSelect, options, 'Select a chapter');
        chapterSelect.disabled = !options.length;
        if (previousSelection) {
          chapterSelect.value = previousSelection;
        }
        renderChapterShelf(bookDir, chapters);
      };

      const loadOutlineContent = async (outlinePath) => {
        const result = await fetchJson(
          `/api/outline-content?outline_path=${encodeURIComponent(outlinePath)}`,
        );
        return result;
      };

      const loadBookContent = async (bookDir) => {
        if (!bookDir) return null;
        const params = new URLSearchParams({
          book_dir: bookDir,
        });
        const summaryParams = buildSummaryParams();
        const result = await fetchJson(
          `/api/book-content?${params.toString()}&${summaryParams}`,
        );
        return result;
      };

      const parseRevisionPrompts = (value) =>
        value
          .split(`\n`)
          .map((line) => line.trim())
          .filter((line) => line);

      const resolveOutlineDir = (outlinePath) => {
        if (!outlinePath) {
          return outlineDir.value || 'outlines';
        }
        const parts = outlinePath.split('/');
        if (parts.length <= 1) {
          return outlineDir.value || 'outlines';
        }
        return parts.slice(0, -1).join('/');
      };

      const resolveOutlinePath = () => {
        const workspacePath = outlineWorkspacePath.textContent.trim();
        if (workspacePath) {
          return workspacePath;
        }
        return outlineSelect.value || '';
      };

      const loadWorkspaceChapterContent = async (bookDir, chapterValue) => {
        if (!bookDir || !chapterValue) return;
        if (currentBookSynopsis) {
          setBookContent(currentBookSynopsis);
          return;
        }
        const audioDir = document.getElementById('audioDir').value || 'audio';
        const videoDir = document.getElementById('videoDir').value || 'video';
        const chapterCoverDir = document.getElementById('chapterCoverDir').value || 'chapter_covers';
        const result = await fetchJson(
          `/api/chapter-content?book_dir=${encodeURIComponent(
            bookDir,
          )}&chapter=${encodeURIComponent(chapterValue)}&audio_dirname=${encodeURIComponent(
            audioDir,
          )}&video_dirname=${encodeURIComponent(videoDir)}&chapter_cover_dir=${encodeURIComponent(
            chapterCoverDir,
          )}&${buildSummaryParams()}`,
        );
        setBookContent(result.content || '');
      };

      const openChapterView = async (bookDir, chapter) => {
        if (!bookDir || !chapter) return;
        const chapterIndex = String(chapter.index);
        const cardAudio = getChapterCardAudio(chapterIndex);
        currentChapter = { ...chapter, bookDir };
        chapterSelect.value = chapterIndex;
        openReader.disabled = false;
        setChapterSelection(chapterIndex);
        const chapterTitle = chapter.title || `Chapter ${chapter.index}`;
        chapterHeading.textContent = displayChapterTitle(chapterTitle);
        chapterSubheading.textContent = `Book: ${bookDir.split('/').pop()}`;
        chapterPageCount.textContent = formatPageCount(chapter.page_count);
        const audioDir = document.getElementById('audioDir').value || 'audio';
        const videoDir = document.getElementById('videoDir').value || 'video';
        const chapterCoverDir = document.getElementById('chapterCoverDir').value || 'chapter_covers';
        const result = await fetchJson(
          `/api/chapter-content?book_dir=${encodeURIComponent(
            bookDir,
          )}&chapter=${encodeURIComponent(chapterIndex)}&audio_dirname=${encodeURIComponent(
            audioDir,
          )}&video_dirname=${encodeURIComponent(videoDir)}&chapter_cover_dir=${encodeURIComponent(
            chapterCoverDir,
          )}&${buildSummaryParams()}`,
        );
        const readerTitleValue = result.title || 'Chapter preview';
        const displayReaderTitle = displayChapterTitle(readerTitleValue);
        chapterReaderTitle.textContent = displayReaderTitle;
        chapterPageCount.textContent = formatPageCount(result.page_count ?? chapter.page_count);
        setSummaryText(chapterSummary, result.summary || chapter.summary || '');
        chapterReaderBody.innerHTML = renderMarkdown(result.content || '');
        restoreChapterAudioToDetail();
        setHiddenImageSource(chapterCoverImage, result.cover_url);
        setCoverHeader(chapterReaderCover, displayReaderTitle, result.cover_url);
        setMediaSource(chapterViewAudioBlock, chapterViewAudio, result.audio_url);
        setMediaSource(chapterViewVideoBlock, chapterViewVideo, result.video_url);
        const { coverUrl: bookCoverUrl, title: bookTitle } = getBookMetadata(bookDir);
        setChapterAudioMetadata(chapterViewAudio, {
          bookDir,
          chapterIndex,
          bookTitle,
          coverUrl: result.cover_url || '',
          bookCoverUrl,
          mediaTitle: displayReaderTitle,
        });
        handoffChapterAudioToDetail(cardAudio, result.audio_url);
        await loadWorkspaceChapterContent(bookDir, chapterIndex);
        showChapterView();
      };

      const fetchChapters = async (bookDir) => {
        if (!bookDir) return [];
        const audioDir = document.getElementById('audioDir').value || 'audio';
        const videoDir = document.getElementById('videoDir').value || 'video';
        const chapterCoverDir = document.getElementById('chapterCoverDir').value || 'chapter_covers';
        const result = await fetchJson(
          `/api/chapters?book_dir=${encodeURIComponent(
            bookDir,
          )}&audio_dirname=${encodeURIComponent(audioDir)}&video_dirname=${encodeURIComponent(
            videoDir,
          )}&chapter_cover_dir=${encodeURIComponent(chapterCoverDir)}&${buildSummaryParams()}`,
        );
        return result.chapters || [];
      };

      const selectEntry = async (type, entry, cardElement = null) => {
        if (!entry) return;
        currentSelection = { type, path: entry.path };
        setSelectedCard(cardElement || findCardByPath(type, entry.path));
        if (type !== 'book') {
          currentBookSynopsis = '';
          setSummaryText(detailSummary, '');
          if (bookContentHeading) {
            bookContentHeading.textContent = 'Book content';
          }
        }
        if (type === 'book') {
          updateNowPlayingPlacement();
          const bookTitle = displayBookTitle(entry.title || '');
          detailSubheading.textContent = bookTitle || entry.path.split('/').pop();
          setSummaryText(detailSummary, entry.summary || '');
        } else {
          detailSubheading.textContent = entry.title || entry.path.split('/').pop();
        }
        showDetailView();

        if (type === 'book') {
          showWorkspace('book');
          bookSelect.value = entry.path;
          const statusFlags = [];
          if (entry.has_text) statusFlags.push('Text');
          if (entry.has_audio) statusFlags.push('Audio');
          if (entry.has_video) statusFlags.push('Video');
          if (entry.has_compilation) statusFlags.push('Compiled');
          const statusLabel = statusFlags.length ? statusFlags.join(' • ') : 'No media yet';
          bookWorkspaceState.textContent = statusLabel;
          const bookTitle = displayBookTitle(entry.title || '');
          const resolvedBookTitle = bookTitle || entry.path.split('/').pop();
          bookWorkspaceTitle.textContent = resolvedBookTitle;
          bookWorkspacePath.textContent = entry.path;
          bookWorkspacePages.textContent = formatPageCount(entry.page_count);
          setMediaSource(bookAudioBlock, bookAudio, entry.book_audio_url);
          setBookAudioMetadata(bookAudio, entry.path, resolvedBookTitle, entry.cover_url || '');
          setHiddenImageSource(bookCoverImage, entry.cover_url);
          setCoverHeader(bookWorkspaceCoverHeader, resolvedBookTitle, entry.cover_url);
          const bookContent = await loadBookContent(entry.path);
          if (bookContent) {
            setSummaryText(detailSummary, bookContent.summary || entry.summary || '');
            setBookSynopsis(bookContent.synopsis);
          } else {
            setBookSynopsis('');
          }
          const chapters = await loadChapters(entry.path);
          renderChapterShelf(entry.path, chapters);
          if (chapters.length) {
            currentChapter = { ...chapters[0], bookDir: entry.path };
            chapterSelect.value = String(chapters[0].index);
            setChapterSelection(chapters[0].index);
            await loadWorkspaceChapterContent(entry.path, chapterSelect.value);
          } else {
            setBookContent('No chapters found for this book.');
          }
          return;
        }

        showWorkspace('outline');
        if (type === 'outline') {
          outlineSelect.value = entry.path;
        }
        outlineWorkspaceState.textContent =
          type === 'completed-outline' ? 'Completed outline' : 'Active outline';
        outlineWorkspaceTitle.textContent = entry.title || entry.path.split('/').pop();
        outlineWorkspacePath.textContent = entry.path;
        const summaryLines = [
          `${entry.item_count || 0} sections`,
          entry.preview || 'No preview available.',
        ];
        outlineWorkspaceSummary.textContent = summaryLines.join(`\n`);
        const result = await loadOutlineContent(entry.path);
        setOutlineContent(result.content || '');
      };

      const loadChapters = async (bookDir) => {
        chapterSelect.disabled = true;
        openReader.disabled = true;
        setSelectOptions(chapterSelect, [], 'Select a chapter');
        readerPanel.classList.remove('active');
        if (!bookDir) {
          currentChapters = [];
          return [];
        }
        try {
          const rawChapters = await fetchChapters(bookDir);
          currentChapters = rawChapters;
          const chapters = rawChapters.map((chapter) => {
            const title = chapter.title || `Chapter ${chapter.index}`;
            return {
              value: String(chapter.index),
              label: `${chapter.index}. ${displayChapterTitle(title)}`,
            };
          });
          setSelectOptions(chapterSelect, chapters, 'Select a chapter');
          chapterSelect.disabled = !chapters.length;
          return rawChapters;
        } catch (error) {
          log(`Chapter list failed: ${error.message}`);
        }
        return [];
      };

      const closeReaderPanel = () => {
        readerPanel.classList.remove('active');
        readerBody.innerHTML = '';
        chapterAudio.removeAttribute('src');
        chapterVideo.removeAttribute('src');
        audioBlock.classList.add('hidden');
        videoBlock.classList.add('hidden');
      };

      const setMediaSource = (block, element, url) => {
        if (!url) {
          block.classList.add('hidden');
          element.removeAttribute('src');
          element.dataset.mediaUrl = '';
          return;
        }
        block.classList.remove('hidden');
        element.dataset.mediaUrl = url;
        if (element.tagName === 'AUDIO') {
          hydrateAudioSource(element, url);
          return;
        }
        element.src = url;
        element.load();
      };

      const setHiddenImageSource = (element, url) => {
        if (!element) return;
        if (!url) {
          element.removeAttribute('src');
          element.dataset.mediaUrl = '';
          return;
        }
        element.src = url;
        element.dataset.mediaUrl = url;
      };

      const setCoverHeader = (element, title, coverUrl) => {
        if (!element) return;
        const resolvedTitle = title || '';
        const coverBackground = coverUrl ? `url("${coverUrl}")` : gradientFor(resolvedTitle);
        const overlayBackground = coverUrl
          ? 'linear-gradient(180deg, rgba(8, 12, 20, 0.1) 0%, rgba(8, 12, 20, 0.78) 100%)'
          : 'linear-gradient(180deg, rgba(8, 12, 20, 0.05) 0%, rgba(8, 12, 20, 0.45) 100%)';
        element.style.setProperty('--card-cover', coverBackground);
        element.style.setProperty('--card-overlay', overlayBackground);
        element.style.setProperty('--card-text', '#f8f9fb');
        element.classList.toggle('has-image', Boolean(coverUrl));
      };

      const parseOptionalNumber = (value) => {
        if (value === null || value === undefined) return null;
        const trimmed = String(value).trim();
        if (!trimmed) return null;
        const parsed = Number(trimmed);
        return Number.isNaN(parsed) ? null : parsed;
      };

      const buildCoverSettings = (options = {}) => {
        const settings = {
          enabled: true,
          prompt: document.getElementById('coverPrompt').value || null,
          negative_prompt: document.getElementById('coverNegativePrompt').value || null,
          model_path: document.getElementById('coverModelPath').value || null,
          module_path: document.getElementById('coverModulePath').value || null,
          steps: parseOptionalNumber(document.getElementById('coverSteps').value),
          guidance_scale: parseOptionalNumber(
            document.getElementById('coverGuidanceScale').value,
          ),
          seed: parseOptionalNumber(document.getElementById('coverSeed').value),
          width: parseOptionalNumber(document.getElementById('coverWidth').value),
          height: parseOptionalNumber(document.getElementById('coverHeight').value),
          output_name: document.getElementById('coverOutputName').value || null,
          overwrite: document.getElementById('coverOverwrite').checked,
          command: document.getElementById('coverCommand').value || null,
        };
        if (options.forceOverwrite) {
          settings.overwrite = true;
        }
        return settings;
      };

      const getChapterCoverDir = () =>
        document.getElementById('chapterCoverDir').value || 'chapter_covers';

      const toggleCoverActions = (disabled) => {
        [
          document.getElementById('generateBookCover'),
          document.getElementById('generateChapterCovers'),
          bookWorkspaceCover,
          bookWorkspaceChapterCovers,
          chapterGenerateCover,
        ].forEach((button) => {
          if (button) {
            button.disabled = disabled;
          }
        });
      };

      const setCoverProgress = (active, label) => {
        if (!coverProgress) return;
        coverProgress.classList.toggle('hidden', !active);
        coverProgressLabel.textContent = label || 'Generating cover art';
        toggleCoverActions(active);
      };

      const buildBookCard = (book) => {
        const statusFlags = [];
        if (book.has_text) statusFlags.push('Text');
        if (book.has_audio) statusFlags.push('Audio');
        if (book.has_video) statusFlags.push('Video');
        if (book.has_compilation) statusFlags.push('Compiled');
        const status = book.has_compilation
          ? 'Compiled'
          : book.has_text
            ? 'Drafting'
            : 'No chapters';
        const summaryLine = book.summary || 'Summary coming soon.';
        const detail = `${summaryLine}\n${getGenreLine(book)}\n${formatPageCount(
          book.page_count,
        )}\n${book.chapter_count || 0} chapters\n${
          statusFlags.join(' • ') || 'No media yet'
        }`;
        const progress = (statusFlags.length / 4) * 100;
        const displayTitle = displayBookTitle(book.title);
        const card = createCard(
          book.title,
          status,
          detail,
          'Book',
          book.path.split('/').pop(),
          progress,
          book.cover_url || null,
          displayTitle,
        );
        card.classList.add('selectable');
        card.dataset.type = 'book';
        card.dataset.path = book.path;
        card.addEventListener('click', () => {
          bookSelect.value = book.path;
          loadChapters(book.path);
          selectEntry('book', book, card);
        });
        return card;
      };

      const renderCatalog = () => {
        const term = getSearchTerm();
        const outlines = filterEntries(catalogState.outlines, (outline) => [
          outline.title || '',
          outline.path || '',
        ]);
        const completed = filterEntries(catalogState.completedOutlines, (outline) => [
          outline.title || '',
          outline.path || '',
        ]);
        const books = filterEntries(catalogState.books, (book) => [
          displayBookTitle(book.title || ''),
          book.path || '',
          normalizeGenres(book.genres).join(' '),
        ]);

        const outlineShelf = document.getElementById('outlineShelf');
        const completedShelf = document.getElementById('completedOutlineShelf');
        const bookShelf = document.getElementById('bookShelf');

        outlineShelf.innerHTML = '';
        completedShelf.innerHTML = '';
        bookShelf.innerHTML = '';

        document.getElementById('outlineCount').textContent = `${outlines.length} outlines`;
        document.getElementById('completedOutlineCount').textContent = `${completed.length} outlines`;
        document.getElementById('bookCount').textContent = `${books.length} books`;

        const outlineEmptyMessage = term
          ? 'No outlines match this search.'
          : 'No outlines found in the outlines directory.';
        const completedEmptyMessage = term
          ? 'No completed outlines match this search.'
          : 'No completed outlines archived yet.';
        const bookEmptyMessage = term
          ? 'No books match this search.'
          : 'No books found in the books directory.';

        if (!outlines.length) {
          renderEmpty(outlineShelf, outlineEmptyMessage);
        } else {
          outlines.forEach((outline) => {
            const title = outline.title || outline.path.split('/').pop();
            const detail = `${outline.item_count || 0} sections`;
            const card = createCard(
              title,
              'Outline ready',
              detail,
              'Outline',
              'Next: Generate book',
              15,
            );
            card.classList.add('selectable');
            card.dataset.type = 'outline';
            card.dataset.path = outline.path;
            card.addEventListener('click', () => {
              outlineSelect.value = outline.path;
              selectEntry('outline', outline, card);
            });
            outlineShelf.appendChild(card);
          });
        }

        if (!completed.length) {
          renderEmpty(completedShelf, completedEmptyMessage);
        } else {
          completed.forEach((outline) => {
            const title = outline.title || outline.path.split('/').pop();
            const detail = `${outline.item_count || 0} sections`;
            const card = createCard(
              title,
              'Archived outline',
              detail,
              'Completed',
              'Stored in completed_outlines',
              100,
            );
            card.classList.add('selectable');
            card.dataset.type = 'completed-outline';
            card.dataset.path = outline.path;
            card.addEventListener('click', () => {
              selectEntry('completed-outline', outline, card);
            });
            completedShelf.appendChild(card);
          });
        }

        if (latestShelf) {
          latestShelf.innerHTML = '';
        }
        if (genreShelves) {
          genreShelves.innerHTML = '';
        }

        const viewAllLabel = showAllBooks ? 'Hide full library' : 'View all';
        [viewAllBooks, viewAllBooksSecondary].forEach((button) => {
          if (button) {
            button.textContent = viewAllLabel;
          }
        });
        if (allBooksSection) {
          allBooksSection.classList.toggle('is-hidden', !showAllBooks);
        }

        if (!books.length) {
          if (latestShelf) {
            renderEmpty(latestShelf, bookEmptyMessage);
          }
          if (genreShelves) {
            renderEmpty(genreShelves, bookEmptyMessage);
          }
          if (showAllBooks) {
            renderEmpty(bookShelf, bookEmptyMessage);
          }
        } else {
          const latestBooks = [...books]
            .sort((a, b) => getBookFolderTimestamp(b) - getBookFolderTimestamp(a))
            .slice(0, 10);
          if (latestShelf) {
            if (!latestBooks.length) {
              renderEmpty(latestShelf, bookEmptyMessage);
            } else {
              latestBooks.forEach((book) => {
                latestShelf.appendChild(buildBookCard(book));
              });
            }
          }

          if (genreShelves) {
            const groupedBooks = groupBooksByGenre(books);
            const genreKeys = sortGenreKeys(Array.from(groupedBooks.keys()));
            if (!genreKeys.length) {
              renderEmpty(genreShelves, bookEmptyMessage);
            } else {
              genreKeys.forEach((genre) => {
                const section = document.createElement('section');
                section.classList.add('shelf-section');
                const heading = document.createElement('h4');
                heading.classList.add('shelf-heading');
                heading.textContent = genre;
                const shelf = document.createElement('div');
                shelf.classList.add('scroll-shelf');
                section.appendChild(heading);
                section.appendChild(shelf);
                groupedBooks.get(genre).forEach((book) => {
                  shelf.appendChild(buildBookCard(book));
                });
                genreShelves.appendChild(section);
              });
            }
          }

          if (showAllBooks) {
            books.forEach((book) => {
              bookShelf.appendChild(buildBookCard(book));
            });
          }
        }

        if (currentSelection.type && currentSelection.path) {
          setSelectedCard(findCardByPath(currentSelection.type, currentSelection.path));
        }

        bindShelfWheelScroll();
      };

      const toggleViewAllBooks = () => {
        showAllBooks = !showAllBooks;
        renderCatalog();
        if (showAllBooks && allBooksSection) {
          allBooksSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      };

      const loadCatalog = async (options = {}) => {
        try {
          const { selectCurrent = true } = options;
          const refreshMode = options.refreshMode || 'full';
          const previousOutline = outlineSelect.value;
          const previousBook = bookSelect.value;
          const shouldFetchOutlines =
            refreshMode === 'full' || catalogState.outlines.length === 0;
          const shouldFetchCompleted =
            refreshMode === 'full' || catalogState.completedOutlines.length === 0;
          const shouldFetchBooks =
            refreshMode === 'full' ||
            refreshMode === 'books' ||
            catalogState.books.length === 0;
          const shouldFetchAuthors =
            refreshMode === 'full' || catalogState.authors.length === 0;
          const shouldFetchTones =
            refreshMode === 'full' || catalogState.tones.length === 0;
          const [
            outlineResponse,
            completedResponse,
            booksResponse,
            authorsResponse,
            tonesResponse,
          ] = await Promise.all([
            shouldFetchOutlines
              ? fetchJson('/api/outlines')
              : Promise.resolve({ outlines: catalogState.outlines }),
            shouldFetchCompleted
              ? fetchJson('/api/completed-outlines')
              : Promise.resolve({ outlines: catalogState.completedOutlines }),
            shouldFetchBooks
              ? fetchJson(`/api/books?${buildSummaryParams()}`)
              : Promise.resolve({ books: catalogState.books }),
            shouldFetchAuthors
              ? fetchJson('/api/authors')
              : Promise.resolve({ authors: catalogState.authors }),
            shouldFetchTones
              ? fetchJson('/api/tones')
              : Promise.resolve({ tones: catalogState.tones }),
          ]);

          const outlines = outlineResponse.outlines || [];
          const completed = completedResponse.outlines || [];
          const books = booksResponse.books || [];
          const authors = authorsResponse.authors || [];
          const tones = tonesResponse.tones || [];
          catalogState.outlines = outlines;
          catalogState.completedOutlines = completed;
          catalogState.books = books;
          catalogState.authors = authors;
          catalogState.tones = tones;

          renderCatalog();

          setSelectOptions(
            outlineSelect,
            outlines.map((outline) => ({
              value: outline.path,
              label: outlineLabel(outline),
            })),
            'Select an outline',
          );
          setSelectOptions(
            outlineWorkspaceAuthor,
            authors.map((author) => ({
              value: author,
              label: `${author} (authors/${author}.md)`,
            })),
            'Default author (PROMPT.md)',
          );
          setSelectOptions(
            outlineWorkspaceTone,
            tones.map((tone) => ({
              value: tone,
              label: tone,
            })),
            'Select a tone',
          );
          if (!outlineWorkspaceTone.value && tones.length) {
            outlineWorkspaceTone.value = tones.includes('instructive self help guide')
              ? 'instructive self help guide'
              : tones[0];
          }
          setSelectOptions(
            bookSelect,
            books.map((book) => ({
              value: book.path,
              label: bookLabel(book),
            })),
            'Select a book',
          );

          if (previousOutline) {
            outlineSelect.value = previousOutline;
          }
          if (previousBook) {
            bookSelect.value = previousBook;
          }

          if (bookSelect.value) {
            await loadChapters(bookSelect.value);
          } else {
            chapterSelect.disabled = true;
          }

          if (selectCurrent && currentSelection.type && currentSelection.path) {
            const activeEntry =
              catalogState.outlines.find((outline) => outline.path === currentSelection.path) ||
              catalogState.completedOutlines.find(
                (outline) => outline.path === currentSelection.path,
              ) ||
              catalogState.books.find((book) => book.path === currentSelection.path);
            if (activeEntry) {
              await selectEntry(currentSelection.type, activeEntry);
            }
          }

          log('Catalog loaded from disk.');
        } catch (error) {
          log(`Catalog load failed: ${error.message}`);
        }
      };

      const buildGenerateBookPayload = (outlinePath, overrides = {}) => {
        const defaultTone =
          document.getElementById('tone').value || 'instructive self help guide';
        const resolvedTone = overrides.tone ? overrides.tone : defaultTone;
        return {
          outline_path: outlinePath || 'OUTLINE.md',
          output_dir: document.getElementById('outputDir').value || 'output',
          base_url: document.getElementById('baseUrl').value || 'http://localhost:1234',
          model: document.getElementById('modelName').value || 'local-model',
          tone: resolvedTone,
          byline: document.getElementById('byline').value || 'Marissa Bard',
          author: overrides.author ? overrides.author : null,
        };
      };

      document.getElementById('generateBook').addEventListener('click', async () => {
        try {
          const payload = buildGenerateBookPayload(outlineSelect.value);
          const result = await postJson('/api/generate-book', payload);
          log(`Generated book with ${result.written_files.length} files.`);
        } catch (error) {
          log(`Generate failed: ${error.message}`);
        }
      });

      document.getElementById('expandBook').addEventListener('click', async () => {
        try {
          const payload = {
            expand_book: bookSelect.value,
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
            book_dir: bookSelect.value,
          };
          await postJson('/api/compile-book', payload);
          log('Compilation complete.');
        } catch (error) {
          log(`Compile failed: ${error.message}`);
        }
      });

      document.getElementById('generateAudio').addEventListener('click', async () => {
        try {
          if (!bookSelect.value) {
            log('Select a book before generating audio.');
            return;
          }
          const payload = {
            book_dir: bookSelect.value,
            tts_settings: {
              audio_dirname: document.getElementById('audioDir').value || 'audio',
              overwrite_audio: document.getElementById('audioOverwrite').checked,
              book_only: document.getElementById('audioBookOnly').checked,
            },
          };
          await postJson('/api/generate-audio', payload);
          await loadWorkspaceChapterContent(bookSelect.value, chapterSelect.value);
          log('Audio generation complete.');
        } catch (error) {
          log(`Audio failed: ${error.message}`);
        }
      });

      document.getElementById('generateVideo').addEventListener('click', async () => {
        try {
          const payload = {
            book_dir: bookSelect.value,
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

      document.getElementById('generateBookCover').addEventListener('click', async () => {
        try {
          if (!bookSelect.value) {
            log('Select a book before generating a cover.');
            return;
          }
          setCoverProgress(true, 'Generating book cover art...');
          const forceOverwrite = Boolean(bookCoverImage.dataset.mediaUrl);
          const payload = {
            book_dir: bookSelect.value,
            base_url: document.getElementById('baseUrl').value || 'http://localhost:1234',
            model: document.getElementById('modelName').value || 'local-model',
            cover_settings: buildCoverSettings({ forceOverwrite }),
          };
          await postJson('/api/generate-cover', payload);
          log('Book cover generation complete.');
          await loadCatalog({ refreshMode: 'books' });
        } catch (error) {
          log(`Cover generation failed: ${error.message}`);
        } finally {
          setCoverProgress(false);
        }
      });

      document.getElementById('generateChapterCovers').addEventListener('click', async () => {
        try {
          if (!bookSelect.value) {
            log('Select a book before generating chapter covers.');
            return;
          }
          setCoverProgress(true, 'Generating chapter cover art...');
          const forceOverwrite = currentChapters.some((chapter) => chapter.cover_url);
          const payload = {
            book_dir: bookSelect.value,
            chapter_cover_dir: getChapterCoverDir(),
            base_url: document.getElementById('baseUrl').value || 'http://localhost:1234',
            model: document.getElementById('modelName').value || 'local-model',
            cover_settings: buildCoverSettings({ forceOverwrite }),
          };
          await postJson('/api/generate-chapter-covers', payload);
          log('Chapter cover generation complete.');
          await loadCatalog({ refreshMode: 'books' });
        } catch (error) {
          log(`Chapter covers failed: ${error.message}`);
        } finally {
          setCoverProgress(false);
        }
      });

      bookSelect.addEventListener('change', async (event) => {
        const value = event.target.value;
        await loadChapters(value);
        openReader.disabled = true;
        if (value) {
          const book = catalogState.books.find((entry) => entry.path === value);
          if (book) {
            selectEntry('book', book);
          }
        }
      });

      outlineSelect.addEventListener('change', (event) => {
        const value = event.target.value;
        if (!value) return;
        const outline = catalogState.outlines.find((entry) => entry.path === value);
        if (outline) {
          selectEntry('outline', outline);
        }
      });

      chapterSelect.addEventListener('change', (event) => {
        openReader.disabled = !event.target.value;
        if (event.target.value) {
          const expandOnlyInput = document.getElementById('expandOnly');
          if (!expandOnlyInput.value || /^[0-9]+$/.test(expandOnlyInput.value)) {
            expandOnlyInput.value = event.target.value;
          }
          if (currentSelection.type === 'book' && currentSelection.path === bookSelect.value) {
            currentChapter = { index: Number(event.target.value), bookDir: bookSelect.value };
            setChapterSelection(event.target.value);
            loadWorkspaceChapterContent(currentSelection.path, event.target.value);
          }
        }
      });

      openReader.addEventListener('click', async () => {
        const bookDir = bookSelect.value;
        const chapter = chapterSelect.value;
        if (!bookDir || !chapter) return;
        try {
          const book = catalogState.books.find((entry) => entry.path === bookDir);
          if (book && (currentSelection.type !== 'book' || currentSelection.path !== bookDir)) {
            await selectEntry('book', book);
          } else {
            showDetailView();
            showWorkspace('book');
          }
          const audioDir = document.getElementById('audioDir').value || 'audio';
          const videoDir = document.getElementById('videoDir').value || 'video';
          const result = await fetchJson(
            `/api/chapter-content?book_dir=${encodeURIComponent(
              bookDir,
            )}&chapter=${encodeURIComponent(chapter)}&audio_dirname=${encodeURIComponent(
              audioDir,
            )}&video_dirname=${encodeURIComponent(videoDir)}`,
          );
          currentChapter = { index: Number(chapter), bookDir };
          setChapterSelection(chapter);
          const readerTitleValue = result.title || 'Chapter preview';
          readerTitle.textContent = displayChapterTitle(readerTitleValue);
          readerBody.innerHTML = renderMarkdown(result.content || '');
          setMediaSource(audioBlock, chapterAudio, result.audio_url);
          setMediaSource(videoBlock, chapterVideo, result.video_url);
          const { coverUrl: bookCoverUrl, title: bookTitle } = getBookMetadata(bookDir);
          setChapterAudioMetadata(chapterAudio, {
            bookDir,
            chapterIndex: chapter,
            bookTitle,
            coverUrl: result.cover_url || '',
            bookCoverUrl,
            mediaTitle: displayChapterTitle(readerTitleValue),
          });
          readerPanel.classList.add('active');
        } catch (error) {
          log(`Reader failed: ${error.message}`);
        }
      });

      closeReader.addEventListener('click', () => {
        closeReaderPanel();
      });

      detailBack.addEventListener('click', async () => {
        updateNowPlayingPlacement();
        await loadCatalog({ selectCurrent: false, refreshMode: 'books' });
        showHomeView();
      });

      if (outlineBack) {
        outlineBack.addEventListener('click', async () => {
          updateNowPlayingPlacement();
          await loadCatalog({ selectCurrent: false, refreshMode: 'books' });
          showHomeView();
        });
      }

      if (viewOutlines) {
        viewOutlines.addEventListener('click', () => {
          showOutlineView();
        });
      }

      if (toggleUtilities && homeUtilities) {
        const setUtilitiesState = (isCollapsed) => {
          homeUtilities.classList.toggle('is-collapsed', isCollapsed);
          toggleUtilities.setAttribute('aria-expanded', String(!isCollapsed));
          toggleUtilities.textContent = isCollapsed ? 'Show tools' : 'Hide tools';
        };
        setUtilitiesState(true);
        toggleUtilities.addEventListener('click', () => {
          const isCollapsed = homeUtilities.classList.contains('is-collapsed');
          setUtilitiesState(!isCollapsed);
        });
      }

      chapterBack.addEventListener('click', async () => {
        restoreChapterAudioToCard();
        updateNowPlayingPlacement();
        await loadCatalog({ refreshMode: 'books' });
        if (detailView.classList.contains('is-hidden')) {
          showDetailView();
        }
      });

      if (searchInput) {
        searchInput.addEventListener('input', () => {
          renderCatalog();
        });
      }

      if (viewAllBooks) {
        viewAllBooks.addEventListener('click', toggleViewAllBooks);
      }

      if (viewAllBooksSecondary) {
        viewAllBooksSecondary.addEventListener('click', toggleViewAllBooks);
      }

      if (nowPlayingClose) {
        nowPlayingClose.addEventListener('click', (event) => {
          event.stopPropagation();
          stopActivePlayback();
        });
      }

      if (nowPlaying) {
        nowPlaying.addEventListener('click', async (event) => {
          if (shouldIgnoreNowPlayingClick(event)) {
            return;
          }
          if (!activePlayback) return;
          if (activePlayback.playbackType === 'book' && activePlayback.bookDir) {
            await navigateToBookDetail(activePlayback.bookDir);
            return;
          }
          if (
            activePlayback.playbackType === 'chapter' &&
            activePlayback.bookDir &&
            activePlayback.chapterIndex !== null &&
            activePlayback.chapterIndex !== undefined
          ) {
            await navigateToChapterDetail(
              activePlayback.bookDir,
              activePlayback.chapterIndex,
            );
          }
        });
      }

      if (nowPlayingAutoplay) {
        autoplayEnabled = nowPlayingAutoplay.checked;
        nowPlayingAutoplay.addEventListener('change', (event) => {
          autoplayEnabled = event.target.checked;
        });
      }

      chapterExpand.addEventListener('click', () => {
        if (!currentChapter) {
          log('Select a chapter before expanding.');
          return;
        }
        document.getElementById('expandOnly').value = String(currentChapter.index);
        document.getElementById('expandBook').click();
      });

      chapterGenerateAudio.addEventListener('click', () => {
        if (!currentChapter) {
          log('Select a chapter before generating audio.');
          return;
        }
        if (currentChapter.bookDir) {
          bookSelect.value = currentChapter.bookDir;
        }
        document.getElementById('generateAudio').click();
      });

      chapterGenerateVideo.addEventListener('click', () => {
        if (!currentChapter) {
          log('Select a chapter before generating video.');
          return;
        }
        if (currentChapter.bookDir) {
          bookSelect.value = currentChapter.bookDir;
        }
        document.getElementById('generateVideo').click();
      });

      chapterGenerateCover.addEventListener('click', async () => {
        if (!currentChapter) {
          log('Select a chapter before generating a cover.');
          return;
        }
        try {
          setCoverProgress(true, 'Generating chapter cover art...');
          const forceOverwrite = Boolean(
            chapterCoverImage.dataset.mediaUrl || currentChapter.cover_url,
          );
          const payload = {
            book_dir: currentChapter.bookDir,
            chapter: currentChapter.index,
            chapter_cover_dir: getChapterCoverDir(),
            base_url: document.getElementById('baseUrl').value || 'http://localhost:1234',
            model: document.getElementById('modelName').value || 'local-model',
            cover_settings: buildCoverSettings({ forceOverwrite }),
          };
          await postJson('/api/generate-chapter-covers', payload);
          log('Chapter cover generation complete.');
          if (currentChapter.bookDir) {
            const chapters = await loadChapters(currentChapter.bookDir);
            const updated = chapters.find(
              (entry) => entry.index === currentChapter.index,
            );
            if (updated) {
              currentChapter = { ...updated, bookDir: currentChapter.bookDir };
              const updatedTitle = displayChapterTitle(
                updated.title || `Chapter ${updated.index}`,
              );
              chapterReaderTitle.textContent = updatedTitle;
              setHiddenImageSource(chapterCoverImage, updated.cover_url);
              setCoverHeader(chapterReaderCover, updatedTitle, updated.cover_url);
            }
          }
        } catch (error) {
          log(`Chapter cover failed: ${error.message}`);
        } finally {
          setCoverProgress(false);
        }
      });

      outlineEditor.addEventListener('input', () => {
        updateOutlinePreview(outlineEditor.value);
      });

      outlineReload.addEventListener('click', async () => {
        const outlinePath = outlineWorkspacePath.textContent;
        if (!outlinePath) {
          log('Select an outline before reloading.');
          return;
        }
        try {
          const result = await loadOutlineContent(outlinePath);
          setOutlineContent(result.content || '');
          log('Outline reloaded.');
        } catch (error) {
          log(`Outline reload failed: ${error.message}`);
        }
      });

      outlineSave.addEventListener('click', async () => {
        const outlinePath = outlineWorkspacePath.textContent;
        if (!outlinePath) {
          log('Select an outline before saving.');
          return;
        }
        try {
          const payload = {
            outline_path: outlinePath,
            content: outlineEditor.value,
            outlines_dir: resolveOutlineDir(outlinePath),
          };
          await postJson('/api/save-outline', payload);
          log('Outline saved.');
          await loadCatalog();
          const outline =
            catalogState.outlines.find((entry) => entry.path === outlinePath) ||
            catalogState.completedOutlines.find((entry) => entry.path === outlinePath);
          if (outline) {
            await selectEntry(
              catalogState.completedOutlines.some((entry) => entry.path === outlinePath)
                ? 'completed-outline'
                : 'outline',
              outline,
            );
          }
        } catch (error) {
          log(`Outline save failed: ${error.message}`);
        }
      });

      outlineWorkspaceGenerate.addEventListener('click', async () => {
        const outlinePath = resolveOutlinePath();
        if (!outlinePath) {
          log('Select an outline before generating a book.');
          return;
        }
        try {
          const payload = buildGenerateBookPayload(outlinePath, {
            tone: outlineWorkspaceTone.value,
            author: outlineWorkspaceAuthor.value,
          });
          const result = await postJson('/api/generate-book', payload);
          log(`Generated book with ${result.written_files.length} files.`);
        } catch (error) {
          log(`Generate failed: ${error.message}`);
        }
      });

      generateOutline.addEventListener('click', async () => {
        const prompt = outlinePrompt.value.trim();
        if (!prompt) {
          log('Outline prompt is required.');
          return;
        }
        try {
          const payload = {
            prompt,
            revision_prompts: parseRevisionPrompts(outlineRevisions.value || ''),
            outline_name: outlineName.value || null,
            outlines_dir: outlineDir.value || 'outlines',
            model: outlineModel.value || document.getElementById('modelName').value || 'local-model',
            base_url:
              outlineBaseUrl.value ||
              document.getElementById('baseUrl').value ||
              'http://localhost:1234',
          };
          const result = await postJson('/api/generate-outline', payload);
          log('Outline generated.');
          outlinePrompt.value = '';
          outlineRevisions.value = '';
          await loadCatalog();
          const outline =
            catalogState.outlines.find((entry) => entry.path === result.outline_path) ||
            catalogState.completedOutlines.find(
              (entry) => entry.path === result.outline_path,
            );
          if (outline) {
            await selectEntry('outline', outline);
          } else {
            outlineWorkspacePath.textContent = result.outline_path;
            setOutlineContent(result.content || '');
          }
          showDetailView();
          showWorkspace('outline');
        } catch (error) {
          log(`Outline generation failed: ${error.message}`);
        }
      });

      bookWorkspaceReader.addEventListener('click', () => {
        openReader.click();
      });

      bookWorkspaceExpand.addEventListener('click', () => {
        document.getElementById('expandBook').click();
      });

      bookWorkspaceCompile.addEventListener('click', () => {
        document.getElementById('compileBook').click();
      });

      bookWorkspaceAudio.addEventListener('click', () => {
        document.getElementById('generateAudio').click();
      });

      bookWorkspaceVideo.addEventListener('click', () => {
        document.getElementById('generateVideo').click();
      });

      bookWorkspaceCover.addEventListener('click', () => {
        document.getElementById('generateBookCover').click();
      });

      bookWorkspaceChapterCovers.addEventListener('click', () => {
        document.getElementById('generateChapterCovers').click();
      });

      loadCatalog();
      trackPlayback(bookAudio, () => bookWorkspaceTitle.textContent || 'Book audio');
      trackPlayback(chapterAudio, () => readerTitle.textContent || 'Chapter audio');
      trackPlayback(chapterViewAudio, () => chapterReaderTitle.textContent || 'Chapter audio');
      updateNowPlayingPlacement();
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

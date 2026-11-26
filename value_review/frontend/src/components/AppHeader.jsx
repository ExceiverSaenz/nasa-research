import React from 'react';

export function GearIcon() {
  return (
    <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </svg>
  );
}

// The top bar of the list screens (canvas): TD back to Papers, the sections, the gear for Settings.
// Only the sections that exist are shown; Extraction and Normalize join when they are built.
export default function AppHeader({ section, onSettings, children }) {
  return (
    <header className="app-header">
      <a className="brand" href="#/" aria-label="Papers" title="Papers">TD</a>
      <span className="app-name">Tensile Data Review</span>
      <nav className="app-nav" aria-label="Sections">
        <a href="#/schemas" aria-current={section === 'schema' ? 'page' : undefined}>Schema</a>
        <a href="#/" aria-current={section === 'review' ? 'page' : undefined}>Review</a>
      </nav>
      <div className="head-title">{children}</div>
      {onSettings && (
        <button type="button" className="icon-btn gear-btn" aria-label="Settings" title="Settings" onClick={onSettings}>
          <GearIcon />
        </button>
      )}
    </header>
  );
}

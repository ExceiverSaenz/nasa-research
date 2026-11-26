import React from 'react';
import useProfile from './useProfile.js';

export function GearIcon() {
  return (
    <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

export const SECTIONS = [
  ['schema', 'Schema', '#/schemas'],
  ['extraction', 'Extraction', '#/extraction'],
  ['review', 'Review', '#/review'],
  ['normalize', 'Normalize', '#/normalize'],
];

// The navy top bar of every section page (canvas boards): TD, the tool's name, the four sections, the gear (the
// Settings page) and the profile's initials and display name.
export default function AppHeader({ section, onNavigate }) {
  const profile = useProfile();
  const go = (e, hash) => { if (onNavigate) { e.preventDefault(); onNavigate(hash); } };
  return (
    <header className="topbar">
      <a className="td" href="#/review" aria-label="Back to papers" onClick={(e) => go(e, '#/review')}>TD</a>
      <div className="topbar-name">TENSILE DATA REVIEW</div>
      <nav aria-label="Sections" className="topbar-nav">
        {SECTIONS.map(([key, label, hash]) => (
          <a key={key} href={hash} className="tab" aria-current={section === key ? 'page' : undefined} onClick={(e) => go(e, hash)}>{label}</a>
        ))}
      </nav>
      <div style={{ flex: '1 1 0' }} />
      <a href="#/settings" aria-label="Settings" title="Settings" className="tab gear" aria-current={section === 'settings' ? 'page' : undefined}
        onClick={(e) => go(e, '#/settings')}><GearIcon /></a>
      <div className="who" title={`Signed in as ${profile.display}`}>
        <span className="avatar" aria-hidden="true">{profile.initials}</span>
        <span>{profile.display}</span>
      </div>
    </header>
  );
}

// Marks a page, or part of one, whose data is canvas sample data until the backend exists (ADR-013).
export function SampleBadge({ what = 'Sample data · backend pending' }) {
  return <span className="sample-badge" title="This part of the tool has no backend yet. What you see and do here is not saved.">{what}</span>;
}

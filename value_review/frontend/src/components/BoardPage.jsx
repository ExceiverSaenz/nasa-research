import React, { useEffect, useState } from 'react';
import AppHeader, { SampleBadge } from './AppHeader.jsx';
import { useSettings } from './useProfile.js';
import DcBoard from '../dc/DcBoard.jsx';
import { profileOf } from '../lib/prefs.js';
import extractionHtml from '../boards/extraction.html?raw';
import extractionCss from '../boards/extraction.css?raw';
import Extraction from '../boards/extraction.logic.js';
import rulesHtml from '../boards/normalize-rules.html?raw';
import rulesCss from '../boards/normalize-rules.css?raw';
import Rules from '../boards/normalize-rules.logic.js';
import validateHtml from '../boards/normalize-validate.html?raw';
import validateCss from '../boards/normalize-validate.css?raw';
import Validate from '../boards/normalize-validate.logic.js';
import resultsHtml from '../boards/normalize-results.html?raw';
import resultsCss from '../boards/normalize-results.css?raw';
import Results from '../boards/normalize-results.logic.js';

// Links between boards (file names on the canvas) and the app's routes.
const LINKS = {
  'Main.dc.html': '#/review', 'Review.dc.html': '#/review', 'Papers-Tablet.dc.html': '#/review', 'Review-Tablet.dc.html': '#/review',
  'Schema.dc.html': '#/schemas', 'Extraction.dc.html': '#/extraction', 'Settings.dc.html': '#/settings',
  'Normalize-Rules.dc.html': '#/normalize', 'Normalize-Validate.dc.html': '#/normalize/sample/validate', 'Normalize-Results.dc.html': '#/normalize/sample/results',
};
const BOARDS = {
  extraction: { html: extractionHtml, css: extractionCss, Logic: Extraction, title: 'Extraction' },
  rules: { html: rulesHtml, css: rulesCss, Logic: Rules, title: 'Normalize' },
  validate: { html: validateHtml, css: validateCss, Logic: Validate, title: 'Validate · Normalize' },
  results: { html: resultsHtml, css: resultsCss, Logic: Results, title: 'Results · Normalize' },
};

// The boards read the canvas's own settings key (display name, autosave, CSV); it mirrors the app's settings.
function mirrorSettings(display, s) {
  const p = s || { autosave_seconds: 60, csv_delimiter: ',', csv_encoding: 'utf8bom' };
  try {
    window.localStorage.setItem('tdr-settings', JSON.stringify({ display, autosave: String(p.autosave_seconds), delim: p.csv_delimiter, enc: p.csv_encoding }));
  } catch (e) { /* private window: the boards use their defaults */ }
}

// Extraction and Normalize (canvas boards on sample data, ADR-013): the app's top bar, a "Sample data" label, and the
// board itself. The board starts again from its sample data each time the page opens.
export default function BoardPage({ board, section }) {
  const b = BOARDS[board];
  const settings = useSettings();
  const profile = profileOf(settings);
  const [round, setRound] = useState(0);   // the section's own tab starts the board again, at its list (canvas)
  mirrorSettings(profile.display, settings);
  const navigate = (hash) => {
    if (window.location.hash === hash || (hash === '#/normalize' && board === 'rules')) {
      try { window.localStorage.removeItem('tdr-norm'); } catch (e) { /* ok */ }
      setRound((r) => r + 1);
    } else window.location.hash = hash;
  };
  useEffect(() => { document.title = `${b.title} · Tensile Data Review`; }, [b.title]);
  return (
    <div>
      <AppHeader section={section} onNavigate={navigate} />
      <div className="board-note"><SampleBadge /><span>This section has no backend yet: what you do here is not saved.</span></div>
      <DcBoard key={`${board}-${round}-${settings ? 'set' : 'default'}`} template={b.html} css={b.css} Logic={b.Logic} links={LINKS} />
    </div>
  );
}

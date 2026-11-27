import React, { useEffect, useState } from 'react';
import AppHeader, { SampleBadge } from './AppHeader.jsx';
import { useSettings } from './useProfile.js';
import DcBoard from '../dc/DcBoard.jsx';
import { profileOf } from '../lib/prefs.js';
import extractionHtml from '../extraction/extraction.html?raw';
import extractionCss from '../extraction/extraction.css?raw';
import Extraction from '../extraction/ExtractionLogic.js';
import rulesHtml from '../boards/normalize-rules.html?raw';
import rulesCss from '../boards/normalize-rules.css?raw';
import Rules from '../normalize/RulesLogic.js';
import validateHtml from '../boards/normalize-validate.html?raw';
import validateCss from '../boards/normalize-validate.css?raw';
import Validate from '../normalize/ValidateLogic.js';
import resultsHtml from '../boards/normalize-results.html?raw';
import resultsCss from '../boards/normalize-results.css?raw';
import Results from '../normalize/ResultsLogic.js';

// Links between boards (file names on the canvas) and the app's routes; Normalize's steps link to the open extraction.
const linksFor = (run) => ({
  'Main.dc.html': run ? `#/review/${run}` : '#/review', 'Review.dc.html': '#/review', 'Papers-Tablet.dc.html': '#/review', 'Review-Tablet.dc.html': '#/review',
  'Schema.dc.html': '#/schemas', 'Extraction.dc.html': '#/extraction', 'Settings.dc.html': '#/settings',
  'Normalize-Rules.dc.html': run ? `#/normalize/${run}` : '#/normalize',
  'Normalize-Validate.dc.html': run ? `#/normalize/${run}/validate` : '#/normalize',
  'Normalize-Results.dc.html': run ? `#/normalize/${run}/results` : '#/normalize',
});
const BOARDS = {
  extraction: { html: extractionHtml, css: extractionCss, Logic: Extraction, title: 'Extraction', real: true },   // 70-extraction-specification.md
  rules: { html: rulesHtml, css: rulesCss, Logic: Rules, title: 'Normalize', real: true },   // 90-normalize-specification.md
  validate: { html: validateHtml, css: validateCss, Logic: Validate, title: 'Validate · Normalize', real: true },
  results: { html: resultsHtml, css: resultsCss, Logic: Results, title: 'Results · Normalize', real: true },
};

// The boards read the canvas's own settings key (display name, autosave, CSV); it mirrors the app's settings.
function mirrorSettings(display, s) {
  const p = s || { autosave_seconds: 60, csv_delimiter: ',', csv_encoding: 'utf8bom' };
  try {
    window.localStorage.setItem('tdr-settings', JSON.stringify({ display, autosave: String(p.autosave_seconds), delim: p.csv_delimiter, enc: p.csv_encoding }));
  } catch (e) { /* private window: the boards use their defaults */ }
}

// Extraction (70-extraction-specification.md) and Normalize (90-normalize-specification.md), both on the service: the
// app's top bar and the canvas board, run by DcBoard with logic that reads and writes through the API.
export default function BoardPage({ board, section, run = null }) {
  const b = BOARDS[board];
  const settings = useSettings();
  const profile = profileOf(settings);
  const [round, setRound] = useState(0);   // the section's own tab starts the board again, at its list (canvas)
  mirrorSettings(profile.display, settings);
  const navigate = (hash) => {
    if (window.location.hash === hash || (hash === '#/normalize' && board === 'rules' && !run)) {
      try { window.localStorage.removeItem('tdr-norm'); } catch (e) { /* ok */ }
      setRound((r) => r + 1);
    } else window.location.hash = hash;
  };
  useEffect(() => { document.title = `${b.title} · Tensile Data Review`; }, [b.title]);
  return (
    <div>
      <AppHeader section={section} onNavigate={navigate} />
      {!b.real && <div className="board-note"><SampleBadge /><span>This section has no backend yet: what you do here is not saved.</span></div>}
      <DcBoard key={b.real ? `${board}-${run}-${round}` : `${board}-${round}-${settings ? 'set' : 'default'}`} template={b.html} css={b.css} Logic={b.Logic}
        links={linksFor(run)} props={{ run }} />
    </div>
  );
}

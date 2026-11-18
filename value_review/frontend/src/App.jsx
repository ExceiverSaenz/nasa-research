import React, { useEffect, useRef, useState } from 'react';
import Papers from './components/Papers.jsx';
import Review from './components/Review.jsx';
import { setSource } from './lib/api.js';

// Hash routes: #/ (papers of the active folder pair), #/source/<pair>/paper/<id> (review of a paper of
// that pair) and #/paper/<id> (a paper of the active pair, links made before there were several pairs).
function parseRoute() {
  const m = window.location.hash.match(/^#\/(?:source\/([a-z0-9-]{1,40})\/)?paper\/(\d{1,4})$/);
  return m ? { view: 'review', source: m[1] || null, paper: m[2] } : { view: 'papers' };
}

export default function App() {
  const [route, setRoute] = useState(parseRoute);
  // The review screen registers {dirty(), ask(targetHash)} here so that leaving with unsaved
  // changes (a link, the Back button) asks first (AC-10).
  const guard = useRef(null);
  const skip = useRef(false);

  useEffect(() => {
    const onHash = (e) => {
      if (skip.current) { skip.current = false; return; }
      const next = parseRoute();
      const current = guard.current;
      if (current && current.dirty() && !(next.view === 'review' && next.paper === current.paper && next.source === current.source)) {
        const target = window.location.hash || '#/';
        skip.current = true;
        window.location.replace(e.oldURL);   // stay; the dialog decides
        current.ask(target);
        return;
      }
      setRoute(next);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  if (route.view === 'review') {
    setSource(route.source);   // the review's requests go to its pair; Papers sets the active one itself
    return <Review key={`${route.source}/${route.paper}`} paperId={route.paper} sourceId={route.source} guard={guard} />;
  }
  return <Papers />;
}

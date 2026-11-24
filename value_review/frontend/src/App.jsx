import React, { useEffect, useRef, useState } from 'react';
import Papers from './components/Papers.jsx';
import Review from './components/Review.jsx';
import SchemaEditor from './components/SchemaEditor.jsx';
import SchemaList from './components/SchemaList.jsx';
import { setSource } from './lib/api.js';
import { parseRoute as parseHash, stepBack } from './lib/routes.js';

// Hash routes (lib/routes.js): #/ Papers, #/source/<pair>/paper/<id> a review, #/schemas and #/schemas/<id> the Schema section.
const parseRoute = () => parseHash(window.location.hash);

// Each history entry the app reaches gets an increasing stamp in history.state, so a navigation that must be undone
// (unsaved changes, "Stay") can be reversed by stepping, instead of rewriting an entry of the history.
let lastStamp = 0;
const stampOf = () => (window.history.state && typeof window.history.state.vr === 'number' ? window.history.state.vr : null);
function stamp() {
  const known = stampOf();
  if (known !== null) { lastStamp = Math.max(lastStamp, known); return known; }
  lastStamp = Math.max(Date.now(), lastStamp + 1);
  window.history.replaceState({ ...(window.history.state || {}), vr: lastStamp }, '');
  return lastStamp;
}

export default function App() {
  const [route, setRoute] = useState(parseRoute);
  // The review screen registers {dirty(), ask(targetHash)} here so that leaving with unsaved
  // changes (a link, the Back button) asks first (AC-10).
  const guard = useRef(null);
  const skip = useRef(false);
  const here = useRef(null);   // stamp of the entry the app is showing

  useEffect(() => {
    here.current = stamp();
    const onHash = () => {
      if (skip.current) { skip.current = false; return; }
      const next = parseRoute();
      const current = guard.current;
      if (current && current.dirty() && !(next.view === 'review' && next.paper === current.paper && next.source === current.source)) {
        const target = window.location.hash || '#/';
        skip.current = true;
        window.history.go(stepBack(stampOf(), here.current));   // stay where we were; the dialog decides
        current.ask(target);
        return;
      }
      here.current = stamp();
      setRoute(next);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  if (route.view === 'review') {
    setSource(route.source);   // the review's requests go to its pair; Papers sets the active one itself
    return <Review key={`${route.source}/${route.paper}`} paperId={route.paper} sourceId={route.source} guard={guard} />;
  }
  if (route.view === 'schemas') return <SchemaList />;
  if (route.view === 'schema') return <SchemaEditor key={route.schema} schemaId={route.schema} />;
  return <Papers />;
}

import React, { useEffect, useRef, useState } from 'react';
import Papers from './components/Papers.jsx';
import Review from './components/Review.jsx';
import ReviewRuns from './components/ReviewRuns.jsx';
import SchemaEditor from './components/SchemaEditor.jsx';
import SchemaList from './components/SchemaList.jsx';
import BoardPage from './components/BoardPage.jsx';
import SettingsPage from './components/SettingsPage.jsx';
import { api, setSource } from './lib/api.js';
import { parseRoute as parseHash, reviewHash, stepBack } from './lib/routes.js';

// Hash routes (lib/routes.js): the four canvas sections and Settings.
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
  // A screen with unsaved work registers {dirty(), ask(targetHash), paper?, source?} here so that leaving
  // (a link, the Back button) asks first (AC-10, AC-F13).
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
        const target = window.location.hash || '#/review';
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

  // Links made before the canvas routes (#/source/<pair>/paper/<id>, #/paper/<id>) open the same paper (AC-F15).
  useEffect(() => {
    if (route.view !== 'review' || !route.legacy) return;
    const go = (pair) => window.location.replace(reviewHash(pair, route.paper));
    if (route.source) go(route.source);
    else api.settings().then((s) => go(s.active_source)).catch(() => setRoute({ ...route, legacy: false }));
  }, [route]);

  if (route.view === 'review') {
    if (route.legacy && route.source !== null) return null;
    setSource(route.source);   // the review's requests go to its pair
    return <Review key={`${route.source}/${route.paper}`} paperId={route.paper} sourceId={route.source} guard={guard} />;
  }
  if (route.view === 'papers') return <Papers key={route.source} pair={route.source} />;
  if (route.view === 'schemas') return <SchemaList />;
  if (route.view === 'schema') return <SchemaEditor key={route.schema} schemaId={route.schema} />;
  if (route.view === 'settings') return <SettingsPage tab={route.tab} />;
  if (route.view === 'extraction') return <BoardPage key="extraction" board="extraction" section="extraction" />;
  if (route.view === 'normalize') {
    const step = route.step === 'validate' || route.step === 'results' ? route.step : 'rules';
    return <BoardPage key={step} board={step} section="normalize" />;
  }
  return <ReviewRuns />;
}

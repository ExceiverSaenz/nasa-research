import React, { useEffect, useRef, useState } from 'react';
import Papers from './components/Papers.jsx';
import Review from './components/Review.jsx';
import { setSource } from './lib/api.js';
import { parseRoute as parseHash } from './lib/routes.js';

// Hash routes (lib/routes.js): #/ Papers, #/source/<pair>/paper/<id> a review.
const parseRoute = () => parseHash(window.location.hash);

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

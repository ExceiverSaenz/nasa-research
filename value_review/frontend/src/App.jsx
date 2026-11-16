import React, { useEffect, useRef, useState } from 'react';
import Papers from './components/Papers.jsx';
import Review from './components/Review.jsx';

// Hash routes: #/ (papers) and #/paper/<id> (review).
function parseRoute() {
  const m = window.location.hash.match(/^#\/paper\/(\d{1,4})$/);
  return m ? { view: 'review', paper: m[1] } : { view: 'papers' };
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
      if (current && current.dirty() && !(next.view === 'review' && next.paper === current.paper)) {
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

  return route.view === 'review' ? <Review key={route.paper} paperId={route.paper} guard={guard} /> : <Papers />;
}

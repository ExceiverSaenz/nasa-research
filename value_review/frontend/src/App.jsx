import React, { useEffect, useState } from 'react';
import Papers from './components/Papers.jsx';
import Review from './components/Review.jsx';

// Hash routes: #/ (papers) and #/paper/<id> (review).
function parseRoute() {
  const m = window.location.hash.match(/^#\/paper\/(\d{1,4})$/);
  return m ? { view: 'review', paper: m[1] } : { view: 'papers' };
}

export default function App() {
  const [route, setRoute] = useState(parseRoute);
  useEffect(() => {
    const onHash = () => setRoute(parseRoute());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return route.view === 'review' ? <Review key={route.paper} paperId={route.paper} /> : <Papers />;
}

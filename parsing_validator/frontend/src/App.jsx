import { useEffect, useState } from 'react';
import { api } from './lib/api.js';
import { parseRoute } from './lib/route.js';
import Collection from './components/Collection.jsx';
import Review from './components/Review.jsx';

export default function App() {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  const [settings, setSettings] = useState(null);
  const [problem, setProblem] = useState(null);

  useEffect(() => {
    const onHash = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    api('/settings').then(({ data }) => setSettings(data)).catch((error) => setProblem(error.message));
  }, []);

  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/" aria-label="Paper collection">
          <span className="brand-mark" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
              <rect x="2" y="2" width="12" height="12" rx="2" strokeDasharray="3 2" />
              <path d="M5 8.5l2 2 4-5" />
            </svg>
          </span>
          <span>Parsing Validator</span>
        </a>
        <span className="topbar-note">code_results / tensile_papers</span>
      </header>
      {problem && <p className="banner error" role="alert">The service answered with an error: {problem}</p>}
      {route.name === 'review' && settings ? (
        <Review key={route.paper} paper={route.paper} page={route.page} settings={settings} />
      ) : (
        route.name === 'collection' && <Collection />
      )}
      {route.name === 'review' && !settings && !problem && <p className="banner">Loading settings…</p>}
    </>
  );
}

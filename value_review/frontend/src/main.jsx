import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
// IBM Plex Sans and Mono, served from the app itself (ADR-016): latin, the weights the canvas uses.
import '@fontsource/ibm-plex-sans/latin-400.css';
import '@fontsource/ibm-plex-sans/latin-500.css';
import '@fontsource/ibm-plex-sans/latin-600.css';
import '@fontsource/ibm-plex-sans/latin-700.css';
import '@fontsource/ibm-plex-mono/latin-400.css';
import '@fontsource/ibm-plex-mono/latin-500.css';
import './styles.css';
import './canvas.css';
import { installModalFocus } from './lib/modalFocus.js';

installModalFocus();   // focus into, within and back out of every modal dialog

createRoot(document.getElementById('root')).render(<App />);

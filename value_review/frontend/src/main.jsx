import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';
import { installModalFocus } from './lib/modalFocus.js';

installModalFocus();   // focus into, within and back out of every modal dialog

createRoot(document.getElementById('root')).render(<App />);

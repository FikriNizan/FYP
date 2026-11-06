import React from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import App from './App.jsx';
import './workspace.css';

// Preserve links made by the earlier HTML starter.
if (location.hash && !location.hash.startsWith('#/')) location.replace('#/' + location.hash.slice(1));
createRoot(document.getElementById('root')).render(<React.StrictMode><HashRouter><App /></HashRouter></React.StrictMode>);

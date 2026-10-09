/**
 * @file index.tsx
 * @description React 18 entry point for the WASAC Smart Billing Platform.
 * Uses createRoot API for concurrent features.
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

const container = document.getElementById('root');
if (!container) throw new Error('index.html has no #root element');
const root = createRoot(container);

root.render(
  <StrictMode>
    <App />
  </StrictMode>
);

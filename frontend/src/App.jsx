/**
 * @file App.jsx
 * @description Root application component for the WASAC Smart Billing Platform.
 * Imports global design-system styles and renders the application router.
 */

import React from 'react';
import './styles/global.css';
import './styles/typography.css';
import AppRouter from './router/index';


function App() {
  return (
    <div className="app-root">
      <AppRouter />
    </div>
  );
}

export default App;

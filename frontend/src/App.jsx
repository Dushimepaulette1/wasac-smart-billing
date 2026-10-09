/**
 * @file App.jsx
 * @description Root application component for the WASAC Smart Billing Platform.
 * Imports global design-system styles and renders the application router.
 */

import React from 'react';
import './styles/fonts.css';
import './styles/tokens.css';
import './styles/base.css';
import AppRouter from './router/index';
import { I18nProvider } from './i18n/I18nProvider';
import { SubmissionProvider } from './household/submission';


function App() {
  return (
    <I18nProvider>
      <SubmissionProvider>
        <AppRouter />
      </SubmissionProvider>
    </I18nProvider>
  );
}

export default App;

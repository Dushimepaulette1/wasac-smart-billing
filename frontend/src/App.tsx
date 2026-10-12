/**
 * @file App.tsx
 * @description Root application component for the WASAC Smart Billing Platform.
 * Imports global design-system styles and renders the application router.
 */

import './styles/fonts.css';
import './styles/tokens.css';
import './styles/base.css';
import AppRouter from './router/index';
import { I18nProvider } from './i18n/I18nProvider';
import { SubmissionProvider } from './household/submission';
import { AuthProvider } from './staff/auth';


function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <SubmissionProvider>
          <AppRouter />
        </SubmissionProvider>
      </AuthProvider>
    </I18nProvider>
  );
}

export default App;

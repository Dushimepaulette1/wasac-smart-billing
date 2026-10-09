/**
 * @file RequestState.jsx
 * @description What a screen shows while its data loads or after loading
 * failed: plain words and a retry, never a spinner on its own.
 */

import React from 'react';
import Button from '../Button/Button';
import Notice from '../Notice/Notice';
import { useI18n } from '../../i18n/I18nProvider';

/** The translated sentence for an ApiError (or any error). */
export function errorMessage(t, error) {
  const kind = error?.kind;
  return t(['offline', 'timeout', 'notFound', 'invalid'].includes(kind) ? `error.${kind}` : 'error.server');
}

/**
 * @param {{ status: string, error?: any, onRetry: () => void, loadingText?: string }} props
 */
function RequestState({ status, error, onRetry, loadingText }) {
  const { t } = useI18n();
  if (status === 'failed') {
    return (
      <Notice
        tone="error"
        live
        actions={
          <Button variant="secondary" onClick={onRetry}>
            {t('action.retry')}
          </Button>
        }
      >
        {errorMessage(t, error)}
      </Notice>
    );
  }
  return (
    <p role="status" className="text-secondary">
      {loadingText || t('status.loading')}
    </p>
  );
}

export default RequestState;

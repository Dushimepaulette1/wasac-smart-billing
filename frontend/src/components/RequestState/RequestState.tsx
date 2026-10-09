/**
 * @file RequestState.tsx
 * @description What a screen shows while its data loads or after loading
 * failed: plain words and a retry, never a spinner on its own.
 */

import Button from '../Button/Button';
import Notice from '../Notice/Notice';
import { useI18n, type Translate } from '../../i18n/I18nProvider';
import { ApiError } from '../../api/client';
import type { RequestStatus } from '../../api/useRequest';

/** The translated sentence for an ApiError; anything else reads as a server error. */
export function errorMessage(t: Translate, error: unknown): string {
  if (error instanceof ApiError && error.kind !== 'server') return t(`error.${error.kind}`);
  return t('error.server');
}

interface RequestStateProps {
  status: RequestStatus;
  error?: unknown;
  onRetry: () => void;
  loadingText?: string;
}

function RequestState({ status, error, onRetry, loadingText }: RequestStateProps) {
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

/**
 * @file PushOptIn.tsx
 * @description "Alerts on this phone": a switch that asks the browser for permission and
 * subscribes this phone to web push, so the household hears when an officer accepts or rejects
 * a reading even with the app closed (public/sw.js shows the notification). Hidden when the
 * browser cannot do push or the server has no keys; says what to do if alerts were blocked.
 */

import { useEffect, useState } from 'react';
import Button from '../components/Button/Button';
import Icon from '../components/Icon/Icon';
import { api } from '../api/client';
import { useI18n } from '../i18n/I18nProvider';
import styles from './PushOptIn.module.css';

type State = 'unsupported' | 'loading' | 'off' | 'on' | 'blocked' | 'busy';

function supported(): boolean {
  return typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

/** The VAPID public key (base64url) as the bytes PushManager.subscribe wants. */
function keyBytes(base64url: string): ArrayBuffer {
  const padded = base64url.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (base64url.length % 4)) % 4);
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0)).buffer;
}

function PushOptIn() {
  const { t } = useI18n();
  const [state, setState] = useState<State>(supported() ? 'loading' : 'unsupported');
  const [key, setKey] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!supported()) return undefined;
    let live = true;
    (async () => {
      try {
        const { public_key } = await api.pushKey();
        if (!public_key) throw new Error('alerts are not set up');
        const registration = await navigator.serviceWorker.ready;
        const existing = await registration.pushManager.getSubscription();
        if (!live) return;
        setKey(public_key);
        if (Notification.permission === 'denied') setState('blocked');
        else setState(existing ? 'on' : 'off');
      } catch {
        if (live) setState('unsupported'); // no keys on the server, or no service worker
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  if (state === 'unsupported' || state === 'loading') return null;

  const turnOn = async () => {
    if (!key) return;
    setState('busy');
    setFailed(false);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setState(permission === 'denied' ? 'blocked' : 'off');
        return;
      }
      const registration = await navigator.serviceWorker.ready;
      const subscription =
        (await registration.pushManager.getSubscription()) ??
        (await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key) }));
      await api.pushSubscribe(subscription.toJSON());
      setState('on');
    } catch {
      setFailed(true);
      setState('off');
    }
  };

  const turnOff = async () => {
    setState('busy');
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await api.pushUnsubscribe(subscription.endpoint).catch(() => undefined);
        await subscription.unsubscribe();
      }
    } finally {
      setState('off');
    }
  };

  return (
    <div className={styles.box}>
      <span className={`${styles.icon} ${state === 'on' ? styles.iconOn : ''}`}>
        <Icon name="bell" size={20} />
      </span>
      <div className={styles.text}>
        <p className={styles.title}>{t(state === 'on' ? 'push.onTitle' : 'push.title')}</p>
        <p className="text-small text-secondary">
          {state === 'blocked' ? t('push.blocked') : state === 'on' ? t('push.onBody') : t('push.body')}
        </p>
        {failed && <p className={`text-small ${styles.error}`}>{t('push.failed')}</p>}
      </div>
      {state !== 'blocked' && (
        <Button
          variant={state === 'on' ? 'text' : 'secondary'}
          loading={state === 'busy'}
          onClick={state === 'on' ? turnOff : turnOn}
          className={styles.button}
        >
          {t(state === 'on' ? 'push.turnOff' : 'push.turnOn')}
        </Button>
      )}
    </div>
  );
}

export default PushOptIn;

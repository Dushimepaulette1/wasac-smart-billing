/**
 * @file Screen.tsx
 * @description Layout for every household page: site header, then the page heading
 * (back, step, title, lede) with the main action beside it, then the content (panels).
 *
 * Wide screens: the action sits under the heading, where the eye already is.
 * Phones: the action is pinned to the bottom within thumb reach, above the
 * bottom navigation when there is one.
 */

import { useEffect, useRef, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../Icon/Icon';
import SiteHeader from '../SiteHeader/SiteHeader';
import HouseholdNav from '../HouseholdNav/HouseholdNav';
import { useI18n } from '../../i18n/I18nProvider';
import { useHousehold } from '../../household/session';
import styles from './Screen.module.css';

interface ScreenProps {
  title: string;
  /** "Step 2 of 3", shown above the title in the submit flow. */
  step?: string;
  /** A sentence under the title. */
  lede?: ReactNode;
  /** A path, or true for browser history. */
  back?: string | boolean;
  /** The main action (one primary button, maybe one text button). */
  action?: ReactNode;
  /** Show the household navigation (header links; bottom bar on phones). */
  nav?: boolean;
  /** Camera-style page: no site header, so the content gets the whole screen height. */
  immersive?: boolean;
  /** A short form (sign-in): one centred column on wide screens, where the page puts its own
   * button inside the form; `action` is then only the pinned button on phones. */
  narrow?: boolean;
  children: ReactNode;
}

function Screen({ title, step, lede, back, action, nav = false, immersive = false, narrow = false, children }: ScreenProps) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const isDemo = useHousehold().account?.is_demo ?? false;
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Move focus to the new page's title so screen readers announce it,
  // unless something on the page already took focus (such as the meter
  // counter opening for typing). Child effects run first, so check.
  useEffect(() => {
    document.title = `${title} | ${t('app.name')}`;
    const active = document.activeElement;
    if (!active || active === document.body) headingRef.current?.focus({ preventScroll: true });
  }, [title, t]);

  const goBack = () => (typeof back === 'string' ? navigate(back) : navigate(-1));

  const classes = [styles.screen, 'stage', nav ? styles.withNav : '', action ? styles.withAction : '', narrow ? styles.narrow : '']
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes}>
      {!immersive && <SiteHeader links={nav} />}

      <main className={styles.main}>
        <div className={styles.head}>
          {(back || isDemo) && (
            <div className={styles.topRow}>
              {back && (
                <button type="button" className={styles.back} onClick={goBack}>
                  <Icon name="back" size={18} />
                  <span>{t('action.back')}</span>
                </button>
              )}
              {/* A label, not a button: this household's data is made up for trying the app. */}
              {isDemo && <span className={`${styles.demo} chip chip-held`}>{t('demo.label')}</span>}
            </div>
          )}
          {step && <p className={`${styles.step} text-small`}>{step}</p>}
          <h1 ref={headingRef} tabIndex={-1} className={`${styles.title} page-title`}>
            {title}
          </h1>
          {lede && <div className={`${styles.lede} text-lead`}>{lede}</div>}
          {action && (
            <div className={styles.action} data-screen-action="">
              {action}
            </div>
          )}
        </div>

        <div className={styles.body}>{children}</div>
      </main>

      {nav && <HouseholdNav />}
    </div>
  );
}

export default Screen;

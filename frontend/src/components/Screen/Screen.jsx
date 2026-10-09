/**
 * @file Screen.jsx
 * @description Layout for every household screen: one column, the title at
 * the top, the main action pinned at the bottom within thumb reach, and the
 * bottom navigation on the screens you navigate between (not inside a flow).
 * On wider screens the same column is centred; households are mobile first.
 */

import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../Icon/Icon';
import HouseholdNav from '../HouseholdNav/HouseholdNav';
import { useI18n } from '../../i18n/I18nProvider';
import styles from './Screen.module.css';

/**
 * @param {{
 *   title: string,
 *   step?: string,
 *   back?: string|boolean,
 *   action?: React.ReactNode,
 *   nav?: boolean,
 *   children: React.ReactNode,
 * }} props
 *   step:   "Step 2 of 3", shown above the title in the submit flow.
 *   back:   a path, or true for browser history.
 *   action: the pinned bottom area (primary button, maybe one text button).
 *   nav:    show the bottom navigation.
 */
function Screen({ title, step, back, action, nav = false, children }) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const headingRef = useRef(null);

  // Move focus to the new screen's title so screen readers announce it.
  useEffect(() => {
    document.title = `${title} | ${t('app.name')}`;
    headingRef.current?.focus({ preventScroll: true });
  }, [title, t]);

  const goBack = () => (typeof back === 'string' ? navigate(back) : navigate(-1));

  return (
    <div className={`${styles.screen} ${nav ? styles.withNav : ''}`}>
      <header className={styles.bar}>
        {back && (
          <button type="button" className={styles.back} onClick={goBack}>
            <Icon name="back" />
            <span className="visually-hidden">{t('action.back')}</span>
          </button>
        )}
        <div className={styles.heading}>
          {step && <p className={`${styles.step} text-small`}>{step}</p>}
          <h1 ref={headingRef} tabIndex={-1} className={`${styles.title} text-lead`}>
            {title}
          </h1>
        </div>
      </header>

      <main className={styles.body}>{children}</main>

      {action && <div className={styles.action}>{action}</div>}
      {nav && <HouseholdNav />}
    </div>
  );
}

export default Screen;

/**
 * @file Landing.tsx
 * @description The public page: what the service is, start a reading, and
 * the way in for WASAC staff. A centred hero on the gradient (the one
 * orchestrated moment in the app), then the three real steps.
 */

import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import SiteHeader from '../../components/SiteHeader/SiteHeader';
import Button from '../../components/Button/Button';
import { useI18n } from '../../i18n/I18nProvider';
import styles from './Landing.module.css';

const STEPS = ['landing.step1', 'landing.step2', 'landing.step3'] as const;

function Landing() {
  const { t } = useI18n();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = t('app.name');
  }, [t]);

  return (
    <div className={`${styles.page} stage stage-hero`}>
      <SiteHeader links={false} />

      <main className={styles.main}>
        <section className={styles.hero} aria-labelledby="landing-title">
          <p className={styles.eyebrow}>{t('landing.eyebrow')}</p>
          <h1 id="landing-title" className={`${styles.title} display`}>
            {t('landing.title')}
          </h1>
          <p className={`${styles.lede} text-lead`}>{t('landing.lede')}</p>
          <div className={styles.actions}>
            <Button icon="camera" onClick={() => navigate('/submit/camera')}>
              {t('home.read')}
            </Button>
            <Button variant="secondary" onClick={() => navigate('/officer')}>
              {t('landing.staff')}
            </Button>
          </div>
          <Link to="/home" className={styles.account}>
            {t('landing.account')}
          </Link>
        </section>

        <section className={styles.steps} aria-labelledby="steps-title">
          <h2 id="steps-title" className="visually-hidden">
            {t('landing.stepsTitle')}
          </h2>
          <ol className={styles.stepList}>
            {STEPS.map((key, i) => (
              <li key={key} className={styles.step}>
                <span className={styles.stepNumber} aria-hidden="true">
                  {i + 1}
                </span>
                <span>{t(key)}</span>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </div>
  );
}

export default Landing;

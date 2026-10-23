/**
 * @file Landing.tsx
 * @description The public page. A split hero: what Mubazi does and the two ways in (read the
 * meter, see my bills), beside a live showcase where the meter counter rolls up to a reading
 * and a bill card settles in. Then the three real steps, what makes it easy, and one small
 * link for WASAC staff at the foot of the page.
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import SiteHeader from '../../components/SiteHeader/SiteHeader';
import Button from '../../components/Button/Button';
import Icon, { type IconName } from '../../components/Icon/Icon';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import { LogoMark } from '../../components/Logo/Logo';
import { useI18n } from '../../i18n/I18nProvider';
import useCounterLabels from '../../i18n/useCounterLabels';
import { cellsFromCubicMetres } from '../../utils/reading';
import InstallApp from '../../pwa/InstallApp';
import styles from './Landing.module.css';

const STEPS: Array<{ icon: IconName; title: string; text: string }> = [
  { icon: 'camera', title: 'landing.step1Title', text: 'landing.step1' },
  { icon: 'check', title: 'landing.step2Title', text: 'landing.step2' },
  { icon: 'wallet', title: 'landing.step3Title', text: 'landing.step3' },
];

const PERKS: Array<{ icon: IconName; text: string }> = [
  { icon: 'sparkle', text: 'landing.perkRead' },
  { icon: 'shield', text: 'landing.perkFair' },
  { icon: 'phone', text: 'landing.perkUssd' },
];

const SHOWN_READING = 565.846;

/** The showcase meter: counts up to the reading once, as if the wheels were turning. */
function useRollingReading(target: number): number {
  const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const [value, setValue] = useState(reduced ? target : target - 0.6);
  useEffect(() => {
    if (reduced) return undefined;
    const start = performance.now();
    const from = target - 0.6;
    let frame = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 1800);
      const eased = 1 - (1 - p) ** 3;
      setValue(from + (target - from) * eased);
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, reduced]);
  return value;
}

function Showcase() {
  const { t, rwf } = useI18n();
  const labels = useCounterLabels();
  const reading = useRollingReading(SHOWN_READING);
  return (
    <div className={styles.showcase} aria-hidden="true">
      <div className={styles.pattern} />
      <div className={`${styles.meterCard} imigongo-band`}>
        <div className={styles.meterTop}>
          <span className="chip chip-brand">{t('landing.demoMeter')}</span>
          <LogoMark size={28} />
        </div>
        <MeterCounter cells={cellsFromCubicMetres(reading)} labels={labels} size="small" />
        <p className={styles.meterNote}>{t('landing.demoRead')}</p>
      </div>
      <div className={styles.billCard}>
        <span className={styles.billIcon}>
          <Icon name="check" size={18} />
        </span>
        <div>
          <p className={styles.billLabel}>{t('landing.demoBill')}</p>
          <p className={styles.billAmount}>{rwf(12400)}</p>
        </div>
        <span className="chip chip-ok">{t('bill.paid')}</span>
      </div>
    </div>
  );
}

function Landing() {
  const { t } = useI18n();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = `${t('app.name')} | ${t('brand.tagline')}`;
  }, [t]);

  return (
    <div className={`${styles.page} stage stage-hero`}>
      <SiteHeader links={false} />

      <main className={styles.main}>
        <section className={styles.hero} aria-labelledby="landing-title">
          <div className={styles.copy}>
            <p className={`${styles.eyebrow} chip chip-brand`}>{t('landing.eyebrow')}</p>
            <h1 id="landing-title" className={`${styles.title} display`}>
              {t('landing.title')}
            </h1>
            <p className={`${styles.lede} text-lead`}>{t('landing.lede')}</p>
            <div className={styles.actions}>
              <Button icon="camera" onClick={() => navigate('/submit/camera')}>
                {t('home.read')}
              </Button>
              <Button variant="secondary" href="/home" onClick={(e) => { e.preventDefault(); navigate('/home'); }}>
                {t('landing.account')}
              </Button>
            </div>
            <InstallApp className={styles.install} />
          </div>
          <Showcase />
        </section>

        <section className={styles.steps} aria-labelledby="steps-title">
          <h2 id="steps-title" className={`${styles.sectionTitle} page-title`}>
            {t('landing.stepsTitle')}
          </h2>
          <ol className={styles.stepList}>
            {STEPS.map((step, i) => (
              <li key={step.text} className={`${styles.step} enter enter-${i + 1}`}>
                <span className={styles.stepIcon}>
                  <Icon name={step.icon} size={22} />
                </span>
                <h3 className={styles.stepTitle}>{t(step.title)}</h3>
                <p className="text-secondary">{t(step.text)}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.perks} aria-label={t('landing.perksTitle')}>
          <ul className={styles.perkList}>
            {PERKS.map((perk) => (
              <li key={perk.text} className={styles.perk}>
                <Icon name={perk.icon} size={20} />
                <span>{t(perk.text)}</span>
              </li>
            ))}
          </ul>
        </section>

        <footer className={styles.footer}>
          <span className="text-small text-secondary">{t('landing.footer')}</span>
          <Link to="/staff/sign-in" className={styles.staffLink}>
            <Icon name="lock" size={16} />
            {t('landing.staffLink')}
          </Link>
        </footer>
      </main>
    </div>
  );
}

export default Landing;

/**
 * @file Landing.tsx
 * @description The public page, in the editorial "Navy and Ink" style: a centred hero (badge,
 * two-line serif headline with the second line italic, two calls to action), the value of the
 * service beside a dark preview of the app checking a reading, a bento grid of features, a navy
 * call to action, and the footer (with the one link for WASAC staff).
 */

import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import SiteHeader from '../../components/SiteHeader/SiteHeader';
import Button from '../../components/Button/Button';
import Icon, { type IconName } from '../../components/Icon/Icon';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import Reveal from '../../components/Reveal/Reveal';
import { LogoMark } from '../../components/Logo/Logo';
import { useI18n } from '../../i18n/I18nProvider';
import useCounterLabels from '../../i18n/useCounterLabels';
import { cellsFromCubicMetres } from '../../utils/reading';
import InstallApp from '../../pwa/InstallApp';
import styles from './Landing.module.css';

const VALUES: Array<{ icon: IconName; title: string; text: string }> = [
  { icon: 'camera', title: 'landing.value1Title', text: 'landing.value1' },
  { icon: 'shield', title: 'landing.value2Title', text: 'landing.value2' },
  { icon: 'wallet', title: 'landing.value3Title', text: 'landing.value3' },
];

const SMALL_FEATURES: Array<{ icon: IconName; title: string; text: string }> = [
  { icon: 'globe', title: 'landing.featureLanguageTitle', text: 'landing.featureLanguage' },
  { icon: 'bills', title: 'landing.featureHistoryTitle', text: 'landing.featureHistory' },
  { icon: 'lock', title: 'landing.featureSignInTitle', text: 'landing.featureSignIn' },
];

/** A dark window with the app inside, checking a reading. Decorative: the copy beside it says it. */
function AppPreview() {
  const { t, rwf } = useI18n();
  const labels = useCounterLabels();
  return (
    <div className={styles.preview} aria-hidden="true">
      <div className={styles.screen}>
        <div className={styles.windowBar}>
          <span className={styles.dot} />
          <span className={styles.dot} />
          <span className={styles.dot} />
          <span className={styles.address} />
        </div>
        <span className={`${styles.skeleton} ${styles.skeletonTitle}`} />
        <div className={styles.meter}>
          <MeterCounter cells={cellsFromCubicMetres(565.846)} labels={labels} size="small" />
        </div>
        <div className={styles.blocks}>
          <span className={styles.blockSoft} />
          <span className={styles.blockGrey} />
        </div>
        <span className={styles.skeleton} />
        <span className={`${styles.skeleton} ${styles.skeletonShort}`} />
      </div>
      <div className={styles.statusBar}>
        <span className={styles.check}>
          <Icon name="check" size={16} />
        </span>
        <span className={styles.statusText}>{t('landing.previewChecked')}</span>
        <span className={styles.tag}>565.846 m³</span>
        <span className={styles.tag}>{rwf(12400)}</span>
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
        {/* Hero */}
        <section className={styles.hero} aria-labelledby="landing-title">
          <p className={`${styles.heroBadge} badge reveal`}>
            {t('landing.eyebrow')}
          </p>
          <h1 id="landing-title" className={`${styles.title} display reveal reveal-1`}>
            {t('landing.title1')}
            <em className={styles.titleLine}>{t('landing.title2')}</em>
          </h1>
          <p className={`${styles.lede} text-lead reveal reveal-2`}>{t('landing.lede')}</p>
          <div className={`${styles.actions} reveal reveal-3`}>
            <Button icon="camera" onClick={() => navigate('/submit/camera')}>
              {t('home.read')}
            </Button>
            <Button variant="secondary" onClick={() => navigate('/home')}>
              {t('landing.account')}
            </Button>
          </div>
          <InstallApp className={styles.install} />
        </section>

        {/* Value: what it does, beside the app doing it */}
        <section className={styles.value} aria-labelledby="value-title">
          <Reveal className={styles.valueCopy}>
            <h2 id="value-title" className="section-title">
              {t('landing.valueTitle1')} <em>{t('landing.valueTitle2')}</em>
            </h2>
            <ul className={styles.valueList}>
              {VALUES.map((v) => (
                <li key={v.title} className={styles.valueItem}>
                  <span className={styles.valueIcon}>
                    <Icon name={v.icon} size={24} />
                  </span>
                  <span>
                    <span className={styles.valueTitle}>{t(v.title)}</span>
                    <span className={styles.valueText}>{t(v.text)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </Reveal>
          <Reveal>
            <AppPreview />
          </Reveal>
        </section>

        {/* Features: a bento grid */}
        <section className={styles.features} aria-labelledby="features-title">
          <Reveal as="h2" id="features-title" className={`${styles.featuresTitle} section-title`}>
            {t('landing.featuresTitle1')} <em>{t('landing.featuresTitle2')}</em>
          </Reveal>
          <div className={styles.bento}>
            <Reveal className={`${styles.card} ${styles.cardLarge}`}>
              <Icon name="phone" size={220} className={styles.cardBackIcon} />
              <span className={styles.cardIcon}>
                <Icon name="phone" size={24} />
              </span>
              <h3 className={styles.cardTitle}>{t('landing.featureUssdTitle')}</h3>
              <p className={styles.cardText}>{t('landing.featureUssd')}</p>
            </Reveal>
            <Reveal className={`${styles.card} ${styles.cardDark}`}>
              <span className={styles.cardIcon}>
                <Icon name="trend" size={24} />
              </span>
              <h3 className={styles.cardTitle}>{t('landing.featureLeakTitle')}</h3>
              <p className={styles.cardText}>{t('landing.featureLeak')}</p>
            </Reveal>
            {/* Phones: one card with three rows. Wider: three cards in the grid. */}
            <Reveal className={styles.smallGroup}>
              {SMALL_FEATURES.map((f) => (
                <div key={f.title} className={`${styles.card} ${styles.smallCard}`}>
                  <span className={styles.cardIcon}>
                    <Icon name={f.icon} size={22} />
                  </span>
                  <div className={styles.smallText}>
                    <h3 className={styles.cardTitle}>{t(f.title)}</h3>
                    <p className={styles.cardText}>{t(f.text)}</p>
                  </div>
                </div>
              ))}
            </Reveal>
          </div>
        </section>

        {/* Call to action */}
        <Reveal as="section" className={styles.cta} aria-labelledby="cta-title">
          <h2 id="cta-title" className={styles.ctaTitle}>
            {t('landing.ctaTitle1')} <em>{t('landing.ctaTitle2')}</em>
          </h2>
          <p className={styles.ctaText}>{t('landing.ctaText')}</p>
          <button type="button" className={styles.ctaButton} onClick={() => navigate('/submit/camera')}>
            <Icon name="camera" size={20} />
            {t('home.read')}
          </button>
          <ul className={styles.trust}>
            <li>{t('landing.trustMomo')}</li>
            <li>{t('landing.trustUssd')}</li>
            <li>{t('landing.trustLanguages')}</li>
          </ul>
        </Reveal>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div className={styles.footerBrand}>
            <span className={`${styles.footerLogo} on-ink`}>
              <LogoMark />
              <span className={styles.footerName}>Mubazi</span>
            </span>
            <p>{t('landing.footerAbout')}</p>
          </div>
          <nav className={styles.footerCol} aria-label={t('landing.footerHouseholds')}>
            <h4>{t('landing.footerHouseholds')}</h4>
            <Link to="/submit/camera">{t('home.read')}</Link>
            <Link to="/history">{t('nav.bills')}</Link>
            <Link to="/messages">{t('nav.messages')}</Link>
          </nav>
          <nav className={styles.footerCol} aria-label={t('landing.footerStaff')}>
            <h4>{t('landing.footerStaff')}</h4>
            <Link to="/staff/sign-in">{t('landing.staffLink')}</Link>
          </nav>
          <div className={styles.footerCol}>
            <h4>{t('landing.footerHelp')}</h4>
            <p>{t('landing.footerCall')}</p>
          </div>
        </div>
        <div className={styles.footerBottom}>
          <span>{t('landing.footerCopy', { year: new Date().getFullYear() })}</span>
        </div>
      </footer>
    </div>
  );
}

export default Landing;

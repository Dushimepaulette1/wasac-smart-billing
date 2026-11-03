/**
 * @file YourData.tsx
 * @description What the household app keeps, who sees it and for how long, in
 * plain words. Public, so a household can read it before signing in. The facts
 * come from the backend: photos are kept PHOTO_RETENTION_DAYS (default 90) and
 * unsent ones a day (app/services/photo_evidence.py); location only decides
 * whether an officer looks (app/anomaly/location.py).
 */

import Screen from '../../components/Screen/Screen';
import { useI18n } from '../../i18n/I18nProvider';

const SECTIONS = [
  { title: 'data.keptTitle', items: ['data.kept1', 'data.kept2', 'data.kept3'] },
  { title: 'data.whoTitle', items: ['data.who'] },
  { title: 'data.photosTitle', items: ['data.photos'] },
  { title: 'data.locationTitle', items: ['data.location'] },
  { title: 'data.contactTitle', items: ['data.contact'] },
];

export default function YourData() {
  const { t } = useI18n();
  return (
    <Screen title={t('data.title')} lede={<p>{t('data.lede')}</p>} back narrow>
      <div className="stack">
        {SECTIONS.map(({ title, items }) => (
          <section key={title} className="panel" aria-labelledby={title}>
            <h2 id={title} className="panel-title">
              {t(title)}
            </h2>
            {items.length > 1 ? (
              <ul>
                {items.map((item) => (
                  <li key={item}>{t(item)}</li>
                ))}
              </ul>
            ) : (
              <p>{t(items[0] ?? '')}</p>
            )}
          </section>
        ))}
        <p className="text-small text-secondary">{t('app.notOfficial')}</p>
      </div>
    </Screen>
  );
}

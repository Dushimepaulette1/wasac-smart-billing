/**
 * @file YourData.tsx
 * @description Public privacy policy, using the household layout and translations.
 * Retention details reflect app/services/photo_evidence.py.
 */

import Screen from '../../components/Screen/Screen';
import { useI18n } from '../../i18n/I18nProvider';

const SECTIONS = [
  { title: 'data.keptTitle', items: ['data.kept1', 'data.kept2', 'data.kept3'] },
  { title: 'data.useTitle', items: ['data.use'] },
  { title: 'data.whoTitle', items: ['data.who'] },
  { title: 'data.hostingTitle', items: ['data.hosting'] },
  { title: 'data.draftsTitle', items: ['data.draftsStored', 'data.draftsClear'] },
  { title: 'data.providersTitle', items: ['data.providerSms', 'data.providerUssd', 'data.providerPayments', 'data.providerPush'] },
  { title: 'data.photosTitle', items: ['data.photos'] },
  { title: 'data.locationTitle', items: ['data.location'] },
  { title: 'data.aiTitle', items: ['data.ai'] },
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
            {title === 'data.contactTitle' && (
              <p>
                <a href="https://github.com/Dushimepaulette1/wasac-smart-billing/issues/new">
                  {t('data.contactLink')}
                </a>
              </p>
            )}
          </section>
        ))}
        <p className="text-small text-secondary">{t('app.notOfficial')}</p>
      </div>
    </Screen>
  );
}

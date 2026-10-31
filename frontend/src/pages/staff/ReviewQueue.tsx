/**
 * @file ReviewQueue.tsx
 * @description Held readings, decided on one screen: the list on the
 * left, and for the selected reading the read digits on the meter counter,
 * the numbers a decision rests on, and the household's last readings.
 *
 * Two kinds of item: a held reading (accept or reject: no bill until then),
 * and follow-up on a reading that was already billed, such as a meter that
 * seems stuck (close once followed up).
 *
 * Keyboard: J / K next and previous, A accept, R reject, C close, U undo.
 * A decision waits 5 seconds before it is sent, so it can be undone
 * (accepting creates a bill, which cannot be taken back once sent).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState, { errorMessage } from '../../components/RequestState/RequestState';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { api } from '../../api/client';
import useRequest from '../../api/useRequest';
import type { ReviewItem } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import { issueKey } from '../../staff/issues';

import DecisionPane, { isFollowUp } from './ReviewDecisionPane';
import styles from './ReviewQueue.module.css';

const UNDO_MS = 5000;
type Outcome = 'accept' | 'reject' | 'close';

const SENT: Record<Outcome, 'accept' | 'reject' | null> = { accept: 'accept', reject: 'reject', close: null };

interface Pending {
  item: ReviewItem;
  outcome: Outcome;
  reason?: string;
  reasonCode?: RejectReason;
}

/** Why a reading is rejected: kept in Activity. 'other' asks the officer to type it. */
const REJECT_REASONS = ['photo', 'digits', 'meter', 'other'] as const;
type RejectReason = (typeof REJECT_REASONS)[number];

function ReviewQueue() {
  const { t, rwf } = useI18n();
  const [params, setParams] = useSearchParams();
  const queue = useRequest(api.reviewQueue, { immediate: true, args: [] });
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(params.get('flag')) || null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState<RejectReason>('photo');
  const [rejectText, setRejectText] = useState('');
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const timer = useRef<number | null>(null);
  const pendingRef = useRef<Pending | null>(null);
  pendingRef.current = pending;
  const paneRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (queue.status === 'success') setItems(queue.data);
  }, [queue.status, queue.data]);

  useEffect(() => setRejecting(false), [selectedId]);

  const visible = items.filter((i) => i.flag.id !== pending?.item.flag.id);
  const selected = visible.find((i) => i.flag.id === selectedId) ?? visible[0] ?? null;

  const select = useCallback(
    (id: number, scroll = false) => {
      setSelectedId(id);
      setParams({ flag: String(id) }, { replace: true });
      if (scroll && !window.matchMedia?.('(min-width: 1100px)').matches) {
        paneRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    },
    [setParams],
  );

  const send = useCallback(
    async ({ item, outcome, reason, reasonCode }: Pending) => {
      setPending(null);
      try {
        const res = await (reason ? api.resolveFlag(item.flag.id, SENT[outcome], reason, reasonCode) : api.resolveFlag(item.flag.id, SENT[outcome]));
        setItems((list) => list.filter((i) => i.flag.id !== item.flag.id));
        const name = item.customer_name ?? item.flag.household_id;
        setResult(
          outcome === 'accept'
            ? res.amount_due !== null
              ? t('staff.review.acceptedBill', { name, amount: rwf(res.amount_due) })
              : item.flag.anomaly_type === 'NO_BASELINE'
                ? t('staff.review.acceptedStart', { name })
                : t('staff.review.accepted', { name })
            : outcome === 'reject'
              ? t('staff.review.rejected', { name })
              : t('staff.review.closed', { name }),
        );
      } catch (err) {
        setError(err);
      }
    },
    [t, rwf],
  );

  const decide = useCallback(
    (outcome: Outcome, reason?: string, reasonCode?: RejectReason) => {
      if (!selected || (outcome === 'close') !== isFollowUp(selected)) return;
      if (outcome === 'reject' && !reason) {
        setRejecting(true); // a reject needs a reason first
        return;
      }
      setRejecting(false);
      if (pending) send(pending); // a second decision sends the first now
      setError(null);
      setResult(null);
      const next = visible[visible.indexOf(selected) + 1] ?? visible[visible.indexOf(selected) - 1];
      const decision = { item: selected, outcome, reason, reasonCode };
      setPending(decision);
      if (next) setSelectedId(next.flag.id);
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => send(decision), UNDO_MS);
    },
    [selected, pending, visible, send],
  );

  const undo = useCallback(() => {
    if (!pending) return;
    if (timer.current) window.clearTimeout(timer.current);
    setSelectedId(pending.item.flag.id);
    setPending(null);
  }, [pending]);

  // Leaving the page sends a waiting decision rather than losing it.
  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
      const waiting = pendingRef.current;
      if (waiting) api.resolveFlag(waiting.item.flag.id, SENT[waiting.outcome], waiting.reason, waiting.reasonCode).catch(() => undefined);
    },
    [],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (e.ctrlKey || e.metaKey || e.altKey || target?.closest('input, select, textarea')) return;
      const index = selected ? visible.indexOf(selected) : -1;
      const key = e.key.toLowerCase();
      const nextItem = visible[index + 1];
      const prevItem = index > 0 ? visible[index - 1] : undefined;
      if (key === 'j' && nextItem) select(nextItem.flag.id);
      else if (key === 'k' && prevItem) select(prevItem.flag.id);
      else if (key === 'a') decide('accept');
      else if (key === 'r') decide('reject');
      else if (key === 'c') decide('close');
      else if (key === 'u') undo();
      else return;
      e.preventDefault();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [visible, selected, select, decide, undo]);

  const count = visible.length;

  if (queue.status !== 'success') {
    return (
      <StaffLayout title={t('staff.nav.review')}>
        <RequestState status={queue.status} error={queue.error} onRetry={queue.retry} />
      </StaffLayout>
    );
  }

  return (
    <StaffLayout
      title={t('staff.nav.review')}
      lede={count ? t('staff.review.lede', { count }) : undefined}
      reviewCount={count}
    >
      <div className={styles.feedback} aria-live="polite">
        {pending && (
          <Notice
            tone="held"
            actions={
              <Button variant="secondary" onClick={undo}>
                {t('staff.review.undo')}
              </Button>
            }
          >
            {t(`staff.review.${{ accept: 'accepting', reject: 'rejecting', close: 'closing' }[pending.outcome]}`, {
              name: pending.item.customer_name ?? pending.item.flag.household_id,
            })}
          </Notice>
        )}
        {result && !pending && <Notice tone="done">{result}</Notice>}
        {Boolean(error) && <Notice tone="error">{errorMessage(t, error)}</Notice>}
      </div>

      {count === 0 ? (
        <section className="panel">
          <h2 className="panel-title">{t('staff.review.emptyTitle')}</h2>
          <p className="text-secondary">{t('staff.review.empty')}</p>
        </section>
      ) : (
        <div className={styles.layout}>
          <section className={`panel ${styles.list}`} aria-labelledby="queue-title">
            <h2 id="queue-title" className={styles.blockTitle}>
              {t('staff.review.listTitle', { count })}
            </h2>
            <ul>
              {visible.map((item) => {
                const active = item.flag.id === selected?.flag.id;
                return (
                  <li key={item.flag.id}>
                    <button
                      type="button"
                      className={`${styles.item} ${active ? styles.itemActive : ''}`}
                      aria-current={active ? 'true' : undefined}
                      onClick={() => select(item.flag.id, true)}
                    >
                      <span className={styles.itemName}>{item.customer_name ?? item.flag.household_id}</span>
                      <span className={styles.itemIssue}>{t(issueKey(item.flag))}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className={`${styles.keys} text-small`}>{t('staff.review.keys')}</p>
          </section>

          {selected && (
            <section ref={paneRef} className={`panel ${styles.pane}`} aria-label={t('staff.review.decision')}>
              <DecisionPane item={selected} />
              {isFollowUp(selected) ? (
                <>
                  <div className={styles.actions}>
                    <Button onClick={() => decide('close')} icon="check">
                      {t('staff.review.close')}
                    </Button>
                  </div>
                  <p className="text-small text-secondary">{t('staff.review.closeNote')}</p>
                </>
              ) : (
                <>
                  <div className={styles.actions}>
                    <Button onClick={() => decide('accept')} icon="check">
                      {t('staff.review.accept')}
                    </Button>
                    <Button variant="secondary" onClick={() => decide('reject')} icon="camera">
                      {t('staff.review.reject')}
                    </Button>
                  </div>
                  {rejecting && (
                    <div className={styles.form}>
                      <label className={styles.filter}>
                        {t('staff.review.rejectWhy')}
                        <select className={styles.select} value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value as RejectReason)}>
                          {REJECT_REASONS.map((r) => <option key={r} value={r}>{t(`staff.review.rejectWhy.${r}`)}</option>)}
                        </select>
                      </label>
                      {rejectReason === 'other' && (
                        <label className={styles.filter}>
                          {t('staff.review.rejectWhyOther')}
                          <input className={styles.search} maxLength={160} value={rejectText}
                            onChange={(e) => setRejectText(e.target.value)} />
                        </label>
                      )}
                      <div className={styles.rowActions}>
                        <Button variant="secondary" disabled={rejectReason === 'other' && rejectText.trim().length < 3}
                          onClick={() => {
                            decide('reject', rejectReason === 'other' ? rejectText.trim() : t(`staff.review.rejectWhy.${rejectReason}`), rejectReason);
                            setRejectText('');
                            setRejectReason('photo');
                          }}>
                          {t('staff.review.rejectConfirm')}
                        </Button>
                        <Button variant="text" onClick={() => setRejecting(false)}>{t('action.cancel')}</Button>
                      </div>
                    </div>
                  )}
                  <p className="text-small text-secondary">
                    {t(selected.flag.anomaly_type === 'NO_BASELINE' ? 'staff.review.acceptNoteStart' : 'staff.review.acceptNote')}
                  </p>
                </>
              )}
            </section>
          )}
        </div>
      )}
    </StaffLayout>
  );
}

export default ReviewQueue;

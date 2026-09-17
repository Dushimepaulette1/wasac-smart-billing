/**
 * @file AnomalyReview.jsx
 * @description Screen 10: Field Officer Anomaly Review Queue.
 */

import React, { useState } from 'react';
import PageHeader from '../../components/PageHeader/PageHeader';
import Card from '../../components/Card/Card';
import Button from '../../components/Button/Button';
import { mockAnomalyReadings } from '../../data/readings';
import { formatDate, formatConsumption } from '../../utils/format';
import styles from './AnomalyReview.module.css';

export default function AnomalyReview() {
  const [items, setItems] = useState(mockAnomalyReadings);
  const [actionStates, setActionStates] = useState({});
  const [removingIds, setRemovingIds] = useState([]);

  const handleAction = (id, type) => {
    setActionStates((prev) => ({ ...prev, [id]: type }));

    setTimeout(() => {
      setRemovingIds((prev) => [...prev, id]);

      setTimeout(() => {
        setItems((prev) => prev.filter((item) => item.id !== id));
      }, 450);
    }, 1600);
  };

  return (
    <div className={styles.container}>
      <PageHeader
        title="Anomaly Review Queue"
        backHref="/officer"
        backLabel="Officer Mode"
      />

      <div className={styles.inner}>
        <div className={styles.officerBadgeRow}>
          <span className={styles.officerPill}>Officer Mode</span>
          <span className={styles.queueCount}>
            {items.length} {items.length === 1 ? 'flagged reading' : 'flagged readings'} pending review
          </span>
        </div>

        {items.length === 0 ? (
          <div className={styles.emptyCard}>
            <div className={styles.emptyIconCircle}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke="var(--color-accent)" strokeWidth="2" />
                <path d="M8 12L11 15L16 9" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h2 className={styles.emptyTitle}>Review queue is clear</h2>
            <p className={styles.emptyText}>
              All anomalous readings have been verified or marked for customer recapture.
            </p>
          </div>
        ) : (
          <div className={styles.queueList}>
            {items.map((item) => {
              const isConfirmed = !!actionStates[item.id];
              const confirmedType = actionStates[item.id];
              const isRemoving = removingIds.includes(item.id);

              return (
                <div
                  key={item.id}
                  className={`${styles.cardWrapper} ${isRemoving ? styles.cardRemoving : ''}`}
                >
                  <Card variant="default" padding="md" className={styles.reviewCard}>
                    <div className={styles.cardHeader}>
                      <div>
                        <h3 className={styles.custName}>{item.customerName}</h3>
                        <span className={styles.custAddr}>{item.customerAddress}</span>
                      </div>
                      <div className={styles.accountBadge}>
                        <span>{item.accountNumber}</span>
                      </div>
                    </div>

                    <div className={styles.deltaBox}>
                      <div className={styles.deltaCol}>
                        <span className={styles.colLabel}>Previous Verified</span>
                        <span className={styles.readingVal}>{item.previousReading.toLocaleString()} m³</span>
                      </div>

                      <div className={styles.arrowCol}>
                        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                          <path
                            d="M4 10H16M16 10L11 5M16 10L11 15"
                            stroke="var(--color-text-muted)"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </div>

                      <div className={styles.deltaCol}>
                        <span className={styles.colLabel}>Submitted Reading</span>
                        <span className={`${styles.readingVal} ${styles.valWarn}`}>
                          {item.submittedReading.toLocaleString()} m³
                        </span>
                      </div>

                      <div className={styles.deltaCol}>
                        <span className={styles.colLabel}>Implied Delta</span>
                        <span className={`${styles.readingVal} ${styles.valHighlight}`}>
                          +{formatConsumption(item.consumption)}
                        </span>
                      </div>
                    </div>

                    <div className={styles.anomalyReasonPill}>
                      <span className={styles.reasonDot} />
                      <span className={styles.reasonLabel}>Flag Reason:</span>
                      <span className={styles.reasonScore}>{item.anomalyScore}</span>
                    </div>

                    <div className={styles.cardFooter}>
                      <div className={styles.metaRow}>
                        <span>Meter ID: {item.meterID}</span>
                        <span>Submitted {formatDate(item.dateSubmitted)}</span>
                      </div>

                      {isConfirmed ? (
                        <div
                          className={`${styles.actionConfirmBox} ${
                            confirmedType === 'approve'
                              ? styles.confirmApprove
                              : styles.confirmRecapture
                          }`}
                        >
                          {confirmedType === 'approve' ? (
                            <>
                              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                                <circle cx="10" cy="10" r="9" stroke="var(--color-accent)" strokeWidth="2" />
                                <path d="M6 10L9 13L14 7" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                              </svg>
                              <span>Reading approved · Generating digital bill</span>
                            </>
                          ) : (
                            <>
                              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                                <path d="M2 5L10 11L18 5" stroke="var(--color-text-primary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                <rect x="2" y="4" width="16" height="12" rx="2" stroke="var(--color-text-primary)" strokeWidth="1.5" />
                              </svg>
                              <span>SMS sent · Customer prompted to retake photo</span>
                            </>
                          )}
                        </div>
                      ) : (
                        <div className={styles.actionsRow}>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleAction(item.id, 'approve')}
                          >
                            Approve Reading
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleAction(item.id, 'recapture')}
                          >
                            Request Recapture
                          </Button>
                        </div>
                      )}
                    </div>
                  </Card>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

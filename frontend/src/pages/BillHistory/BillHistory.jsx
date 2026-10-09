/**
 * @file BillHistory.jsx
 * @description Screen 8: Bill History featuring smooth accordion-style tier inspection.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../../components/PageHeader/PageHeader';
import Card from '../../components/Card/Card';
import StatusBadge from '../../components/StatusBadge/StatusBadge';
import Button from '../../components/Button/Button';
import { mockBills } from '../../data/bills';
import { formatCurrency, formatDate, formatConsumption } from '../../utils/format';
import styles from './BillHistory.module.css';

export default function BillHistory() {
  const navigate = useNavigate();
  const [expandedId, setExpandedId] = useState(mockBills[0]?.id || null);

  const toggleExpand = (id) => {
    setExpandedId((curr) => (curr === id ? null : id));
  };

  const avgConsumption = Math.round(
    mockBills.reduce((acc, b) => acc + b.consumption, 0) / mockBills.length
  );

  return (
    <div className={styles.container}>
      <PageHeader
        title="Bill History"
        backHref="/home"
        backLabel="Home"
      />

      <div className={styles.inner}>
        <Card variant="accent" padding="md" className={styles.summaryBanner}>
          <div className={styles.bannerRow}>
            <div className={styles.bannerIcon}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"
                  stroke="var(--color-accent)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div className={styles.bannerText}>
              <span className={styles.bannerLabel}>Average Monthly Consumption</span>
              <div className={styles.bannerValue}>
                {avgConsumption} m³ <span className={styles.bannerPeriod}>/ month (past 6 months)</span>
              </div>
            </div>
          </div>
        </Card>

        <div className={styles.historyList}>
          {mockBills.map((bill) => {
            const isExpanded = expandedId === bill.id;

            return (
              <div
                key={bill.id}
                className={`${styles.billCard} ${isExpanded ? styles.cardOpen : ''}`}
              >
                <div
                  className={styles.cardHeaderRow}
                  onClick={() => toggleExpand(bill.id)}
                  role="button"
                  tabIndex={0}
                  aria-expanded={isExpanded}
                >
                  <div className={styles.headerLeft}>
                    <div className={styles.periodName}>{bill.period}</div>
                    <div className={styles.dateMeta}>
                      Billed {formatDate(bill.billingDate)} · {formatConsumption(bill.consumption)}
                    </div>
                  </div>

                  <div className={styles.headerRight}>
                    <span className={styles.billTotal}>{formatCurrency(bill.totalAmount)}</span>
                    <StatusBadge status={bill.status} size="sm" />
                    
                    <div className={`${styles.chevron} ${isExpanded ? styles.chevronRotated : ''}`}>
                      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                        <path
                          d="M5 7.5L10 12.5L15 7.5"
                          stroke="var(--color-text-secondary)"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </div>
                  </div>
                </div>

                {isExpanded && (
                  <div className={styles.expandedSection}>
                    <div className={styles.expandedDivider} />

                    <div className={styles.expandedContent}>
                      <div className={styles.tierSection}>
                        <div className={styles.tierBarTrack}>
                          {bill.tiers.map((t, idx) => {
                            const pct = (t.units / bill.consumption) * 100;
                            const colors = ['#3B82F6', '#60A5FA', '#93C5FD', '#FBBF24'];
                            return (
                              <div
                                key={idx}
                                className={styles.tierBarSlice}
                                style={{
                                  width: `${pct}%`,
                                  backgroundColor: colors[idx % colors.length],
                                }}
                              />
                            );
                          })}
                        </div>
                      </div>

                      <div className={styles.itemsList}>
                        {bill.tiers.map((t, idx) => (
                          <div key={idx} className={styles.itemRow}>
                            <span className={styles.itemLabel}>
                              {t.name} ({t.units} m³ @ {t.ratePerUnit} RWF)
                            </span>
                            <span className={styles.itemVal}>{formatCurrency(t.cost)}</span>
                          </div>
                        ))}
                        <div className={styles.itemRow}>
                          <span className={styles.itemLabel}>Monthly Service Charge</span>
                          <span className={styles.itemVal}>{formatCurrency(bill.serviceCharge)}</span>
                        </div>
                      </div>

                      <div className={styles.footerRow}>
                        {bill.status === 'paid' ? (
                          <div className={styles.paidMeta}>
                            <span>Paid via MoMo · Ref: {bill.transactionRef}</span>
                          </div>
                        ) : bill.status === 'review' ? (
                          <div className={styles.reviewNotice}>
                            <span>Under review by field officer</span>
                          </div>
                        ) : (
                          <div className={styles.unpaidAction}>
                            <span className={styles.dueNotice}>Due {formatDate(bill.dueDate)}</span>
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate('/payment');
                              }}
                            >
                              Pay Now
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

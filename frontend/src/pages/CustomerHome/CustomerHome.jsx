/**
 * @file CustomerHome.jsx
 * @description Screen 2: Customer Home Dashboard for WASAC Smart Water Billing Platform.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../../components/Card/Card';
import Button from '../../components/Button/Button';
import StatusBadge from '../../components/StatusBadge/StatusBadge';
import SkeletonLoader from '../../components/SkeletonLoader/SkeletonLoader';
import { mockCurrentCustomer } from '../../data/customers';
import { mockBills } from '../../data/bills';
import { getGreeting, formatCurrency, formatDate, formatConsumption } from '../../utils/format';
import styles from './CustomerHome.module.css';

export default function CustomerHome() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);

  const customer = mockCurrentCustomer;
  const latestBill = mockBills[0];
  const recentBills = mockBills.slice(0, 3);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1200);
    return () => clearTimeout(timer);
  }, []);

  const todayStr = new Date().toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className={styles.container}>
      <div className={styles.bgDecoration} aria-hidden="true">
        <svg viewBox="0 0 1000 300" fill="none" preserveAspectRatio="none">
          <path
            d="M0,160 C320,300 420,0 1000,160 L1000,0 L0,0 Z"
            fill="rgba(59, 130, 246, 0.04)"
          />
        </svg>
      </div>

      <div className={styles.inner}>
        <header className={styles.header}>
          {loading ? (
            <div className={styles.skeletonHeader}>
              <SkeletonLoader width="140px" height="14px" />
              <SkeletonLoader width="260px" height="32px" />
              <SkeletonLoader width="200px" height="16px" />
            </div>
          ) : (
            <>
              <span className={styles.dateLabel}>{todayStr}</span>
              <h1 className={styles.greeting}>
                {getGreeting()}, {customer.name.split(' ')[0]}
              </h1>
              <p className={styles.accountMeta}>
                Account <span className={styles.accountNumber}>{customer.accountNumber}</span> · {customer.district}
              </p>
            </>
          )}
        </header>

        <section className={styles.summarySection} aria-label="Account Summary">
          {loading ? (
            <div className={styles.summaryGrid}>
              <div className={styles.skeletonCard}><SkeletonLoader height="130px" borderRadius="var(--radius-lg)" /></div>
              <div className={styles.skeletonCard}><SkeletonLoader height="130px" borderRadius="var(--radius-lg)" /></div>
              <div className={styles.skeletonCard}><SkeletonLoader height="130px" borderRadius="var(--radius-lg)" /></div>
            </div>
          ) : (
            <div className={styles.summaryScroll}>
              <Card variant="default" padding="md" className={styles.summaryCard}>
                <div className={styles.cardHeader}>
                  <span className={styles.cardLabel}>Last Reading</span>
                  <span className={styles.indicatorDot} />
                </div>
                <div className={styles.cardMainValue}>
                  {customer.previousReading.toLocaleString()} <span className={styles.unit}>m³</span>
                </div>
                <div className={styles.cardFootnote}>
                  Recorded {formatDate(customer.lastReadingDate)}
                </div>
              </Card>

              <Card variant="accent" padding="md" className={styles.summaryCard}>
                <div className={styles.cardHeader}>
                  <span className={styles.cardLabel}>Monthly Estimate</span>
                  <span className={styles.tagEstimate}>Sept</span>
                </div>
                <div className={`${styles.cardMainValue} ${styles.accentValue}`}>
                  {formatCurrency(latestBill.totalAmount)}
                </div>
                <div className={styles.cardFootnote}>
                  Based on {formatConsumption(latestBill.consumption)}
                </div>
              </Card>

              <Card variant="default" padding="md" className={styles.summaryCard}>
                <div className={styles.cardHeader}>
                  <span className={styles.cardLabel}>Account Status</span>
                  <StatusBadge status={customer.accountStatus} size="sm" />
                </div>
                <div className={styles.cardMainValue}>
                  {customer.accountStatus === 'current' ? (
                    <span className={styles.statusCurrentText}>Up to date</span>
                  ) : (
                    <span className={styles.statusDueText}>{formatCurrency(customer.outstandingBalance)}</span>
                  )}
                </div>
                <div className={styles.cardFootnote}>
                  Meter ID: {customer.meterID}
                </div>
              </Card>
            </div>
          )}
        </section>

        <section className={styles.actionsSection}>
          <div className={styles.actionCard}>
            <div className={styles.actionInfo}>
              <h2 className={styles.actionTitle}>Ready for your reading?</h2>
              <p className={styles.actionDesc}>
                Take a quick photo of your water meter to calculate your digital bill.
              </p>
            </div>
            <div className={styles.actionButtons}>
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={() => navigate('/submit/camera')}
              >
                Start Meter Reading
              </Button>
              <Button
                variant="secondary"
                size="md"
                fullWidth
                onClick={() => navigate('/history')}
              >
                View Bill History
              </Button>
            </div>
          </div>
        </section>

        <section className={styles.recentSection}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>Recent Activity</h2>
            <button
              type="button"
              className={styles.viewAllBtn}
              onClick={() => navigate('/history')}
            >
              See all
            </button>
          </div>

          {loading ? (
            <div className={styles.skeletonList}>
              <SkeletonLoader height="56px" borderRadius="var(--radius-md)" />
              <SkeletonLoader height="56px" borderRadius="var(--radius-md)" />
            </div>
          ) : (
            <Card variant="default" padding="none" className={styles.recentList}>
              {recentBills.map((bill, index) => (
                <div
                  key={bill.id}
                  className={`${styles.recentRow} ${
                    index < recentBills.length - 1 ? styles.rowBorder : ''
                  }`}
                  onClick={() => navigate('/history')}
                  role="button"
                  tabIndex={0}
                >
                  <div className={styles.rowLeft}>
                    <div className={styles.periodName}>{bill.period}</div>
                    <div className={styles.periodMeta}>
                      {formatConsumption(bill.consumption)} · {formatDate(bill.billingDate)}
                    </div>
                  </div>
                  <div className={styles.rowRight}>
                    <span className={styles.rowAmount}>{formatCurrency(bill.totalAmount)}</span>
                    <StatusBadge status={bill.status} size="sm" />
                  </div>
                </div>
              ))}
            </Card>
          )}
        </section>
      </div>
    </div>
  );
}

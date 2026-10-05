/**
 * @file BillDisplay.jsx
 * @description Screen 5: Digital Bill & Receipt for WASAC Smart Water Billing Platform.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../../components/PageHeader/PageHeader';
import ProgressStep from '../../components/ProgressStep/ProgressStep';
import Card from '../../components/Card/Card';
import Button from '../../components/Button/Button';
import StatusBadge from '../../components/StatusBadge/StatusBadge';
import { mockBills } from '../../data/bills';
import { mockCurrentCustomer } from '../../data/customers';
import { formatCurrency, formatDate, formatConsumption } from '../../utils/format';
import styles from './BillDisplay.module.css';

export default function BillDisplay() {
  const navigate = useNavigate();
  const [isAnomaly, setIsAnomaly] = useState(false);
  const [smsRequested, setSmsRequested] = useState(false);

  const bill = mockBills[0];
  const customer = mockCurrentCustomer;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className={styles.container}>
      <PageHeader
        title="Digital Bill"
        backHref="/home"
        backLabel="Home"
      />

      <div className={styles.inner}>
        <div className={styles.progressWrap}>
          <ProgressStep currentStep={3} totalSteps={4} label="Digital Bill" />
        </div>

        <div className={styles.demoToggleRow}>
          <button
            type="button"
            className={styles.demoPill}
            onClick={() => setIsAnomaly(!isAnomaly)}
          >
            {isAnomaly ? 'Showing Anomaly Review Mode · Click to view standard bill' : 'Click to simulate Anomaly Review state'}
          </button>
        </div>

        {isAnomaly ? (
          <div className={styles.anomalyCard}>
            <div className={styles.anomalyIconWrap}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke="var(--color-warning)" strokeWidth="2" />
                <path d="M12 6V12L16 14" stroke="var(--color-warning)" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </div>

            <h1 className={styles.anomalyHeading}>Your reading is under review</h1>

            <p className={styles.anomalyText}>
              Your submitted reading shows a higher consumption than usual for this billing period. A WASAC officer has been assigned to verify the meter reading to ensure your billing is accurate.
            </p>

            <div className={styles.reviewMetaBox}>
              <div className={styles.reviewMetaRow}>
                <span className={styles.metaLabel}>Estimated review time</span>
                <span className={styles.metaValue}>24–48 hours</span>
              </div>
              <div className={styles.reviewMetaRow}>
                <span className={styles.metaLabel}>Account</span>
                <span className={styles.metaValue}>{customer.accountNumber}</span>
              </div>
              <div className={styles.reviewMetaRow}>
                <span className={styles.metaLabel}>Meter ID</span>
                <span className={styles.metaValue}>{customer.meterID}</span>
              </div>
            </div>

            <div className={styles.smsActionArea}>
              {smsRequested ? (
                <div className={styles.smsConfirmed}>
                  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <circle cx="10" cy="10" r="9" stroke="var(--color-accent)" strokeWidth="2" />
                    <path d="M6 10L9 13L14 7" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span>SMS alert active for {customer.phone}</span>
                </div>
              ) : (
                <Button
                  variant="secondary"
                  size="md"
                  fullWidth
                  onClick={() => setSmsRequested(true)}
                >
                  Notify me by SMS when verified
                </Button>
              )}
            </div>

            <Button
              variant="ghost"
              size="md"
              fullWidth
              onClick={() => navigate('/home')}
            >
              Return to Dashboard
            </Button>
          </div>
        ) : (
          <div className={styles.billContent}>
            <div className={styles.billTitleBlock}>
              <div className={styles.titleTop}>
                <h1 className={styles.billMainHeading}>Your bill is ready</h1>
                <StatusBadge status="unpaid" size="md" />
              </div>
              <p className={styles.billingPeriodText}>
                Billing Cycle: {bill.period} · Due by {formatDate(bill.dueDate)}
              </p>
            </div>

            <div className={styles.receiptCard}>
              <div className={styles.receiptHeader}>
                <div>
                  <span className={styles.corpTitle}>WASAC Utility Bill</span>
                  <div className={styles.accountRef}>{customer.name} · {customer.accountNumber}</div>
                </div>
                <div className={styles.consumptionBadge}>
                  <span className={styles.consumptionNum}>{bill.consumption}</span>
                  <span className={styles.consumptionUnit}>m³ Total</span>
                </div>
              </div>

              <div className={styles.tierSection}>
                <div className={styles.tierBarHeader}>
                  <span className={styles.tierBarTitle}>Tariff Tier Breakdown</span>
                  <span className={styles.tierBarSub}>{bill.consumption} m³ billed</span>
                </div>

                <div className={styles.stackedBarTrack}>
                  {bill.tiers.map((t, idx) => {
                    const pct = (t.units / bill.consumption) * 100;
                    const tierColors = ['#0D9488', '#14B8A6', '#2DD4BF', '#F59E0B'];
                    return (
                      <div
                        key={idx}
                        className={styles.tierSegment}
                        style={{
                          width: `${pct}%`,
                          backgroundColor: tierColors[idx % tierColors.length],
                        }}
                        title={`${t.name}: ${t.units} m³`}
                      />
                    );
                  })}
                </div>

                <div className={styles.tierLegendRow}>
                  {bill.tiers.map((t, idx) => {
                    const dotColors = ['#0D9488', '#14B8A6', '#2DD4BF', '#F59E0B'];
                    return (
                      <div key={idx} className={styles.legendItem}>
                        <span
                          className={styles.legendDot}
                          style={{ backgroundColor: dotColors[idx % dotColors.length] }}
                        />
                        <span className={styles.legendText}>
                          {t.name} ({t.units} m³)
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className={styles.chargeList}>
                {bill.tiers.map((t, idx) => (
                  <div key={idx} className={styles.chargeRow}>
                    <div className={styles.chargeDesc}>
                      <span className={styles.chargeName}>{t.name}</span>
                      <span className={styles.chargeCalc}>
                        {t.units} m³ × {t.ratePerUnit} RWF
                      </span>
                    </div>
                    <span className={styles.chargeAmount}>
                      {formatCurrency(t.cost)}
                    </span>
                  </div>
                ))}

                <div className={styles.chargeRow}>
                  <div className={styles.chargeDesc}>
                    <span className={styles.chargeName}>Monthly Service Fee</span>
                    <span className={styles.chargeCalc}>Standard infrastructure charge</span>
                  </div>
                  <span className={styles.chargeAmount}>
                    {formatCurrency(bill.serviceCharge)}
                  </span>
                </div>

                <div className={styles.receiptDivider} />

                <div className={styles.totalRow}>
                  <div>
                    <span className={styles.totalLabel}>Total Amount Due</span>
                    <span className={styles.totalSub}>Tax and fees included</span>
                  </div>
                  <span className={styles.grandTotal}>
                    {formatCurrency(bill.totalAmount)}
                  </span>
                </div>
              </div>
            </div>

            <div className={styles.billActions}>
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={() => navigate('/payment')}
              >
                Pay with Mobile Money
              </Button>

              <Button
                variant="secondary"
                size="md"
                fullWidth
                onClick={handlePrint}
              >
                Save Receipt
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

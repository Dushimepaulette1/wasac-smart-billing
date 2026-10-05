/**
 * @file Payment.jsx
 * @description Screen 7: Mobile Money Payment flow for WASAC.
 */

import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import PageHeader from '../../components/PageHeader/PageHeader';
import ProgressStep from '../../components/ProgressStep/ProgressStep';
import Card from '../../components/Card/Card';
import Button from '../../components/Button/Button';
import LoadingState from '../../components/LoadingState/LoadingState';
import { mockBills } from '../../data/bills';
import { mockCurrentCustomer } from '../../data/customers';
import { formatCurrency } from '../../utils/format';
import styles from './Payment.module.css';

export default function Payment() {
  const navigate = useNavigate();
  const customer = mockCurrentCustomer;
  const bill = mockBills[0];

  const [phase, setPhase] = useState('summary');
  const [phone, setPhone] = useState(customer.phone);
  const [txRef, setTxRef] = useState('');

  const handlePay = (e) => {
    e.preventDefault();
    setPhase('processing');

    setTimeout(() => {
      const now = new Date();
      const datePart = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
      const generatedRef = `TXN-${datePart}-${Math.floor(100000 + Math.random() * 900000)}`;
      setTxRef(generatedRef);
      setPhase('success');
    }, 2200);
  };

  return (
    <div className={`${styles.container} ${phase === 'success' ? styles.containerSuccess : ''}`}>
      {phase === 'processing' && (
        <LoadingState
          variant="fullscreen"
          message="Sending payment request to your phone"
          submessage="Please check your phone screen to approve the Mobile Money prompt"
        />
      )}

      {phase === 'summary' && (
        <>
          <PageHeader
            title="Mobile Money Payment"
            backHref="/bill"
            backLabel="Back to Bill"
          />

          <div className={styles.inner}>
            <div className={styles.progressWrap}>
              <ProgressStep currentStep={4} totalSteps={4} label="Payment" />
            </div>

            <form onSubmit={handlePay} className={styles.paymentStack}>
              <Card variant="elevated" padding="lg" className={styles.summaryCard}>
                <div className={styles.summaryTop}>
                  <span className={styles.amountLabel}>Total Payable Amount</span>
                  <span className={styles.billingCycle}>{bill.period} Cycle</span>
                </div>
                <div className={styles.totalPayable}>
                  {formatCurrency(bill.totalAmount)}
                </div>
                <div className={styles.summaryFooter}>
                  <span>Customer: {customer.name}</span>
                  <span>Meter: {customer.meterID}</span>
                </div>
              </Card>

              <div className={styles.inputGroupCard}>
                <h2 className={styles.sectionHeading}>Mobile Money Details</h2>
                <p className={styles.phoneHint}>
                  Your payment authorization prompt will be sent immediately to this registered number.
                </p>

                <div className={styles.phoneInputContainer}>
                  <label htmlFor="momo-phone" className={styles.fieldLabel}>
                    Phone Number
                  </label>
                  <div className={styles.phoneRow}>
                    <span className={styles.countryCode}>+250</span>
                    <input
                      id="momo-phone"
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      className={styles.telInput}
                      placeholder="078 000 0000"
                      required
                    />
                  </div>
                </div>

                <div className={styles.momoProviders}>
                  <span className={styles.providerTag}>MTN MoMo</span>
                  <span className={styles.providerTag}>Airtel Money</span>
                </div>
              </div>

              <div className={styles.actionArea}>
                <Button
                  variant="primary"
                  size="lg"
                  fullWidth
                  type="submit"
                >
                  Send Payment Request
                </Button>

                <p className={styles.securityNote}>
                  Secured by WASAC Digital Utility Services · Instant settlement
                </p>
              </div>
            </form>
          </div>
        </>
      )}

      {phase === 'success' && (
        <div className={styles.successScreen}>
          <div className={styles.successCard}>
            <div className={styles.checkCircle}>
              <svg className={styles.checkSvg} viewBox="0 0 52 52">
                <circle
                  className={styles.checkCircleTrack}
                  cx="26"
                  cy="26"
                  r="23"
                  fill="none"
                />
                <path
                  className={styles.checkPath}
                  fill="none"
                  d="M14 27l7 7 16-16"
                />
              </svg>
            </div>

            <div className={styles.successHeadingBlock}>
              <h1 className={styles.successTitle}>Payment request sent</h1>
              <p className={styles.successDesc}>
                Check your phone screen now. Enter your Mobile Money PIN to complete the transaction.
              </p>
            </div>

            <div className={styles.receiptBox}>
              <div className={styles.receiptRow}>
                <span className={styles.receiptKey}>Transaction Ref</span>
                <span className={styles.receiptValMono}>{txRef}</span>
              </div>
              <div className={styles.receiptRow}>
                <span className={styles.receiptKey}>Amount Requested</span>
                <span className={styles.receiptVal}>{formatCurrency(bill.totalAmount)}</span>
              </div>
              <div className={styles.receiptRow}>
                <span className={styles.receiptKey}>Recipient Number</span>
                <span className={styles.receiptVal}>+250 {phone}</span>
              </div>
            </div>

            <p className={styles.smsNotice}>
              An SMS confirmation receipt has been sent to your phone.
            </p>

            <div className={styles.successButtons}>
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={() => navigate('/home')}
              >
                Return to Dashboard
              </Button>
              <Button
                variant="ghost"
                size="md"
                fullWidth
                onClick={() => navigate('/history')}
              >
                View Bill History
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

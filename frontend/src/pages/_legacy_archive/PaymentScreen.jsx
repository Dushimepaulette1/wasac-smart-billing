import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import styles from './PaymentScreen.module.css';

const API = 'http://localhost:8000';

export default function PaymentScreen() {
  const navigate = useNavigate();
  const { state } = useLocation();

  const bill = state?.bill;
  const amount = bill?.bill_amount ?? 0;
  const billId = bill?.bill_id;

  const [phone, setPhone] = useState('+250788123456');
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const [txId, setTxId] = useState('');

  const handlePay = async () => {
    setStatus('loading');

    // Simulate MTN Mobile Money sandbox — 2 second delay
    await new Promise(r => setTimeout(r, 2000));

    try {
      if (billId) {
        await fetch(`${API}/bills/${billId}/pay`, { method: 'POST' });
      }
      const generatedTx = `MOMO-${Date.now().toString().slice(-8)}-RW`;
      setTxId(generatedTx);
      setStatus('success');
    } catch {
      setStatus('error');
    }
  };

  if (status === 'success') {
    return (
      <div className={styles.container}>
        <div className={styles.successCard}>
          <div className={styles.successIcon}>✅</div>
          <h2 className={styles.successTitle}>Payment Successful!</h2>
          <p className={styles.successAmount}>
            RWF {amount.toLocaleString('en-RW', { maximumFractionDigits: 0 })}
          </p>
          <div className={styles.txRow}>
            <span className={styles.txLabel}>Transaction ID</span>
            <span className={styles.txId}>{txId}</span>
          </div>
          <p className={styles.smsNote}>
            📱 An SMS receipt has been sent to {phone}
          </p>
          <button
            className="btn btn-primary"
            style={{ marginTop: 20 }}
            onClick={() => navigate('/camera')}
          >
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.section}>
        <h2 className={styles.title}>Mobile Money Payment</h2>
        <p className={styles.subtitle}>MTN Mobile Money · Sandbox Mode</p>
      </div>

      <div className={styles.summaryCard}>
        <span className={styles.summaryLabel}>Amount Due</span>
        <span className={styles.summaryAmount}>
          RWF {amount.toLocaleString('en-RW', { maximumFractionDigits: 0 })}
        </span>
      </div>

      <div className={styles.formCard}>
        <label className={styles.fieldLabel}>Mobile Money Number</label>
        <input
          className={styles.phoneInput}
          type="tel"
          value={phone}
          onChange={e => setPhone(e.target.value)}
          placeholder="+250 7XX XXX XXX"
        />
        <p className={styles.hint}>
          A USSD prompt will be sent to this number to confirm payment.
        </p>
      </div>

      {status === 'error' && (
        <div className={styles.errorBox}>
          ⚠️ Payment failed. Please try again.
        </div>
      )}

      <div className={styles.footer}>
        {status === 'loading' ? (
          <div className="spinner-wrap">
            <div className="spinner" />
            <span>Processing payment via MTN Mobile Money…</span>
          </div>
        ) : (
          <>
            <button className="btn btn-green" onClick={handlePay}>
              💳 Pay Now
            </button>
            <button className="btn btn-ghost" onClick={() => navigate(-1)}>
              ← Back to Bill
            </button>
          </>
        )}
      </div>
    </div>
  );
}

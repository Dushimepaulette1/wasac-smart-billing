import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import TariffBreakdown from '../components/TariffBreakdown';
import styles from './BillDisplay.module.css';

export default function BillDisplay() {
  const navigate = useNavigate();
  const { state } = useLocation();

  const bill = state?.bill;

  if (!bill) {
    return (
      <div className={styles.container}>
        <div className="card">
          <p>No bill data found. <button className="btn btn-ghost" onClick={() => navigate('/camera')}>Start over</button></p>
        </div>
      </div>
    );
  }

  const { consumption_m3, tariff_breakdown, bill_amount, anomaly_flagged, bill_id } = bill;
  const today = new Date();
  const period = today.toLocaleDateString('en-RW', { month: 'long', year: 'numeric' });

  const handlePrint = () => window.print();

  return (
    <div className={styles.container}>
      <div className={styles.billCard}>
        <div className={styles.billHeader}>
          <div className={styles.logo}>💧 WASAC</div>
          <div className={styles.billMeta}>
            <span className={styles.billTitle}>Water Bill</span>
            <span className={styles.billPeriod}>{period}</span>
            {bill_id && <span className={styles.billId}>Bill #{bill_id}</span>}
          </div>
        </div>

        {anomaly_flagged && (
          <div className={styles.anomalyAlert}>
            ⚠️ Unusual consumption detected. This bill is under review by WASAC.
          </div>
        )}

        <div className={styles.summaryRow}>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Consumption</span>
            <span className={styles.summaryValue}>{consumption_m3?.toFixed(1)} m³</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Status</span>
            <span className={`badge ${anomaly_flagged ? 'badge-yellow' : 'badge-green'}`}>
              {anomaly_flagged ? 'Under Review' : 'Validated'}
            </span>
          </div>
        </div>

        {tariff_breakdown && (
          <TariffBreakdown breakdown={tariff_breakdown} />
        )}

        <div className={styles.totalRow}>
          <span className={styles.totalLabel}>Total Amount Due</span>
          <span className={styles.totalAmount}>
            RWF {bill_amount?.toLocaleString('en-RW', { maximumFractionDigits: 0 })}
          </span>
        </div>
      </div>

      <div className={styles.actions}>
        <button
          className="btn btn-green"
          onClick={() => navigate('/payment', { state: { bill } })}
        >
          💳 Pay with Mobile Money
        </button>
        <button className="btn btn-outline" onClick={handlePrint}>
          🖨️ Download Receipt
        </button>
        <button className="btn btn-ghost" onClick={() => navigate('/camera')}>
          Submit Another Reading
        </button>
      </div>
    </div>
  );
}

import React from 'react';
import styles from './TariffBreakdown.module.css';

const TIERS = [
  { key: 'tier1', label: 'Tier 1', range: '0–5 m³', rate: 350 },
  { key: 'tier2', label: 'Tier 2', range: '6–15 m³', rate: 530 },
  { key: 'tier3', label: 'Tier 3', range: '16–30 m³', rate: 791 },
  { key: 'tier4', label: 'Tier 4', range: '>30 m³', rate: 1000 },
];

export default function TariffBreakdown({ breakdown }) {
  return (
    <div className={styles.container}>
      <h3 className={styles.heading}>Tariff Breakdown</h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Tier</th>
            <th>Range</th>
            <th>Units</th>
            <th>Rate</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {TIERS.map(({ key, label, range, rate }) => {
            const units = breakdown[`${key}_units`] ?? 0;
            const amount = breakdown[`${key}_amount`] ?? 0;
            if (units <= 0) return null;
            return (
              <tr key={key}>
                <td>{label}</td>
                <td className={styles.dim}>{range}</td>
                <td>{units.toFixed(1)}</td>
                <td className={styles.dim}>{rate}/m³</td>
                <td className={styles.amount}>{amount.toLocaleString('en-RW', { maximumFractionDigits: 0 })}</td>
              </tr>
            );
          })}
          <tr className={styles.serviceRow}>
            <td colSpan={4}>Service charge</td>
            <td className={styles.amount}>
              {(breakdown.service_charge ?? 1000).toLocaleString('en-RW', { maximumFractionDigits: 0 })}
            </td>
          </tr>
        </tbody>
      </table>
      <p className={styles.currency}>All amounts in RWF</p>
    </div>
  );
}

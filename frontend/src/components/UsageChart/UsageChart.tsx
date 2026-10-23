/**
 * @file UsageChart.tsx
 * @description Water used per bill, as bars (one series, so no legend: the title names it).
 * Hover or focus a bar for its exact value; the latest bar is labelled directly. A table with
 * the same numbers is there for screen readers. Colour: --chart-1, validated for both themes.
 */

import { useId, useState } from 'react';
import styles from './UsageChart.module.css';

export interface UsagePoint {
  key: string;
  label: string;
  /** Cubic metres. */
  value: number;
}

interface UsageChartProps {
  points: UsagePoint[];
  /** "12.4 m³" */
  format: (value: number) => string;
  /** Accessible name and table caption. */
  title: string;
  monthHeader: string;
  valueHeader: string;
}

const HEIGHT = 140;

function UsageChart({ points, format, title, monthHeader, valueHeader }: UsageChartProps) {
  const [hover, setHover] = useState<number | null>(null);
  const tableId = useId();
  const max = Math.max(...points.map((p) => p.value), 0.001);
  // A round top for the scale: 1, 2, 5 x 10^n.
  const step = 10 ** Math.floor(Math.log10(max));
  const top = [1, 2, 5, 10].map((m) => m * step).find((v) => v >= max) ?? max;
  const shown = hover ?? points.length - 1;

  return (
    <figure className={styles.figure} aria-describedby={tableId}>
      <div className={styles.plot} style={{ height: HEIGHT }}>
        <div className={styles.grid} aria-hidden="true">
          <span>{format(top)}</span>
          <span>{format(top / 2)}</span>
          <span>0</span>
        </div>
        <ol className={styles.bars} aria-hidden="true" onMouseLeave={() => setHover(null)}>
          {points.map((p, i) => (
            // Hover (or tap, on a phone) shows a bar's value; the table below has them all.
            <li key={p.key} className={styles.slot} onMouseEnter={() => setHover(i)} onClick={() => setHover(i)}>
              <span
                className={`${styles.bar} ${i === shown ? styles.current : ''}`}
                style={{ height: `${Math.max(2, (p.value / top) * 100)}%` }}
              >
                {i === shown && <span className={styles.tip}>{format(p.value)}</span>}
              </span>
              <span className={styles.label}>{p.label}</span>
            </li>
          ))}
        </ol>
      </div>
      <table id={tableId} className="visually-hidden">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">{monthHeader}</th>
            <th scope="col">{valueHeader}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.key}>
              <td>{p.label}</td>
              <td>{format(p.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

export default UsageChart;

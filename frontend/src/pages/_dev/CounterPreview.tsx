/**
 * @file CounterPreview.tsx
 * @description Development-only page for reviewing MeterCounter states.
 * Registered at /dev/counter in development builds only; it is not
 * part of the product, so its strings are not translated.
 */

import { useState } from 'react';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import { normalizeReading, cellsToDigits } from '../../utils/reading';
import styles from './CounterPreview.module.css';

const LABELS = {
  reading: 'Meter reading',
  cubicMetres: 'm³',
  litres: 'litres',
  cubicMetresLong: 'cubic metres',
};

function EditableExample({ raw, autoFocus = false }: { raw: string; autoFocus?: boolean }) {
  const initial = normalizeReading(raw);
  const [cells, setCells] = useState(initial.cells);
  return (
    <>
      <p className="text-small text-secondary num">
        Digit reader returned "{raw}" → {initial.needsCheck ? 'needs check, opened for typing' : `padded to ${cellsToDigits(initial.cells)}`}
      </p>
      <MeterCounter
        cells={cells}
        labels={LABELS}
        mode="edit"
        showValue
        autoFocus={autoFocus}
        onChange={setCells}
      />
    </>
  );
}

function CounterPreview() {
  return (
    <main className={styles.page}>
      <h1 className="text-title">Meter counter</h1>

      <section className={styles.section} data-shot="display">
        <h2 className="text-lead">Display</h2>
        <p className="text-small text-secondary num">Reading "02813450"</p>
        <MeterCounter cells={normalizeReading('02813450').cells} labels={LABELS} />
      </section>

      <section className={styles.section} data-shot="display-paper">
        <h2 className="text-lead">Display on a Paper surface, with value</h2>
        <div className={styles.paper}>
          <MeterCounter cells={normalizeReading('02813450').cells} labels={LABELS} showValue />
        </div>
      </section>

      <section className={styles.section} data-shot="edit">
        <h2 className="text-lead">Edit</h2>
        <EditableExample raw="02813450" />
      </section>

      <section className={styles.section} data-shot="short">
        <h2 className="text-lead">Short reading (dropped leading zeros)</h2>
        <EditableExample raw="565846" />
      </section>

      <section className={styles.section} data-shot="needs-check">
        <h2 className="text-lead">Wrong length, opened for checking</h2>
        <EditableExample raw="1234567890" />
      </section>

      <section className={`${styles.section} staff`} data-shot="small">
        <h2 className="text-lead">Small (staff review pane)</h2>
        <MeterCounter cells={normalizeReading('01971000').cells} labels={LABELS} size="small" />
      </section>
    </main>
  );
}

export default CounterPreview;

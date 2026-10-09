/**
 * @file format.ts
 * @description Formatting utility functions for the WASAC Smart Billing Platform.
 * Covers currency, dates, greetings, and meter consumption display.
 * Used by the staff screens that predate the redesign.
 */

/**
 * Formats a numeric amount as Rwandan Francs.
 * Returns Formatted string e.g. 'RWF 34,650'
 */
export function formatCurrency(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) return 'RWF 0';
  const formatted = Math.round(amount).toLocaleString('en-US');
  return `RWF ${formatted}`;
}

/**
 * Formats an ISO date string to long format.
 * Returns e.g. '14 Sep 2025'
 */
export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  try {
    const date = new Date(dateString + 'T00:00:00');
    return date.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateString;
  }
}

/**
 * Formats an ISO date string to short month-year format.
 * Returns e.g. 'Sep 2025'
 */
export function formatDateShort(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  try {
    const date = new Date(dateString + 'T00:00:00');
    return date.toLocaleDateString('en-GB', {
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateString;
  }
}

/**
 * Returns a time-appropriate greeting based on the current hour.
 * Returns 'Good morning', 'Good afternoon', or 'Good evening'
 */
export function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 18) return 'Good afternoon';
  return 'Good evening';
}

/**
 * Formats a cubic meter consumption value for display.
 * Returns e.g. '56 m³'
 */
export function formatConsumption(m3: number | null | undefined): string {
  if (m3 === null || m3 === undefined || isNaN(m3)) return '0 m³';
  return `${Math.round(m3).toLocaleString('en-US')} m\u00B3`;
}

/**
 * Formats a meter reading number for display.
 * Returns e.g. '2,847 m³'
 */
export function formatReading(reading: number | null | undefined): string {
  if (reading === null || reading === undefined || isNaN(reading)) return '0 m³';
  return `${Number(reading).toLocaleString('en-US')} m\u00B3`;
}

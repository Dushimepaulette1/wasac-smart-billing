/**
 * @file format.js
 * @description Formatting utility functions for the WASAC Smart Billing Platform.
 * Covers currency, dates, greetings, and meter consumption display.
 */

/**
 * Formats a numeric amount as Rwandan Francs.
 * @param {number} amount - The amount in RWF
 * @returns {string} Formatted string e.g. 'RWF 34,650'
 */
export function formatCurrency(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) return 'RWF 0';
  const formatted = Math.round(amount).toLocaleString('en-US');
  return `RWF ${formatted}`;
}

/**
 * Formats an ISO date string to long format.
 * @param {string} dateString - ISO date string e.g. '2025-09-14'
 * @returns {string} e.g. '14 Sep 2025'
 */
export function formatDate(dateString) {
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
 * @param {string} dateString - ISO date string e.g. '2025-09-14'
 * @returns {string} e.g. 'Sep 2025'
 */
export function formatDateShort(dateString) {
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
 * @returns {string} 'Good morning', 'Good afternoon', or 'Good evening'
 */
export function getGreeting() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 18) return 'Good afternoon';
  return 'Good evening';
}

/**
 * Formats a cubic meter consumption value for display.
 * @param {number} m3 - Consumption in cubic meters
 * @returns {string} e.g. '56 m³'
 */
export function formatConsumption(m3) {
  if (m3 === null || m3 === undefined || isNaN(m3)) return '0 m³';
  return `${Math.round(m3).toLocaleString('en-US')} m\u00B3`;
}

/**
 * Formats a meter reading number for display.
 * @param {number} reading - Meter reading in cubic meters
 * @returns {string} e.g. '2,847 m³'
 */
export function formatReading(reading) {
  if (reading === null || reading === undefined || isNaN(reading)) return '0 m³';
  return `${Number(reading).toLocaleString('en-US')} m\u00B3`;
}

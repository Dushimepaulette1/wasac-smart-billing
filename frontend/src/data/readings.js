/**
 * @file readings.js
 * @description Mock meter reading data — consumption values pending calibration.
 */

export const mockReadings = [
  { id: 'rdg-006', period: 'September 2025', reading: 2847, previousReading: 2791, consumption: 56, readingDate: '2025-09-14', status: 'pending', submittedBy: 'customer', confidence: 88 },
  { id: 'rdg-005', period: 'August 2025', reading: 2791, previousReading: 2736, consumption: 55, readingDate: '2025-08-15', status: 'confirmed', submittedBy: 'customer', confidence: 97 },
  { id: 'rdg-004', period: 'July 2025', reading: 2736, previousReading: 2678, consumption: 58, readingDate: '2025-07-13', status: 'confirmed', submittedBy: 'officer', confidence: 99 },
  { id: 'rdg-003', period: 'June 2025', reading: 2678, previousReading: 2621, consumption: 57, readingDate: '2025-06-16', status: 'confirmed', submittedBy: 'customer', confidence: 95 },
  { id: 'rdg-002', period: 'May 2025', reading: 2621, previousReading: 2558, consumption: 63, readingDate: '2025-05-14', status: 'anomaly', submittedBy: 'customer', confidence: 52 },
  { id: 'rdg-001', period: 'April 2025', reading: 2558, previousReading: 2502, consumption: 56, readingDate: '2025-04-15', status: 'confirmed', submittedBy: 'officer', confidence: 99 },
];

export const mockPredictedReading = {
  value: 2847,
  confidence: 92,
  previousReading: 2791,
  consumption: 56,
};

export const mockAnomalyReadings = [
  { id: 'anom-001', customerName: 'Nzeyimana Jean-Pierre', customerAddress: 'KN 12 Ave, Nyamirambo, Nyarugenge', meterID: 'MTR-NYA-003155', accountNumber: 'WAS-KIG-2018-03155', submittedReading: 1971, previousReading: 1843, consumption: 128, anomalyScore: 'Significantly above average', dateSubmitted: '2025-09-13' },
  { id: 'anom-002', customerName: 'Hakizimana Théogène', customerAddress: 'KK 88 Rd, Kanombe, Kicukiro', meterID: 'MTR-KIC-009312', accountNumber: 'WAS-KIG-2020-09312', submittedReading: 3495, previousReading: 3481, consumption: 14, anomalyScore: 'Below expected minimum', dateSubmitted: '2025-09-14' },
  { id: 'anom-003', customerName: 'Ingabire Soline', customerAddress: 'KG 211 St, Kimironko, Gasabo', meterID: 'MTR-GAS-006740', accountNumber: 'WAS-KIG-2022-06740', submittedReading: 1489, previousReading: 1402, consumption: 87, anomalyScore: 'Image quality uncertain', dateSubmitted: '2025-09-15' },
];

/**
 * @file customers.js
 * @description Mock customer data for WASAC Smart Billing Platform.
 * Contains 3 realistic Rwandan customer accounts and a reference to the
 * currently logged-in customer.
 */

/** @typedef {Object} Customer */
export const mockCustomers = [
  {
    id: 'cust-001',
    accountNumber: 'WAS-KIG-2019-04821',
    name: 'Uwimana Clarisse',
    phone: '0788245670',
    email: 'clarisse.uwimana@gmail.com',
    address: 'KG 547 St, Remera',
    district: 'Gasabo',
    meterID: 'MTR-GAS-004821',
    previousReading: 2791,
    lastReadingDate: '2025-08-15',
    accountStatus: 'current',
    outstandingBalance: 0,
  },
  {
    id: 'cust-002',
    accountNumber: 'WAS-KIG-2018-03155',
    name: 'Nzeyimana Jean-Pierre',
    phone: '0722193045',
    email: 'jp.nzeyimana@yahoo.fr',
    address: 'KN 12 Ave, Nyamirambo',
    district: 'Nyarugenge',
    meterID: 'MTR-NYA-003155',
    previousReading: 1843,
    lastReadingDate: '2025-08-14',
    accountStatus: 'outstanding',
    outstandingBalance: 47650,
  },
  {
    id: 'cust-003',
    accountNumber: 'WAS-KIG-2021-07740',
    name: 'Mukamana Espérance',
    phone: '0733872201',
    email: 'esperance.mukamana@outlook.com',
    address: 'KK 15 Rd, Gikondo',
    district: 'Kicukiro',
    meterID: 'MTR-KIC-007740',
    previousReading: 3218,
    lastReadingDate: '2025-08-16',
    accountStatus: 'current',
    outstandingBalance: 0,
  },
];

/**
 * The currently authenticated customer (first in the array).
 * Used throughout the app to simulate a logged-in session.
 */
export const mockCurrentCustomer = mockCustomers[0];

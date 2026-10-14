/**
 * @file household.tsx
 * @description Household pages need a signed-in household: this signs in the
 * fixtures' household (CUST001 / MTR001) for a test.
 */

import type { ReactNode } from 'react';
import { HouseholdProvider } from '../household/session';
import type { HouseholdAccount } from '../api/types';

export const TEST_ACCOUNT: HouseholdAccount = {
  customer_id: 'CUST001',
  name: 'Uwimana Jean Pierre',
  meter_id: 'MTR001',
  sector: 'Kacyiru',
  is_demo: false,
};

export function signInHousehold(accounts: HouseholdAccount[] = [TEST_ACCOUNT]): void {
  window.localStorage.setItem(
    'wasac.household',
    JSON.stringify({
      token: 'test-token',
      expiresAt: Date.now() / 1000 + 3600,
      phone: '+250788123456',
      accounts,
      customerId: accounts[0]?.customer_id ?? null,
    }),
  );
}

/** Wrap a household page: signed in as `account` (default TEST_ACCOUNT). */
export function TestHousehold({ children, account = TEST_ACCOUNT }: { children: ReactNode; account?: HouseholdAccount }) {
  signInHousehold([account]);
  return <HouseholdProvider>{children}</HouseholdProvider>;
}

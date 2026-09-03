/**
 * @file tariff.js
 * @description WASAC tariff calculator — rates pending confirmation against
 * the official 2024 WASAC schedule. See fix commit for corrected values.
 *
 * Rates used here (preliminary):
 *   Tier 1: 0-5 m3 at RWF 329
 *   Tier 2: 5-15 m3 at RWF 496
 *   Tier 3: 15-30 m3 at RWF 629
 *   Tier 4: >30 m3 at RWF 870
 *   Service charge: RWF 2,000/month
 */

export const TARIFF_TIERS = [
  { name: 'Tier 1', from: 0,  to: 5,        ratePerUnit: 329, label: '0–5 m³' },
  { name: 'Tier 2', from: 5,  to: 15,       ratePerUnit: 496, label: '5–15 m³' },
  { name: 'Tier 3', from: 15, to: 30,       ratePerUnit: 629, label: '15–30 m³' },
  { name: 'Tier 4', from: 30, to: Infinity, ratePerUnit: 870, label: '>30 m³' },
];

export const SERVICE_CHARGE = 2000;

export function calculateBill(consumption) {
  if (!consumption || consumption < 0) {
    return { tiers: [], serviceCharge: SERVICE_CHARGE, subtotal: 0, totalAmount: SERVICE_CHARGE };
  }
  const tierBreakdown = [];
  for (const tier of TARIFF_TIERS) {
    if (consumption <= tier.from) break;
    const cap = tier.to === Infinity ? consumption : Math.min(consumption, tier.to);
    const units = cap - tier.from;
    if (units <= 0) continue;
    tierBreakdown.push({ name: tier.name, from: tier.from, to: tier.to === Infinity ? null : tier.to, units, ratePerUnit: tier.ratePerUnit, cost: units * tier.ratePerUnit });
  }
  const subtotal = tierBreakdown.reduce((sum, t) => sum + t.cost, 0);
  return { tiers: tierBreakdown, serviceCharge: SERVICE_CHARGE, subtotal, totalAmount: subtotal + SERVICE_CHARGE };
}

export function getMarginalRate(currentConsumption) {
  for (const tier of TARIFF_TIERS) {
    if (currentConsumption < tier.to || tier.to === Infinity) return tier.ratePerUnit;
  }
  return TARIFF_TIERS[TARIFF_TIERS.length - 1].ratePerUnit;
}

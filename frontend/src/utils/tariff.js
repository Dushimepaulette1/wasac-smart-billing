/**
 * @file tariff.js
 * @description WASAC tariff calculation utilities.
 *
 * Official WASAC tiered tariff rates (2024 schedule):
 *   Tier 1:  0–5 m³   at RWF 350/m³
 *   Tier 2:  6–15 m³  at RWF 530/m³
 *   Tier 3:  16–30 m³ at RWF 791/m³
 *   Tier 4:  >30 m³   at RWF 1,000/m³
 *   Monthly service charge: RWF 1,000
 */

export const TARIFF_TIERS = [
  { name: 'Tier 1', from: 0,  to: 5,        ratePerUnit: 350,  label: '0–5 m³' },
  { name: 'Tier 2', from: 5,  to: 15,       ratePerUnit: 530,  label: '6–15 m³' },
  { name: 'Tier 3', from: 15, to: 30,       ratePerUnit: 791,  label: '16–30 m³' },
  { name: 'Tier 4', from: 30, to: Infinity, ratePerUnit: 1000, label: '>30 m³' },
];

export const SERVICE_CHARGE = 1000;

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

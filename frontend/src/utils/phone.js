/**
 * @file phone.js
 * @description Rwandan phone numbers as people write them:
 * "+250788123456" -> "078 812 3456". Anything else is returned unchanged.
 */

export function formatRwandanPhone(phone) {
  const digits = String(phone ?? '').replace(/\D/g, '');
  const local = digits.startsWith('250') && digits.length === 12 ? `0${digits.slice(3)}` : digits;
  if (/^07\d{8}$/.test(local)) return `${local.slice(0, 3)} ${local.slice(3, 6)} ${local.slice(6)}`;
  return String(phone ?? '');
}

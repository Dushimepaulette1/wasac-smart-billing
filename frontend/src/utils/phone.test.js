import { formatRwandanPhone } from './phone';

it.each([
  ['+250788123456', '078 812 3456'],
  ['250788123456', '078 812 3456'],
  ['0788123456', '078 812 3456'],
  ['+44 20 7946 0000', '+44 20 7946 0000'],
  [null, ''],
])('formats %s as %s', (input, expected) => {
  expect(formatRwandanPhone(input)).toBe(expected);
});

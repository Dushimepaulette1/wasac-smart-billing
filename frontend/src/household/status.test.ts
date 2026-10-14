import { parseUtc, readingIsWaiting, unreadCount } from './status';
import { makeFlag } from '../test/fixtures';

describe('household status', () => {
  it('reads backend times as UTC, not local time', () => {
    expect(parseUtc('2026-10-14T08:00:00')).toBe(Date.UTC(2026, 9, 14, 8));
    expect(parseUtc('2026-10-14T08:00:00Z')).toBe(Date.UTC(2026, 9, 14, 8));
  });

  it('knows when a reading is waiting for an officer', () => {
    expect(readingIsWaiting([makeFlag({ status: 'open', requires_staff_review: true })])).toBe(true);
    expect(readingIsWaiting([makeFlag({ status: 'resolved', requires_staff_review: true })])).toBe(false);
    expect(readingIsWaiting([makeFlag({ status: 'open', requires_staff_review: false })])).toBe(false);
  });

  it('counts messages created or decided since Messages was last opened', () => {
    const seen = Date.UTC(2026, 9, 14, 12);
    const flags = [
      makeFlag({ id: 1, anomaly_type: 'SPIKE', created_at: '2026-10-14T13:00:00' }), // new
      makeFlag({ id: 2, anomaly_type: 'SPIKE', created_at: '2026-10-14T09:00:00' }), // old
      makeFlag({
        id: 3,
        anomaly_type: 'MISREAD_SUSPECTED',
        created_at: '2026-10-14T09:00:00',
        resolved_at: '2026-10-14T14:00:00', // decided after: new again
      }),
      makeFlag({ id: 4, anomaly_type: 'NORMAL', created_at: '2026-10-14T15:00:00' }), // not a message
    ];
    expect(unreadCount(flags, seen)).toBe(2);
  });
});

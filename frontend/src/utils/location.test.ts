import { locationFinding } from './location';

describe('locationFinding', () => {
  it('reads the reasons that need a look, with distances', () => {
    expect(locationFinding({ location_check: 'far', distance_m: 1234, accuracy_m: 20 })).toEqual({
      reason: 'far',
      distanceM: 1234,
      accuracyM: 20,
    });
    expect(locationFinding({ location_check: 'upload' })?.reason).toBe('upload');
  });

  it('ignores outcomes that need nothing, and missing features', () => {
    expect(locationFinding({ location_check: 'ok' })).toBeNull();
    expect(locationFinding({ location_check: 'not_checked' })).toBeNull();
    expect(locationFinding(null)).toBeNull();
  });
});

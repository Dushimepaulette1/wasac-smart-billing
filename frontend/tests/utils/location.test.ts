import { locationFinding } from '../../src/utils/location';

describe('locationFinding', () => {
  it('when the check needs a look, should read the reason and the distances', () => {
    expect(locationFinding({ location_check: 'far', distance_m: 1234, accuracy_m: 20 })).toEqual({
      reason: 'far',
      distanceM: 1234,
      accuracyM: 20,
    });
    expect(locationFinding({ location_check: 'upload' })?.reason).toBe('upload');
  });

  it('when the check needs nothing or is missing, should return nothing', () => {
    expect(locationFinding({ location_check: 'ok' })).toBeNull();
    expect(locationFinding({ location_check: 'not_checked' })).toBeNull();
    expect(locationFinding(null)).toBeNull();
  });
});

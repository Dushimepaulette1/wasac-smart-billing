import { locationFinding } from '../../src/utils/location';

describe('locationFinding', () => {
  it('when the check needs a look, should read the reason and the distances', () => {
    expect(locationFinding({ location_check: 'far', distance_m: 1234, accuracy_m: 20, lat: -1.95, lng: 30.07 })).toEqual({
      reason: 'far',
      distanceM: 1234,
      accuracyM: 20,
      lat: -1.95,
      lng: 30.07,
    });
    expect(locationFinding({ location_check: 'upload' })?.reason).toBe('upload');
  });

  it('when the meter has no location yet, should report the first location', () => {
    expect(locationFinding({ location_check: 'first_location', accuracy_m: 12 })?.reason).toBe('first_location');
  });

  it('when the check needs nothing or is missing, should return nothing', () => {
    expect(locationFinding({ location_check: 'ok' })).toBeNull();
    expect(locationFinding({ location_check: 'not_checked' })).toBeNull();
    expect(locationFinding(null)).toBeNull();
  });
});

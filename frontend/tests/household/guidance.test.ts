import { isFramed, liveHint, photoOutcome, thumbnailUrl } from '../../src/household/guidance';
import { makeNoMeterResponse, makePhotoResponse } from '../support/fixtures';

describe('liveHint', () => {
  it('when the frame is good, should say "hold still"', () => {
    expect(liveHint(['OK'])).toBe('guidance.holdStill');
  });

  it('when several codes apply, should show only the most important one', () => {
    expect(liveHint(['NO_METER', 'TOO_DARK'])).toBe('guidance.noMeter');
    expect(liveHint(['TOO_FAR', 'CUT_OFF', 'GLARE'])).toBe('guidance.tooFar');
  });

  it('when the window is framed with a lighting hint, should still say "hold still"', () => {
    expect(liveHint(['GLARE'])).toBe('guidance.holdStill');
    expect(liveHint(['TOO_DARK', 'GLARE'])).toBe('guidance.holdStill');
  });

  it('when a code has no message, should skip it (BLURRY is off)', () => {
    expect(liveHint(['BLURRY', 'TOO_FAR'])).toBe('guidance.tooFar');
    expect(liveHint([])).toBeNull();
  });
});

describe('isFramed', () => {
  it('when the window is found and fully in the picture, should count as framed', () => {
    expect(isFramed(['OK'])).toBe(true);
    expect(isFramed(['GLARE', 'TOO_DARK'])).toBe(true);
  });

  it('when the meter is missing, too far or cut off, should not count as framed', () => {
    expect(isFramed(['NO_METER'])).toBe(false);
    expect(isFramed(['TOO_FAR'])).toBe(false);
    expect(isFramed(['GLARE', 'CUT_OFF'])).toBe(false);
    expect(isFramed([])).toBe(false);
  });
});

describe('photoOutcome', () => {
  it('when the photo is good, should go to the confirm screen', () => {
    expect(photoOutcome(makePhotoResponse())).toEqual({ kind: 'confirm', checkNumbers: false });
  });

  it('when the answer is CHECK_NUMBERS, should ask to check the numbers on the confirm screen', () => {
    expect(photoOutcome(makePhotoResponse({ guidance: ['CHECK_NUMBERS'] }))).toEqual({
      kind: 'confirm',
      checkNumbers: true,
    });
  });

  it('when no meter is found, should offer a retake or typing', () => {
    expect(photoOutcome(makeNoMeterResponse())).toEqual({ kind: 'noMeter' });
  });

  it('when a problem is fixable, should offer a soft retake before CHECK_NUMBERS', () => {
    expect(photoOutcome(makePhotoResponse({ guidance: ['GLARE', 'HARD_TO_READ', 'CHECK_NUMBERS'] }))).toEqual({
      kind: 'soft',
      code: 'GLARE',
    });
  });

  it('when the photo is blurry, should never prompt about it', () => {
    expect(photoOutcome(makePhotoResponse({ guidance: ['BLURRY'] }))).toEqual({ kind: 'confirm', checkNumbers: false });
  });

  it('when there is no reading and no other reason, should fall back to "unreadable"', () => {
    const result = makePhotoResponse({ status: 'unreadable', guidance: ['OK'], raw_digits: null, predicted_reading: null });
    expect(photoOutcome(result)).toEqual({ kind: 'unreadable' });
  });
});

it('when a thumbnail is returned, should turn it into an image URL', () => {
  expect(thumbnailUrl(makePhotoResponse({ thumbnail_jpeg_base64: 'AAAA' }))).toBe('data:image/jpeg;base64,AAAA');
  expect(thumbnailUrl(makeNoMeterResponse())).toBeNull();
});

import { liveHint, photoOutcome, thumbnailUrl } from './guidance';
import { makeNoMeterResponse, makePhotoResponse } from '../test/fixtures';

describe('liveHint', () => {
  it('says "hold still" for a good frame', () => {
    expect(liveHint(['OK'])).toBe('guidance.holdStill');
  });

  it('shows only the most important code', () => {
    expect(liveHint(['NO_METER', 'TOO_DARK'])).toBe('guidance.noMeter');
    expect(liveHint(['TOO_FAR', 'CUT_OFF', 'GLARE'])).toBe('guidance.tooFar');
  });

  it('skips codes without a message (BLURRY is off) and reading-only codes', () => {
    expect(liveHint(['BLURRY', 'GLARE'])).toBe('guidance.glare');
    expect(liveHint(['CHECK_NUMBERS'])).toBeNull();
    expect(liveHint([])).toBeNull();
  });
});

describe('photoOutcome', () => {
  it('goes to the confirm screen for a good photo', () => {
    expect(photoOutcome(makePhotoResponse())).toEqual({ kind: 'confirm', checkNumbers: false });
  });

  it('asks to check the numbers on the confirm screen for CHECK_NUMBERS', () => {
    expect(photoOutcome(makePhotoResponse({ guidance: ['CHECK_NUMBERS'] }))).toEqual({
      kind: 'confirm',
      checkNumbers: true,
    });
  });

  it('offers retake or typing when no meter is found', () => {
    expect(photoOutcome(makeNoMeterResponse())).toEqual({ kind: 'noMeter' });
  });

  it('offers a soft retake for the first fixable problem, before CHECK_NUMBERS', () => {
    expect(photoOutcome(makePhotoResponse({ guidance: ['GLARE', 'HARD_TO_READ', 'CHECK_NUMBERS'] }))).toEqual({
      kind: 'soft',
      code: 'GLARE',
    });
  });

  it('never prompts about BLURRY', () => {
    expect(photoOutcome(makePhotoResponse({ guidance: ['BLURRY'] }))).toEqual({ kind: 'confirm', checkNumbers: false });
  });

  it('falls back to "unreadable" when there is no reading and no other reason', () => {
    const result = makePhotoResponse({ status: 'unreadable', guidance: ['OK'], raw_digits: null, predicted_reading: null });
    expect(photoOutcome(result)).toEqual({ kind: 'unreadable' });
  });
});

it('turns the thumbnail into an image URL', () => {
  expect(thumbnailUrl(makePhotoResponse({ thumbnail_jpeg_base64: 'AAAA' }))).toBe('data:image/jpeg;base64,AAAA');
  expect(thumbnailUrl(makeNoMeterResponse())).toBeNull();
});

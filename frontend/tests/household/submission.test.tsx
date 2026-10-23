import { act, render, screen } from '@testing-library/react';
import { HouseholdProvider, useHousehold } from '../../src/household/session';
import { SubmissionProvider, useSubmission } from '../../src/household/submission';
import { signInHousehold, TEST_ACCOUNT } from '../support/household';

const OTHER = { ...TEST_ACCOUNT, customer_id: 'CUST002', meter_id: 'MTR002', name: 'Second meter' };
let household: ReturnType<typeof useHousehold>;
let draft: ReturnType<typeof useSubmission>;

function Probe() {
  household = useHousehold();
  draft = useSubmission();
  return <p>{draft.photo ?? 'no photo'}</p>;
}

const renderDraft = () =>
  render(
    <HouseholdProvider>
      <SubmissionProvider>
        <Probe />
      </SubmissionProvider>
    </HouseholdProvider>,
  );

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe('reading draft', () => {
  it('when another meter is chosen, should drop the draft instead of sending it for that meter', () => {
    signInHousehold([TEST_ACCOUNT, OTHER]);
    renderDraft();
    act(() => draft.setPhoto('data:image/jpeg;base64,AAA', { photoSource: 'camera', location: null }));
    expect(screen.getByText('data:image/jpeg;base64,AAA')).toBeInTheDocument();

    act(() => household.choose('CUST002'));
    expect(screen.getByText('no photo')).toBeInTheDocument();
    act(() => household.choose('CUST001'));
    expect(screen.getByText('no photo')).toBeInTheDocument(); // dropped, not hidden
  });

  it('when the page reloads for the same account, should keep the draft; for another, should not', () => {
    signInHousehold();
    const first = renderDraft();
    act(() => draft.setPhoto('data:image/jpeg;base64,BBB', { photoSource: 'camera', location: null }));
    first.unmount();

    renderDraft().unmount();
    expect(JSON.parse(window.sessionStorage.getItem('wasac.submission') ?? '{}').photo).toBe('data:image/jpeg;base64,BBB');

    signInHousehold([OTHER]);
    renderDraft();
    expect(screen.getByText('no photo')).toBeInTheDocument();
  });

  it('when the household signs out, should forget the photo', () => {
    signInHousehold();
    renderDraft();
    act(() => draft.setPhoto('data:image/jpeg;base64,CCC', { photoSource: 'camera', location: null }));
    act(() => household.signOut());
    expect(JSON.parse(window.sessionStorage.getItem('wasac.submission') ?? '{}').photo).toBeNull();
  });
});

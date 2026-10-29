/**
 * @file status.ts
 * @description The household's state as told by its anomaly flags: whether a
 * reading is waiting for a WASAC officer, and how many messages are new.
 *
 * "New" is per device and per meter: messages created or decided after
 * Messages was last opened for that meter on this phone. There is no
 * server-side read state yet.
 */

import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AnomalyFlag, AnomalyType } from '../api/types';
import { currentAccount, useAccountId } from './session';

/** Types a household gets a message for; NORMAL and BASELINE need none. */
export const SHOWN_TYPES: readonly AnomalyType[] = [
  'SPIKE',
  'SUSTAINED_HIGH',
  'MISREAD_SUSPECTED',
  'METER_STUCK',
  'UNUSUAL',
  'LOCATION_CHECK',
  'NO_BASELINE',
];

const SEEN_KEY = 'wasac.messagesSeenAt';

function seenKey(meterId = currentAccount()?.meter_id): string {
  return `${SEEN_KEY}:${meterId ?? ''}`;
}

/** The flag holds a reading back from billing until an officer decides. (An open flag on a
 *  reading that was already billed is follow-up work for WASAC; the household need not wait.) */
export function holdsReading(flag: AnomalyFlag): boolean {
  return flag.status === 'open' && flag.requires_staff_review && flag.reading_status === 'pending_review';
}

/** A reading the household sent is waiting for an officer's decision. */
export function readingIsWaiting(flags: readonly AnomalyFlag[]): boolean {
  return flags.some(holdsReading);
}

export function shownMessages(flags: readonly AnomalyFlag[]): AnomalyFlag[] {
  return flags.filter((f) => SHOWN_TYPES.includes(f.anomaly_type));
}

function seenAt(): number {
  try {
    return Number(window.localStorage.getItem(seenKey())) || 0;
  } catch {
    return 0;
  }
}

const SEEN_EVENT = 'wasac:messages-seen';

export function markMessagesSeen(now = Date.now()): void {
  try {
    window.localStorage.setItem(seenKey(), String(now));
  } catch {
    // Storage blocked: the count just stays until storage works.
  }
  window.dispatchEvent(new Event(SEEN_EVENT)); // counts already on screen update now
}

/** The backend sends UTC times without a zone ("2026-10-14T08:00:00"); browsers would read them as local. */
export function parseUtc(iso: string): number {
  return Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
}

/** Messages created, or decided, since Messages was last opened on this device. */
export function unreadCount(flags: readonly AnomalyFlag[], since = seenAt()): number {
  const changedAt = (f: AnomalyFlag) => parseUtc(f.resolved_at ?? f.created_at);
  return shownMessages(flags).filter((f) => changedAt(f) > since).length;
}

/** One request shared by the header and the bottom bar, reused for a short while. */
const SHARE_MS = 15_000;
let shared: { at: number; meterId: string; request: Promise<AnomalyFlag[]> } | null = null;

function loadFlags(): Promise<AnomalyFlag[]> {
  const meterId = currentAccount()?.meter_id;
  if (!meterId) return Promise.resolve([]); // signed out: nothing to count
  if (!shared || shared.meterId !== meterId || Date.now() - shared.at > SHARE_MS) {
    shared = { at: Date.now(), meterId, request: api.getHouseholdFlags(meterId) };
    shared.request.catch(() => {
      shared = null; // a failure is not reused
    });
  }
  return shared.request;
}

/** Forget the shared answer (tests; after the household sends a reading). */
export function refreshHouseholdFlags(): void {
  shared = null;
}

/** The household's flags, or [] if they cannot be loaded (navigation must never fail). */
export function useHouseholdFlags(): AnomalyFlag[] {
  const [flags, setFlags] = useState<AnomalyFlag[]>([]);
  const [, rerender] = useState(0);
  const accountId = useAccountId(); // another meter chosen: load its flags
  useEffect(() => {
    let live = true;
    setFlags([]);
    loadFlags()
      .then((data) => live && setFlags(data))
      .catch(() => undefined);
    const onSeen = () => rerender((n) => n + 1);
    window.addEventListener(SEEN_EVENT, onSeen);
    return () => {
      live = false;
      window.removeEventListener(SEEN_EVENT, onSeen);
    };
  }, [accountId]);
  return flags;
}

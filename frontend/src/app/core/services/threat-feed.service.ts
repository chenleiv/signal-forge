import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, of, switchMap, timer } from 'rxjs';

export type FeedState  = 'live' | 'cached' | 'sample' | 'unavailable';
export type FeedReason = 'quota' | 'no_key' | 'error' | null;

export interface ThreatFeedStatus {
  state: FeedState;
  reason: FeedReason;
}

export interface FeedNotice {
  long: string;
  short: string;
}

export const FEED_POLL_MS = 60_000;

/**
 * Why the live stream is paused or showing sample data, or null when there
 * is nothing to explain. Without it an exhausted AbuseIPDB quota looks like a
 * broken dashboard full of zeros.
 */
export function feedNotice(status: ThreatFeedStatus | null): FeedNotice | null {
  if (!status || status.state === 'live' || status.state === 'cached') return null;
  const resumes = 'Live data resumes automatically.';
  if (status.state === 'sample') {
    switch (status.reason) {
      case 'quota':
        return {
          long: `Showing sample data: the free AbuseIPDB daily quota is used up. This is expected, not a bug. ${resumes}`,
          short: 'Sample data: AbuseIPDB daily quota used up (expected).',
        };
      case 'no_key':
        return {
          long: 'Showing sample data: no AbuseIPDB API key is configured.',
          short: 'Sample data: no AbuseIPDB key.',
        };
      default:
        return {
          long: `Showing sample data: the AbuseIPDB threat feed is unreachable right now. ${resumes}`,
          short: 'Sample data: AbuseIPDB unreachable.',
        };
    }
  }
  switch (status.reason) {
    case 'quota':
      return {
        long: `Live threat feed paused: the AbuseIPDB daily quota is used up. ${resumes}`,
        short: 'Feed paused: AbuseIPDB quota used up.',
      };
    case 'no_key':
      return {
        long: 'No threat feed: set ABUSEIPDB_API_KEY to stream live data.',
        short: 'No threat feed: AbuseIPDB key not set.',
      };
    default:
      return {
        long: `Live threat feed unavailable: AbuseIPDB could not be reached. ${resumes}`,
        short: 'Feed unavailable: AbuseIPDB unreachable.',
      };
  }
}

@Injectable({ providedIn: 'root' })
export class ThreatFeedService {
  private http = inject(HttpClient);

  readonly status = signal<ThreatFeedStatus | null>(null);
  readonly notice = computed(() => feedNotice(this.status()));

  /** Polls the feed status until `destroyRef` (the signed-in layout) is destroyed. */
  watch(destroyRef: DestroyRef): void {
    timer(0, FEED_POLL_MS).pipe(
      // A failed poll keeps the last known status; the banner is informational.
      switchMap(() => this.http.get<ThreatFeedStatus>('/api/threat-feed').pipe(catchError(() => of(null)))),
      takeUntilDestroyed(destroyRef),
    ).subscribe(status => {
      if (status) this.status.set(status);
    });
  }
}

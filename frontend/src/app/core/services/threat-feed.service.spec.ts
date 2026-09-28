import { DestroyRef } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { FEED_POLL_MS, ThreatFeedService, feedNotice } from './threat-feed.service';

describe('feedNotice', () => {
  it('says nothing while the feed has data of its own', () => {
    expect(feedNotice(null)).toBeNull();
    expect(feedNotice({ state: 'live', reason: null })).toBeNull();
    expect(feedNotice({ state: 'cached', reason: 'quota' })).toBeNull();
  });

  it('tells a visitor an exhausted quota is expected, not a bug', () => {
    const notice = feedNotice({ state: 'sample', reason: 'quota' });
    expect(notice?.long).toContain('sample data');
    expect(notice?.long).toContain('quota');
    expect(notice?.long).toContain('not a bug');
    expect(notice?.short).toContain('quota');
  });

  it('explains a paused feed', () => {
    expect(feedNotice({ state: 'unavailable', reason: 'quota' })?.long).toContain('paused');
    expect(feedNotice({ state: 'unavailable', reason: 'no_key' })?.long).toContain('ABUSEIPDB_API_KEY');
    expect(feedNotice({ state: 'unavailable', reason: 'error' })?.long).toContain('could not be reached');
  });
});

describe('ThreatFeedService', () => {
  let service: ThreatFeedService;
  let server: HttpTestingController;
  let destroy: () => void;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ThreatFeedService);
    server  = TestBed.inject(HttpTestingController);
    const callbacks: (() => void)[] = [];
    destroy = () => callbacks.forEach(cb => cb());
    service.watch({ onDestroy: (cb: () => void) => { callbacks.push(cb); return () => undefined; } } as DestroyRef);
  });

  afterEach(() => {
    destroy();
    vi.useRealTimers();
  });

  it('shows the banner when the quota runs out and hides it when the feed is back', () => {
    vi.advanceTimersByTime(0);
    server.expectOne('/api/threat-feed').flush({ state: 'sample', reason: 'quota' });
    expect(service.notice()).not.toBeNull();

    vi.advanceTimersByTime(FEED_POLL_MS);
    server.expectOne('/api/threat-feed').flush({ state: 'live', reason: null });
    expect(service.notice()).toBeNull();
  });

  it('keeps the last status when a poll fails', () => {
    vi.advanceTimersByTime(0);
    server.expectOne('/api/threat-feed').flush({ state: 'sample', reason: 'quota' });

    vi.advanceTimersByTime(FEED_POLL_MS);
    server.expectOne('/api/threat-feed').flush('down', { status: 502, statusText: 'Bad Gateway' });
    expect(service.status()).toEqual({ state: 'sample', reason: 'quota' });
  });

  it('stops polling when the layout is destroyed', () => {
    vi.advanceTimersByTime(0);
    server.expectOne('/api/threat-feed').flush({ state: 'live', reason: null });
    destroy();
    vi.advanceTimersByTime(FEED_POLL_MS * 3);
    server.expectNone('/api/threat-feed');
  });
});

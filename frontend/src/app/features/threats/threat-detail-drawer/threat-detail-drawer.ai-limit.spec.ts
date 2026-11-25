import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';

import { ThreatDetailDrawerComponent } from './threat-detail-drawer.component';
import { ThreatStoreService } from '../../../core/services/threat-store.service';

const LIMIT_TEXT = 'AI summary limit reached. Try again later.';

describe('ThreatDetailDrawerComponent AI summary limit', () => {
  let summaryReply: () => Observable<{ summary: string | null }>;
  let summaryCalls: number;

  beforeEach(() => {
    summaryCalls = 0;
    summaryReply = () => of({ summary: 'A summary.' });
    TestBed.configureTestingModule({
      imports: [ThreatDetailDrawerComponent],
      providers: [
        { provide: Router, useValue: { navigate: () => Promise.resolve(true) } },
        { provide: ThreatStoreService, useValue: {
          // What the server sends for an IP with no stored events.
          fetchIpHistory: (ip: string) => of({ ip, score: 0, threat_level: 'low', events: [], regions: [], mitre_tags: [] }),
          fetchAiSummary: () => { summaryCalls++; return summaryReply(); },
          fetchIpGeo: () => of(null),
          fetchRelatedIps: () => of({ related: [] }),
          getBlockStatus: () => of({ blocked: false }),
          getIpCase: () => of({ case_id: null }),
        } },
      ],
    });
  });

  const open = (ip: string) => {
    const fixture = TestBed.createComponent(ThreatDetailDrawerComponent);
    fixture.componentRef.setInput('ip', ip);
    fixture.detectChanges();
    return fixture;
  };

  it('shows the limit message on a 429', () => {
    summaryReply = () => throwError(() => new HttpErrorResponse({ status: 429 }));
    const fixture = open('8.8.8.8');
    const message = fixture.nativeElement.querySelector('.ai-limited');
    expect(message?.textContent?.trim()).toBe(LIMIT_TEXT);
    expect(message?.getAttribute('role')).toBe('status');
    expect(fixture.componentInstance.aiLoading()).toBe(false);
  });

  it('shows nothing for other errors', () => {
    summaryReply = () => throwError(() => new HttpErrorResponse({ status: 500 }));
    const fixture = open('8.8.8.8');
    expect(fixture.nativeElement.textContent).not.toContain(LIMIT_TEXT);
    expect(fixture.nativeElement.querySelector('.ai-summary')).toBeNull();
  });

  it('does not cache a refusal: the same IP asks again and shows the summary', () => {
    summaryReply = () => throwError(() => new HttpErrorResponse({ status: 429 }));
    const fixture = open('8.8.8.8');
    summaryReply = () => of({ summary: 'A summary.' });
    fixture.componentRef.setInput('ip', '1.1.1.1');
    fixture.detectChanges();
    fixture.componentRef.setInput('ip', '8.8.8.8');
    fixture.detectChanges();
    expect(summaryCalls).toBe(3);
    expect(fixture.nativeElement.textContent).not.toContain(LIMIT_TEXT);
    expect(fixture.nativeElement.querySelector('.ai-summary')?.textContent?.trim()).toBe('A summary.');
  });
});

import { TestBed } from '@angular/core/testing';
import { HttpRequest, provideHttpClient } from '@angular/common/http';
import { DemoSimulatorService } from './demo-simulator.service';

describe('DemoSimulatorService', () => {
  let sim: DemoSimulatorService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient()] });
    sim = TestBed.inject(DemoSimulatorService);
  });

  it('keeps an acknowledged alert acknowledged after the list is refetched', () => {
    const serverAlerts = [{ id: 'a1', status: 'new' }];

    sim.overlay('/api/alerts', serverAlerts);

    // 2. המשתמש מאשר את ההתראה
    const req = new HttpRequest('PATCH', '/api/alerts/a1', { status: 'acknowledged' });
    sim.simulate(req, '/api/alerts/a1');

    const result = sim.overlay('/api/alerts', serverAlerts) as { status: string }[];

    // 4. מה צריך להיות הסטטוס?
    expect(result[0].status).toBe('acknowledged');
  });
});

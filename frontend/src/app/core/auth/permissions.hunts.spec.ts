import { CurrentUser, DENY_REASONS, canDeleteHunt } from './permissions';

const ALICE: CurrentUser = { username: 'alice', display_name: 'Alice Chen', role: 'analyst' };
const MIRA: CurrentUser  = { username: 'mira',  display_name: 'Mira Cohen', role: 'manager' };
const ADMIN: CurrentUser = { username: 'admin', display_name: 'Sarah Kim',  role: 'admin' };

const denied = { allowed: false, reason: DENY_REASONS.huntOwner };

describe('canDeleteHunt (mirrors backend can_delete_hunt)', () => {
  it('lets the creator delete their own hunt', () => {
    expect(canDeleteHunt(ALICE, { created_by: 'alice' })).toEqual({ allowed: true });
    expect(canDeleteHunt(MIRA, { created_by: 'mira' })).toEqual({ allowed: true });
  });

  it("refuses an analyst or a manager on another user's hunt", () => {
    expect(canDeleteHunt(ALICE, { created_by: 'bob' })).toEqual(denied);
    expect(canDeleteHunt(MIRA, { created_by: 'alice' })).toEqual(denied);
  });

  it('keeps a hunt with no owner for the admin only', () => {
    for (const hunt of [{ created_by: null }, {}]) {
      expect(canDeleteHunt(ALICE, hunt)).toEqual(denied);
      expect(canDeleteHunt(MIRA, hunt)).toEqual(denied);
      expect(canDeleteHunt(ADMIN, hunt)).toEqual({ allowed: true });
    }
  });

  it("lets the admin delete anyone's hunt", () => {
    expect(canDeleteHunt(ADMIN, { created_by: 'bob' })).toEqual({ allowed: true });
  });

  it('refuses when nobody is signed in', () => {
    expect(canDeleteHunt(null, { created_by: 'alice' })).toEqual({ allowed: false, reason: DENY_REASONS.notAuthenticated });
  });
});

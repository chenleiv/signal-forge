import { DrawerResize } from './drawer-resize';

const mouse = (clientX: number) => ({ clientX, preventDefault: vi.fn(), stopPropagation: vi.fn() }) as unknown as MouseEvent;

describe('DrawerResize', () => {
  it('widens when the left edge is dragged left, within its limits', () => {
    const r = new DrawerResize(500, 400, 700);
    r.start(mouse(1000));
    r.move(mouse(900));
    expect(r.width()).toBe(600);
    r.move(mouse(0));
    expect(r.width()).toBe(700);   // max
    r.move(mouse(2000));
    expect(r.width()).toBe(400);   // min
  });

  it('ignores mouse moves unless a drag is in progress', () => {
    const r = new DrawerResize(500, 400, 700);
    r.move(mouse(100));
    expect(r.width()).toBe(500);
    r.start(mouse(1000));
    r.end();
    r.move(mouse(900));
    expect(r.width()).toBe(500);
  });
});

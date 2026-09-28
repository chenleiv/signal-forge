import { signal } from '@angular/core';

/**
 * Drag-to-resize for a right-hand detail drawer (a mouse feature; hidden on
 * narrow screens). The page forwards document mousemove/mouseup to it.
 */
export class DrawerResize {
  readonly width;
  private dragging = false;
  private startX = 0;
  private startWidth = 0;

  constructor(initial: number, private readonly min: number, private readonly max: number) {
    this.width = signal(initial);
  }

  start(e: MouseEvent): void {
    this.dragging = true;
    this.startX = e.clientX;
    this.startWidth = this.width();
    e.preventDefault();
    e.stopPropagation();
  }

  move(e: MouseEvent): void {
    if (!this.dragging) return;
    // Dragging the left edge to the left widens the drawer.
    const width = this.startWidth + this.startX - e.clientX;
    this.width.set(Math.min(this.max, Math.max(this.min, width)));
  }

  end(): void {
    this.dragging = false;
  }
}

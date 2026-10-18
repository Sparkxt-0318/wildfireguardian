import { describe, expect, it } from 'vitest';
import { hoverEdgeClass } from '../../planner/src/map/hoverEdge';

describe('hoverEdgeClass (map hover card stays inside the map)', () => {
  it('clamps horizontally and vertically', () => {
    expect(hoverEdgeClass({ x: 500, y: 300 }, 1000)).toBe('');
    expect(hoverEdgeClass({ x: 20, y: 300 }, 1000)).toBe(' edge-left');
    expect(hoverEdgeClass({ x: 990, y: 300 }, 1000)).toBe(' edge-right');
    expect(hoverEdgeClass({ x: 500, y: 12 }, 1000)).toBe(' edge-top');
    expect(hoverEdgeClass({ x: 20, y: 12 }, 1000)).toBe(' edge-left edge-top');
  });
});

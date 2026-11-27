import { afterEach, describe, expect, it, vi } from 'vitest';
import { request } from '../src/services/runtime';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('session recovery', () => {
  it('creates a new empty session and retries after a stale-cookie response', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401 } as Response)
      .mockResolvedValueOnce({ ok: true, status: 200 } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ status: 'idle', releaseApproved: false }),
      } as Response);
    vi.stubGlobal('fetch', fetchMock);

    await expect(request<{ status: string }>('/run')).resolves.toEqual({
      status: 'idle',
      releaseApproved: false,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/run',
      expect.objectContaining({ credentials: 'same-origin', cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/session',
      expect.objectContaining({ method: 'POST', credentials: 'same-origin' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/run',
      expect.objectContaining({ credentials: 'same-origin', cache: 'no-store' }),
    );
  });

  it('shares one bootstrap across concurrent stale-session requests', async () => {
    const requestCounts = new Map<string, number>();
    let bootstrapCount = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith('/api/session')) {
        bootstrapCount += 1;
        return { ok: true, status: 200 } as Response;
      }
      const count = (requestCounts.get(path) ?? 0) + 1;
      requestCounts.set(path, count);
      if (count === 1) return { ok: false, status: 401 } as Response;
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: 'idle' }),
      } as Response;
    });
    vi.stubGlobal('fetch', fetchMock);

    await Promise.all([
      request('/run'),
      request('/results'),
    ]);

    expect(bootstrapCount).toBe(1);
    expect(requestCounts.get('/api/run')).toBe(2);
    expect(requestCounts.get('/api/results')).toBe(2);
  });
});

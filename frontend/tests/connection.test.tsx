import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ConnectionPill } from '../src/components/ConnectionPill';
import LandingPage from '../src/pages/LandingPage';
import { ThemeProvider } from '../src/app/ThemeControl';
import { MemoryRouter } from 'react-router-dom';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubBackend(modelAvailable: boolean) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const body = String(input).endsWith('/api/health')
      ? { status: 'ready', modelAvailable, modelFeatureVersion: '2.0' }
      : { status: 'idle', releaseApproved: false, stages: {}, counts: {}, contractValid: null };
    return { ok: true, json: async () => body } as Response;
  }));
}

function renderLanding() {
  vi.stubGlobal('IntersectionObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  return render(<MemoryRouter><ThemeProvider><LandingPage /></ThemeProvider></MemoryRouter>);
}

describe('backend readiness status', () => {
  it('distinguishes a connected backend with a loaded model', async () => {
    stubBackend(true);
    render(<ConnectionPill />);

    expect(await screen.findByText('ENGINE CONNECTED · MODEL AVAILABLE')).toBeInTheDocument();
  });

  it('reports the model unavailable without claiming the engine is offline', async () => {
    stubBackend(false);
    render(<ConnectionPill />);

    expect(await screen.findByText('ENGINE CONNECTED · MODEL UNAVAILABLE')).toBeInTheDocument();
  });

  it('reports a backend connection failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    render(<ConnectionPill />);

    expect(await screen.findByText('ENGINE OFFLINE')).toBeInTheDocument();
  });

  it('shows live backend and model readiness on the homepage', async () => {
    stubBackend(true);
    renderLanding();

    expect(await screen.findByText('The local backend and trained model are ready. Start a synthetic-data run in the workspace.')).toBeInTheDocument();
  });

  it('keeps the homepage release-locked when the backend has no model', async () => {
    stubBackend(false);
    renderLanding();

    expect(await screen.findByText('The backend is connected, but the trained model is unavailable. Releases remain locked.')).toBeInTheDocument();
  });
});

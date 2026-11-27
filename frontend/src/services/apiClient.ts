import type { ConnectionState, ShieldBackendAdapter } from '../contracts/api';

const backendBaseUrl = import.meta.env.VITE_BACKEND_BASE_URL?.trim() ?? '';

export class BackendNotConnectedError extends Error {
  constructor() {
    super('The Shield processing engine is not connected. No data has been sent or processed.');
    this.name = 'BackendNotConnectedError';
  }
}

/**
 * A dependency-injection boundary for a future, agreed Python API adapter.
 * The current frontend intentionally has no adapter implementation and calls no routes.
 */
export class ShieldApiClient {
  constructor(private readonly adapter?: ShieldBackendAdapter) {}

  get configuredBaseUrl(): string | undefined {
    return backendBaseUrl || undefined;
  }

  async getConnectionState(): Promise<ConnectionState> {
    if (!this.adapter) return { status: 'disconnected', reason: 'contract-pending' };
    try {
      return await this.adapter.getConnectionState();
    } catch {
      return { status: 'unavailable', safeMessage: 'The configured engine could not be reached.' };
    }
  }

  requireAdapter(): ShieldBackendAdapter {
    if (!this.adapter) throw new BackendNotConnectedError();
    return this.adapter;
  }
}

export const apiClient = new ShieldApiClient();

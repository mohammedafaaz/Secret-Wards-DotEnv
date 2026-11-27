export type ConnectionState =
  | { status: 'disconnected'; reason: 'not-configured' | 'contract-pending' }
  | { status: 'connecting' }
  | { status: 'connected'; backendVersion?: string }
  | { status: 'unavailable'; safeMessage: string };

export type StageStatus = 'pending' | 'running' | 'completed' | 'failed' | 'unavailable';
export type ProcessingStageId =
  | 'ingestion'
  | 'normalization'
  | 'pii-detection'
  | 'identity-resolution'
  | 'transformation'
  | 'verification'
  | 'release-generation';

export interface ProcessingStageEvent {
  runId: string;
  stageId: ProcessingStageId;
  status: StageStatus;
  occurredAt: string;
  safeSummary?: string;
}

export interface ProcessingRunState {
  runId: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  currentStage?: ProcessingStageId;
  startedAt?: string;
  finishedAt?: string;
  filesProcessed?: number;
  totalFiles?: number;
  safeErrorSummary?: string;
}

export interface ReportSummary {
  privacy?: {
    detectedIdentifierCount?: number;
    quasiIdentifierTransformations?: number;
    measuredReidentificationRisk?: number;
    leakageVerification?: 'clear' | 'findings' | 'inconclusive';
    quarantinedCount?: number;
    suppressedCount?: number;
  };
  clinicalIntegrity?: {
    medicinePreservation?: number;
    dosagePreservation?: number;
    diagnosisPreservation?: number;
    vitalAndLabPreservation?: number;
    stayLengthPreservation?: number;
    ageBandVerification?: number;
  };
  verificationSource?: 'internal' | 'practice-checker' | 'official-hidden-evaluation';
  totals?: Record<string, number>;
}

export interface SanitizedArtifact {
  id: string;
  safeLabel: string;
  safePath: string;
  kind: 'sanitized-archive' | 'report' | 'records';
  mediaType: string;
  sizeBytes?: number;
}

export interface IdentitySummary {
  pseudonymousId: string;
  linkedRecordCount: number;
  resolution: 'confirmed' | 'unresolved';
}

export interface IdentityResolutionSummary {
  identities: IdentitySummary[];
  unresolvedCount: number;
  confirmedDuplicateEncounters?: number;
  possibleDuplicateEncounters?: number;
}

export interface SafeApiError {
  code: string;
  safeMessage: string;
  requestId?: string;
}

/**
 * Proposed adapter contract only. No HTTP route or backend endpoint is implemented here.
 * An integration must be supplied by a future backend agreed against its actual contract.
 */
export interface ShieldBackendAdapter {
  getConnectionState(): Promise<ConnectionState>;
  startProcessing(files: readonly File[]): Promise<ProcessingRunState>;
  subscribeToRun(runId: string, onEvent: (event: ProcessingStageEvent) => void): () => void;
  getReport(runId: string): Promise<ReportSummary>;
  getIdentities(runId: string): Promise<IdentityResolutionSummary>;
  listArtifacts(runId: string): Promise<readonly SanitizedArtifact[]>;
  downloadArtifact(artifact: SanitizedArtifact): Promise<Blob>;
}

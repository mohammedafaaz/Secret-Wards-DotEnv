import type { ReportSummary, SanitizedArtifact } from './api';

export interface RecordsJsonlRecord {
  [key: string]: unknown;
}

export interface ParseResult<T> {
  value?: T;
  error?: 'invalid-json' | 'invalid-shape' | 'empty';
}

/** Parse data supplied by a connected integration; this function does not read files itself. */
export function parseReportJson(input: string): ParseResult<ReportSummary> {
  if (!input.trim()) return { error: 'empty' };
  let parsed: unknown;
  try {
    parsed = JSON.parse(input);
  } catch {
    return { error: 'invalid-json' };
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return { error: 'invalid-shape' };
  return { value: parsed as ReportSummary };
}

/** Streaming callers can parse each record line individually without rendering raw contents. */
export function parseRecordsJsonlLine(line: string): ParseResult<RecordsJsonlRecord> {
  if (!line.trim()) return { error: 'empty' };
  let parsed: unknown;
  try {
    parsed = JSON.parse(line);
  } catch {
    return { error: 'invalid-json' };
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return { error: 'invalid-shape' };
  return { value: parsed as RecordsJsonlRecord };
}

export function isDownloadableArtifact(artifact: SanitizedArtifact): boolean {
  return artifact.kind === 'sanitized-archive' || artifact.kind === 'report' || artifact.kind === 'records';
}

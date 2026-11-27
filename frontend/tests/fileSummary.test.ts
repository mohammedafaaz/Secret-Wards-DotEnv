import { describe, expect, it } from 'vitest';
import { formatBytes, summarizeSelectedFiles } from '../src/services/fileSummary';

const file = (name: string, size: number, type = '') => ({ name, size, type }) as File;

describe('summarizeSelectedFiles', () => {
  it('returns only aggregate metadata and does not return a selected filename', () => {
    const result = summarizeSelectedFiles([file('private-example.csv', 512), file('records.json', 1024)]);
    expect(result).toEqual({ fileCount: 2, totalBytes: 1536, supportedTypes: { CSV: 1, JSON: 1 }, otherCount: 0 });
    expect(JSON.stringify(result)).not.toContain('private-example');
  });
  it('keeps unrecognized formats countable without declaring them processed', () => {
    expect(summarizeSelectedFiles([file('input.bin', 2)]).otherCount).toBe(1);
  });
});

describe('formatBytes', () => {
  it('formats actual byte totals', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1024)).toBe('1.0 KB');
  });
});

import { describe, expect, it } from 'vitest';
import { parseRecordsJsonlLine, parseReportJson } from '../src/contracts/parsers';

describe('data contracts', () => {
  it('rejects malformed report JSON without exposing parser internals', () => {
    expect(parseReportJson('{')).toEqual({ error: 'invalid-json' });
    expect(parseReportJson('[]')).toEqual({ error: 'invalid-shape' });
  });
  it('accepts an empty metrics object without fabricating fields', () => {
    expect(parseReportJson('{}')).toEqual({ value: {} });
  });
  it('validates JSONL line shape for an injected backend result', () => {
    expect(parseRecordsJsonlLine('')).toEqual({ error: 'empty' });
    expect(parseRecordsJsonlLine('null')).toEqual({ error: 'invalid-shape' });
    expect(parseRecordsJsonlLine('{"ok":true}')).toEqual({ value: { ok: true } });
  });
});

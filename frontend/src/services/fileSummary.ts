export interface FileSelectionSummary {
  fileCount: number;
  totalBytes: number;
  supportedTypes: Readonly<Record<string, number>>;
  otherCount: number;
}

const extensions: Readonly<Record<string, string>> = {
  csv: 'CSV', tsv: 'TSV', json: 'JSON', txt: 'TXT', ndjson: 'JSONL', jsonl: 'JSONL', zip: 'Archive', tar: 'Archive', gz: 'Archive',
};

function safeType(file: File): string | undefined {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (extensions[extension]) return extensions[extension];
  const mime = file.type.toLowerCase();
  if (mime === 'application/fhir+json') return 'FHIR R4';
  return undefined;
}

/** Returns aggregate metadata only. Callers must not display File.name or read file contents. */
export function summarizeSelectedFiles(files: readonly File[]): FileSelectionSummary {
  const supportedTypes: Record<string, number> = {};
  let otherCount = 0;
  for (const file of files) {
    const kind = safeType(file);
    if (kind) supportedTypes[kind] = (supportedTypes[kind] ?? 0) + 1;
    else otherCount += 1;
  }
  return {
    fileCount: files.length,
    totalBytes: files.reduce((sum, file) => sum + file.size, 0),
    supportedTypes,
    otherCount,
  };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

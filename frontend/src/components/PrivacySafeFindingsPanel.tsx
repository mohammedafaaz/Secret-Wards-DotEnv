import { useEffect, useState } from 'react';
import { AlertTriangle, FileText, ChevronDown, Search, Filter } from 'lucide-react';
import { fetchFindings, type DetailedFinding } from '../services/runtime';

const CATEGORY_LABELS: Record<string, string> = {
  accounting: 'Accounting',
  missing_record_file: 'Missing Record File',
  missing_pseudonym: 'Missing Pseudonym',
  invalid_record_locator: 'Invalid Record Locator',
  known_identifier: 'Known Identifier',
  known_name: 'Known Name',
  residual_labeled_pii: 'Residual Labeled PII',
  fhir_reference_or_structure: 'FHIR Reference/Structure',
  table_shape: 'Table Shape',
  clinical_probe_missing: 'Clinical Probe Missing',
  clinical_path_changed: 'Clinical Path Changed',
  residual_direct_pattern: 'Residual Direct Pattern',
  verification_error: 'Verification Error',
};

const CATEGORY_SEVERITY: Record<string, 'high' | 'medium' | 'low'> = {
  accounting: 'high',
  missing_record_file: 'high',
  missing_pseudonym: 'high',
  invalid_record_locator: 'medium',
  known_identifier: 'high',
  known_name: 'high',
  residual_labeled_pii: 'high',
  fhir_reference_or_structure: 'medium',
  table_shape: 'medium',
  clinical_probe_missing: 'medium',
  clinical_path_changed: 'medium',
  residual_direct_pattern: 'high',
  verification_error: 'high',
};

function SeverityBadge({ severity }: { severity: 'high' | 'medium' | 'low' }) {
  return (
    <span className={`severity-badge severity-${severity}`}>
      {severity === 'high' && 'Critical'}
      {severity === 'medium' && 'Warning'}
      {severity === 'low' && 'Info'}
    </span>
  );
}

function FindingRow({ finding, onToggle }: { finding: DetailedFinding; onToggle: () => void }) {
  const severity = CATEGORY_SEVERITY[finding.category] ?? 'low';
  const label = CATEGORY_LABELS[finding.category] ?? finding.category;

  return (
    <div className="finding-row">
      <div className="finding-main" onClick={onToggle}>
        <div className="finding-header">
          <SeverityBadge severity={severity} />
          <span className="finding-category">{label}</span>
          <span className="finding-file">{finding.fileRef}</span>
        </div>
        <div className="finding-locator">Record: {finding.recordLocator}</div>
      </div>
      <button className="finding-expand" onClick={onToggle} aria-label="Expand finding details">
        <ChevronDown size={14} />
      </button>
    </div>
  );
}

function FindingDetails({ finding }: { finding: DetailedFinding }) {
  return (
    <div className="finding-details">
      <div className="detail-field">
        <span className="detail-label">Reason</span>
        <span className="detail-value">{finding.reason}</span>
      </div>
      <div className="detail-field">
        <span className="detail-label">Suggested Action</span>
        <span className="detail-value">{finding.suggestedAction}</span>
      </div>
    </div>
  );
}

export function PrivacySafeFindingsPanel({ runId }: { runId?: string }) {
  const [findings, setFindings] = useState<DetailedFinding[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>('all');

  useEffect(() => {
    if (!runId) {
      setFindings([]);
      setLoading(false);
      return;
    }
    async function load() {
      setLoading(true);
      try {
        const data = await fetchFindings();
        setFindings(data);
      } catch {
        setFindings([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [runId]);

  const categories = ['all', ...new Set(findings.map(f => f.category))];

  const filteredFindings = filterCategory === 'all'
    ? findings
    : findings.filter(f => f.category === filterCategory);

  if (loading) {
    return (
      <div className="findings-panel">
        <div className="findings-loading">
          <Search className="spin" size={16} />
          <span>Loading verification findings...</span>
        </div>
      </div>
    );
  }

  if (findings.length === 0) {
    return (
      <div className="findings-panel">
        <div className="findings-empty">
          <FileText size={24} />
          <p>No verification findings available. Run a dataset to see detailed results.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="findings-panel">
      <div className="findings-header">
        <h3><AlertTriangle size={16} /> Privacy-Safe Verification Findings</h3>
        <p className="findings-subtitle">
          {findings.length} finding{findings.length !== 1 ? 's' : ''} — Internal conservative checks only. Not proof of anonymity.
        </p>
        <div className="findings-filter">
          <Filter size={14} />
          <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)}>
            <option value="all">All Categories</option>
            {categories.filter(c => c !== 'all').map(cat => (
              <option key={cat} value={cat}>{CATEGORY_LABELS[cat] ?? cat}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="findings-list">
        {filteredFindings.map((finding, idx) => (
          <div key={idx} className="finding-item">
            <FindingRow finding={finding} onToggle={() => setExpandedIndex(expandedIndex === idx ? null : idx)} />
            {expandedIndex === idx && <FindingDetails finding={finding} />}
          </div>
        ))}
      </div>
    </div>
  );
}
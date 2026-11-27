import { useNavigate } from 'react-router-dom';
import { useRuntime, startRun } from '../services/runtime';
import { useMemo, useRef, useState, type ChangeEvent, type DragEvent, type InputHTMLAttributes } from 'react';
import { Archive, ArrowUpRight, FileInput, FolderOpen, LockKeyhole, ShieldCheck, Upload } from 'lucide-react';
import { PageHeader, StateLabel } from '../components/Primitives';
import { ConnectionPill } from '../components/ConnectionPill';
import { formatBytes, summarizeSelectedFiles } from '../services/fileSummary';
import { PrivacyEngineAnimation } from '../components/PrivacyEngineAnimation';

export default function WorkspacePage() {
  const { run, connected, modelAvailable } = useRuntime();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const active = busy || run?.status === 'running' || run?.status === 'queued';
  async function launch(practice = false) {
    setBusy(true);
    setError('');
    try {
      await startRun(practice ? undefined : files);
      setFiles([]);
      navigate('/engine');
    } catch {
      setError('Could not start the run. Check the engine and import limits.');
    } finally {
      setBusy(false);
    }
  }
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);
  const archiveRef = useRef<HTMLInputElement>(null);
  const summary = useMemo(() => summarizeSelectedFiles(files), [files]);
  const update = (event: ChangeEvent<HTMLInputElement>) => setFiles(Array.from(event.currentTarget.files ?? []));
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    setFiles(Array.from(event.dataTransfer.files));
  };
  const folderProps = { webkitdirectory: '', directory: '' } as InputHTMLAttributes<HTMLInputElement>;

  return (
    <div className="page-content">
      <PageHeader eyebrow="01 / INTAKE" title="Data Workspace" description="Select a local dataset to prepare an import. Files stay in this page's memory; nothing is uploaded while the engine is disconnected." aside={<ConnectionPill />} />
      <div className="workspace-grid">
        <section className="import-column">
          <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
            <div className="drop-ornament"><div className="drop-orbit orbit-a" /><div className="drop-orbit orbit-b" /><Upload size={21} strokeWidth={1.4} /></div>
            <h2>{files.length ? 'Selection ready' : 'Bring a dataset into the workspace'}</h2>
            <p>Choose files or drop them here. Raw names and record contents are never shown.</p>
            <div className="drop-controls">
              <button className="button button-primary" onClick={() => fileRef.current?.click()}><FileInput size={15} /> Select files</button>
              <button className="button button-outline" onClick={() => folderRef.current?.click()}><FolderOpen size={15} /> Select folder</button>
            </div>
            <div className="drop-formats">CSV <i /> TSV <i /> JSON / FHIR R4 <i /> TXT <i /> optional archive</div>
            <input ref={fileRef} className="visually-hidden" type="file" multiple onChange={update} aria-label="Select dataset files" />
            <input ref={folderRef} className="visually-hidden" type="file" multiple {...folderProps} onChange={update} aria-label="Select a dataset folder" />
            <input ref={archiveRef} className="visually-hidden" type="file" accept=".zip" onChange={update} aria-label="Select a ZIP archive" />
          </div>
          <div className="archive-row"><div className="archive-icon"><Archive size={16} /></div><div><strong>Archive import</strong><span>ZIP — extraction and safety checks belong to the backend.</span></div><button className="text-action" onClick={() => archiveRef.current?.click()}>Choose archive <ArrowUpRight size={13} /></button></div>
          <div className="selection-summary" aria-live="polite">
            <div className="summary-head"><span>LOCAL SELECTION</span><StateLabel tone={files.length ? 'mint' : 'muted'}>{files.length ? 'IN MEMORY' : 'EMPTY'}</StateLabel></div>
            {files.length ? (
              <>
                <div className="summary-numbers">
                  <div><strong>{summary.fileCount}</strong><span>files selected</span></div>
                  <div><strong>{formatBytes(summary.totalBytes)}</strong><span>total size</span></div>
                  <div><strong>{summary.otherCount}</strong><span>other / unclassified</span></div>
                </div>
                <div className="type-rollup">{Object.entries(summary.supportedTypes).length ? Object.entries(summary.supportedTypes).map(([type, count]) => <span key={type}><b>{type}</b> {count}</span>) : <span>No recognized file types</span>}</div>
                <button className="clear-selection" onClick={() => { setFiles([]); if (fileRef.current) fileRef.current.value = ''; if (folderRef.current) folderRef.current.value = ''; if (archiveRef.current) archiveRef.current.value = ''; }}>Clear selection</button>
              </>
            ) : (
              <p className="summary-empty">Selected file totals will appear here. No file content is read or retained.</p>
            )}
          </div>
        </section>
        <aside className="readiness-column">
          <div className="readiness-card">
            <div className="readiness-header"><span className="readiness-icon"><ShieldCheck size={17} /></span><span>READINESS</span><span className="readiness-number">01</span></div>
            <h3>{!connected ? 'Waiting for engine' : modelAvailable ? 'Engine and model ready' : 'Model unavailable'}</h3>
            <p>Synthetic datasets only. Candidate outputs are withheld until independent release checks pass.</p>
            <div className="readiness-divider" />
            <div className="readiness-line"><span>Processing engine</span><b>{connected ? 'Connected' : 'Not connected'}</b></div>
            <div className="readiness-line"><span>Trained model</span><b>{modelAvailable ? 'Available' : 'Unavailable'}</b></div>
            <div className="readiness-line"><span>Data transfer</span><b>{active ? 'Running' : 'Ready'}</b></div>
            <button className="button button-primary" disabled={!connected || !modelAvailable || active || !files.length} onClick={() => void launch()}><LockKeyhole size={14} /> Start Processing</button>
            <button className="button button-outline" disabled={!connected || !modelAvailable || active} onClick={() => void launch(true)}>Run official practice dataset</button>
            {error && <small role="alert">{error}</small>}
            <small>Actual processing; no mock results.</small>
            {(run?.status === 'running' || run?.status === 'queued') && (
              <div className="workspace-engine-preview" style={{marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--line)'}}>
                <PrivacyEngineAnimation stages={run?.stages} status={run?.status ?? 'idle'} releaseApproved={!!run?.releaseApproved} compact />
              </div>
            )}
          </div>
          <div className="privacy-note"><LockKeyhole size={15} /><p><strong>Private by default</strong><br />No browser storage. No raw names. Upload only when you start a run.</p></div>
        </aside>
      </div>
      <div className="supported-strip"><span>SUPPORTED INPUTS</span><div><b>CSV</b><b>TSV</b><b>JSON</b><b>FHIR R4</b><b>TXT</b><em>Unsupported files may be sent to a backend quarantine decision; this UI does not validate them.</em></div></div>
    </div>
  );
}
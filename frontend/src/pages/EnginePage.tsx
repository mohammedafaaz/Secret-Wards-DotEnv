import { Activity } from 'lucide-react';
import { PageHeader, StateLabel } from '../components/Primitives';
import { ConnectionPill } from '../components/ConnectionPill';
import { useRuntime } from '../services/runtime';
import { Link } from 'react-router-dom';
import { PrivacyEngineAnimation } from '../components/PrivacyEngineAnimation';

export default function EnginePage() {
  const { run, connected } = useRuntime();
  return (
    <div className="page-content">
      <PageHeader eyebrow="02 / PIPELINE" title="Privacy Engine" description="Actual local processing state. Stages are supplied by the local engine; no simulated progress." aside={<ConnectionPill />} />
      <div className="engine-explainer">
        <div className="engine-orb"><Activity size={17} /></div>
        <div>
          <strong>{run?.status ?? 'Unavailable'}</strong>
          <span>{run?.safeSummary ?? (connected ? 'Waiting for a dataset.' : 'Connect the local engine.')}</span>
        </div>
        <StateLabel tone={run?.releaseApproved ? 'mint' : 'amber'}>{run?.releaseApproved ? 'RELEASE APPROVED' : 'RELEASE LOCKED'}</StateLabel>
      </div>
      <section className="pipeline-panel">
        <div className="pipeline-meta">
          <span>ACTUAL RUN</span>
          <span>{run?.runId ? 'Local engine' : 'No run'}</span>
        </div>
        <PrivacyEngineAnimation stages={run?.stages} status={run?.status ?? 'idle'} releaseApproved={!!run?.releaseApproved} />
        <div className="pipeline-foot">
          <span>ELAPSED</span>
          <b>{run?.startedAt ? `${Math.max(0, Math.round((run.finishedAt ?? Date.now() / 1000) - run.startedAt))} s` : '—'}</b>
          <span>FILES</span>
          <b>{run?.counts.files_total ?? '—'}</b>
        </div>
      </section>
      <div className="hero-actions">
        <Link className="button button-outline" to="/integrity">View measured counts</Link>
        <Link className="button button-outline" to="/release">Release Center</Link>
      </div>
    </div>
  );
}
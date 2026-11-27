import { useRuntime } from '../services/runtime';
import { Activity, HeartPulse, LockKeyhole, ShieldCheck } from 'lucide-react';
import { ConnectionPill } from '../components/ConnectionPill';
import { PageHeader, StateLabel } from '../components/Primitives';
import { PrivacySafeFindingsPanel } from '../components/PrivacySafeFindingsPanel';

const privacyItems = ['Detected identifiers', 'Quasi-identifier transformations', 'Measured re-identification risk', 'Leakage verification', 'Quarantine & suppression'];
const clinicalItems = ['Medicines', 'Dosage', 'Diagnosis', 'Vitals & laboratory values', 'Hospital-stay length', 'Truthful age-band verification'];
function MeasureList({ items, values = {} }: { items: string[]; values?: Record<string, string|number> }) {
  return <dl className="measure-list">{items.map(item => <div className="measure-row" key={item}><dt>{item}</dt><dd><span>{values[item]??'Not measured'}</span></dd></div>)}</dl>;
}

function getVerificationStatus(verification: {approved?:boolean; findings?:Record<string,number>} | undefined): 'passed' | 'withheld' | 'not-measured' {
  if (!verification) return 'not-measured';
  if (verification.approved === true) return 'passed';
  return 'withheld';
}

export default function IntegrityPage() {
  const {run}=useRuntime(); const counts=run?.counts??{}; const v=run?.verification;
  const checks=v?.checks??{}; const findings=v?.findings??{};
  const verificationStatus = getVerificationStatus(v);
  const showDetails = !!run?.runId;

  return <div className="page-content">
    <PageHeader eyebrow="04 / VERIFICATION" title="Privacy & Integrity" description="Two promises, shown separately. Measurements appear only when an actual backend supplies verified results." aside={<ConnectionPill />} />
    <div className="integrity-banner">
      <div className="integrity-banner-icon"><Activity size={16} /></div>
      <p><strong>{run?.contractValid===true?"Output format check passed.":run?.contractValid===false?"Output format check failed.":"No verification results available."}</strong> Structural validity is not proof of privacy.</p>
      <StateLabel tone={verificationStatus==='passed'?'mint':verificationStatus==='withheld'?'amber':'muted'}>
        {verificationStatus==='passed'?'CHECKS PASSED':verificationStatus==='withheld'?'WITHHELD':'NOT MEASURED'}
      </StateLabel>
    </div>
    <div className="integrity-panels">
      <section className="integrity-panel privacy-panel">
        <div className="integrity-panel-head"><span className="integrity-icon"><LockKeyhole size={18} /></span><div><span>01 / PERSON</span><h2>Privacy protection</h2></div><span className="panel-index">P</span></div>
        <p className="panel-intro">Evidence that identifying information was transformed and leakage checks were performed.</p>
        <MeasureList items={privacyItems} values={{
          'Detected identifiers': counts.identifiers_detected ?? 'Not measured',
          'Quasi-identifier transformations': checks.known_identifiers ? `${checks.known_identifiers} checks` : 'Ground truth unavailable',
          'Measured re-identification risk': run?.riskProxy ? `${run.riskProxy.rare_condition_profiles} rare-condition profiles (proxy, not attack score)` : 'Not measured',
          'Leakage verification': findings.known_identifier || findings.known_name || findings.residual_labeled_pii || findings.residual_direct_pattern
            ? `${(findings.known_identifier||0)+(findings.known_name||0)+(findings.residual_labeled_pii||0)+(findings.residual_direct_pattern||0)} internal finding(s)`
            : 'No findings',
          'Quarantine & suppression': counts.files_quarantined!==undefined ? `${counts.files_quarantined} files quarantined · ${counts.records_suppressed??0} records suppressed` : 'Not measured',
        }} />
        <div className="panel-source"><span>RESULT SOURCE</span><b>{run?.runId?"Engine report (candidate) — Internal verification":"Unavailable"}</b></div>
      </section>
      <section className="integrity-panel clinical-panel">
        <div className="integrity-panel-head"><span className="integrity-icon"><HeartPulse size={18} /></span><div><span>02 / CARE</span><h2>Medical integrity</h2></div><span className="panel-index">M</span></div>
        <p className="panel-intro">Preservation checks for clinical facts and the truthful use of age bands.</p>
        <MeasureList items={clinicalItems} values={{
          Medicines: checks.clinical_probes ? `${checks.clinical_probes} probes (internal)` : 'Ground truth unavailable',
          Dosage: checks.clinical_path_checks ? `${checks.clinical_path_checks} path checks (internal)` : 'Ground truth unavailable',
          Diagnosis: findings.clinical_probe_missing ? `${findings.clinical_probe_missing} missing (internal)` : 'Ground truth unavailable',
          'Vitals & laboratory values': checks.clinical_probes ? `${checks.clinical_probes} probes (internal)` : 'Ground truth unavailable',
          'Hospital-stay length': findings.clinical_probe_missing ? `${findings.clinical_probe_missing} missing (internal)` : 'Ground truth unavailable',
          'Truthful age-band verification': run?.riskProxy ? `${run.riskProxy.coarse_age_profiles} profiles (proxy)` : 'Ground truth unavailable',
        }} />
        <p>Internal clinical probes: {checks.clinical_probes??'Not measured'}; missing: {findings.clinical_probe_missing??0}.</p>
        <div className="panel-source"><span>GROUND TRUTH</span><b>Unavailable — Internal verification only</b></div>
      </section>
    </div>
    <div className="verification-sources">
      <span className="sources-title"><ShieldCheck size={14} /> EVALUATION SOURCES</span>
      <span>Internal verification <b>{v?"Completed":"Unavailable"}</b></span>
      <span>Practice checker <b>Unavailable</b></span>
      <span>Official hidden evaluation <b>Unavailable</b></span>
    </div>
    {showDetails && <PrivacySafeFindingsPanel runId={run.runId} />}
    <details className="integrity-details"><summary>How to read these results</summary><p>Internal checks, practice-checker results and official hidden evaluation are distinct sources. This frontend will label the source and display only supported measurements supplied by the connected backend. Ground truth is required to verify clinical preservation. "Ground truth unavailable" indicates the measurement requires independent labeled data not present in this run.</p></details>
  </div>;
}

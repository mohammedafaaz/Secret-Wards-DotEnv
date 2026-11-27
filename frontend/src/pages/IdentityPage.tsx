import { useEffect, useState } from 'react';
import { useRuntime, request } from '../services/runtime';
import { Fingerprint, ListTree, Network, Search } from 'lucide-react';
import { PageHeader, StateLabel } from '../components/Primitives';
import { ConnectionPill } from '../components/ConnectionPill';

export default function IdentityPage() {
  const {run}=useRuntime(); const approved=!!run?.releaseApproved; const [data,setData]=useState<{identities:{pseudonymousId:string;linkedRecordCount:number}[];unresolvedCount:number}|null>(null);
  useEffect(()=>{let live=true;setData(null);if(approved)request<NonNullable<typeof data>>('/release/identities').then(d=>{if(live)setData(d);}).catch(()=>{});return()=>{live=false;};},[approved,run?.runId]);
  if(approved&&data)return <div className="page-content"><PageHeader eyebrow="03 / LINKAGE" title="Identity Resolution" description="Approved pseudonymous record clusters." aside={<ConnectionPill/>}/><section className="research-panel"><p>{data.unresolvedCount} unresolved records</p><div className="research-table-wrap"><table className="research-table"><thead><tr><th>Patient pseudonym</th><th>Linked records</th></tr></thead><tbody>{data.identities.map(i=><tr key={i.pseudonymousId}><td>{i.pseudonymousId}</td><td>{i.linkedRecordCount}</td></tr>)}</tbody></table></div></section></div>;
  return <div className="page-content">
    <PageHeader eyebrow="03 / LINKAGE" title="Identity Resolution" description="Explore sanitized identity clusters after a real processing run. Original identity evidence is never displayed here." aside={<ConnectionPill />} />
    <div className="identity-overview"><div><span className="identity-glyph"><Fingerprint size={20} /></span><div><strong>No resolved identities</strong><span>Identity results are withheld until the privacy release is approved.</span></div></div><StateLabel>NO DATASET</StateLabel></div>
    <section className="identity-blank" aria-label="No identity graph available">
      <div className="identity-blank-grid" aria-hidden="true"><div className="identity-blank-ring"><div /><div /><div /></div><Network size={18} className="identity-center-icon" /></div>
      <div className="identity-blank-copy"><span className="eyebrow"><span className="eyebrow-line" />CLUSTER EXPLORER</span><h2>Nothing linked.<br /><i>Nothing inferred.</i></h2><p>When backend results exist, pseudonymous clusters can be explored as a graph or a conventional list. No original names, identity numbers, phone numbers or raw match evidence will be shown.</p><div className="identity-view-switch"><button disabled aria-pressed="true"><Network size={14} /> Graph</button><button disabled><ListTree size={14} /> List</button></div></div>
    </section>
    <div className="identity-foot"><div><Search size={15} /><span>Unresolved identities remain distinct from confirmed links.</span></div><span className="mono-tag">NO MATCH OVERRIDE</span></div>
  </div>;
}

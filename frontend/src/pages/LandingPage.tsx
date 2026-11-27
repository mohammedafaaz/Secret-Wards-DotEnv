import { lazy, Suspense, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowDown, ArrowRight, ArrowUpRight, Globe2, LockKeyhole, ScanSearch, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ConnectionPill } from '../components/ConnectionPill';
import { ThemeToggle } from '../app/ThemeControl';
import { SectionRule, StateLabel } from '../components/Primitives';
import { useRuntime } from '../services/runtime';

const VaultScene = lazy(() => import('../components/VaultScene'));
const chapters = [
  { n: '01', title: 'Import', note: 'Source records enter a local boundary.' },
  { n: '02', title: 'Detect', note: 'Language and meaning are read in context.' },
  { n: '03', title: 'Link', note: 'Fragmented identities meet conservatively.' },
  { n: '04', title: 'Protect', note: 'Identifiers are transformed, medicine preserved.' },
  { n: '05', title: 'Verify', note: 'Privacy and clinical integrity are checked.' },
  { n: '06', title: 'Release', note: 'Only validated, sanitized artifacts leave.' },
];
const traps = [
  { title: 'Language Trap', text: 'Meaning may shift across English, Hindi and Hinglish.' },
  { title: 'Meaning Trap', text: 'A personal identifier and a clinical term can look alike.' },
  { title: 'Fragmented Identity Trap', text: 'One person may appear across hospitals and scripts.' },
  { title: 'Re-identification Trap', text: 'Quasi-identifiers can reveal more in combination.' },
  { title: 'Clinical Integrity Trap', text: 'Protection must not rewrite the medicine.' },
  { title: 'Hidden Leakage Trap', text: 'Sensitive values can remain outside obvious fields.' },
];

function Wordmark() {
  return <Link to="/" className="brand brand-top" aria-label="Shield, home"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span className="brand-name">shield<span className="brand-dot">.</span></span></Link>;
}

export default function LandingPage() {
  const [activeTrap, setActiveTrap] = useState(0);
  const {connected,modelAvailable}=useRuntime();
  const readiness=!connected
    ? 'The local backend is offline. Start START_SHIELD.cmd to check the engine and trained model.'
    : modelAvailable
      ? 'The local backend and trained model are ready. Start a synthetic-data run in the workspace.'
      : 'The backend is connected, but the trained model is unavailable. Releases remain locked.';
  return <div className="landing-page">
    <header className="landing-nav"><Wordmark /><nav className="landing-links" aria-label="Main navigation"><a href="#approach">Approach</a><a href="#challenges">Six challenges</a></nav><div className="landing-nav-end"><ConnectionPill compact /><ThemeToggle /><Link className="nav-launch" to="/workspace">Launch workspace <ArrowUpRight size={14} /></Link></div></header>
    <main>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-line" />A LOCAL PRIVACY FIREWALL <span className="eyebrow-index">/ 01</span></div>
          <h1 id="hero-title"><span>Protect</span><br /><em>identity.</em><br /><span>Preserve</span><br /><em>medicine.</em></h1>
          <p className="hero-lede">A multilingual privacy firewall<br />for healthcare data.</p>
          <div className="hero-actions"><Link className="button button-primary" to="/workspace">Launch Workspace <ArrowRight size={16} /></Link><a className="button button-quiet" href="#approach">Explore the Engine <ArrowDown size={14} /></a></div>
          <div className="hero-footnote"><span className="hero-footnote-line" /> OFFLINE BY DESIGN <span className="hero-footnote-copy">CPU-only · no LLM · local processing</span></div>
        </div>
        <div className="hero-art"><div className="art-ambient" /><Suspense fallback={<div className="vault-fallback" aria-hidden="true"><span /><span /><span /></div>}><VaultScene /></Suspense></div>
        <div className="hero-side-index"><span>01 — 06</span><i /><span>SCROLL TO EXPLORE</span></div>
      </section>

      <section className="approach-section" id="approach">
        <div className="approach-intro"><div className="eyebrow"><span className="eyebrow-line" />A QUIETLY RIGOROUS PROCESS</div><h2>Six moments.<br /><i>One boundary.</i></h2><p>Conceptual overview; live backend and model availability are shown in the status above.</p></div>
        <div className="chapter-rail" aria-label="Conceptual workflow">
          {chapters.map((chapter, i) => <motion.div className="chapter" key={chapter.n} initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.45 }} transition={{ delay: i * 0.06, duration: 0.45 }}>
            <span className="chapter-no">{chapter.n}</span><span className={`chapter-mark mark-${i}`}><i /></span><h3>{chapter.title}</h3><p>{chapter.note}</p>
          </motion.div>)}
        </div>
        <div className="concept-note"><span className="note-symbol">i</span><span>This sequence describes the intended workflow; run results appear in the workspace.</span><StateLabel>CONCEPTUAL</StateLabel></div>
      </section>

      <section className="vault-statement">
        <SectionRule index="02" label="DESIGN INTENT" />
        <div className="statement-row"><div className="statement-icon"><LockKeyhole size={18} /></div><div><h2>Privacy protects<br />the person.<br /><span>Integrity protects</span><br /><span>the care.</span></h2></div><aside><p>Shield is designed for synthetic Indian hospital records. It distinguishes personal information from medical meaning, connects fragmented identity carefully, and keeps clinical facts intact.</p><div className="statement-spec"><div><Globe2 size={15} /><span>EN · HI · HINGLISH</span></div><div><ScanSearch size={15} /><span>CONTEXT-AWARE DETECTION</span></div><div><ShieldCheck size={15} /><span>VERIFY BEFORE RELEASE</span></div></div></aside></div>
      </section>

      <section className="traps-section" id="challenges">
        <SectionRule index="03" label="THE SIX PRIVACY TRAPS" />
        <div className="traps-grid"><div className="traps-list" role="tablist" aria-label="Privacy challenge explanations">
          {traps.map((trap, i) => <button key={trap.title} role="tab" aria-selected={activeTrap === i} className={`trap-tab ${activeTrap === i ? 'selected' : ''}`} onClick={() => setActiveTrap(i)}><span>0{i + 1}</span><strong>{trap.title}</strong><ArrowUpRight size={14} /></button>)}
        </div><div className="trap-detail" role="tabpanel"><span className="trap-detail-no">0{activeTrap + 1} / 06</span><div className="trap-ring"><span /><span /><span /></div><h3>{traps[activeTrap].title}</h3><p>{traps[activeTrap].text}</p><small>CHALLENGE AREA · STATUS NOT YET MEASURED</small></div></div>
        <p className="trap-disclaimer">Challenge areas are explanatory only. None is marked as solved without verified backend evidence.</p>
      </section>

      <section className="final-cta"><div className="final-cta-inner"><div className="eyebrow"><span className="eyebrow-line" />LOCAL ENGINE STATUS</div><h2>Bring the data.<br /><i>Keep it private.</i></h2><p>{readiness}</p><Link className="button button-primary" to="/workspace">Open Data Workspace <ArrowRight size={16} /></Link><div className="final-stamp"><span>SH</span><span>LOCAL / PRIVATE / PRECISE</span></div></div></section>
    </main>
    <footer className="landing-footer"><Wordmark /><span>Healthcare data privacy firewall</span><span>LOCAL BACKEND · LIVE MODEL STATUS ABOVE</span></footer>
  </div>;
}

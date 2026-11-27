import { lazy, Suspense, useEffect, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Route, Routes, useLocation } from 'react-router-dom';
import LandingPage from '../pages/LandingPage';
import WorkspaceLayout from './WorkspaceLayout';

const WorkspacePage = lazy(() => import('../pages/WorkspacePage'));
const EnginePage = lazy(() => import('../pages/EnginePage'));
const IdentityPage = lazy(() => import('../pages/IdentityPage'));
const IntegrityPage = lazy(() => import('../pages/IntegrityPage'));
const ResearchPage = lazy(() => import('../pages/ResearchPage'));
const ReleasePage = lazy(() => import('../pages/ReleasePage'));

function EntryReveal() {
  const reducedMotion = useReducedMotion();
  const [visible, setVisible] = useState(() => {
    if (typeof window === 'undefined') return false;
    return !reducedMotion && !window.sessionStorage.getItem('shield-entry-seen');
  });

  useEffect(() => {
    if (!visible) return;
    const timer = window.setTimeout(() => {
      window.sessionStorage.setItem('shield-entry-seen', '1');
      setVisible(false);
    }, 1050);
    return () => window.clearTimeout(timer);
  }, [visible]);

  if (!visible) return null;
  return (
    <motion.div className="entry-reveal" aria-hidden="true"
      initial={{ opacity: 1 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <div className="entry-aperture"><i /><i /><i /></div>
      <span className="entry-wordmark">shield</span>
      <span className="entry-caption">PRIVACY VAULT / 01</span>
    </motion.div>
  );
}

function RouteStage() {
  const location = useLocation();
  const reducedMotion = useReducedMotion();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div key={location.pathname} className="route-stage"
        initial={reducedMotion ? false : { opacity: 0, y: 7 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reducedMotion ? undefined : { opacity: 0, y: -4 }}
        transition={{ duration: reducedMotion ? 0 : 0.22, ease: 'easeOut' }}>
        <Suspense fallback={<div className="route-loading" role="status">Opening workspace…</div>}>
          <Routes location={location}>
            <Route path="/" element={<LandingPage />} />
            <Route element={<WorkspaceLayout />}>
              <Route path="/workspace" element={<WorkspacePage />} />
              <Route path="/engine" element={<EnginePage />} />
              <Route path="/identities" element={<IdentityPage />} />
              <Route path="/integrity" element={<IntegrityPage />} />
              <Route path="/research" element={<ResearchPage />} />
              <Route path="/release" element={<ReleasePage />} />
            </Route>
            <Route path="*" element={<LandingPage />} />
          </Routes>
        </Suspense>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return <><EntryReveal /><RouteStage /></>;
}

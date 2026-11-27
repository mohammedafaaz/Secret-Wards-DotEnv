import { WifiOff, Wifi } from 'lucide-react';
import { useRuntime } from '../services/runtime';
export function ConnectionPill({ compact = false }: { compact?: boolean }) {
  const {connected,modelAvailable}=useRuntime(); const Icon=connected?Wifi:WifiOff;
  const status=!connected?'ENGINE OFFLINE':modelAvailable?'ENGINE CONNECTED · MODEL AVAILABLE':'ENGINE CONNECTED · MODEL UNAVAILABLE';
  return <span className={`connection-pill ${compact ? 'compact' : ''}`} role="status" aria-live="polite"><Icon size={13} strokeWidth={1.8}/><span>{status}</span></span>;
}

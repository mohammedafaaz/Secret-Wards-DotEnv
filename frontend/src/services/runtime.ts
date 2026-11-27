import { useEffect, useState } from 'react';
export type Run = { runId?: string; status: string; releaseApproved: boolean; stages: Record<string,string>; counts: Record<string,number>; contractValid: boolean|null; verification?: {approved:boolean; checks:Record<string,number>; findings:Record<string,number>; scope:string}; riskProxy?: {profiles:number;rare_condition_profiles:number;coarse_age_profiles:number;method:string}; modelActive?: boolean; resources?: {peak_rss_mb:number|null}; safeSummary?: string; startedAt?: number; finishedAt?: number; detailedFindings?: DetailedFinding[] };
export type DetailedFinding = { fileRef: string; recordLocator: string; category: string; reason: string; suggestedAction: string };
export type Health = {status:string;modelAvailable:boolean;modelFeatureVersion?:string};
export const base = (import.meta.env.VITE_BACKEND_BASE_URL || '').replace(/\/$/, '');
let sessionInitialization: Promise<boolean> | undefined;
async function fetchApi(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${base}/api${path}`, {...init, credentials:'same-origin', cache:'no-store'});
}
function initializeSession(): Promise<boolean> {
  if (!sessionInitialization) {
    sessionInitialization = fetchApi('/session', {method:'POST'})
      .then(response => response.ok)
      .finally(() => { sessionInitialization = undefined; });
  }
  return sessionInitialization;
}
async function sessionFetch(path: string, init?: RequestInit): Promise<Response> {
  let r = await fetchApi(path, init);
  if (r.status === 401 && path !== '/session') {
    if (await initializeSession()) r = await fetchApi(path, init);
  }
  return r;
}
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await sessionFetch(path, init);
  if (!r.ok) throw new Error('The engine could not complete this request.');
  return r.json() as Promise<T>;
}
export function useRuntime() {
  const [run,setRun] = useState<Run|null>(null);
  const [connected,setConnected] = useState(false);
  const [modelAvailable,setModelAvailable] = useState(false);
  useEffect(() => { let active=true; let timer: ReturnType<typeof setTimeout>;
    async function refresh() { try { const [r,health]=await Promise.all([request<Run>('/run'),request<Health>('/health')]); if(active){setRun(r);setConnected(health.status==='ready');setModelAvailable(health.modelAvailable);} } catch {if(active){setConnected(false);setModelAvailable(false);setRun(null);}} finally {if(active)timer=setTimeout(refresh,1000);} }
    void refresh(); return ()=>{active=false;clearTimeout(timer);};
  },[]);
  return {run,connected,modelAvailable};
}
export async function startRun(files?: readonly File[]) {
  if (!files) return request<Run>('/run/practice',{method:'POST'});
  const body=new FormData();
  for(const f of files) body.append('files',f,f.webkitRelativePath || f.name);
  return request<Run>('/run/upload',{method:'POST',body});
}
export async function download(path:string, name:string) {
  const r=await sessionFetch(path,{method:'GET'}); if(!r.ok)throw new Error('Download unavailable');
  const url=URL.createObjectURL(await r.blob()); const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export async function fetchFindings(): Promise<DetailedFinding[]> {
  const r=await sessionFetch('/run/findings',{method:'GET'});
  if(!r.ok) return [];
  const data=await r.json();
  return data.findings ?? [];
}

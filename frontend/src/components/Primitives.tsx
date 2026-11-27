import type { ReactNode } from 'react';
import { ArrowUpRight, CircleSlash, LockKeyhole } from 'lucide-react';

export function PageHeader({ eyebrow, title, description, aside }: { eyebrow: string; title: string; description: string; aside?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" />{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{aside && <div className="page-heading-aside">{aside}</div>}</div>;
}

export function EmptyState({ icon = 'lock', title, body, action }: { icon?: 'lock' | 'empty'; title: string; body: string; action?: ReactNode }) {
  const Icon = icon === 'lock' ? LockKeyhole : CircleSlash;
  return <section className="empty-state"><div className="empty-icon"><Icon size={17} strokeWidth={1.5} /></div><div className="empty-copy"><h3>{title}</h3><p>{body}</p>{action && <div className="empty-action">{action}</div>}</div><ArrowUpRight className="empty-corner" size={14} /></section>;
}

export function StateLabel({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'amber' | 'mint' }) {
  return <span className={`state-label state-${tone}`}><i />{children}</span>;
}

export function SectionRule({ index, label }: { index: string; label: string }) {
  return <div className="section-rule"><span>{index}</span><span>{label}</span><i /></div>;
}

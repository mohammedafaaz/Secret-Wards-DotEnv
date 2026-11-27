import { useMemo } from 'react';
import {
  FileText,
  Layers,
  Search,
  GitMerge,
  Shield,
  CheckCheck,
  Archive,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

export type StageKey =
  | 'ingestion'
  | 'normalization'
  | 'pii-detection'
  | 'identity-resolution'
  | 'transformation'
  | 'verification'
  | 'release-generation';

export interface StageConfig {
  key: StageKey;
  label: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string; strokeWidth?: number }>;
  color: string;
  bgColor: string;
}

export const STAGES: StageConfig[] = [
  {
    key: 'ingestion',
    label: 'Ingestion',
    description: 'Incoming documents entering the processing pipeline',
    icon: FileText,
    color: '#22d3ee',
    bgColor: 'rgba(34, 211, 238, 0.15)',
  },
  {
    key: 'normalization',
    label: 'Normalization',
    description: 'Different file formats being organized and standardized',
    icon: Layers,
    color: '#a855f7',
    bgColor: 'rgba(168, 85, 247, 0.15)',
  },
  {
    key: 'pii-detection',
    label: 'PII Detection',
    description: 'Sensitive information being identified and highlighted',
    icon: Search,
    color: '#f43f5e',
    bgColor: 'rgba(244, 63, 94, 0.15)',
  },
  {
    key: 'identity-resolution',
    label: 'Identity Resolution',
    description: 'Related patient records being connected across files',
    icon: GitMerge,
    color: '#f97316',
    bgColor: 'rgba(249, 115, 22, 0.15)',
  },
  {
    key: 'transformation',
    label: 'Privacy Transformation',
    description: 'Sensitive identifiers being replaced or generalized',
    icon: Shield,
    color: '#84cc16',
    bgColor: 'rgba(132, 204, 22, 0.15)',
  },
  {
    key: 'verification',
    label: 'Verification',
    description: 'Privacy and clinical integrity checks running',
    icon: CheckCheck,
    color: '#06b6d4',
    bgColor: 'rgba(6, 182, 212, 0.15)',
  },
  {
    key: 'release-generation',
    label: 'Release Generation',
    description: 'Approved sanitized documents being assembled',
    icon: Archive,
    color: '#eab308',
    bgColor: 'rgba(234, 179, 8, 0.15)',
  },
];

export type StageStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface StageState {
  key: StageKey;
  status: StageStatus;
  progress: number;
}

export function useStageAnimation(
  stages: Record<string, string> | undefined,
  status: string,
  releaseApproved: boolean
): StageState[] {
  return useMemo(() => {
    if (!stages) {
      return STAGES.map((s) => ({ key: s.key, status: 'pending' as StageStatus, progress: 0 }));
    }

    const stageOrder = STAGES.map((s) => s.key);
    const result: StageState[] = [];
    let foundRunning = false;

    for (const key of stageOrder) {
      const backendStatus = stages[key];
      let status: StageStatus = 'pending';
      let progress = 0;

      if (backendStatus === 'completed') {
        status = 'completed';
        progress = 100;
      } else if (backendStatus === 'running') {
        status = 'running';
        progress = 50;
        foundRunning = true;
      } else if (backendStatus === 'failed') {
        status = 'failed';
        progress = 0;
      } else if (!foundRunning && backendStatus !== 'completed') {
        status = 'pending';
        progress = 0;
      }

      result.push({ key, status, progress });
    }

    if (status === 'completed' && releaseApproved) {
      result.forEach((s) => {
        if (s.status !== 'failed') {
          s.status = 'completed';
          s.progress = 100;
        }
      });
    }

    if (status === 'failed') {
      const failedStage = Object.entries(stages).find(([, v]) => v === 'failed');
      if (failedStage) {
        const failedKey = failedStage[0] as StageKey;
        result.forEach((s) => {
          if (s.key === failedKey) {
            s.status = 'failed';
            s.progress = 0;
          } else if (stageOrder.indexOf(s.key) < stageOrder.indexOf(failedKey)) {
            s.status = 'completed';
            s.progress = 100;
          }
        });
      }
    }

    return result;
  }, [stages, status, releaseApproved]);
}

export function StageIndicator({ stage, config, compact = false }: { stage: StageState; config: StageConfig; compact?: boolean }) {
  const isRunning = stage.status === 'running';
  const isCompleted = stage.status === 'completed';
  const isFailed = stage.status === 'failed';
  const isPending = stage.status === 'pending';

  const Icon = config.icon;

  const ringStyle = {
    '--stage-color': config.color,
    '--stage-bg': config.bgColor,
  } as React.CSSProperties;

  if (compact) {
    return (
      <div className="stage-indicator-compact" style={ringStyle} title={`${config.label}: ${stage.status}`}>
        <div className={`stage-ring ${stage.status}`}>
          <Icon size={14} strokeWidth={2.5} />
        </div>
        <span className="stage-label-compact">{config.label}</span>
      </div>
    );
  }

  return (
    <div className="stage-indicator" style={ringStyle}>
      <div className="stage-visual">
        <div className={`stage-ring ${stage.status}`}>
          {isRunning && <Loader2 size={20} className="stage-spinner" />}
          {isCompleted && <CheckCircle2 size={20} className="stage-check" />}
          {isFailed && <AlertCircle size={20} className="stage-error" />}
          {isPending && <Icon size={20} strokeWidth={2} />}
        </div>
        {isRunning && <div className="stage-pulse-ring" />}
        {isCompleted && <div className="stage-complete-ring" />}
      </div>
      <div className="stage-info">
        <div className="stage-header">
          <Icon size={16} strokeWidth={2} />
          <div>
            <span className="stage-title">{config.label}</span>
            <span className={`stage-status-badge ${stage.status}`}>
              {stage.status === 'running' && 'Processing...'}
              {stage.status === 'completed' && 'Completed'}
              {stage.status === 'failed' && 'Failed'}
              {stage.status === 'pending' && 'Waiting'}
            </span>
          </div>
        </div>
        <p className="stage-description">{config.description}</p>
        <div className="stage-progress-bar">
          <div
            className={`stage-progress-fill ${stage.status}`}
            style={{ width: `${stage.progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}

export function PrivacyEngineAnimation({
  stages,
  status,
  releaseApproved,
  compact = false,
}: {
  stages: Record<string, string> | undefined;
  status: string;
  releaseApproved: boolean;
  compact?: boolean;
}) {
  const animatedStages = useStageAnimation(stages, status, releaseApproved);
  const allCompleted = animatedStages.every(s => s.status === 'completed' || s.status === 'failed');

  return (
    <div className={`privacy-engine-animation ${compact ? 'compact' : ''}`} role="region" aria-label="Privacy engine processing stages">
      {animatedStages.map((stage) => {
        const config = STAGES.find((s) => s.key === stage.key)!;
        return <StageIndicator key={stage.key} stage={stage} config={config} compact={compact} />;
      })}
      {(status === 'completed' && releaseApproved && allCompleted) && (
        <div className="engine-complete-banner">
          <CheckCircle2 size={16} />
          <span>Privacy engine complete — release approved</span>
        </div>
      )}
    </div>
  );
}
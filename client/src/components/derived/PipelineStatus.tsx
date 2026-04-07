/**
 * Pipeline status indicator component (Section 7.3).
 * Shows status of pipeline jobs for a node.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { pipelineJobsApi } from '../../api/endpoints';
import type { PipelineJobResponse } from '../../types';

interface PipelineStatusProps {
  nodeId: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: tokens.colors.warning,
  running: tokens.colors.accent,
  completed: tokens.colors.success,
  failed: tokens.colors.error,
  cancelled: tokens.colors.textMuted,
};

export function PipelineStatus({ nodeId }: PipelineStatusProps) {
  const [jobs, setJobs] = useState<PipelineJobResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    pipelineJobsApi.list({ target_node_id: nodeId, limit: 5 })
      .then((res) => setJobs(res.items))
      .catch(() => setJobs([]))
      .finally(() => setLoading(false));
  }, [nodeId]);

  if (loading || jobs.length === 0) return null;

  const activeJobs = jobs.filter((j) => j.status === 'pending' || j.status === 'running');
  const recentJobs = jobs.filter((j) => j.status !== 'pending' && j.status !== 'running').slice(0, 3);

  return (
    <div style={styles.container}>
      {activeJobs.length > 0 && (
        <div style={styles.activeSection}>
          {activeJobs.map((job) => (
            <div key={job.id} style={styles.activeJob}>
              <span style={styles.statusDot(job.status)} />
              <span style={styles.jobType}>{job.job_type.replace(/_/g, ' ')}</span>
              <span style={styles.jobStatus}>{job.status}</span>
            </div>
          ))}
        </div>
      )}

      {recentJobs.length > 0 && (
        <div style={styles.recentSection}>
          {recentJobs.map((job) => (
            <div key={job.id} style={styles.recentJob}>
              <span style={styles.statusDot(job.status)} />
              <span style={styles.jobTypeSmall}>{job.job_type.replace(/_/g, ' ')}</span>
              {job.error_message && (
                <span style={styles.errorMsg} title={job.error_message}>!</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties | ((...args: any[]) => React.CSSProperties)> = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 4,
  },
  activeSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 2,
  },
  activeJob: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '3px 8px',
    background: `${tokens.colors.accent}10`,
    borderRadius: tokens.radius,
    fontSize: 12,
  },
  recentSection: {
    display: 'flex',
    gap: 6,
  },
  recentJob: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  statusDot: (status: string): React.CSSProperties => ({
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: STATUS_COLORS[status] || tokens.colors.textMuted,
    flexShrink: 0,
  }),
  jobType: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.text,
    textTransform: 'capitalize' as const,
  },
  jobTypeSmall: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    textTransform: 'capitalize' as const,
  },
  jobStatus: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
    marginLeft: 'auto',
  },
  errorMsg: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.error,
    fontWeight: 700,
  },
};

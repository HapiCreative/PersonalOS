/**
 * Context Layer component (Section 9.1, Phase 5).
 * Bottom section of the Detail Pane showing related content.
 *
 * 2-stage retrieval:
 * - Stage 1: Explicit links via graph traversal (highest confidence, unlabeled)
 * - Stage 2: Suggested links via embedding similarity (labeled "Suggested")
 *
 * Priority order:
 * 1. Backlinks (grouped by relation type)
 * 2. Outgoing links (weight indicators for goals)
 * 3. Provenance / supporting sources
 * 4. Review status / habit signals / activity
 * 5. AI suggestions (pending edges, max 2)
 * 6. Resurfaced content (max 2)
 * 7. Decay flags (max 1)
 *
 * Invariant U-03: Hard cap of 8 items, target 5-8.
 * Invariant U-04: Per-category caps enforced by backend.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { derivedApi, edgesApi, edgeStateApi, llmApi } from '../../api/endpoints';
import type { ContextLayerResponse, ContextCategoryResponse, ContextItemResponse, EdgeState } from '../../types';

const CATEGORY_LABELS: Record<string, string> = {
  backlinks: 'Backlinks',
  outgoing_links: 'Outgoing Links',
  provenance: 'Provenance',
  review_status: 'Review Status',
  ai_suggestions: 'AI Suggestions',
  resurfaced: 'Resurfaced',
  decay_flags: 'Decay Flags',
};

const CATEGORY_ICONS: Record<string, string> = {
  backlinks: '\u2190',
  outgoing_links: '\u2192',
  provenance: '\u2197',
  review_status: '\u25C7',
  ai_suggestions: '\u2726',
  resurfaced: '\u21BB',
  decay_flags: '\u26A0',
};

const NODE_TYPE_LABELS: Record<string, string> = {
  kb_entry: 'KB',
  task: 'Task',
  journal_entry: 'Journal',
  goal: 'Goal',
  memory: 'Memory',
  source_item: 'Source',
  inbox_item: 'Inbox',
  project: 'Project',
};

const RELATION_TYPE_LABELS: Record<string, string> = {
  semantic_reference: 'References',
  derived_from_source: 'Derived from',
  parent_child: 'Parent/Child',
  belongs_to: 'Belongs to',
  goal_tracks_task: 'Tracks',
  goal_tracks_kb: 'Tracks KB',
  blocked_by: 'Blocked by',
  journal_reflects_on: 'Reflects on',
  source_supports_goal: 'Supports',
  source_quoted_in: 'Quoted in',
  captured_for: 'Captured for',
};

interface ContextLayerProps {
  nodeId: string;
  onNavigateToNode?: (nodeId: string, nodeType: string) => void;
}

export function ContextLayer({ nodeId, onNavigateToNode }: ContextLayerProps) {
  const [data, setData] = useState<ContextLayerResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const fetchContext = useCallback(async () => {
    if (!nodeId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await derivedApi.getContextLayer(nodeId);
      setData(result);
    } catch (e: any) {
      setError(e.message || 'Failed to load context');
    } finally {
      setLoading(false);
    }
  }, [nodeId]);

  useEffect(() => {
    fetchContext();
  }, [fetchContext]);

  // Phase 9: Link suggestion accept/dismiss via edge state transitions
  const handlePromoteLink = useCallback(async (edgeId: string) => {
    try {
      await edgeStateApi.updateState(edgeId, 'active');
      await fetchContext();
    } catch (e: any) {
      console.error('Failed to promote link:', e);
    }
  }, [fetchContext]);

  const handleDismissLink = useCallback(async (edgeId: string) => {
    try {
      await edgeStateApi.updateState(edgeId, 'dismissed');
      await fetchContext();
    } catch (e: any) {
      console.error('Failed to dismiss link:', e);
    }
  }, [fetchContext]);

  // Phase 9: Trigger link suggestions for this node
  const handleSuggestLinks = useCallback(async () => {
    try {
      await llmApi.suggestLinks(nodeId);
      await fetchContext();
    } catch (e: any) {
      console.error('Failed to suggest links:', e);
    }
  }, [nodeId, fetchContext]);

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <span style={styles.headerTitle}>Context</span>
        </div>
        <div style={styles.loadingState}>Loading context...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <span style={styles.headerTitle}>Context</span>
        </div>
        <div style={styles.errorState}>{error}</div>
      </div>
    );
  }

  if (!data || data.total_count === 0) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <span style={styles.headerTitle}>Context</span>
          <span style={styles.headerCount}>0</span>
        </div>
        <div style={styles.emptyState}>No related items</div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={styles.header}
      >
        <span style={styles.headerIcon}>{collapsed ? '\u25B6' : '\u25BC'}</span>
        <span style={styles.headerTitle}>Context</span>
        <span style={styles.headerCount}>
          {data.total_count}
          {/* Invariant U-03: Hard cap of 8 items */}
        </span>
        {data.suppression_applied && (
          <span style={styles.suppressionBadge} title="Some items suppressed due to volume">
            filtered
          </span>
        )}
      </button>

      {/* Phase 9: Suggest Links button */}
      <div style={styles.suggestLinksRow}>
        <button onClick={handleSuggestLinks} style={styles.suggestLinksButton}>
          Suggest Links
        </button>
      </div>

      {!collapsed && (
        <div style={styles.categoriesContainer}>
          {data.categories.map((category) => (
            <ContextCategory
              key={category.name}
              category={category}
              onNavigateToNode={onNavigateToNode}
              onPromote={handlePromoteLink}
              onDismiss={handleDismissLink}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ContextCategory({
  category,
  onNavigateToNode,
  onPromote,
  onDismiss,
}: {
  category: ContextCategoryResponse;
  onNavigateToNode?: (nodeId: string, nodeType: string) => void;
  onPromote: (edgeId: string) => void;
  onDismiss: (edgeId: string) => void;
}) {
  const label = CATEGORY_LABELS[category.name] || category.name;
  const icon = CATEGORY_ICONS[category.name] || '\u25CF';

  return (
    <div style={styles.category}>
      <div style={styles.categoryHeader}>
        <span style={styles.categoryIcon}>{icon}</span>
        <span style={styles.categoryTitle}>{label}</span>
        <span style={styles.categoryCount}>{category.items.length}</span>
      </div>
      <div style={styles.categoryItems}>
        {category.items.map((item, idx) => (
          <ContextItemCard
            key={`${item.node_id}-${idx}`}
            item={item}
            onNavigateToNode={onNavigateToNode}
            onPromote={onPromote}
            onDismiss={onDismiss}
          />
        ))}
      </div>
    </div>
  );
}

function ContextItemCard({
  item,
  onNavigateToNode,
  onPromote,
  onDismiss,
}: {
  item: ContextItemResponse;
  onNavigateToNode?: (nodeId: string, nodeType: string) => void;
  onPromote: (edgeId: string) => void;
  onDismiss: (edgeId: string) => void;
}) {
  const handleClick = () => {
    if (onNavigateToNode) {
      onNavigateToNode(item.node_id, item.node_type);
    }
  };

  const typeLabel = NODE_TYPE_LABELS[item.node_type] || item.node_type;
  const relationLabel = item.relation_type
    ? RELATION_TYPE_LABELS[item.relation_type] || item.relation_type
    : null;

  return (
    <div style={styles.itemCard}>
      <button onClick={handleClick} style={styles.itemClickable}>
        <div style={styles.itemTop}>
          <span style={styles.itemTypeBadge}>{typeLabel}</span>
          <span style={styles.itemTitle}>{item.title}</span>
          {item.label && (
            <span style={styles.suggestedBadge}>{item.label}</span>
          )}
        </div>
        <div style={styles.itemMeta}>
          {relationLabel && (
            <span style={styles.relationLabel}>{relationLabel}</span>
          )}
          {item.weight !== null && item.weight !== undefined && item.weight !== 1.0 && (
            <span style={styles.weightLabel}>w:{item.weight.toFixed(1)}</span>
          )}
          {item.confidence !== null && item.confidence !== undefined && (
            <span style={styles.confidenceLabel}>
              {Math.round(item.confidence * 100)}%
            </span>
          )}
          {item.signal_score !== null && item.signal_score !== undefined && (
            <span style={styles.signalLabel}>
              S:{item.signal_score.toFixed(2)}
            </span>
          )}
        </div>
      </button>

      {/* One-click promotion for suggested items */}
      {item.is_suggested && item.edge_id && (
        <div style={styles.itemActions}>
          <button
            onClick={() => onPromote(item.edge_id!)}
            style={styles.actionButton}
            title="Promote to explicit link"
          >
            +
          </button>
          <button
            onClick={() => onDismiss(item.edge_id!)}
            style={styles.actionButtonDismiss}
            title="Dismiss suggestion"
          >
            x
          </button>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    borderTop: `1px solid ${tokens.colors.border}`,
    background: tokens.colors.surface,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '8px 16px',
    width: '100%',
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    textAlign: 'left' as const,
  },
  headerIcon: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    width: 12,
  },
  headerTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 12,
    color: tokens.colors.text,
    flex: 1,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  headerCount: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    padding: '1px 5px',
    background: `${tokens.colors.textMuted}15`,
    borderRadius: tokens.radius,
  },
  suppressionBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 9,
    color: tokens.colors.warning,
    padding: '1px 4px',
    border: `1px solid ${tokens.colors.warning}40`,
    borderRadius: tokens.radius,
    marginLeft: 4,
  },
  loadingState: {
    padding: '12px 16px',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
  },
  errorState: {
    padding: '12px 16px',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.error,
  },
  emptyState: {
    padding: '12px 16px',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
  },
  categoriesContainer: {
    display: 'flex',
    flexDirection: 'column',
  },
  category: {
    borderTop: `1px solid ${tokens.colors.border}`,
  },
  categoryHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '6px 16px',
  },
  categoryIcon: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.accent,
    width: 16,
    textAlign: 'center' as const,
  },
  categoryTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 500,
    fontSize: 11,
    color: tokens.colors.textMuted,
    flex: 1,
  },
  categoryCount: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
  },
  categoryItems: {
    display: 'flex',
    flexDirection: 'column',
  },
  itemCard: {
    display: 'flex',
    alignItems: 'center',
    borderTop: `1px solid ${tokens.colors.border}20`,
  },
  itemClickable: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    padding: '6px 16px 6px 34px',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    textAlign: 'left' as const,
  },
  itemTop: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  itemTypeBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 9,
    color: tokens.colors.textMuted,
    padding: '0px 4px',
    background: `${tokens.colors.textMuted}15`,
    borderRadius: '2px',
    flexShrink: 0,
  },
  itemTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.text,
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  suggestedBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 9,
    color: tokens.colors.violet,
    padding: '0px 4px',
    border: `1px solid ${tokens.colors.violet}50`,
    borderRadius: '2px',
    flexShrink: 0,
  },
  itemMeta: {
    display: 'flex',
    gap: 8,
    paddingLeft: 0,
  },
  relationLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
  },
  weightLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
  },
  confidenceLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.violet,
  },
  signalLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
  },
  itemActions: {
    display: 'flex',
    gap: 4,
    padding: '0 8px',
    flexShrink: 0,
  },
  actionButton: {
    width: 20,
    height: 20,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '2px',
    border: `1px solid ${tokens.colors.accent}50`,
    background: 'none',
    color: tokens.colors.accent,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    cursor: 'pointer',
    padding: 0,
  },
  actionButtonDismiss: {
    width: 20,
    height: 20,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '2px',
    border: `1px solid ${tokens.colors.textMuted}50`,
    background: 'none',
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    cursor: 'pointer',
    padding: 0,
  },
  suggestLinksRow: {
    padding: '4px 16px 8px',
    display: 'flex',
    justifyContent: 'flex-end',
  },
  suggestLinksButton: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.violet,
    background: `${tokens.colors.violet}10`,
    border: `1px solid ${tokens.colors.violet}30`,
    borderRadius: tokens.radius,
    padding: '3px 8px',
    cursor: 'pointer',
  },
};

/**
 * TypeScript types matching the backend schemas.
 * Mirrors the Pydantic models and database enums.
 */

// Section 2.2: Node types
export type NodeType =
  | 'kb_entry'
  | 'task'
  | 'journal_entry'
  | 'goal'
  | 'memory'
  | 'source_item'
  | 'inbox_item'
  | 'project';

// Section 2.3: Edge relation types (all 11)
export type EdgeRelationType =
  | 'semantic_reference'
  | 'derived_from_source'
  | 'parent_child'
  | 'belongs_to'
  | 'goal_tracks_task'
  | 'goal_tracks_kb'
  | 'blocked_by'
  | 'journal_reflects_on'
  | 'source_supports_goal'
  | 'source_quoted_in'
  | 'captured_for';

export type EdgeOrigin = 'user' | 'system' | 'llm';
export type EdgeState = 'active' | 'pending_review' | 'dismissed';

// Inbox item status (Section 2.4)
export type InboxItemStatus = 'pending' | 'promoted' | 'dismissed' | 'merged' | 'archived';

// Task status (Section 2.4) - Invariant B-03: state machine
export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'cancelled';

// Task priority (Section 2.4)
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';

// Mood (Section 2.4) - v6 ENUM
export type Mood = 'great' | 'good' | 'neutral' | 'low' | 'bad';

// Task execution event type (Section 3.7)
export type TaskExecutionEventType = 'completed' | 'skipped' | 'deferred';

// Template target type (Section 2.4)
export type TemplateTargetType = 'goal' | 'task' | 'journal_entry';

// Response types
export interface NodeResponse {
  id: string;
  type: NodeType;
  owner_id: string;
  title: string;
  summary: string | null;
  created_at: string;
  updated_at: string;
  last_accessed_at: string | null;
  archived_at: string | null;
}

export interface NodeListResponse {
  items: NodeResponse[];
  total: number;
}

export interface EdgeResponse {
  id: string;
  source_id: string;
  target_id: string;
  relation_type: EdgeRelationType;
  origin: EdgeOrigin;
  state: EdgeState;
  weight: number;
  confidence: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface EdgeListResponse {
  items: EdgeResponse[];
  total: number;
}

export interface InboxItemResponse {
  node_id: string;
  title: string;
  raw_text: string;
  status: InboxItemStatus;
  promoted_to_node_id: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface InboxItemListResponse {
  items: InboxItemResponse[];
  total: number;
}

// Phase 5: Search result with signal score
export interface SearchResultItem {
  node: NodeResponse;
  signal_score: number | null;
}

export interface SearchResponse {
  items: SearchResultItem[];
  total: number;
  query: string;
}

// Phase 2: Task response
export interface TaskResponse {
  node_id: string;
  title: string;
  summary: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  recurrence: string | null;
  is_recurring: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface TaskListResponse {
  items: TaskResponse[];
  total: number;
}

// Phase 2: Journal response
export interface JournalResponse {
  node_id: string;
  title: string;
  summary: string | null;
  content: string;
  entry_date: string;
  mood: Mood | null;
  tags: string[];
  word_count: number;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface JournalListResponse {
  items: JournalResponse[];
  total: number;
}

// Phase 2: Template response
export interface TemplateResponse {
  id: string;
  owner_id: string;
  name: string;
  target_type: TemplateTargetType;
  structure: Record<string, unknown>;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface TemplateListResponse {
  items: TemplateResponse[];
  total: number;
}

// Phase 2: Task execution event response
export interface TaskExecutionEventResponse {
  id: string;
  task_id: string;
  user_id: string;
  event_type: TaskExecutionEventType;
  expected_for_date: string;
  notes: string | null;
  created_at: string;
  node_deleted: boolean;
}

export interface TaskExecutionEventListResponse {
  items: TaskExecutionEventResponse[];
  total: number;
}

export interface UserResponse {
  id: string;
  username: string;
  display_name: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

// =============================================================================
// Phase 3: Sources + KB + Memory
// =============================================================================

// Source type (Section 6)
export type SourceType = 'article' | 'tweet' | 'bookmark' | 'note' | 'podcast' | 'video' | 'pdf' | 'other';

// Source processing status (Section 6: 4-stage)
export type ProcessingStatus = 'raw' | 'normalized' | 'enriched' | 'error';

// Source triage status (Section 6)
export type TriageStatus = 'unreviewed' | 'ready' | 'promoted' | 'dismissed';

// Source permanence (Section 6)
export type Permanence = 'ephemeral' | 'reference' | 'canonical';

// Source fragment type (Section 6)
export type FragmentType = 'paragraph' | 'quote' | 'heading' | 'list_item' | 'code' | 'image_ref';

// KB compile status (Section 7: 6-stage)
export type CompileStatus = 'ingest' | 'parse' | 'compile' | 'review' | 'accept' | 'stale';

// KB pipeline stage (Section 7: 5-stage)
export type PipelineStage = 'draft' | 'review' | 'accepted' | 'published' | 'archived';

// Memory type (Section 2.4)
export type MemoryType = 'decision' | 'insight' | 'lesson' | 'principle' | 'preference';

// Source response
export interface SourceResponse {
  node_id: string;
  title: string;
  summary: string | null;
  source_type: SourceType;
  url: string | null;
  author: string | null;
  platform: string | null;
  published_at: string | null;
  captured_at: string;
  capture_context: string | null;
  raw_content: string;
  canonical_content: string | null;
  processing_status: ProcessingStatus;
  triage_status: TriageStatus;
  permanence: Permanence;
  checksum: string | null;
  media_refs: unknown[];
  // Phase 10: ai_summary, ai_takeaways, ai_entities removed.
  // Enrichments now live in node_enrichments (Section 4.8).
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface SourceListResponse {
  items: SourceResponse[];
  total: number;
}

export interface SourcePromoteResponse {
  promoted_node_id: string;
  edge_id: string;
  source_node_id: string;
  target_type: string;
}

// Source fragment response
export interface FragmentResponse {
  id: string;
  source_node_id: string;
  fragment_text: string;
  position: number;
  fragment_type: FragmentType;
  section_ref: string | null;
  created_at: string;
}

export interface FragmentListResponse {
  items: FragmentResponse[];
  total: number;
}

// KB response
export interface KBResponse {
  node_id: string;
  title: string;
  summary: string | null;
  content: string;
  raw_content: string | null;
  compile_status: CompileStatus;
  pipeline_stage: PipelineStage;
  tags: string[];
  compile_version: number;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface KBListResponse {
  items: KBResponse[];
  total: number;
}

export interface KBCompileResponse {
  node_id: string;
  compile_status: CompileStatus;
  pipeline_stage: PipelineStage;
  compile_version: number;
}

// Memory response
export interface MemoryResponse {
  node_id: string;
  title: string;
  summary: string | null;
  memory_type: MemoryType;
  content: string;
  context: string | null;
  review_at: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface MemoryListResponse {
  items: MemoryResponse[];
  total: number;
}

// =============================================================================
// Phase 4: Goals + Today View
// =============================================================================

// Goal status (Section 2.4)
export type GoalStatus = 'active' | 'completed' | 'archived';

// Goal response
export interface GoalResponse {
  node_id: string;
  title: string;
  summary: string | null;
  status: GoalStatus;
  start_date: string | null;
  end_date: string | null;
  timeframe_label: string | null;
  progress: number; // CACHED DERIVED, Invariant D-03
  milestones: Record<string, unknown>[];
  notes: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface GoalLinkedTaskResponse {
  node_id: string;
  title: string;
  status: string;
  priority: string;
  due_date: string | null;
  is_recurring: boolean;
  edge_id: string;
  edge_weight: number;
}

export interface GoalWithTasksResponse extends GoalResponse {
  linked_tasks: GoalLinkedTaskResponse[];
}

export interface GoalListResponse {
  items: GoalResponse[];
  total: number;
}

// Today View (Section 5.1)
export interface TodayItemResponse {
  section: string;
  item_type: string;
  node_id: string | null;
  title: string;
  subtitle: string;
  priority: string | null;
  due_date: string | null;
  progress: number | null;
  is_unsolicited: boolean;
  metadata: Record<string, unknown>;
}

export interface TodaySectionResponse {
  name: string;
  items: TodayItemResponse[];
}

export interface TodayViewResponse {
  items: TodayItemResponse[];
  total_count: number;
  sections: TodaySectionResponse[];
  stage: string;
  date: string;
  has_plan: boolean; // Phase 7: whether morning commitment exists
  active_focus_task_id: string | null; // Phase 7: task in active focus session
}

// =============================================================================
// Phase 5: Derived Intelligence + Context Layer
// =============================================================================

// Signal score (Section 4 — 5-factor composite)
// Invariant D-03: Non-canonical, recomputable (D-02)
export interface SignalScoreResponse {
  node_id: string;
  score: number;
  recency_score: number;
  link_density_score: number;
  completion_state_score: number;
  reference_frequency_score: number;
  user_interaction_score: number;
  computed_at: string;
  version: string | null;
}

export interface SignalScoreBatchResponse {
  items: SignalScoreResponse[];
  total: number;
}

// Progress intelligence (Section 4)
// Invariant D-03: Non-canonical, recomputable (D-02)
export interface ProgressIntelligenceResponse {
  node_id: string;
  progress: number;
  momentum: number;
  consistency_streak: number;
  drift_score: number;
  last_progress_at: string | null;
  computed_at: string;
  version: string | null;
}

export interface ProgressBatchResponse {
  items: ProgressIntelligenceResponse[];
  total: number;
}

// Retrieval modes (Section 4)
export interface RetrievalModeInfo {
  name: string;
  description: string;
  max_results: number;
  type_weights: Record<string, number>;
  recency_bias: number;
}

export interface RetrievalResultResponse {
  node_id: string;
  node_type: string;
  title: string;
  summary: string | null;
  signal_score: number | null;
  mode_weight: number;
  combined_score: number;
  metadata: Record<string, unknown>;
}

export interface RetrievalResponse {
  mode: string;
  items: RetrievalResultResponse[];
  total: number;
}

// Context layer (Section 4, 9.1)
// Invariant U-03: Hard cap of 8 items
// Invariant U-04: Per-category caps
export interface ContextItemResponse {
  category: string;
  node_id: string;
  node_type: string;
  title: string;
  relation_type: string | null;
  edge_id: string | null;
  weight: number | null;
  confidence: number | null;
  is_suggested: boolean;
  label: string | null;
  signal_score: number | null;
  metadata: Record<string, unknown>;
}

export interface ContextCategoryResponse {
  name: string;
  items: ContextItemResponse[];
}

export interface ContextLayerResponse {
  items: ContextItemResponse[];
  total_count: number;
  categories: ContextCategoryResponse[];
  node_id: string;
  suppression_applied: boolean;
}

// =============================================================================
// Phase 6: Stale Detection + Cleanup System + DerivedExplanation
// =============================================================================

// Section 4.11: DerivedExplanation schema type
// Invariant D-01: Required for all user-facing Derived outputs
export interface DerivedFactor {
  signal: string;
  value: unknown;
  weight: number;
}

export interface DerivedExplanation {
  summary: string;
  factors: DerivedFactor[];
  confidence?: number | null;
  generated_at?: string | null;
  version?: string | null;
}

// Stale item (Section 4.6)
export interface StaleItemResponse {
  node_id: string;
  node_type: string;
  title: string;
  stale_category: string;
  days_stale: number;
  last_activity_at: string | null;
  prompt: string;
  explanation: DerivedExplanation; // Invariant D-01
  snoozed_until: string | null;
  metadata: Record<string, unknown>;
}

// Cleanup queue (Section 5.6)
export interface CleanupQueueResponse {
  items: StaleItemResponse[];
  total_stale: number;
  total_snoozed: number;
  total_archived: number;
  categories: Record<string, StaleItemResponse[]>;
}

// Cleanup action
export type CleanupAction = 'archive' | 'snooze' | 'keep';

export interface CleanupActionRequest {
  action: CleanupAction;
  node_ids: string[];
  snoozed_until?: string;
}

export interface CleanupActionResponse {
  action: string;
  affected_node_ids: string[];
  total_affected: number;
}

// Snooze record (Section 3.5)
export interface SnoozeResponse {
  id: string;
  node_id: string;
  snoozed_until: string;
  created_at: string;
}

// Stale check result
export interface StaleCheckResponse {
  is_stale: boolean;
  node_id: string;
  stale_category?: string | null;
  days_stale?: number | null;
  prompt?: string | null;
  explanation?: DerivedExplanation | null;
}

// =============================================================================
// Phase 7: Daily Behavior Loop (Morning Commit + Focus + Evening Reflection)
// =============================================================================

// Daily plan (Section 3, TABLE 22)
export interface DailyPlanResponse {
  id: string;
  user_id: string;
  date: string;
  selected_task_ids: string[];
  intention_text: string | null;
  created_at: string;
  closed_at: string | null;
}

export interface DailyPlanListResponse {
  items: DailyPlanResponse[];
  total: number;
}

// Focus session (Section 3, TABLE 25)
export interface FocusSessionResponse {
  id: string;
  user_id: string;
  task_id: string;
  started_at: string;
  ended_at: string | null;
  duration: number | null; // seconds
}

export interface FocusSessionListResponse {
  items: FocusSessionResponse[];
  total: number;
}

// Morning commit suggestions
export interface SuggestedTaskResponse {
  node_id: string;
  title: string;
  priority: string;
  due_date: string | null;
  status: string;
  is_recurring: boolean;
  signal_score: number | null;
  reason: string; // overdue, due_today, high_signal, goal_drift
  goal_title: string | null;
}

export interface MorningCommitSuggestionsResponse {
  suggested_tasks: SuggestedTaskResponse[];
  existing_plan: Record<string, unknown> | null;
  date: string;
  ai_briefing: string[];
}

export interface CommitResponse {
  id: string;
  date: string;
  selected_task_ids: string[];
  intention_text: string | null;
  created_at: string;
  closed_at: string | null;
}

// Evening reflection
export interface TaskReflectionItemResponse {
  node_id: string;
  title: string;
  priority: string;
  status: string;
  was_planned: boolean;
  event_type: string | null;
  focus_time_seconds: number;
  notes: string | null;
}

export interface ReflectionPromptResponse {
  prompt_id: string;
  text: string;
  category: string; // completion, blockers, gratitude, tomorrow
}

export interface EveningReflectionResponse {
  date: string;
  plan_exists: boolean;
  planned_tasks: TaskReflectionItemResponse[];
  unplanned_completed: TaskReflectionItemResponse[];
  total_planned: number;
  total_completed: number;
  total_focus_time_seconds: number;
  completion_rate: number; // 0.0-1.0
  prompts: ReflectionPromptResponse[];
  plan_id: string | null;
  intention_text: string | null;
}

export interface ReflectionSubmitResponse {
  skipped: string[];
  deferred: string[];
  plan_closed: boolean;
  errors: string[];
}

// =============================================================================
// Phase 8: Projects + Weekly/Monthly Reviews
// =============================================================================

// Project status (Section 2.4)
export type ProjectStatus = 'active' | 'completed' | 'archived';

// Project response
export interface ProjectResponse {
  node_id: string;
  title: string;
  summary: string | null;
  status: ProjectStatus;
  description: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface ProjectListResponse {
  items: ProjectResponse[];
  total: number;
}

export interface ProjectLinkedItemResponse {
  node_id: string;
  title: string;
  node_type: string; // 'goal' or 'task'
  status: string;
  edge_id: string;
  edge_weight: number;
}

export interface ProjectWithLinksResponse extends ProjectResponse {
  linked_items: ProjectLinkedItemResponse[];
}

// Weekly review (Section 5.5)
export interface WeeklyTaskSummaryResponse {
  node_id: string;
  title: string;
  status: string;
  priority: string;
  completed: boolean;
  was_planned: boolean;
}

export interface WeeklyGoalSummaryResponse {
  node_id: string;
  title: string;
  status: string;
  progress: number;
  linked_task_count: number;
  completed_task_count: number;
}

export interface WeeklyReviewSummaryResponse {
  week_start: string;
  week_end: string;
  completed_tasks: WeeklyTaskSummaryResponse[];
  planned_tasks: WeeklyTaskSummaryResponse[];
  stalled_goals: WeeklyGoalSummaryResponse[];
  active_goals: WeeklyGoalSummaryResponse[];
  total_planned: number;
  total_completed: number;
  completion_rate: number;
  total_focus_time_seconds: number;
  existing_snapshot: Record<string, unknown> | null;
}

export interface WeeklySnapshotResponse {
  id: string;
  week_start_date: string;
  week_end_date: string;
  focus_areas: string[];
  priority_task_ids: string[];
  notes: string | null;
  created_at: string;
}

// Monthly review (Section 5.5)
export interface MonthlyGoalSummaryResponse {
  node_id: string;
  title: string;
  status: string;
  progress: number;
  tasks_completed_this_month: number;
}

export interface WeeklySnapshotBriefResponse {
  week_start: string;
  week_end: string;
  focus_areas: string[];
  notes: string | null;
}

export interface MonthlyReviewSummaryResponse {
  month: string;
  month_name: string;
  weekly_snapshots: WeeklySnapshotBriefResponse[];
  goals: MonthlyGoalSummaryResponse[];
  total_tasks_completed: number;
  total_focus_time_seconds: number;
  existing_snapshot: Record<string, unknown> | null;
}

export interface MonthlySnapshotResponse {
  id: string;
  month: string;
  focus_areas: string[];
  notes: string | null;
  created_at: string;
}

// =============================================================================
// Phase 9: AI Modes + LLM Pipeline + Enrichments
// =============================================================================

// Pipeline job types (Section 7.3)
export type PipelineJobType =
  | 'compile'
  | 'lint'
  | 'embed'
  | 'suggest_links'
  | 'normalize_source'
  | 'enrich_source'
  | 'classify_inbox';

export type PipelineJobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

// Enrichment types (Section 4.8)
export type EnrichmentType = 'summary' | 'takeaways' | 'entities';
export type EnrichmentStatus = 'pending' | 'processing' | 'completed' | 'failed';

// AI modes (Section 5.5)
export type AIMode = 'ask' | 'plan' | 'reflect' | 'improve';

// Pipeline job response
export interface PipelineJobResponse {
  id: string;
  user_id: string;
  target_node_id: string | null;
  job_type: PipelineJobType;
  status: PipelineJobStatus;
  idempotency_key: string | null;
  prompt_version: string | null;
  model_version: string | null;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  error_message: string | null;
  retry_count: number;
  max_retries: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface PipelineJobListResponse {
  items: PipelineJobResponse[];
  total: number;
}

// Node enrichment response (Section 4.8)
// Invariant S-05: One active enrichment per type
export interface EnrichmentResponse {
  id: string;
  node_id: string;
  enrichment_type: EnrichmentType;
  payload: Record<string, unknown>;
  status: EnrichmentStatus;
  prompt_version: string | null;
  model_version: string | null;
  superseded_at: string | null;
  created_at: string;
  pipeline_job_id: string | null;
}

export interface EnrichmentListResponse {
  items: EnrichmentResponse[];
  total: number;
}

// AI Mode responses (Section 5.5)
export interface AICitationResponse {
  node_id: string;
  title: string;
  node_type: string;
}

export interface AIContextItemResponse {
  node_id: string;
  node_type: string;
  title: string;
  summary: string | null;
  combined_score: number;
}

export interface AIModeResponse {
  mode: AIMode;
  query: string;
  response_text: string;
  response_data: Record<string, unknown>;
  citations: AICitationResponse[];
  context_items: AIContextItemResponse[];
  duration_ms: number;
  model_version: string;
  prompt_version: string;
}

// Link suggestion response
export interface LinkSuggestionResponse {
  edge_id: string;
  source_id: string;
  target_id: string;
  relation_type: EdgeRelationType;
  confidence: number | null;
  rationale: string;
}

export interface SuggestLinksResponse {
  node_id: string;
  suggestions: LinkSuggestionResponse[];
  total: number;
}

// Source enrichment response
export interface EnrichSourceResponse {
  node_id: string;
  status: string;
  enrichments: Record<string, string>;
  error: string | null;
}

// KB lint response
export interface LintKBResponse {
  node_id: string;
  quality_score: number | null;
  is_stale: boolean | null;
  issues: string[];
  suggestions: string[];
  error: string | null;
}

// Inbox classification response
export interface ClassifyInboxResponse {
  node_id: string;
  classification: string | null;
  title: string | null;
  priority: string | null;
  memory_type: string | null;
  confidence: number | null;
  rationale: string | null;
  error: string | null;
}

// AI briefing response
export interface BriefingResponse {
  bullets: string[];
}

// =============================================================================
// Phase 10: Export/Import + Admin
// =============================================================================

export interface ExportResponse {
  version: string;
  exported_at: string;
  owner_id: string;
  node_count: number;
  edge_count: number;
  enrichment_count: number;
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  enrichments: Record<string, unknown>[];
}

export interface ImportResponse {
  nodes_created: number;
  nodes_skipped: number;
  edges_created: number;
  edges_skipped: number;
  enrichments_created: number;
  errors: string[];
  id_mapping: Record<string, string>;
}

export interface RetentionEnforceResponse {
  pipeline_jobs_deleted: number;
  enrichments_deleted: number;
  errors: string[];
}

export interface RetentionStatsResponse {
  pipeline_jobs: {
    total: number;
    eligible_for_cleanup: number;
    retention_days: number;
  };
  enrichments: {
    total: number;
    superseded_eligible_for_cleanup: number;
    retention_days: number;
  };
}

export interface BatchEmbedResponse {
  total_processed: number;
  total_embedded: number;
  total_skipped: number;
  total_errors: number;
  node_ids_embedded: string[];
}

export interface CacheRefreshResponse {
  materialized_views: Record<string, string>;
}

// =============================================================================
// Phase PC: Analytics + Intelligence
// =============================================================================

// Invariant D-04: Analytics output classification
export type AnalyticsClassification = 'descriptive' | 'correlational' | 'recommendation';

// Analytics output (Invariant D-04: every output must be classified)
export interface AnalyticsOutputResponse {
  classification: AnalyticsClassification;
  label: string; // "" for descriptive, "Pattern detected" for correlational, "Suggestion" for recommendation
  explanation: DerivedExplanation;
  data: Record<string, unknown>;
}

// Tier A: Operational metrics (live query - today/7d/14d)
export interface TierAResponse {
  period: string;
  start_date: string;
  end_date: string;
  tasks_completed: number;
  tasks_planned: number;
  tasks_planned_completed: number;
  planning_accuracy: number;
  focus_seconds_total: number;
  focus_sessions_count: number;
  journal_entries: number;
  avg_mood: number | null;
  current_streak: number;
}

// Daily rollup (Tier B pre-aggregated)
export interface DailyRollupResponse {
  date: string;
  tasks_completed: number;
  tasks_planned: number;
  tasks_planned_completed: number;
  planning_accuracy: number;
  focus_seconds_total: number;
  focus_seconds_by_goal: Record<string, number>;
  journal_mood_score: number | null;
  active_goal_progress_delta: number;
  streak_eligible_flag: boolean;
  computed_at: string;
}

// Weekly rollup (Tier B pre-aggregated)
export interface WeeklyRollupResponse {
  week_start_date: string;
  completion_rate: number;
  planning_accuracy: number;
  total_focus_time: number;
  goal_time_distribution: Record<string, number>;
  momentum: number;
  drift_summary: { goal_id: string; drift_score: number }[];
  avg_mood: number | null;
  mood_productivity_correlation_inputs: {
    date: string;
    mood_score: number;
    tasks_completed: number;
    focus_seconds: number;
  }[];
  computed_at: string;
}

// Tier B response (pre-aggregated rollups)
export interface TierBResponse {
  period: string;
  start_date: string;
  end_date: string;
  daily_rollups: DailyRollupResponse[];
  weekly_rollups: WeeklyRollupResponse[];
}

// Execution Dashboard (primary view)
export interface ExecutionDashboardResponse {
  tier_a: TierAResponse;
  insights: AnalyticsOutputResponse[];
}

// Strategic Alignment (secondary tab)
export interface StrategicAlignmentResponse {
  tier_b: TierBResponse;
  insights: AnalyticsOutputResponse[];
}

// Wellbeing Patterns (tertiary overlay)
export interface WellbeingPatternsResponse {
  mood_data: { date: string; mood_score: number }[];
  insights: AnalyticsOutputResponse[];
}

// Semantic clustering (Section 4.9)
export interface ClusterMemberResponse {
  node_id: string;
  title: string;
  type: string;
  similarity: number;
}

export interface ClusterResponse {
  cluster_id: string | null;
  label: string;
  node_count: number;
  coherence_score: number;
  members: ClusterMemberResponse[];
}

export interface ClustersListResponse {
  clusters: ClusterResponse[];
  total: number;
}

// Smart resurfacing (Section 4.10)
export interface ResurfacedItemResponse {
  node_id: string;
  node_type: string;
  title: string;
  reason: string;
  signal_score: number | null;
  similarity: number | null;
  cluster_label: string | null;
  explanation: DerivedExplanation | null;
  metadata: Record<string, unknown>;
}

export interface ResurfacingResponse {
  items: ResurfacedItemResponse[];
  total: number;
  mode: string; // "context" | "today"
}

// Rollup computation
export interface RollupComputeResponse {
  daily_count: number;
  weekly_count: number;
  start_date: string;
  end_date: string;
}

// =============================================================================
// Phase PB: Decision Resurfacing + Edge Weights + Depth
// =============================================================================

// Decision resurfacing (Section 5.7)
export interface ResurfacedDecisionResponse {
  node_id: string;
  title: string;
  content: string;
  context: string | null;
  review_at: string | null;
  created_at: string;
  resurfacing_reason: string; // "review_due", "no_outcome_7d", "no_outcome_30d", "no_outcome_90d"
  days_since_creation: number;
  has_outcome_edges: boolean;
  explanation: DerivedExplanation;
  tags: string[];
}

export interface DecisionResurfacingResponse {
  items: ResurfacedDecisionResponse[];
  total_count: number;
  review_due_count: number;
  no_outcome_count: number;
}

// Memory contextual surfacing (Section 4.5)
export interface SurfacedMemoryResponse {
  node_id: string;
  title: string;
  memory_type: string;
  content_preview: string;
  context: string | null;
  review_at: string | null;
  source: string; // "graph" or "embedding"
  relation_type: string | null;
  edge_id: string | null;
  similarity: number | null;
  is_suggested: boolean;
  label: string | null;
  tags: string[];
}

export interface MemorySurfacingResponse {
  explicit: SurfacedMemoryResponse[];
  suggested: SurfacedMemoryResponse[];
  total_count: number;
  node_id: string;
}

// Focus session stats (Phase PB: deepened focus mode)
export interface FocusStatsResponse {
  period_days: number;
  total_sessions: number;
  total_seconds: number;
  avg_session_seconds: number;
  longest_session_seconds: number;
  daily_breakdown: {
    date: string;
    sessions: number;
    seconds: number;
  }[];
  task_breakdown: {
    task_id: string;
    title: string;
    sessions: number;
    total_seconds: number;
  }[];
}

// Cleanup action (Phase PB: enhanced with convert/reassign)
export type CleanupActionPB = 'archive' | 'snooze' | 'keep' | 'convert' | 'reassign';

export interface CleanupActionRequestPB {
  action: CleanupActionPB;
  node_ids: string[];
  snoozed_until?: string;
  target_type?: string; // For convert
  target_project_id?: string; // For reassign
  target_goal_id?: string; // For reassign
}

export interface CleanupActionResponsePB {
  action: string;
  affected_node_ids: string[];
  total_affected: number;
  details?: Record<string, unknown>;
}

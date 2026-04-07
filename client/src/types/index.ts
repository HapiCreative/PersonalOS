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
  ai_summary: string | null;
  ai_takeaways: unknown[] | null;
  ai_entities: unknown[] | null;
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

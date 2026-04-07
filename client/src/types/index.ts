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

export interface SearchResponse {
  items: NodeResponse[];
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

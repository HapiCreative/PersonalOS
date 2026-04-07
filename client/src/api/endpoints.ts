/**
 * API endpoint functions matching Section 8.3.
 */

import { api, setToken } from './client';
import type {
  TokenResponse,
  NodeResponse,
  NodeListResponse,
  EdgeResponse,
  EdgeListResponse,
  InboxItemResponse,
  InboxItemListResponse,
  SearchResponse,
  TaskResponse,
  TaskListResponse,
  JournalResponse,
  JournalListResponse,
  TemplateResponse,
  TemplateListResponse,
  TaskExecutionEventResponse,
  TaskExecutionEventListResponse,
  SourceResponse,
  SourceListResponse,
  SourcePromoteResponse,
  FragmentResponse,
  FragmentListResponse,
  KBResponse,
  KBListResponse,
  KBCompileResponse,
  MemoryResponse,
  MemoryListResponse,
  GoalResponse,
  GoalListResponse,
  GoalWithTasksResponse,
  GoalStatus,
  TodayViewResponse,
  SignalScoreResponse,
  SignalScoreBatchResponse,
  ProgressIntelligenceResponse,
  ProgressBatchResponse,
  RetrievalModeInfo,
  RetrievalResponse,
  ContextLayerResponse,
  NodeType,
  InboxItemStatus,
  EdgeRelationType,
  EdgeOrigin,
  EdgeState,
  TaskStatus,
  TaskPriority,
  Mood,
  TaskExecutionEventType,
  TemplateTargetType,
  SourceType,
  ProcessingStatus,
  TriageStatus,
  Permanence,
  CompileStatus,
  PipelineStage,
  MemoryType,
} from '../types';

// Auth
export const authApi = {
  register: (username: string, password: string, display_name?: string) =>
    api.post<TokenResponse>('/auth/register', { username, password, display_name }),
  login: (username: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { username, password }),
};

// Nodes
export const nodesApi = {
  list: (params?: { type?: NodeType; include_archived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.type) query.set('type', params.type);
    if (params?.include_archived) query.set('include_archived', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<NodeListResponse>(`/nodes?${query}`);
  },
  get: (id: string) => api.get<NodeResponse>(`/nodes/${id}`),
  create: (type: NodeType, title: string, summary?: string) =>
    api.post<NodeResponse>('/nodes', { type, title, summary }),
  update: (id: string, data: { title?: string; summary?: string }) =>
    api.put<NodeResponse>(`/nodes/${id}`, data),
  delete: (id: string, permanent = false) =>
    api.delete<void>(`/nodes/${id}?permanent=${permanent}`),
  restore: (id: string) => api.post<NodeResponse>(`/nodes/${id}/restore`),
};

// Edges
export const edgesApi = {
  create: (data: {
    source_id: string;
    target_id: string;
    relation_type: EdgeRelationType;
    origin?: EdgeOrigin;
    state?: EdgeState;
    weight?: number;
    confidence?: number;
    metadata?: Record<string, unknown>;
  }) => api.post<EdgeResponse>('/edges', data),
  getForNode: (nodeId: string, params?: { direction?: string; relation_type?: EdgeRelationType; state?: EdgeState }) => {
    const query = new URLSearchParams();
    if (params?.direction) query.set('direction', params.direction);
    if (params?.relation_type) query.set('relation_type', params.relation_type);
    if (params?.state) query.set('state', params.state);
    return api.get<EdgeListResponse>(`/nodes/${nodeId}/edges?${query}`);
  },
  delete: (id: string) => api.delete<void>(`/edges/${id}`),
};

// Inbox
export const inboxApi = {
  list: (params?: { status?: InboxItemStatus; include_archived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.include_archived) query.set('include_archived', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<InboxItemListResponse>(`/inbox?${query}`);
  },
  get: (nodeId: string) => api.get<InboxItemResponse>(`/inbox/${nodeId}`),
  create: (raw_text: string, title?: string) =>
    api.post<InboxItemResponse>('/inbox', { raw_text, title }),
  update: (nodeId: string, data: { raw_text?: string; status?: InboxItemStatus; title?: string }) =>
    api.put<InboxItemResponse>(`/inbox/${nodeId}`, data),
};

// Tasks (Phase 2)
export const tasksApi = {
  list: (params?: { status?: TaskStatus; priority?: TaskPriority; include_archived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.priority) query.set('priority', params.priority);
    if (params?.include_archived) query.set('include_archived', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<TaskListResponse>(`/tasks?${query}`);
  },
  get: (nodeId: string) => api.get<TaskResponse>(`/tasks/${nodeId}`),
  create: (data: {
    title: string;
    summary?: string;
    status?: TaskStatus;
    priority?: TaskPriority;
    due_date?: string;
    recurrence?: string;
    notes?: string;
  }) => api.post<TaskResponse>('/tasks', data),
  update: (nodeId: string, data: {
    title?: string;
    summary?: string;
    priority?: TaskPriority;
    due_date?: string | null;
    recurrence?: string | null;
    notes?: string | null;
  }) => api.put<TaskResponse>(`/tasks/${nodeId}`, data),
  transition: (nodeId: string, new_status: TaskStatus) =>
    api.post<TaskResponse>(`/tasks/${nodeId}/transition`, { new_status }),
};

// Journal (Phase 2)
export const journalApi = {
  list: (params?: { mood?: Mood; include_archived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.mood) query.set('mood', params.mood);
    if (params?.include_archived) query.set('include_archived', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<JournalListResponse>(`/journal?${query}`);
  },
  get: (nodeId: string) => api.get<JournalResponse>(`/journal/${nodeId}`),
  create: (data: {
    title: string;
    summary?: string;
    content?: string;
    entry_date?: string;
    mood?: Mood;
    tags?: string[];
  }) => api.post<JournalResponse>('/journal', data),
  update: (nodeId: string, data: {
    title?: string;
    summary?: string;
    content?: string;
    mood?: Mood | null;
    tags?: string[];
  }) => api.put<JournalResponse>(`/journal/${nodeId}`, data),
};

// Templates (Phase 2)
export const templatesApi = {
  list: (params?: { target_type?: TemplateTargetType; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.target_type) query.set('target_type', params.target_type);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<TemplateListResponse>(`/templates?${query}`);
  },
  get: (id: string) => api.get<TemplateResponse>(`/templates/${id}`),
  create: (data: {
    name: string;
    target_type: TemplateTargetType;
    structure?: Record<string, unknown>;
    is_system?: boolean;
  }) => api.post<TemplateResponse>('/templates', data),
  update: (id: string, data: { name?: string; structure?: Record<string, unknown> }) =>
    api.put<TemplateResponse>(`/templates/${id}`, data),
  delete: (id: string) => api.delete<void>(`/templates/${id}`),
};

// Task Execution Events (Phase 2 - Temporal)
export const executionEventsApi = {
  list: (params?: { task_id?: string; expected_for_date?: string; include_deleted?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.task_id) query.set('task_id', params.task_id);
    if (params?.expected_for_date) query.set('expected_for_date', params.expected_for_date);
    if (params?.include_deleted) query.set('include_deleted', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<TaskExecutionEventListResponse>(`/task-execution-events?${query}`);
  },
  create: (data: {
    task_id: string;
    event_type: TaskExecutionEventType;
    expected_for_date: string;
    notes?: string;
  }) => api.post<TaskExecutionEventResponse>('/task-execution-events', data),
};

// Search (Phase 3: hybrid search with mode parameter)
export const searchApi = {
  search: (q: string, params?: { type?: string; mode?: string; limit?: number; offset?: number; include_archived?: boolean }) => {
    const query = new URLSearchParams({ q });
    if (params?.type) query.set('type', params.type);
    if (params?.mode) query.set('mode', params.mode);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    if (params?.include_archived) query.set('include_archived', 'true');
    return api.get<SearchResponse>(`/search?${query}`);
  },
};

// Sources (Phase 3)
export const sourcesApi = {
  list: (params?: { processing_status?: ProcessingStatus; triage_status?: TriageStatus; source_type?: SourceType; include_archived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.processing_status) query.set('processing_status', params.processing_status);
    if (params?.triage_status) query.set('triage_status', params.triage_status);
    if (params?.source_type) query.set('source_type', params.source_type);
    if (params?.include_archived) query.set('include_archived', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<SourceListResponse>(`/sources?${query}`);
  },
  get: (nodeId: string) => api.get<SourceResponse>(`/sources/${nodeId}`),
  create: (data: {
    title: string;
    summary?: string;
    source_type?: SourceType;
    url?: string;
    author?: string;
    platform?: string;
    published_at?: string;
    capture_context?: string;
    raw_content?: string;
    permanence?: Permanence;
  }) => api.post<SourceResponse>('/sources', data),
  update: (nodeId: string, data: {
    title?: string;
    summary?: string;
    source_type?: SourceType;
    url?: string;
    author?: string;
    platform?: string;
    capture_context?: string;
    raw_content?: string;
    canonical_content?: string;
    permanence?: Permanence;
    processing_status?: ProcessingStatus;
    triage_status?: TriageStatus;
  }) => api.put<SourceResponse>(`/sources/${nodeId}`, data),
  promote: (nodeId: string, data: {
    target_type: string;
    title?: string;
    memory_type?: string;
    priority?: string;
  }) => api.post<SourcePromoteResponse>(`/sources/${nodeId}/promote`, data),
  listFragments: (nodeId: string, params?: { limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<FragmentListResponse>(`/sources/${nodeId}/fragments?${query}`);
  },
  createFragment: (nodeId: string, data: {
    fragment_text: string;
    position?: number;
    fragment_type?: string;
    section_ref?: string;
  }) => api.post<FragmentResponse>(`/sources/${nodeId}/fragments`, data),
};

// KB (Phase 3)
export const kbApi = {
  list: (params?: { compile_status?: CompileStatus; pipeline_stage?: PipelineStage; include_archived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.compile_status) query.set('compile_status', params.compile_status);
    if (params?.pipeline_stage) query.set('pipeline_stage', params.pipeline_stage);
    if (params?.include_archived) query.set('include_archived', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<KBListResponse>(`/kb?${query}`);
  },
  get: (nodeId: string) => api.get<KBResponse>(`/kb/${nodeId}`),
  create: (data: {
    title: string;
    summary?: string;
    content?: string;
    raw_content?: string;
    tags?: string[];
  }) => api.post<KBResponse>('/kb', data),
  update: (nodeId: string, data: {
    title?: string;
    summary?: string;
    content?: string;
    raw_content?: string;
    tags?: string[];
  }) => api.put<KBResponse>(`/kb/${nodeId}`, data),
  compile: (nodeId: string, action: string) =>
    api.post<KBCompileResponse>(`/kb/${nodeId}/compile`, { action }),
};

// Goals (Phase 4)
export const goalsApi = {
  list: (params?: { status?: GoalStatus; include_archived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.include_archived) query.set('include_archived', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<GoalListResponse>(`/goals?${query}`);
  },
  get: (nodeId: string) => api.get<GoalWithTasksResponse>(`/goals/${nodeId}`),
  create: (data: {
    title: string;
    summary?: string;
    status?: GoalStatus;
    start_date?: string;
    end_date?: string;
    timeframe_label?: string;
    milestones?: Record<string, unknown>[];
    notes?: string;
  }) => api.post<GoalResponse>('/goals', data),
  update: (nodeId: string, data: {
    title?: string;
    summary?: string;
    status?: GoalStatus;
    start_date?: string | null;
    end_date?: string | null;
    timeframe_label?: string | null;
    milestones?: Record<string, unknown>[];
    notes?: string | null;
  }) => api.put<GoalResponse>(`/goals/${nodeId}`, data),
  refreshProgress: (nodeId: string) =>
    api.post<GoalResponse>(`/goals/${nodeId}/refresh-progress`),
};

// Today View (Phase 4 - Behavioral)
export const todayApi = {
  get: () => api.get<TodayViewResponse>('/today'),
};

// Derived Intelligence (Phase 5)
export const derivedApi = {
  // Signal Scores
  getSignalScore: (nodeId: string) =>
    api.get<SignalScoreResponse>(`/derived/signal-score/${nodeId}`),
  computeSignalScore: (nodeId: string) =>
    api.post<SignalScoreResponse>(`/derived/signal-score/${nodeId}/compute`),
  computeSignalScoresBatch: (limit?: number) => {
    const query = new URLSearchParams();
    if (limit) query.set('limit', String(limit));
    return api.post<SignalScoreBatchResponse>(`/derived/signal-score/compute-batch?${query}`);
  },

  // Progress Intelligence
  getProgress: (nodeId: string) =>
    api.get<ProgressIntelligenceResponse>(`/derived/progress/${nodeId}`),
  computeProgress: (nodeId: string) =>
    api.post<ProgressIntelligenceResponse>(`/derived/progress/${nodeId}/compute`),
  computeProgressBatch: (params?: { node_type?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.node_type) query.set('node_type', params.node_type);
    if (params?.limit) query.set('limit', String(params.limit));
    return api.post<ProgressBatchResponse>(`/derived/progress/compute-batch?${query}`);
  },

  // Retrieval Modes
  listRetrievalModes: () =>
    api.get<RetrievalModeInfo[]>('/derived/retrieval-modes'),
  retrieve: (mode: string, params?: { q?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.q) query.set('q', params.q);
    if (params?.limit) query.set('limit', String(params.limit));
    return api.get<RetrievalResponse>(`/derived/retrieve/${mode}?${query}`);
  },

  // Context Layer
  getContextLayer: (nodeId: string) =>
    api.get<ContextLayerResponse>(`/derived/context/${nodeId}`),
};

// Edge state update (Phase 5: for promoting suggested links)
export const edgeStateApi = {
  updateState: (edgeId: string, state: EdgeState) =>
    api.patch<EdgeResponse>(`/edges/${edgeId}/state`, { state }),
};

// Memory (Phase 3)
export const memoryApi = {
  list: (params?: { memory_type?: MemoryType; include_archived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.memory_type) query.set('memory_type', params.memory_type);
    if (params?.include_archived) query.set('include_archived', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<MemoryListResponse>(`/memory?${query}`);
  },
  get: (nodeId: string) => api.get<MemoryResponse>(`/memory/${nodeId}`),
  create: (data: {
    title: string;
    summary?: string;
    memory_type: MemoryType;
    content?: string;
    context?: string;
    review_at?: string;
    tags?: string[];
  }) => api.post<MemoryResponse>('/memory', data),
  update: (nodeId: string, data: {
    title?: string;
    summary?: string;
    content?: string;
    context?: string;
    review_at?: string | null;
    tags?: string[];
  }) => api.put<MemoryResponse>(`/memory/${nodeId}`, data),
};

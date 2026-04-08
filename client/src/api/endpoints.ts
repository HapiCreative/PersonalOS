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
  CleanupQueueResponse,
  CleanupAction,
  CleanupActionResponse,
  SnoozeResponse,
  StaleCheckResponse,
  // Phase 7
  DailyPlanResponse,
  // Phase 8
  ProjectResponse,
  ProjectListResponse,
  ProjectWithLinksResponse,
  ProjectStatus,
  WeeklyReviewSummaryResponse,
  WeeklySnapshotResponse,
  MonthlyReviewSummaryResponse,
  MonthlySnapshotResponse,
  DailyPlanListResponse,
  FocusSessionResponse,
  FocusSessionListResponse,
  MorningCommitSuggestionsResponse,
  CommitResponse,
  EveningReflectionResponse,
  ReflectionSubmitResponse,
  // Phase 9
  AIModeResponse,
  AIMode,
  SuggestLinksResponse,
  EnrichSourceResponse,
  LintKBResponse,
  ClassifyInboxResponse,
  BriefingResponse,
  EnrichmentResponse,
  EnrichmentListResponse,
  EnrichmentType,
  PipelineJobResponse,
  PipelineJobListResponse,
  PipelineJobType,
  PipelineJobStatus,
  // Phase 10
  ExportResponse,
  ImportResponse,
  RetentionEnforceResponse,
  RetentionStatsResponse,
  BatchEmbedResponse,
  CacheRefreshResponse,
  // Phase PC: Analytics + Intelligence
  ExecutionDashboardResponse,
  StrategicAlignmentResponse,
  WellbeingPatternsResponse,
  ClustersListResponse,
  ClusterResponse,
  ResurfacingResponse,
  RollupComputeResponse,
  DailyRollupResponse,
  // Phase PB: Decision Resurfacing + Edge Weights + Depth
  DecisionResurfacingResponse,
  MemorySurfacingResponse,
  FocusStatsResponse,
  CleanupActionPB,
  CleanupActionResponsePB,
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
  // Phase PB: Edge weight user override
  updateWeight: (edgeId: string, weight: number) =>
    api.patch<EdgeResponse>(`/edges/${edgeId}/weight`, { weight }),
};

// Cleanup (Phase 6 — Behavioral + Derived)
export const cleanupApi = {
  getQueue: (params?: { category?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.category) query.set('category', params.category);
    if (params?.limit) query.set('limit', String(params.limit));
    return api.get<CleanupQueueResponse>(`/cleanup/queue?${query}`);
  },
  executeAction: (data: { action: CleanupAction; node_ids: string[]; snoozed_until?: string }) =>
    api.post<CleanupActionResponse>('/cleanup/action', data),
};

// Snooze (Phase 6 — Temporal)
export const snoozeApi = {
  create: (node_id: string, snoozed_until: string) =>
    api.post<SnoozeResponse>('/snooze', { node_id, snoozed_until }),
  remove: (node_id: string) =>
    api.delete<{ removed: boolean; node_id: string }>('/snooze', { data: { node_id } }),
  get: (nodeId: string) =>
    api.get<SnoozeResponse | null>(`/snooze/${nodeId}`),
};

// Stale check (Phase 6 — Derived)
export const staleApi = {
  check: (nodeId: string) =>
    api.get<StaleCheckResponse>(`/derived/stale/${nodeId}`),
};

// =============================================================================
// Phase 7: Daily Plans + Focus Sessions + Morning Commit + Evening Reflection
// =============================================================================

// Daily Plans (Temporal)
export const dailyPlansApi = {
  list: (params?: { limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<DailyPlanListResponse>(`/daily-plans?${query}`);
  },
  getToday: () => api.get<DailyPlanResponse | null>('/daily-plans/today'),
  getByDate: (date: string) => api.get<DailyPlanResponse | null>(`/daily-plans/${date}`),
  create: (data: { date?: string; selected_task_ids: string[]; intention_text?: string }) =>
    api.post<DailyPlanResponse>('/daily-plans', data),
  close: (date: string) => api.post<DailyPlanResponse>(`/daily-plans/${date}/close`),
};

// Focus Sessions (Temporal)
export const focusSessionsApi = {
  list: (params?: { task_id?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.task_id) query.set('task_id', params.task_id);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<FocusSessionListResponse>(`/focus-sessions?${query}`);
  },
  get: (id: string) => api.get<FocusSessionResponse>(`/focus-sessions/${id}`),
  getActive: () => api.get<FocusSessionResponse | null>('/focus-sessions/active'),
  start: (task_id: string) =>
    api.post<FocusSessionResponse>('/focus-sessions', { task_id }),
  end: (id: string) =>
    api.post<FocusSessionResponse>(`/focus-sessions/${id}/end`),
};

// Morning Commit (Behavioral)
export const morningCommitApi = {
  getSuggestions: () =>
    api.get<MorningCommitSuggestionsResponse>('/today/suggestions'),
  commit: (selected_task_ids: string[], intention_text?: string) =>
    api.post<CommitResponse>('/today/commit', { selected_task_ids, intention_text }),
};

// Evening Reflection (Behavioral)
export const eveningReflectionApi = {
  get: (date?: string) => {
    const query = new URLSearchParams();
    if (date) query.set('reflection_date', date);
    return api.get<EveningReflectionResponse>(`/today/reflection?${query}`);
  },
  submit: (data: {
    skipped_task_ids?: string[];
    deferred_task_ids?: string[];
    reflection_notes?: string;
  }) => api.post<ReflectionSubmitResponse>('/today/reflection', data),
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

// =============================================================================
// Phase 8: Projects + Weekly/Monthly Reviews
// =============================================================================

// Projects (Core)
export const projectsApi = {
  list: (params?: { status?: ProjectStatus; include_archived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.include_archived) query.set('include_archived', 'true');
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<ProjectListResponse>(`/projects?${query}`);
  },
  get: (nodeId: string) => api.get<ProjectWithLinksResponse>(`/projects/${nodeId}`),
  create: (data: {
    title: string;
    summary?: string;
    status?: ProjectStatus;
    description?: string;
    tags?: string[];
  }) => api.post<ProjectResponse>('/projects', data),
  update: (nodeId: string, data: {
    title?: string;
    summary?: string;
    status?: ProjectStatus;
    description?: string | null;
    tags?: string[];
  }) => api.put<ProjectResponse>(`/projects/${nodeId}`, data),
};

// Weekly Review (Behavioral)
export const weeklyReviewApi = {
  get: (referenceDate?: string) => {
    const query = new URLSearchParams();
    if (referenceDate) query.set('reference_date', referenceDate);
    return api.get<WeeklyReviewSummaryResponse>(`/review/weekly?${query}`);
  },
  save: (data: {
    focus_areas: string[];
    priority_task_ids?: string[];
    notes?: string;
    reference_date?: string;
  }) => api.post<WeeklySnapshotResponse>('/review/weekly', data),
};

// Monthly Review (Behavioral)
export const monthlyReviewApi = {
  get: (referenceDate?: string) => {
    const query = new URLSearchParams();
    if (referenceDate) query.set('reference_date', referenceDate);
    return api.get<MonthlyReviewSummaryResponse>(`/review/monthly?${query}`);
  },
  save: (data: {
    focus_areas: string[];
    notes?: string;
    reference_date?: string;
  }) => api.post<MonthlySnapshotResponse>('/review/monthly', data),
};

// =============================================================================
// Phase 9: AI Modes + LLM Pipeline + Enrichments
// =============================================================================

// AI Modes (Section 5.5 — Behavioral)
export const llmApi = {
  query: (mode: AIMode, query: string) =>
    api.post<AIModeResponse>('/llm/query', { mode, query }),
  suggestLinks: (nodeId: string) =>
    api.post<SuggestLinksResponse>(`/llm/suggest-links/${nodeId}`),
  enrichSource: (nodeId: string) =>
    api.post<EnrichSourceResponse>(`/llm/enrich-source/${nodeId}`),
  lintKB: (nodeId: string) =>
    api.post<LintKBResponse>(`/llm/lint-kb/${nodeId}`),
  classifyInbox: (nodeId: string) =>
    api.post<ClassifyInboxResponse>(`/llm/classify-inbox/${nodeId}`),
  briefing: () =>
    api.post<BriefingResponse>('/llm/briefing'),
};

// Node Enrichments (Section 4.8 — Derived)
export const enrichmentsApi = {
  getForNode: (nodeId: string, includeSupereded?: boolean) => {
    const query = new URLSearchParams();
    if (includeSupereded) query.set('include_superseded', 'true');
    return api.get<EnrichmentListResponse>(`/enrichments/${nodeId}?${query}`);
  },
  getActive: (nodeId: string, enrichmentType: EnrichmentType) =>
    api.get<EnrichmentResponse>(`/enrichments/${nodeId}/${enrichmentType}`),
  getHistory: (nodeId: string, enrichmentType: EnrichmentType, limit?: number) => {
    const query = new URLSearchParams();
    if (limit) query.set('limit', String(limit));
    return api.get<EnrichmentListResponse>(`/enrichments/${nodeId}/${enrichmentType}/history?${query}`);
  },
  rollback: (nodeId: string, enrichmentType: EnrichmentType, restoreEnrichmentId: string) =>
    api.post<EnrichmentResponse>(`/enrichments/${nodeId}/${enrichmentType}/rollback`, {
      restore_enrichment_id: restoreEnrichmentId,
    }),
};

// =============================================================================
// Phase 10: Admin (Export/Import, Retention, Caching, Batch Embedding)
// =============================================================================

export const adminApi = {
  // Export/Import (Section 1.1: Core entities are exportable)
  exportData: (params?: { include_archived?: boolean; include_enrichments?: boolean }) =>
    api.post<ExportResponse>('/admin/export', params || {}),
  importData: (data: Record<string, unknown>, mergeStrategy?: string) =>
    api.post<ImportResponse>('/admin/import', {
      data,
      merge_strategy: mergeStrategy || 'skip_existing',
    }),

  // Retention Policy (Section 1.7)
  enforceRetention: () =>
    api.post<RetentionEnforceResponse>('/admin/retention/enforce'),
  retentionStats: () =>
    api.get<RetentionStatsResponse>('/admin/retention/stats'),

  // Caching (Phase 10: materialized view refresh)
  refreshCache: () =>
    api.post<CacheRefreshResponse>('/admin/cache/refresh'),

  // Batch Embedding (Phase 10)
  batchEmbed: (params?: { node_ids?: string[]; force_recompute?: boolean; limit?: number }) =>
    api.post<BatchEmbedResponse>('/admin/batch-embed', params || {}),
};

// Pipeline Jobs (Section 7.3)
export const pipelineJobsApi = {
  list: (params?: { job_type?: PipelineJobType; status?: PipelineJobStatus; target_node_id?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.job_type) query.set('job_type', params.job_type);
    if (params?.status) query.set('status', params.status);
    if (params?.target_node_id) query.set('target_node_id', params.target_node_id);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return api.get<PipelineJobListResponse>(`/pipeline-jobs?${query}`);
  },
  get: (jobId: string) =>
    api.get<PipelineJobResponse>(`/pipeline-jobs/${jobId}`),
  cancel: (jobId: string) =>
    api.post<PipelineJobResponse>(`/pipeline-jobs/${jobId}/cancel`),
};

// =============================================================================
// Phase PC: Analytics + Intelligence
// =============================================================================

// Analytics Dashboard (Section 4.7)
// Invariant D-04: All analytics outputs classified as descriptive/correlational/recommendation
export const analyticsApi = {
  // Execution Dashboard (primary view — Tier A live query)
  getExecution: (period?: string) => {
    const query = new URLSearchParams();
    if (period) query.set('period', period);
    return api.get<ExecutionDashboardResponse>(`/analytics/execution?${query}`);
  },

  // Strategic Alignment (secondary tab — Tier B rollups)
  getStrategic: (period?: string) => {
    const query = new URLSearchParams();
    if (period) query.set('period', period);
    return api.get<StrategicAlignmentResponse>(`/analytics/strategic?${query}`);
  },

  // Wellbeing Patterns (tertiary overlay — Tier B rollups)
  getWellbeing: (period?: string) => {
    const query = new URLSearchParams();
    if (period) query.set('period', period);
    return api.get<WellbeingPatternsResponse>(`/analytics/wellbeing?${query}`);
  },

  // Compute/recompute rollups
  computeRollups: (days?: number) => {
    const query = new URLSearchParams();
    if (days) query.set('days', String(days));
    return api.post<RollupComputeResponse>(`/analytics/rollups/compute?${query}`);
  },
  computeTodayRollup: () =>
    api.post<DailyRollupResponse>('/analytics/rollups/compute-today'),

  // Semantic Clustering (Section 4.9)
  getClusters: () =>
    api.get<ClustersListResponse>('/analytics/clusters'),
  computeClusters: () =>
    api.post<ClustersListResponse>('/analytics/clusters/compute'),
  getNodeCluster: (nodeId: string) =>
    api.get<ClusterResponse | null>(`/analytics/clusters/node/${nodeId}`),
  getClusterPeers: (nodeId: string, limit?: number) => {
    const query = new URLSearchParams();
    if (limit) query.set('limit', String(limit));
    return api.get<{ node_id: string; peers: unknown[]; total: number }>(
      `/analytics/clusters/node/${nodeId}/peers?${query}`
    );
  },

  // Smart Resurfacing (Section 4.10)
  resurfaceContext: (nodeId: string, limit?: number) => {
    const query = new URLSearchParams();
    if (limit) query.set('limit', String(limit));
    return api.get<ResurfacingResponse>(`/analytics/resurface/context/${nodeId}?${query}`);
  },
  resurfaceToday: () =>
    api.get<ResurfacingResponse>('/analytics/resurface/today'),
};

// =============================================================================
// Phase PB: Decision Resurfacing + Edge Weights + Depth
// =============================================================================

// Decision resurfacing (Section 5.7 — Behavioral)
export const decisionResurfacingApi = {
  get: (limit?: number) => {
    const query = new URLSearchParams();
    if (limit) query.set('limit', String(limit));
    return api.get<DecisionResurfacingResponse>(`/decisions/resurfacing?${query}`);
  },
};

// Memory contextual surfacing (Section 4.5 — Derived)
export const memorySurfacingApi = {
  getForNode: (nodeId: string) =>
    api.get<MemorySurfacingResponse>(`/derived/memories/${nodeId}`),
};

// Focus session stats (Phase PB — Temporal)
export const focusStatsApi = {
  getStats: (params?: { task_id?: string; days?: number }) => {
    const query = new URLSearchParams();
    if (params?.task_id) query.set('task_id', params.task_id);
    if (params?.days) query.set('days', String(params.days));
    return api.get<FocusStatsResponse>(`/focus-sessions/stats?${query}`);
  },
};

// Enhanced cleanup (Phase PB — Behavioral)
export const cleanupPBApi = {
  executeAction: (data: {
    action: CleanupActionPB;
    node_ids: string[];
    snoozed_until?: string;
    target_type?: string;
    target_project_id?: string;
    target_goal_id?: string;
  }) => api.post<CleanupActionResponsePB>('/cleanup/action', data),
};

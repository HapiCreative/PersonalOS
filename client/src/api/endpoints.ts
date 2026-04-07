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

// Search
export const searchApi = {
  search: (q: string, params?: { type?: string; limit?: number; offset?: number; include_archived?: boolean }) => {
    const query = new URLSearchParams({ q });
    if (params?.type) query.set('type', params.type);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    if (params?.include_archived) query.set('include_archived', 'true');
    return api.get<SearchResponse>(`/search?${query}`);
  },
};

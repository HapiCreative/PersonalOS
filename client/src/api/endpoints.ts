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
  NodeType,
  InboxItemStatus,
  EdgeRelationType,
  EdgeOrigin,
  EdgeState,
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

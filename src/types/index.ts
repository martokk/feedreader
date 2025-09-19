export interface Feed {
  id: string;
  url: string;
  title: string | null;
  last_fetch_at: string | null;
  last_status: number | null;
  next_run_at: string;
  interval_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface FeedCreate {
  url: string;
  title?: string;
  interval_seconds?: number;
}

export interface FeedUpdate {
  title?: string;
  interval_seconds?: number;
}

export interface FeedStats {
  feed_id: string;
  total_items: number;
  unread_items: number;
  last_fetch_at: string | null;
  last_fetch_status: number | null;
  next_run_at: string;
}

export interface FeedValidation {
  url: string;
  is_valid: boolean;
  feed_title?: string;
  error_message?: string;
}

export interface Item {
  id: string;
  feed_id: string;
  title: string | null;
  url: string | null;
  published_at: string | null;
  fetched_at: string;
  created_at: string;
  is_read: boolean;
  starred: boolean;
}

export interface ItemDetail extends Item {
  content_html: string | null;
  content_text: string | null;
}

export interface Category {
  id: string;
  name: string;
  description: string | null;
  color: string | null;
  order: number;
  created_at: string;
  updated_at: string;
}

export interface CategoryCreate {
  name: string;
  description?: string;
  color?: string;
  order?: number;
}

export interface CategoryUpdate {
  name?: string;
  description?: string;
  color?: string;
  order?: number;
}

export interface CategoryStats {
  category_id: string;
  feed_count: number;
  total_items: number;
  unread_items: number;
  last_updated: string | null;
}

export interface ReadStateUpdate {
  is_read: boolean;
  starred?: boolean;
}

export interface SSEEvent {
  type: string;
  timestamp: string;
  data: any;
}

export interface ApiError {
  detail: string;
} 
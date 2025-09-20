'use client';

import { ArrowLeft, ExternalLink, Eye, EyeOff } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import FeedItemActionTray from '@/components/feed/FeedItemActionTray';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

import { api } from '@/lib/api';
import { Feed, ItemDetail } from '@/types';

interface ReaderViewProps {
  itemId: string;
  feeds: Feed[];
  onClose: () => void;
  onMarkAsRead: (itemId: string, isRead: boolean) => void;
}

// Helper function to get feed title by feed_id
const getFeedTitle = (feedId: string, feeds: Feed[]): string => {
  const feed = feeds.find(f => f.id === feedId);
  return feed?.title || 'Unknown Feed';
};

// Helper function to get feed homepage URL from feed URL
const getFeedHomepage = (feedId: string, feeds: Feed[]): string | null => {
  const feed = feeds.find(f => f.id === feedId);
  if (!feed?.url) return null;

  try {
    const url = new URL(feed.url);
    return `${url.protocol}//${url.hostname}`;
  } catch {
    return null;
  }
};

// Helper function to format relative time
const formatRelativeTime = (dateString: string): string => {
  try {
    const date = new Date(dateString);

    if (isNaN(date.getTime())) {
      return 'Unknown time';
    }

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffWeeks = Math.floor(diffDays / 7);
    const diffMonths = Math.floor(diffDays / 30);

    if (diffMs < 0) {
      return 'Future date';
    }

    if (diffMinutes < 1) {
      return 'just now';
    } else if (diffMinutes < 60) {
      return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`;
    } else if (diffHours < 24) {
      return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
    } else if (diffDays < 7) {
      return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
    } else if (diffWeeks < 4) {
      return diffWeeks === 1 ? '1 week ago' : `${diffWeeks} weeks ago`;
    } else if (diffMonths < 12) {
      return diffMonths === 1 ? '1 month ago' : `${diffMonths} months ago`;
    } else {
      return date.toLocaleDateString();
    }
  } catch (error) {
    console.error('Error formatting relative time:', error, dateString);
    return 'Unknown time';
  }
};

export function ReaderView({ itemId, feeds, onClose, onMarkAsRead }: ReaderViewProps) {
  const [item, setItem] = useState<ItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadItem();
  }, [itemId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadItem = async () => {
    try {
      setLoading(true);
      setError(null);
      const itemData = await api.getItem(itemId);
      setItem(itemData);

      // Auto-mark as read when opening reader view
      if (!itemData.is_read) {
        onMarkAsRead(itemId, true);
        setItem(prev => prev ? { ...prev, is_read: true } : null);
      }
    } catch (error) {
      console.error('Failed to load item:', error);
      setError('Failed to load article');
      toast.error('Failed to load article');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsRead = async () => {
    if (!item) return;

    try {
      await api.markItemRead(item.id, !item.is_read);
      setItem(prev => prev ? { ...prev, is_read: !prev.is_read } : null);
      onMarkAsRead(item.id, !item.is_read);
      toast.success(item.is_read ? 'Marked as unread' : 'Marked as read');
    } catch (error) {
      console.error('Failed to update read status:', error);
      toast.error('Failed to update item');
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-background z-50 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full mx-auto" />
          <p className="text-muted-foreground">Loading article...</p>
        </div>
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="fixed inset-0 bg-background z-50 flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-red-500">{error || 'Article not found'}</p>
          <Button onClick={onClose}>Close</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-4rem)] overflow-y-auto bg-background">
        <div className="max-w-4xl mx-auto p-6">
          {/* Article Header */}
          <div className="mb-8">
            {/* Title with Action Tray */}
            <div className="relative group mb-4">
              {item.url ? (
                <h1 className="text-3xl font-bold leading-tight pr-20">
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:text-primary transition-colors"
                  >
                    {item.title || 'Untitled Article'}
                  </a>
                </h1>
              ) : (
                <h1 className="text-3xl font-bold leading-tight pr-20">
                  {item.title || 'Untitled Article'}
                </h1>
              )}
              <FeedItemActionTray placement="top-right" className="opacity-100 pointer-events-auto translate-y-0 md:opacity-100 md:pointer-events-auto md:translate-y-0">
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-primary transition-colors p-1 rounded hover:bg-accent/50"
                    aria-label="Open original article"
                    title="Open original article"
                  >
                    <ExternalLink className="h-5 w-5" />
                  </a>
                )}
                <button
                  className="text-muted-foreground hover:text-primary transition-colors p-1 rounded hover:bg-accent/50"
                  onClick={handleMarkAsRead}
                  aria-label={item.is_read ? 'Mark as unread' : 'Mark as read'}
                  title={item.is_read ? 'Mark as unread' : 'Mark as read'}
                >
                  {item.is_read ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </FeedItemActionTray>
            </div>

            {/* Metadata */}
            <div className="flex items-center gap-4 text-sm text-muted-foreground mb-6">
              {getFeedHomepage(item.feed_id, feeds) ? (
                <a
                  href={getFeedHomepage(item.feed_id, feeds)!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium hover:text-primary transition-colors"
                >
                  {getFeedTitle(item.feed_id, feeds)}
                </a>
              ) : (
                <span className="font-medium">
                  {getFeedTitle(item.feed_id, feeds)}
                </span>
              )}
              {item.published_at && (
                <>
                  <span>•</span>
                  <span>
                    {formatRelativeTime(item.published_at)}
                  </span>
                </>
              )}
              {item.starred && (
                <>
                  <span>•</span>
                  <Badge variant="secondary" className="text-xs">★</Badge>
                </>
              )}
            </div>

            {/* Article Image */}
            {item.image_url && (
              <div className="mb-6">
                <img
                  src={item.image_url}
                  alt={item.title || 'Article image'}
                  className="w-full max-w-2xl max-h-96 object-cover mx-auto rounded-lg"
                />
              </div>
            )}
          </div>

          {/* Article Content */}
          <div className="max-w-none article-content">
            {item.content_html ? (
              <div dangerouslySetInnerHTML={{ __html: item.content_html }} />
            ) : item.content_text ? (
              <div className="whitespace-pre-wrap">
                {item.content_text}
              </div>
            ) : (
              <p className="text-muted-foreground italic">
                No content available for this article.
              </p>
            )}
          </div>

          {/* End of Article Actions */}
          <div className="mt-12 pt-8 border-t border-border">
            <div className="flex flex-col items-center gap-4">
              {/* Second Action Tray */}
              <div className="flex items-center gap-1 rounded-md border bg-background px-1.5 py-1">
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-primary transition-colors p-1 rounded hover:bg-accent/50"
                    aria-label="Open original article"
                    title="Open original article"
                  >
                    <ExternalLink className="h-5 w-5" />
                  </a>
                )}
                <button
                  className="text-muted-foreground hover:text-primary transition-colors p-1 rounded hover:bg-accent/50"
                  onClick={handleMarkAsRead}
                  aria-label={item.is_read ? 'Mark as unread' : 'Mark as read'}
                  title={item.is_read ? 'Mark as unread' : 'Mark as read'}
                >
                  {item.is_read ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>

              {/* Back Button */}
              <Button
                variant="outline"
                onClick={onClose}
                className="flex items-center gap-2"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
            </div>
          </div>

          {/* Footer spacing */}
          <div className="h-16"></div>
        </div>
    </div>
  );
}
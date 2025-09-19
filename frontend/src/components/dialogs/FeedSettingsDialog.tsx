import { Loader2, RefreshCw, Settings, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';

import { api } from '@/lib/api';
import { Category, Feed } from '@/types';

import { ConfirmDialog } from './ConfirmDialog';

interface FeedSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  feed: Feed | null;
  categories: Category[];
  onFeedUpdated: (feed: Feed) => void;
  onFeedDeleted: (feedId: string) => void;
}

export function FeedSettingsDialog({
  open,
  onOpenChange,
  feed,
  categories,
  onFeedUpdated,
  onFeedDeleted,
}: FeedSettingsDialogProps) {
  const [title, setTitle] = useState('');
  const [intervalSeconds, setIntervalSeconds] = useState(900);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>('');
  const [currentCategoryId, setCurrentCategoryId] = useState<string>('');
  const [isUpdating, setIsUpdating] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Reset form when feed changes
  useEffect(() => {
    if (feed) {
      setTitle(feed.title || '');
      setIntervalSeconds(feed.interval_seconds);
      loadFeedCategories(feed.id);
    }
  }, [feed]);

  const loadFeedCategories = async (feedId: string) => {
    try {
      const feedCategories = await api.getFeedCategories(feedId);
      // Set the first category as selected, or empty if no categories
      const currentCategory = feedCategories.length > 0 ? feedCategories[0].id : '';
      setCurrentCategoryId(currentCategory);
      setSelectedCategoryId(currentCategory);
    } catch (error) {
      console.error('Failed to load feed categories:', error);
      setCurrentCategoryId('');
      setSelectedCategoryId('');
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!feed) return;

    try {
      setIsUpdating(true);
      const updatedFeed = await api.updateFeed(feed.id, {
        title: title.trim() || undefined,
        interval_seconds: intervalSeconds,
      });

      // Handle category assignment changes
      if (selectedCategoryId !== currentCategoryId) {
        try {
          // Remove from current category if it has one
          if (currentCategoryId) {
            await api.removeFeedFromCategory(feed.id, currentCategoryId);
          }
          
          // Add to new category if one is selected
          if (selectedCategoryId) {
            await api.addFeedToCategory(feed.id, selectedCategoryId);
            toast.success('Feed moved to category successfully');
          } else {
            toast.success('Feed removed from category');
          }
        } catch (error) {
          console.error('Failed to update feed category:', error);
          toast.error('Feed updated but failed to update category');
        }
      }

      toast.success('Feed updated successfully');
      onFeedUpdated(updatedFeed);
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to update feed:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update feed');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleRefresh = async () => {
    if (!feed) return;

    try {
      setIsRefreshing(true);
      await api.refreshFeed(feed.id);
      toast.success('Feed refresh initiated');
    } catch (error) {
      console.error('Failed to refresh feed:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to refresh feed');
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleDelete = async () => {
    if (!feed) return;

    try {
      setIsDeleting(true);
      await api.deleteFeed(feed.id);
      toast.success('Feed deleted successfully');
      onFeedDeleted(feed.id);
      onOpenChange(false);
      setShowDeleteConfirm(false);
    } catch (error) {
      console.error('Failed to delete feed:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to delete feed');
    } finally {
      setIsDeleting(false);
    }
  };

  if (!feed) return null;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Feed Settings
            </DialogTitle>
            <DialogDescription>
              Manage settings for &ldquo;{feed.title || 'Untitled Feed'}&rdquo;
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleUpdate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="url">Feed URL</Label>
              <Input
                id="url"
                value={feed.url}
                disabled
                className="bg-muted"
              />
              <p className="text-xs text-muted-foreground">
                URL cannot be changed after creation
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                placeholder="Feed title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={isUpdating}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="interval">Update Interval (minutes)</Label>
              <Input
                id="interval"
                type="number"
                min="5"
                max="1440"
                value={intervalSeconds / 60}
                onChange={(e) => setIntervalSeconds(parseInt(e.target.value) * 60 || 900)}
                disabled={isUpdating}
              />
            </div>

            {categories.length > 0 && (
              <div className="space-y-2">
                <Label htmlFor="category">Category</Label>
                <select
                  id="category"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={selectedCategoryId}
                  onChange={(e) => setSelectedCategoryId(e.target.value)}
                  disabled={isUpdating}
                >
                  <option value="">No category</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <Separator />

            <div className="space-y-2">
              <Label>Feed Status</Label>
              <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                <div>
                  <p className="text-sm font-medium">
                    Last fetch: {feed.last_fetch_at ? new Date(feed.last_fetch_at).toLocaleString() : 'Never'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Status: {feed.last_status && feed.last_status >= 200 && feed.last_status < 400 ? 'OK' : 'Error'}
                    {feed.last_status && ` (${feed.last_status})`}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                >
                  {isRefreshing ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <DialogFooter className="flex items-center justify-between">
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isUpdating || isDeleting}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Feed
              </Button>

              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => onOpenChange(false)}
                  disabled={isUpdating}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isUpdating}
                >
                  {isUpdating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Updating...
                    </>
                  ) : (
                    'Update Feed'
                  )}
                </Button>
              </div>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={showDeleteConfirm}
        onOpenChange={setShowDeleteConfirm}
        title="Delete Feed"
        description={`Are you sure you want to delete "${feed.title || 'Untitled Feed'}"? This action cannot be undone and will remove all associated items.`}
        confirmText="Delete Feed"
        variant="destructive"
        onConfirm={handleDelete}
        loading={isDeleting}
      />
    </>
  );
} 
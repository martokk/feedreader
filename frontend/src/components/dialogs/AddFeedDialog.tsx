import { CheckCircle, Loader2, Plus, X, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
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

import { api } from '@/lib/api';
import { Category, Feed, FeedValidation } from '@/types';

interface AddFeedDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: Category[];
  onFeedAdded: (feed: Feed) => void;
}

export function AddFeedDialog({
  open,
  onOpenChange,
  categories,
  onFeedAdded,
}: AddFeedDialogProps) {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [intervalSeconds, setIntervalSeconds] = useState(900); // 15 minutes default
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [isValidating, setIsValidating] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [validation, setValidation] = useState<FeedValidation | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Reset form when dialog opens/closes
  useEffect(() => {
    if (!open) {
      setUrl('');
      setTitle('');
      setIntervalSeconds(900);
      setSelectedCategoryIds([]);
      setValidation(null);
      setValidationError(null);
    }
  }, [open]);

  // Validate URL when it changes (debounced)
  useEffect(() => {
    if (!url.trim()) {
      setValidation(null);
      setValidationError(null);
      return;
    }

    const timeoutId = setTimeout(async () => {
      if (url.trim() && url.includes('://')) {
        try {
          setIsValidating(true);
          setValidationError(null);
          const result = await api.validateFeedUrl(url.trim());
          setValidation(result);
          if (result.is_valid && result.feed_title && !title) {
            setTitle(result.feed_title);
          }
        } catch (error) {
          setValidationError(error instanceof Error ? error.message : 'Validation failed');
          setValidation(null);
        } finally {
          setIsValidating(false);
        }
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [url, title]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!url.trim()) {
      toast.error('Please enter a feed URL');
      return;
    }

    if (validation && !validation.is_valid) {
      toast.error('Please enter a valid feed URL');
      return;
    }

    try {
      setIsCreating(true);
      const newFeed = await api.createFeed({
        url: url.trim(),
        title: title.trim() || undefined,
        interval_seconds: intervalSeconds,
      });

      // If a category is selected, assign the feed to it
      if (selectedCategoryIds.length > 0) {
        try {
          await api.assignFeedToCategories(newFeed.id, selectedCategoryIds);
          console.log('Feed assigned to categories:', selectedCategoryIds);
        } catch (error) {
          console.warn('Failed to assign categories:', error);
          // Don't fail the entire operation for category assignment
        }
      }

      toast.success('Feed added successfully');
      onFeedAdded(newFeed);
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to create feed:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to add feed');
    } finally {
      setIsCreating(false);
    }
  };

  const isValid = url.trim() && (!validation || validation.is_valid) && !validationError;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="h-5 w-5" />
            Add Feed
          </DialogTitle>
          <DialogDescription>
            Add a new RSS feed to your collection. We&apos;ll validate the URL and fetch the feed title automatically.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="url">Feed URL *</Label>
            <div className="relative">
              <Input
                id="url"
                type="url"
                placeholder="https://example.com/feed.xml"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={isCreating}
              />
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                {isValidating && (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                )}
                {!isValidating && validation && validation.is_valid && (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                )}
                {!isValidating && (validation && !validation.is_valid || validationError) && (
                  <XCircle className="h-4 w-4 text-destructive" />
                )}
              </div>
            </div>
            {validationError && (
              <p className="text-sm text-destructive">{validationError}</p>
            )}
            {validation && !validation.is_valid && validation.error_message && (
              <p className="text-sm text-destructive">{validation.error_message}</p>
            )}
            {validation && validation.is_valid && (
              <p className="text-sm text-green-600">Valid RSS feed detected</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              placeholder="Feed title (auto-detected)"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isCreating}
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
              disabled={isCreating}
            />
          </div>

          {categories.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="category">Categories (Optional)</Label>
              <div className="flex flex-wrap items-center gap-2 p-2 border border-input rounded-md bg-muted">
                {categories.map((category) => (
                  <Badge
                    key={category.id}
                    variant={selectedCategoryIds.includes(category.id) ? 'default' : 'secondary'}
                    className="flex items-center gap-1 cursor-pointer"
                    onClick={() => {
                      setSelectedCategoryIds(prev => {
                        const newSelected = [...prev];
                        const index = newSelected.indexOf(category.id);
                        if (index > -1) {
                          newSelected.splice(index, 1);
                        } else {
                          newSelected.push(category.id);
                        }
                        return newSelected;
                      });
                    }}
                  >
                    {category.name}
                    {selectedCategoryIds.includes(category.id) && (
                      <X className="h-3 w-3" />
                    )}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isCreating}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!isValid || isCreating || isValidating}
            >
              {isCreating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Adding Feed...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Feed
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
} 
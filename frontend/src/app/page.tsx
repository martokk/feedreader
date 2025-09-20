'use client';

import { AlertTriangle, ChevronDown, ChevronRight, Edit, ExternalLink, Filter, Folder, FolderPlus, MoreVertical, Plus, RefreshCw, Rss, Settings, Upload } from 'lucide-react';
import { useCallback, useEffect, useRef, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

import { api } from '@/lib/api';
import { SSEClient } from '@/lib/sse';
import { Category, Feed, Item, UserSettings } from '@/types';

import { AddFeedDialog } from '@/components/dialogs/AddFeedDialog';
import { CategoryDialog } from '@/components/dialogs/CategoryDialog';
import { FeedSettingsDialog } from '@/components/dialogs/FeedSettingsDialog';
import { Settings as SettingsPage } from '@/components/Settings';
import { ThemeToggle } from '@/components/theme-toggle';

// Helper function to get feed title by feed_id
const getFeedTitle = (feedId: string, feeds: Feed[]): string => {
  const feed = feeds.find(f => f.id === feedId);
  return feed?.title || 'Unknown Feed';
};

// Helper function to check if a feed has an error
const isFeedInError = (feed: Feed): boolean => {
  return !!(feed.last_error || (feed.last_status && (feed.last_status < 200 || feed.last_status >= 400)));
};

// Helper function to check if a category contains feeds with errors
const categoryHasErrors = (categoryId: string, feedsByCategory: Record<string, Feed[]>): boolean => {
  const categoryFeeds = feedsByCategory[categoryId] || [];
  return categoryFeeds.some(feed => isFeedInError(feed));
};

// Helper function to format relative time
const formatRelativeTime = (dateString: string): string => {
  try {
    const date = new Date(dateString);
    
    // Check if date is valid
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

    // Handle future dates
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

function HomePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [feedsByCategory, setFeedsByCategory] = useState<Record<string, Feed[]>>({});
  const [selectedFeed, setSelectedFeed] = useState<Feed | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null);
  const [loading, setLoading] = useState(true);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [filterUnread, setFilterUnread] = useState(true);
  const [sseClient, setSseClient] = useState<SSEClient | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [draggedFeed, setDraggedFeed] = useState<Feed | null>(null);
  
  // Dialog states
  const [showAddFeedDialog, setShowAddFeedDialog] = useState(false);
  const [showCategoryDialog, setShowCategoryDialog] = useState(false);
  const [showFeedSettingsDialog, setShowFeedSettingsDialog] = useState(false);
  const [selectedFeedForSettings, setSelectedFeedForSettings] = useState<Feed | null>(null);
  const [selectedCategoryForEdit, setSelectedCategoryForEdit] = useState<Category | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [selectedSettingsCategory, setSelectedSettingsCategory] = useState('behavior');
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  
  // Refs for scroll detection
  const itemRefs = useRef<Map<string, HTMLElement>>(new Map());
  const observerRef = useRef<IntersectionObserver | null>(null);

  // URL parameter management
  const updateUrlParams = useCallback((feedId?: string, categoryId?: string) => {
    const params = new URLSearchParams(searchParams.toString());

    if (feedId) {
      params.set('feed', feedId);
      params.delete('category');
    } else if (categoryId) {
      params.set('category', categoryId);
      params.delete('feed');
    } else {
      params.delete('feed');
      params.delete('category');
    }

    router.replace(`?${params.toString()}`, { scroll: false });
  }, [router, searchParams]);

  // Restore state from URL params
  const restoreStateFromUrl = useCallback(() => {
    const feedId = searchParams.get('feed');
    const categoryId = searchParams.get('category');

    if (feedId) {
      const feed = feeds.find(f => f.id === feedId);
      if (feed) {
        setSelectedFeed(feed);
        setSelectedCategory(null);
        loadFeedItems(feed);
      }
    } else if (categoryId) {
      const category = categories.find(c => c.id === categoryId);
      if (category) {
        setSelectedCategory(category);
        setSelectedFeed(null);
        loadCategoryItems(category);
      }
    }
  }, [searchParams, feeds, categories]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load initial data
  useEffect(() => {
    loadInitialData();
    setupSSE();

    return () => {
      if (sseClient) {
        sseClient.disconnect();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Restore state from URL when data loads
  useEffect(() => {
    if (feeds.length > 0 && categories.length >= 0) {
      restoreStateFromUrl();
    }
  }, [feeds, categories, restoreStateFromUrl]);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const [feedsData, categoriesData] = await Promise.all([
        api.getFeeds(),
        api.getCategories(),
        loadUserSettings()
      ]);
      
      setFeeds(feedsData);
      setCategories(categoriesData);

      // Load feeds for each category
      const categoryFeedsMap: Record<string, Feed[]> = {};
      for (const category of categoriesData) {
        try {
          const categoryFeeds = await api.getCategoryFeeds(category.id);
          categoryFeedsMap[category.id] = categoryFeeds;
        } catch (error) {
          console.error(`Failed to load feeds for category ${category.name}:`, error);
          categoryFeedsMap[category.id] = [];
        }
      }
      setFeedsByCategory(categoryFeedsMap);
    } catch (error) {
      console.error('Failed to load initial data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadUserSettings = async () => {
    try {
      const settings = await api.getUserSettings();
      setUserSettings(settings);
    } catch (error) {
      console.error('Failed to load user settings:', error);
      // Create default settings if none exist
      try {
        const defaultSettings = await api.createUserSettings({ 
          theme: 'system',
          mark_read_on_scroll: true
        });
        setUserSettings(defaultSettings);
      } catch (createError) {
        console.error('Failed to create default settings:', createError);
      }
    }
  };

  const setupSSE = () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const client = new SSEClient(`${apiUrl}/api/v1/sse/events`);
    
    client.on('connected', () => {
      setConnectionStatus('connected');
      toast.success('Connected to live updates');
    });
    
    client.on('new_items', (event) => {
      const { feed_id, count } = event.data;
      const feed = feeds.find(f => f.id === feed_id);
      toast.success(`${count} new items in ${feed?.title || 'Unknown feed'}`);
      
      // Refresh items if viewing this feed
      if (selectedFeed && selectedFeed.id === feed_id) {
        loadFeedItems(selectedFeed);
      }
    });

    client.on('fetch_status', (event) => {
      const { feed_id, status, message } = event.data;
      if (status === 'error') {
        const feed = feeds.find(f => f.id === feed_id);
        toast.error(`Feed error: ${feed?.title || 'Unknown feed'} - ${message}`);
      }
    });

    client.on('error', () => {
      setConnectionStatus('disconnected');
    });

    setConnectionStatus('connecting');
    client.connect();
    setSseClient(client);
  };

  const loadFeedItems = useCallback(async (feed: Feed, customFilterUnread?: boolean, skipLoading?: boolean) => {
    try {
      if (!skipLoading) {
        setItemsLoading(true);
      }
      const shouldFilterUnread = customFilterUnread !== undefined ? customFilterUnread : filterUnread;
      const itemsData = await api.getFeedItems(feed.id, {
        limit: 100,
        unread_only: shouldFilterUnread
      });
      setItems(itemsData);
    } catch (error) {
      console.error('Failed to load feed items:', error);
      toast.error('Failed to load items');
    } finally {
      if (!skipLoading) {
        setItemsLoading(false);
      }
    }
  }, [filterUnread]);

  const loadCategoryItems = useCallback(async (category: Category, customFilterUnread?: boolean, skipLoading?: boolean) => {
    try {
      if (!skipLoading) {
        setItemsLoading(true);
      }
      const shouldFilterUnread = customFilterUnread !== undefined ? customFilterUnread : filterUnread;
      const itemsData = await api.getCategoryItems(category.id, {
        limit: 100,
        read_status: shouldFilterUnread ? 'unread' : undefined
      });
      setItems(itemsData);
    } catch (error) {
      console.error('Failed to load category items:', error);
      toast.error('Failed to load items');
    } finally {
      if (!skipLoading) {
        setItemsLoading(false);
      }
    }
  }, [filterUnread]);

  const handleFeedSelect = (feed: Feed) => {
    setSelectedFeed(feed);
    setSelectedCategory(null);
    updateUrlParams(feed.id);
    loadFeedItems(feed);
  };

  const handleCategorySelect = (category: Category) => {
    setSelectedCategory(category);
    setSelectedFeed(null);
    updateUrlParams(undefined, category.id);
    loadCategoryItems(category);
  };

  const toggleCategoryExpanded = (categoryId: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(categoryId)) {
      newExpanded.delete(categoryId);
    } else {
      newExpanded.add(categoryId);
    }
    setExpandedCategories(newExpanded);
  };

  const handleMarkAsRead = async (item: Item) => {
    try {
      await api.markItemRead(item.id, !item.is_read);
      setItems(prev => prev.map(i => 
        i.id === item.id ? { ...i, is_read: !item.is_read } : i
      ));
      toast.success(item.is_read ? 'Marked as unread' : 'Marked as read');
    } catch (error) {
      console.error('Failed to update read status:', error);
      toast.error('Failed to update item');
    }
  };

  const markItemAsRead = useCallback(async (itemId: string) => {
    try {
      await api.markItemRead(itemId, true);
      setItems(prev => prev.map(i => 
        i.id === itemId ? { ...i, is_read: true } : i
      ));
    } catch (error) {
      console.error('Failed to mark item as read:', error);
    }
  }, []);

  // Set up intersection observer for scroll-to-read functionality
  useEffect(() => {
    // Only set up observer if mark read on scroll is enabled
    if (!userSettings?.mark_read_on_scroll) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const itemId = entry.target.getAttribute('data-item-id');
          if (!itemId) return;

          const item = items.find(i => i.id === itemId);
          if (!item || item.is_read) return;

          // If item is no longer intersecting (scrolled out of view), mark as read
          if (!entry.isIntersecting && entry.boundingClientRect.top < 0) {
            markItemAsRead(itemId);
          }
        });
      },
      {
        root: null, // viewport
        rootMargin: '0px',
        threshold: 0
      }
    );

    observerRef.current = observer;

    // Observe all currently mounted item elements
    itemRefs.current.forEach((element) => {
      observer.observe(element);
    });

    return () => {
      observer.disconnect();
    };
  }, [userSettings?.mark_read_on_scroll, items, markItemAsRead]);

  const setItemRef = useCallback((itemId: string, element: HTMLElement | null) => {
    if (element) {
      itemRefs.current.set(itemId, element);
      // If observer is set up, observe this element
      if (observerRef.current && userSettings?.mark_read_on_scroll) {
        observerRef.current.observe(element);
      }
    } else {
      // Clean up when element is unmounted
      const oldElement = itemRefs.current.get(itemId);
      if (oldElement && observerRef.current) {
        observerRef.current.unobserve(oldElement);
      }
      itemRefs.current.delete(itemId);
    }
  }, [userSettings?.mark_read_on_scroll]);

  const filteredItems = items.filter(item => {
    if (filterUnread && item.is_read) return false;
    return true;
  });

  const unreadCount = items.filter(item => !item.is_read).length;

  // Dialog handlers
  const handleFeedAdded = (newFeed: Feed) => {
    setFeeds(prev => [newFeed, ...prev]);
    // Refresh categorization data
    loadInitialData();
  };

  const handleFeedUpdated = (updatedFeed: Feed) => {
    setFeeds(prev => prev.map(feed => 
      feed.id === updatedFeed.id ? updatedFeed : feed
    ));
    if (selectedFeed?.id === updatedFeed.id) {
      setSelectedFeed(updatedFeed);
    }
    // Refresh categorization data
    loadInitialData();
  };

  const handleFeedDeleted = (feedId: string) => {
    setFeeds(prev => prev.filter(feed => feed.id !== feedId));
    if (selectedFeed?.id === feedId) {
      setSelectedFeed(null);
      setItems([]);
    }
    // Refresh categorization data
    loadInitialData();
  };

  const handleCategoryCreated = (newCategory: Category) => {
    setCategories(prev => [...prev, newCategory].sort((a, b) => a.order - b.order));
    // Refresh categorization data
    loadInitialData();
  };

  const handleCategoryUpdated = (updatedCategory: Category) => {
    setCategories(prev => prev.map(category => 
      category.id === updatedCategory.id ? updatedCategory : category
    ).sort((a, b) => a.order - b.order));
    // Refresh categorization data
    loadInitialData();
  };

  const handleOpenFeedSettings = (feed: Feed) => {
    setSelectedFeedForSettings(feed);
    setShowFeedSettingsDialog(true);
  };

  const handleOpenCategoryCreation = () => {
    setSelectedCategoryForEdit(null);
    setShowCategoryDialog(true);
  };

  const handleOpenCategorySettings = (category: Category) => {
    setSelectedCategoryForEdit(category);
    setShowCategoryDialog(true);
  };

  const handleCloseCategoryDialog = async () => {
    setShowCategoryDialog(false);
    setSelectedCategoryForEdit(null);
    await loadInitialData(); // Refresh data after category edit
  };

  const handleOpenSettings = () => {
    setShowSettings(true);
  };

  const handleCloseSettings = () => {
    setShowSettings(false);
    // Restore state from URL when closing settings
    restoreStateFromUrl();
  };

  const handleOpmlImport = async (file: File) => {
    try {
      const result = await api.importOpml(file);
      toast.success(`OPML imported successfully! Created ${result.feeds_created} feeds, skipped ${result.feeds_skipped} duplicates.`);
      if (result.errors.length > 0) {
        console.warn('Import errors:', result.errors);
        toast.warning(`Some feeds had errors: ${result.errors.length} issues`);
      }
      // Refresh the feeds data
      await loadInitialData();
    } catch (error) {
      console.error('Failed to import OPML:', error);
      toast.error('Failed to import OPML file');
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      handleOpmlImport(file);
    }
    // Reset the input value so the same file can be selected again
    event.target.value = '';
  };

  const handleDragStart = (e: React.DragEvent, feed: Feed) => {
    setDraggedFeed(feed);
    e.dataTransfer.setData('text/plain', feed.id);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragEnd = () => {
    setDraggedFeed(null);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDropOnCategory = async (e: React.DragEvent, targetCategoryId: string) => {
    e.preventDefault();
    
    if (!draggedFeed) return;

    try {
      // Get current categories for the feed
      const currentCategories = await api.getFeedCategories(draggedFeed.id);
      const currentCategoryIds = currentCategories.map(cat => cat.id);
      
      // Add the target category if it's not already there
      if (!currentCategoryIds.includes(targetCategoryId)) {
        const newCategoryIds = [...currentCategoryIds, targetCategoryId];
        await api.updateFeedCategories(draggedFeed.id, newCategoryIds);
        
        // Refresh the feeds data
        await loadInitialData();
        
        toast.success('Feed moved to category successfully');
      } else {
        toast.info('Feed is already in this category');
      }
    } catch (error) {
      console.error('Failed to move feed to category:', error);
      toast.error('Failed to move feed to category');
    } finally {
      setDraggedFeed(null);
    }
  };

  const handleDropOnUncategorized = async (e: React.DragEvent) => {
    e.preventDefault();
    
    if (!draggedFeed) return;

    try {
      // Remove feed from all categories (make it uncategorized)
      await api.updateFeedCategories(draggedFeed.id, []);
      
      // Refresh the feeds data
      await loadInitialData();
      
      toast.success('Feed moved to uncategorized');
    } catch (error) {
      console.error('Failed to move feed to uncategorized:', error);
      toast.error('Failed to move feed to uncategorized');
    } finally {
      setDraggedFeed(null);
    }
  };

  // Get feeds by category
  const getFeedsByCategory = (categoryId: string) => {
    if (feedsByCategory[categoryId]) {
      return feedsByCategory[categoryId];
    }
    return [];
  };

  const getUncategorizedFeeds = () => {
    // Get all feed IDs that are in categories
    const categorizedFeedIds = new Set<string>();
    Object.values(feedsByCategory).forEach(categoryFeeds => {
      categoryFeeds.forEach(feed => categorizedFeedIds.add(feed.id));
    });
    
    // Return feeds that are not in any category
    return feeds.filter(feed => !categorizedFeedIds.has(feed.id));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <Rss className="h-12 w-12 animate-spin mx-auto text-primary" />
          <p className="text-muted-foreground">Loading RSS Reader...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur supports-[backdrop-filter]:bg-card/50 sticky top-0 z-50">
        <div className="h-16 flex">
          {/* Sidebar Header */}
          <div className="w-80 px-6 flex items-center justify-between border-r">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <Rss className="h-6 w-6 text-primary" />
                <h1 className="text-xl font-bold">RSS Reader</h1>
              </div>
              
              {/* Connection Status */}
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full ${
                  connectionStatus === 'connected' ? 'bg-green-500' :
                  connectionStatus === 'connecting' ? 'bg-yellow-500' :
                  'bg-red-500'
                }`} />
                <span className="text-xs text-muted-foreground">
                  {connectionStatus === 'connected' ? 'Live' :
                   connectionStatus === 'connecting' ? 'Connecting...' :
                   'Offline'}
                </span>
              </div>
            </div>

            {/* Plus Button */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setShowAddFeedDialog(true)}>
                  <Rss className="h-4 w-4 mr-2" />
                  Add Feed
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleOpenCategoryCreation}>
                  <FolderPlus className="h-4 w-4 mr-2" />
                  Add Category
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => document.getElementById('opml-import')?.click()}>
                  <Upload className="h-4 w-4 mr-2" />
                  Import OPML
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <input
              id="opml-import"
              type="file"
              accept=".opml,.xml"
              onChange={handleFileUpload}
              className="hidden"
            />
          </div>

          {/* Main Content Header */}
          <div className="flex-1 px-6 flex items-center justify-between">
            {showSettings ? (
              /* Settings header */
              <>
                {/* Left spacer */}
                <div className="flex-1"></div>
                
                {/* Centered Settings title */}
                <div className="flex items-center space-x-2">
                  <h2 className="text-lg font-semibold">Settings</h2>
                </div>
                
                {/* Right spacer */}
                <div className="flex-1"></div>
              </>
            ) : (selectedFeed || selectedCategory) ? (
              <>
                {/* Left spacer */}
                <div className="flex-1"></div>
                
                {/* Centered title with unread counter */}
                <div className="flex items-center space-x-2">
                  {selectedCategory && (
                    <>
                      {/* Category color indicator */}
                      {selectedCategory.color && (
                        <div 
                          className="w-3 h-3 rounded-full border"
                          style={{ backgroundColor: selectedCategory.color }}
                        />
                      )}
                      {/* Category folder icon */}
                      <Folder className="h-4 w-4" />
                    </>
                  )}
                  <h2 
                    className={`text-lg font-semibold ${selectedFeed ? 'cursor-pointer hover:text-primary transition-colors' : ''}`}
                    onClick={() => {
                      if (selectedFeed) {
                        handleOpenFeedSettings(selectedFeed);
                      }
                    }}
                    title={selectedFeed ? 'Click to edit feed settings' : undefined}
                  >
                    {selectedFeed ? selectedFeed.title || 'Untitled Feed' : selectedCategory?.name}
                  </h2>
                  {unreadCount > 0 && (
                    <Badge className="text-xs bg-black text-white hover:bg-black/80 dark:bg-white dark:text-black dark:hover:bg-white/80">
                      {unreadCount}
                    </Badge>
                  )}
                </div>
                
                {/* Right side - 3-dot menu */}
                <div className="flex-1 flex justify-end">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        size="sm"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => {
                        const newFilterValue = !filterUnread;
                        setFilterUnread(newFilterValue);
                        // Reload items with the new filter, skip loading state for smooth transition
                        if (selectedFeed) {
                          loadFeedItems(selectedFeed, newFilterValue, true);
                        } else if (selectedCategory) {
                          loadCategoryItems(selectedCategory, newFilterValue, true);
                        }
                      }}>
                        <Filter className="h-4 w-4 mr-2" />
                        {filterUnread ? "Show All" : "Hide Read"}
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        onClick={() => {
                          if (selectedFeed) {
                            handleOpenFeedSettings(selectedFeed);
                          } else if (selectedCategory) {
                            handleOpenCategorySettings(selectedCategory);
                          }
                        }}
                      >
                        <Edit className="h-4 w-4 mr-2" />
                        {selectedFeed ? "Edit Feed" : "Edit Category"}
                      </DropdownMenuItem>
                      {selectedFeed && selectedFeed.url && (
                        <DropdownMenuItem onClick={() => window.open(selectedFeed.url, '_blank')}>
                          <ExternalLink className="h-4 w-4 mr-2" />
                          Open RSS URL
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </>
            ) : (
              /* Empty state - no content selected */
              <div className="flex-1"></div>
            )}
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-4rem)]">
        {/* Sidebar */}
        <div className="w-80 border-r bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 relative">
          <div className="h-[calc(100vh-4rem-4rem)] overflow-y-auto">
            <div className="p-4 space-y-2">
              {/* Feeds Section */}
              <div className="space-y-1">

                {categories.map((category) => (
                  <div key={category.id} className="space-y-1">
                    <div
                      className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors hover:bg-accent group ${
                        selectedCategory?.id === category.id ? 'bg-accent' : ''
                      } ${draggedFeed ? 'border-2 border-dashed border-primary/50' : ''}`}
                      onClick={() => handleCategorySelect(category)}
                      onDragOver={handleDragOver}
                      onDrop={(e) => handleDropOnCategory(e, category.id)}
                    >
                      <div className="flex items-center space-x-2 flex-1 min-w-0">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-4 w-4 p-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleCategoryExpanded(category.id);
                          }}
                        >
                          {expandedCategories.has(category.id) ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
                        </Button>
                        {categoryHasErrors(category.id, feedsByCategory) && (
                          <AlertTriangle className="h-4 w-4 flex-shrink-0 text-red-500" />
                        )}
                        {category.color && (
                          <div 
                            className="w-3 h-3 rounded-full border"
                            style={{ backgroundColor: category.color }}
                          />
                        )}
                        <Folder className="h-4 w-4 flex-shrink-0" />
                        <span className={`flex-1 truncate ${categoryHasErrors(category.id, feedsByCategory) ? 'text-red-500' : ''}`}>
                          {category.name}
                        </span>
                        {(category.unread_count || 0) > 0 && (
                          <span className="ml-auto text-xs font-semibold text-muted-foreground/80 pr-2">
                            {(category.unread_count || 0)}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Category Feeds */}
                    {expandedCategories.has(category.id) && (
                      <div className="ml-6 space-y-1">
                        {getFeedsByCategory(category.id).map((feed) => (
                          <div
                            key={feed.id}
                            draggable
                            className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors hover:bg-accent ${
                              selectedFeed?.id === feed.id ? 'bg-accent' : ''
                            } ${draggedFeed?.id === feed.id ? 'opacity-50' : ''}`}
                            onClick={() => handleFeedSelect(feed)}
                            onDragStart={(e) => handleDragStart(e, feed)}
                            onDragEnd={handleDragEnd}
                          >
                            <div className="flex items-center space-x-2 flex-1 min-w-0">
                              {isFeedInError(feed) && (
                                <AlertTriangle className="h-3 w-3 flex-shrink-0 text-red-500" />
                              )}
                              <Rss className="h-3 w-3 flex-shrink-0" />
                              <span className={`text-sm truncate ${isFeedInError(feed) ? 'text-red-500' : ''}`}>
                                {feed.title || 'Untitled Feed'}
                              </span>
                            </div>
                            {(feed.unread_count || 0) > 0 && (
                              <span className="ml-auto text-xs font-semibold text-muted-foreground/80 pr-2">
                                {(feed.unread_count || 0)}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {/* Uncategorized Feeds */}
                {getUncategorizedFeeds().length > 0 && (
                  <div className="space-y-1">
                    <h4 
                      className={`text-sm font-medium text-muted-foreground px-2 py-1 ${
                        draggedFeed ? 'border-2 border-dashed border-primary/50 rounded' : ''
                      }`}
                      onDragOver={handleDragOver}
                      onDrop={handleDropOnUncategorized}
                    >
                      Uncategorized
                    </h4>
                    {getUncategorizedFeeds().map((feed) => (
                      <div
                        key={feed.id}
                        draggable
                        className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors hover:bg-accent group ${
                          selectedFeed?.id === feed.id ? 'bg-accent' : ''
                        } ${draggedFeed?.id === feed.id ? 'opacity-50' : ''}`}
                        onClick={() => handleFeedSelect(feed)}
                        onDragStart={(e) => handleDragStart(e, feed)}
                        onDragEnd={handleDragEnd}
                      >
                        <div className="flex items-center space-x-2 flex-1 min-w-0">
                          {isFeedInError(feed) && (
                            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-red-500" />
                          )}
                          <Rss className="h-4 w-4 flex-shrink-0" />
                          <span className={`font-medium truncate ${isFeedInError(feed) ? 'text-red-500' : ''}`}>
                            {feed.title || 'Untitled Feed'}
                          </span>
                        </div>
                        {(feed.unread_count || 0) > 0 && (
                          <span className="ml-auto text-xs font-semibold text-muted-foreground/80 pr-2">
                            {(feed.unread_count || 0)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
          
          {/* Sidebar Footer - Absolutely pinned to bottom */}
          <div className="absolute bottom-0 left-0 right-0 border-t p-4 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex items-center justify-center space-x-2">
              <Button variant="outline" size="sm" onClick={() => loadInitialData()}>
                <RefreshCw className="h-4 w-4" />
              </Button>
              <ThemeToggle />
              <Button variant="outline" size="sm" onClick={handleOpenSettings}>
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1">
          {showSettings ? (
            <SettingsPage
              selectedCategory={selectedSettingsCategory}
              onCategoryChange={setSelectedSettingsCategory}
              onClose={handleCloseSettings}
            />
          ) : (selectedFeed || selectedCategory) ? (
            <div className="h-[calc(100vh-4rem)] overflow-y-auto">
                  {itemsLoading ? (
                    <div className="flex items-center justify-center h-64">
                      <div className="text-center">
                        <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
                        <p className="text-muted-foreground">Loading articles...</p>
                      </div>
                    </div>
                  ) : filteredItems.length === 0 ? (
                    <div className="flex items-center justify-center h-64">
                      <div className="text-center">
                        <Rss className="h-16 w-16 mx-auto mb-4 opacity-50 text-muted-foreground" />
                        <p className="text-muted-foreground">No articles found</p>
                      </div>
                    </div>
                  ) : (
                    <div className="max-w-4xl mx-auto">
                      {/* Clean vertical list layout */}
                      <div className="divide-y divide-border">
                        {filteredItems.map((item) => (
                          <article
                            key={item.id}
                            ref={(el) => setItemRef(item.id, el)}
                            data-item-id={item.id}
                            className={`group cursor-pointer transition-colors hover:bg-accent/30 ${
                              item.is_read ? 'opacity-50' : ''
                            }`}
                            onClick={() => handleMarkAsRead(item)}
                          >
                            <div className="px-6 py-5">
                              <div className="flex items-start gap-4">
                                {/* Placeholder image */}
                                <div className={`w-16 h-16 bg-gradient-to-br from-primary/10 to-secondary/10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                                  item.is_read ? 'opacity-60' : ''
                                }`}>
                                  <Rss className="h-6 w-6 text-primary/40" />
                                </div>
                                
                                <div className="flex-1 min-w-0 flex justify-between">
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                      <h3 className={`text-base font-normal leading-relaxed line-clamp-2 ${
                                        item.is_read ? 'text-muted-foreground/70' : 'text-foreground hover:text-primary transition-colors'
                                      }`}>
                                        {item.title || 'Untitled'}
                                      </h3>
                                      {item.url && (
                                        <a
                                          href={item.url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className={`text-muted-foreground hover:text-primary transition-colors flex-shrink-0 ${
                                            item.is_read ? 'opacity-60' : ''
                                          }`}
                                          onClick={(e) => e.stopPropagation()}
                                          title="Open original article"
                                        >
                                          <ExternalLink className="h-4 w-4" />
                                        </a>
                                      )}
                                    </div>
                                    
                                    {item.published_at && (
                                      <div className="mb-2 flex items-center gap-2">
                                        <span className={`text-xs font-medium ${
                                          item.is_read ? 'text-muted-foreground/50' : 'text-muted-foreground/60'
                                        }`}>
                                          {getFeedTitle(item.feed_id, feeds)}
                                        </span>
                                        <span className={`${
                                          item.is_read ? 'text-muted-foreground/40' : 'text-muted-foreground/40'
                                        }`}>•</span>
                                        <span className={`text-xs font-medium ${
                                          item.is_read ? 'text-muted-foreground/50' : 'text-muted-foreground/60'
                                        }`}>
                                          {formatRelativeTime(item.published_at)}
                                        </span>
                                      </div>
                                    )}
                                    
                                    {item.content_text && (
                                      <p className={`text-sm mb-3 line-clamp-2 leading-relaxed ${
                                        item.is_read ? 'text-muted-foreground/60' : 'text-muted-foreground'
                                      }`}>
                                        {item.content_text}
                                      </p>
                                    )}
                                    
                                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                                      {selectedCategory && selectedFeed && (
                                        <span className={`text-xs font-medium ${
                                          item.is_read ? 'text-muted-foreground/50' : 'text-muted-foreground/70'
                                        }`}>
                                          {selectedFeed.title || 'Unknown Source'}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  
                                  <div className="flex items-start space-x-2 flex-shrink-0">
                                    {item.starred && (
                                      <Badge variant="secondary" className={`text-xs ${
                                        item.is_read ? 'opacity-60' : ''
                                      }`}>★</Badge>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
            </div>
          ) : (
            <div className="h-[calc(100vh-4rem)] flex items-center justify-center">
              <div className="text-center max-w-md">
                <Rss className="h-24 w-24 mx-auto mb-6 text-muted-foreground opacity-50" />
                <h3 className="text-2xl font-semibold mb-4">Welcome to RSS Reader</h3>
                <p className="text-muted-foreground mb-8">
                  Select a feed or category from the sidebar to start reading articles
                </p>
                {feeds.length === 0 && (
                  <Button onClick={() => setShowAddFeedDialog(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Your First Feed
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <AddFeedDialog
        open={showAddFeedDialog}
        onOpenChange={setShowAddFeedDialog}
        categories={categories}
        onFeedAdded={handleFeedAdded}
      />

      <FeedSettingsDialog
        open={showFeedSettingsDialog}
        onOpenChange={() => setShowFeedSettingsDialog(false)}
        feed={selectedFeedForSettings}
        categories={categories}
        onFeedUpdated={handleFeedUpdated}
        onFeedDeleted={handleFeedDeleted}
      />

      <CategoryDialog
        open={showCategoryDialog}
        onOpenChange={handleCloseCategoryDialog}
        onCategoryCreated={handleCategoryCreated}
        onCategoryUpdated={handleCategoryUpdated}
        category={selectedCategoryForEdit}
      />
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="text-center space-y-4">
        <Rss className="h-12 w-12 animate-spin mx-auto text-primary" />
        <p className="text-muted-foreground">Loading RSS Reader...</p>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <HomePageContent />
    </Suspense>
  );
}

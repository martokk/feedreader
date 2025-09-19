'use client';

import { ChevronDown, ChevronRight, ExternalLink, Filter, Folder, FolderPlus, Plus, RefreshCw, Rss, Search, Settings } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';

import { api } from '@/lib/api';
import { SSEClient } from '@/lib/sse';
import { Category, Feed, Item } from '@/types';

import { AddFeedDialog } from '@/components/dialogs/AddFeedDialog';
import { CategoryDialog } from '@/components/dialogs/CategoryDialog';
import { FeedSettingsDialog } from '@/components/dialogs/FeedSettingsDialog';

// Helper function to get feed title by feed_id
const getFeedTitle = (feedId: string, feeds: Feed[]): string => {
  const feed = feeds.find(f => f.id === feedId);
  return feed?.title || 'Unknown Feed';
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

export default function HomePage() {
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [feedsByCategory, setFeedsByCategory] = useState<Record<string, Feed[]>>({});
  const [selectedFeed, setSelectedFeed] = useState<Feed | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null);
  const [loading, setLoading] = useState(true);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterUnread, setFilterUnread] = useState(false);
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

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const [feedsData, categoriesData] = await Promise.all([
        api.getFeeds(),
        api.getCategories()
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

  const loadFeedItems = async (feed: Feed) => {
    try {
      setItemsLoading(true);
      const itemsData = await api.getFeedItems(feed.id, {
        limit: 100,
        unread_only: filterUnread
      });
      setItems(itemsData);
    } catch (error) {
      console.error('Failed to load feed items:', error);
      toast.error('Failed to load items');
    } finally {
      setItemsLoading(false);
    }
  };

  const loadCategoryItems = async (category: Category) => {
    try {
      setItemsLoading(true);
      const itemsData = await api.getCategoryItems(category.id, {
        limit: 100,
        read_status: filterUnread ? 'unread' : undefined
      });
      setItems(itemsData);
    } catch (error) {
      console.error('Failed to load category items:', error);
      toast.error('Failed to load items');
    } finally {
      setItemsLoading(false);
    }
  };

  const handleFeedSelect = (feed: Feed) => {
    setSelectedFeed(feed);
    setSelectedCategory(null);
    loadFeedItems(feed);
  };

  const handleCategorySelect = (category: Category) => {
    setSelectedCategory(category);
    setSelectedFeed(null);
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

  const filteredItems = items.filter(item => {
    if (filterUnread && item.is_read) return false;
    if (searchTerm && !item.title?.toLowerCase().includes(searchTerm.toLowerCase())) return false;
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

  const handleOpenCategoryEdit = (category: Category) => {
    setSelectedCategoryForEdit(category);
    setShowCategoryDialog(true);
  };

  const handleOpenCategoryCreate = () => {
    setSelectedCategoryForEdit(null);
    setShowCategoryDialog(true);
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
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur supports-[backdrop-filter]:bg-card/50 sticky top-0 z-50">
        <div className="h-16 px-6 flex items-center justify-between">
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

          {/* Search Bar */}
          <div className="flex-1 max-w-md mx-8">
            {(selectedFeed || selectedCategory) && (
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search articles..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm" onClick={() => loadInitialData()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button size="sm" onClick={() => setShowAddFeedDialog(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Feed
            </Button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex">
        {/* Sidebar */}
        <div className="w-80 border-r bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <ScrollArea className="h-[calc(100vh-4rem)]">
            <div className="p-4 space-y-2">
              {/* Categories Section */}
              <div className="space-y-1">
                <div className="flex items-center justify-between px-2 py-1">
                  <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Categories</h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleOpenCategoryCreate}
                    className="h-6 w-6 p-0"
                  >
                    <FolderPlus className="h-3 w-3" />
                  </Button>
                </div>

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
                          {expandedCategories.has(category.id) ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronRight className="h-3 w-3" />
                          )}
                        </Button>
                        {category.color && (
                          <div 
                            className="w-3 h-3 rounded-full border"
                            style={{ backgroundColor: category.color }}
                          />
                        )}
                        <Folder className="h-4 w-4 flex-shrink-0" />
                        <span className="font-medium truncate">{category.name}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenCategoryEdit(category);
                        }}
                      >
                        <Settings className="h-3 w-3" />
                      </Button>
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
                              <Rss className="h-3 w-3 flex-shrink-0" />
                              <span className="text-sm truncate">{feed.title || 'Untitled Feed'}</span>
                            </div>
                            <Badge 
                              variant={feed.last_status && feed.last_status >= 200 && feed.last_status < 400 ? 'default' : 'destructive'} 
                              className="text-xs"
                            >
                              {feed.last_status && feed.last_status >= 200 && feed.last_status < 400 ? 'OK' : 'Error'}
                            </Badge>
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
                          <Rss className="h-4 w-4 flex-shrink-0" />
                          <span className="font-medium truncate">{feed.title || 'Untitled Feed'}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge 
                            variant={feed.last_status && feed.last_status >= 200 && feed.last_status < 400 ? 'default' : 'destructive'} 
                            className="text-xs"
                          >
                            {feed.last_status && feed.last_status >= 200 && feed.last_status < 400 ? 'OK' : 'Error'}
                          </Badge>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenFeedSettings(feed);
                            }}
                          >
                            <Settings className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </ScrollArea>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col">
          {(selectedFeed || selectedCategory) ? (
            <>
              {/* Content Header */}
              <div className="border-b p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-2xl font-bold">
                      {selectedFeed ? selectedFeed.title || 'Untitled Feed' : selectedCategory?.name}
                    </h2>
                    <p className="text-muted-foreground mt-1">
                      {selectedFeed ? selectedFeed.url : selectedCategory?.description}
                    </p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button
                      variant={filterUnread ? "default" : "outline"}
                      size="sm"
                      onClick={() => setFilterUnread(!filterUnread)}
                    >
                      <Filter className="h-4 w-4 mr-2" />
                      Unread ({unreadCount})
                    </Button>
                    {selectedFeed && (
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleOpenFeedSettings(selectedFeed)}
                      >
                        <Settings className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              {/* Articles Content */}
              <div className="flex-1 overflow-hidden">
                <ScrollArea className="h-full">
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
                        {filteredItems.map((item, index) => (
                          <article
                            key={item.id}
                            className={`group cursor-pointer transition-colors hover:bg-accent/30 ${
                              item.is_read ? 'opacity-70' : ''
                            }`}
                            onClick={() => handleMarkAsRead(item)}
                          >
                                                        <div className="px-6 py-5">
                              <div className="flex items-start gap-4">
                                {/* Placeholder image */}
                                <div className="w-16 h-16 bg-gradient-to-br from-primary/10 to-secondary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                  <Rss className="h-6 w-6 text-primary/40" />
                                </div>
                                
                                <div className="flex-1 min-w-0 flex justify-between">
                                  <div className="flex-1 min-w-0">
                                    <h3 className={`text-base font-normal mb-1 leading-relaxed line-clamp-2 ${
                                      item.is_read ? 'text-muted-foreground' : 'text-foreground hover:text-primary transition-colors'
                                    }`}>
                                      {item.title || 'Untitled'}
                                    </h3>
                                    
                                    {item.published_at && (
                                      <div className="mb-2 flex items-center gap-2">
                                        <span className={`text-xs font-medium ${
                                          item.is_read ? 'text-muted-foreground/40' : 'text-muted-foreground/60'
                                        }`}>
                                          {getFeedTitle(item.feed_id, feeds)}
                                        </span>
                                        <span className="text-muted-foreground/40">•</span>
                                        <span className={`text-xs font-medium ${
                                          item.is_read ? 'text-muted-foreground/60' : 'text-muted-foreground'
                                        }`}>
                                          {formatRelativeTime(item.published_at)}
                                        </span>
                                      </div>
                                    )}
                                    
                                    {item.content_text && (
                                      <p className={`text-sm mb-3 line-clamp-2 leading-relaxed ${
                                        item.is_read ? 'text-muted-foreground/80' : 'text-muted-foreground'
                                      }`}>
                                        {item.content_text}
                                      </p>
                                    )}
                                    
                                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                                      {selectedCategory && selectedFeed && (
                                        <span className="text-xs font-medium">
                                          {selectedFeed.title || 'Unknown Source'}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  
                                  <div className="flex items-start space-x-2 flex-shrink-0">
                                    {item.url && (
                                      <a
                                        href={item.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-muted-foreground hover:text-primary transition-colors p-1"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <ExternalLink className="h-4 w-4" />
                                      </a>
                                    )}
                                    {!item.is_read && (
                                      <div className="w-2 h-2 bg-primary rounded-full mt-1" />
                                    )}
                                    {item.starred && (
                                      <Badge variant="secondary" className="text-xs">★</Badge>
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
                </ScrollArea>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
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
        onOpenChange={setShowFeedSettingsDialog}
        feed={selectedFeedForSettings}
        categories={categories}
        onFeedUpdated={handleFeedUpdated}
        onFeedDeleted={handleFeedDeleted}
      />

      <CategoryDialog
        open={showCategoryDialog}
        onOpenChange={setShowCategoryDialog}
        category={selectedCategoryForEdit}
        onCategoryCreated={handleCategoryCreated}
        onCategoryUpdated={handleCategoryUpdated}
      />
    </div>
  );
}

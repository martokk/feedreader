'use client';

import { Filter, MoreHorizontal, Plus, RefreshCw, Rss, Search, Settings } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';

import { api } from '@/lib/api';
import { SSEClient } from '@/lib/sse';
import { Category, Feed, Item } from '@/types';

export default function HomePage() {
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedFeed, setSelectedFeed] = useState<Feed | null>(null);
  const [loading, setLoading] = useState(true);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterUnread, setFilterUnread] = useState(false);
  const [sseClient, setSseClient] = useState<SSEClient | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');

  // Load initial data
  useEffect(() => {
    loadInitialData();
    setupSSE();

    return () => {
      if (sseClient) {
        sseClient.disconnect();
      }
    };
  }, []);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const [feedsData, categoriesData] = await Promise.all([
        api.getFeeds(),
        api.getCategories()
      ]);
      
      setFeeds(feedsData);
      setCategories(categoriesData);
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
      if (selectedFeed?.id === feed_id) {
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

  const handleFeedSelect = (feed: Feed) => {
    setSelectedFeed(feed);
    loadFeedItems(feed);
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
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur supports-[backdrop-filter]:bg-card/50">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
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

          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm" onClick={() => loadInitialData()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Add Feed
            </Button>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar */}
          <div className="lg:col-span-1 space-y-6">
            {/* Feeds List */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center justify-between">
                  Feeds ({feeds.length})
                  <Button variant="ghost" size="sm">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2">
                    {feeds.map((feed) => (
                      <div
                        key={feed.id}
                        className={`p-3 rounded-lg cursor-pointer transition-colors ${
                          selectedFeed?.id === feed.id 
                            ? 'bg-primary text-primary-foreground' 
                            : 'hover:bg-accent'
                        }`}
                        onClick={() => handleFeedSelect(feed)}
                      >
                        <div className="font-medium truncate">
                          {feed.title || 'Untitled Feed'}
                        </div>
                        <div className="text-sm opacity-70 truncate">
                          {feed.url}
                        </div>
                        <div className="flex items-center justify-between mt-2">
                          <Badge variant={feed.last_status === 200 ? 'default' : 'destructive'} className="text-xs">
                            {feed.last_status === 200 ? 'OK' : 'Error'}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Categories */}
            {categories.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Categories</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {categories.map((category) => (
                      <div
                        key={category.id}
                        className="p-2 rounded-lg hover:bg-accent cursor-pointer flex items-center justify-between"
                      >
                        <div className="flex items-center space-x-2">
                          {category.color && (
                            <div 
                              className="w-3 h-3 rounded-full" 
                              style={{ backgroundColor: category.color }}
                            />
                          )}
                          <span className="font-medium">{category.name}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Main Content */}
          <div className="lg:col-span-3 space-y-6">
            {selectedFeed ? (
              <>
                {/* Feed Header */}
                <Card>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-xl">
                          {selectedFeed.title || 'Untitled Feed'}
                        </CardTitle>
                        <p className="text-muted-foreground mt-1">{selectedFeed.url}</p>
                      </div>
                      <Button variant="outline" size="sm">
                        <Settings className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardHeader>
                </Card>

                {/* Filters */}
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center space-x-4">
                      <div className="flex-1">
                        <div className="relative">
                          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                          <Input
                            placeholder="Search articles..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="pl-10"
                          />
                        </div>
                      </div>
                      <Button
                        variant={filterUnread ? "default" : "outline"}
                        size="sm"
                        onClick={() => setFilterUnread(!filterUnread)}
                      >
                        <Filter className="h-4 w-4 mr-2" />
                        Unread ({unreadCount})
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Items List */}
                <Card>
                  <CardHeader>
                    <CardTitle>Articles ({filteredItems.length})</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {filteredItems.length === 0 ? (
                      <div className="text-center py-8 text-muted-foreground">
                        <Rss className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>No articles found</p>
                      </div>
                    ) : (
                      <ScrollArea className="h-[600px]">
                        <div className="space-y-4">
                          {filteredItems.map((item) => (
                            <div
                              key={item.id}
                              className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                                item.is_read 
                                  ? 'bg-muted/50 opacity-75' 
                                  : 'bg-background hover:bg-accent'
                              }`}
                              onClick={() => handleMarkAsRead(item)}
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex-1 min-w-0">
                                  <h3 className={`font-medium mb-2 ${
                                    item.is_read ? 'text-muted-foreground' : 'text-foreground'
                                  }`}>
                                    {item.title || 'Untitled'}
                                  </h3>
                                  
                                  <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                                    {item.published_at && (
                                      <span>
                                        {new Date(item.published_at).toLocaleDateString()}
                                      </span>
                                    )}
                                    {item.url && (
                                      <a
                                        href={item.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-primary hover:underline"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        Read Original
                                      </a>
                                    )}
                                  </div>
                                </div>
                                
                                <div className="flex items-center space-x-2 ml-4">
                                  {!item.is_read && (
                                    <div className="w-2 h-2 bg-primary rounded-full" />
                                  )}
                                  {item.starred && (
                                    <Badge variant="secondary" className="text-xs">★</Badge>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    )}
                  </CardContent>
                </Card>
              </>
            ) : (
              <Card>
                <CardContent className="pt-12 pb-12">
                  <div className="text-center">
                    <Rss className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                    <h3 className="text-xl font-medium mb-2">Welcome to RSS Reader</h3>
                    <p className="text-muted-foreground mb-6">
                      Select a feed from the sidebar to start reading articles
                    </p>
                    {feeds.length === 0 && (
                      <Button>
                        <Plus className="h-4 w-4 mr-2" />
                        Add Your First Feed
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 
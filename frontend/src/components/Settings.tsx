'use client';

import { Monitor, Moon, Settings as SettingsIcon, Sun, X } from 'lucide-react';
import { useTheme } from 'next-themes';
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { Switch } from '@/components/ui/switch';
import { api } from '@/lib/api';
import { UserSettings } from '@/types';

interface SettingsProps {
  selectedCategory: string;
  onCategoryChange: (category: string) => void;
  onClose: () => void;
  onSettingsChanged?: (settings: UserSettings) => void;
}

const settingsCategories = [
  { id: 'appearance', label: 'Appearance', icon: Monitor },
  { id: 'behavior', label: 'Behavior', icon: SettingsIcon },
];

export function Settings({ selectedCategory, onCategoryChange, onClose, onSettingsChanged }: SettingsProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [settings, setSettings] = useState<UserSettings | null>(null);

  const loadSettings = React.useCallback(async () => {
    try {
      const userSettings = await api.getUserSettings();
      setSettings(userSettings);
      // Sync theme with loaded settings
      if (userSettings.theme && userSettings.theme !== theme) {
        setTheme(userSettings.theme);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
      // If no settings exist, create default ones
      try {
        const defaultSettings = await api.createUserSettings({ theme: theme || 'system' });
        setSettings(defaultSettings);
      } catch (createError) {
        console.error('Failed to create default settings:', createError);
        toast.error('Failed to load settings');
      }
    }
  }, [theme, setTheme]);

  useEffect(() => {
    setMounted(true);
    loadSettings();
  }, [loadSettings]);

  const handleThemeChange = async (newTheme: string) => {
    try {
      setTheme(newTheme);
      
      // Update local state immediately for better UX
      if (settings) {
        setSettings({ ...settings, theme: newTheme });
      }
      
      // Save to database
      const updatedSettings = await api.updateUserSettings({ theme: newTheme });
      setSettings(updatedSettings);
      onSettingsChanged?.(updatedSettings);
      
      toast.success('Theme preference saved');
    } catch (error) {
      console.error('Failed to save theme setting:', error);
      toast.error('Failed to save theme preference');
      
      // Revert theme if save failed
      if (settings?.theme) {
        setTheme(settings.theme);
      }
    }
  };

  const handleMarkReadOnScrollChange = async (enabled: boolean) => {
    try {
      // Update local state immediately for better UX
      if (settings) {
        setSettings({ ...settings, mark_read_on_scroll: enabled });
      }

      // Save to database
      const updatedSettings = await api.updateUserSettings({ mark_read_on_scroll: enabled });
      setSettings(updatedSettings);
      onSettingsChanged?.(updatedSettings);

      toast.success('Mark read on scroll preference saved');
    } catch (error) {
      console.error('Failed to save mark read on scroll setting:', error);
      toast.error('Failed to save preference');

      // Revert setting if save failed
      if (settings?.mark_read_on_scroll !== undefined) {
        setSettings({ ...settings, mark_read_on_scroll: !enabled });
      }
    }
  };

  const handleHideReadItemsChange = async (enabled: boolean) => {
    try {
      // Update local state immediately for better UX
      if (settings) {
        setSettings({ ...settings, hide_read_items: enabled });
      }

      // Save to database
      const updatedSettings = await api.updateUserSettings({ hide_read_items: enabled });
      setSettings(updatedSettings);
      onSettingsChanged?.(updatedSettings);

      toast.success('Hide read items preference saved');
    } catch (error) {
      console.error('Failed to save hide read items setting:', error);
      toast.error('Failed to save preference');

      // Revert setting if save failed
      if (settings?.hide_read_items !== undefined) {
        setSettings({ ...settings, hide_read_items: !enabled });
      }
    }
  };

  const getThemeIcon = (themeValue: string) => {
    switch (themeValue) {
      case 'light': return <Sun className="h-4 w-4" />;
      case 'dark': return <Moon className="h-4 w-4" />;
      default: return <Monitor className="h-4 w-4" />;
    }
  };

  const getThemeLabel = (themeValue: string) => {
    switch (themeValue) {
      case 'light': return 'Light';
      case 'dark': return 'Dark';
      default: return 'System';
    }
  };

  const renderAppearanceSettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">Appearance</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Theme</label>
              <p className="text-sm text-muted-foreground">
                Choose your preferred theme
              </p>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="w-32">
                  {mounted ? (
                    <>
                      {getThemeIcon(theme || 'system')}
                      <span className="ml-2">{getThemeLabel(theme || 'system')}</span>
                    </>
                  ) : (
                    <>
                      <Monitor className="h-4 w-4" />
                      <span className="ml-2">System</span>
                    </>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleThemeChange('light')}>
                  <Sun className="h-4 w-4 mr-2" />
                  Light
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleThemeChange('dark')}>
                  <Moon className="h-4 w-4 mr-2" />
                  Dark
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleThemeChange('system')}>
                  <Monitor className="h-4 w-4 mr-2" />
                  System
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </div>
  );

  const renderBehaviorSettings = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">Behavior</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Mark Read on Scroll</label>
              <p className="text-sm text-muted-foreground">
                Automatically mark articles as read when scrolled out of view
              </p>
            </div>
            <Switch
              checked={settings?.mark_read_on_scroll ?? true}
              onCheckedChange={handleMarkReadOnScrollChange}
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Hide Read Items</label>
              <p className="text-sm text-muted-foreground">
                Hide items that were already read when loading. Items marked as read during browsing remain visible (dimmed).
              </p>
            </div>
            <Switch
              checked={settings?.hide_read_items ?? false}
              onCheckedChange={handleHideReadItemsChange}
            />
          </div>
        </div>
      </div>
    </div>
  );

  const renderSettingsContent = () => {
    switch (selectedCategory) {
      case 'appearance':
        return renderAppearanceSettings();
      case 'behavior':
        return renderBehaviorSettings();
      default:
        return <div>Select a settings category</div>;
    }
  };

  return (
    <div className="h-[calc(100vh-4rem)] overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <div></div>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          
          {/* Settings Navigation */}
          <div className="mb-8">
            <nav className="flex space-x-1 bg-muted/50 p-1 rounded-lg w-fit">
              {settingsCategories.map((category) => {
                const Icon = category.icon;
                return (
                  <button
                    key={category.id}
                    onClick={() => onCategoryChange(category.id)}
                    className={`flex items-center px-4 py-2 text-sm rounded-md transition-colors ${
                      selectedCategory === category.id
                        ? 'bg-background text-foreground shadow-sm'
                        : 'hover:bg-background/50 text-muted-foreground'
                    }`}
                  >
                    <Icon className="h-4 w-4 mr-2" />
                    {category.label}
                  </button>
                );
              })}
            </nav>
          </div>
          
          {/* Settings Content */}
          {renderSettingsContent()}
        </div>
      </div>
    </div>
  );
}
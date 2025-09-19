import { Folder, MoreHorizontal, Plus, Settings } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface FeedMenuProps {
  onAddFeed: () => void;
  onAddCategory: () => void;
  onManageCategories: () => void;
}

export function FeedMenu({
  onAddFeed,
  onAddCategory,
  onManageCategories,
}: FeedMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuItem onClick={onAddFeed}>
          <Plus className="h-4 w-4 mr-2" />
          Add Feed
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={onAddCategory}>
          <Folder className="h-4 w-4 mr-2" />
          Add Category
        </DropdownMenuItem>
        <DropdownMenuItem onClick={onManageCategories}>
          <Settings className="h-4 w-4 mr-2" />
          Manage Categories
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
} 
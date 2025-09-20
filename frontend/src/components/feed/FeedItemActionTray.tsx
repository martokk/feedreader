import { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Placement = "top-right" | "top-left" | "bottom-right" | "bottom-left";

const placementClass: Record<Placement, string> = {
  "top-right": "top-2 right-2",
  "top-left": "top-2 left-2",
  "bottom-right": "bottom-2 right-2",
  "bottom-left": "bottom-2 left-2",
};

export interface FeedItemActionTrayProps {
  children: ReactNode;
  className?: string;
  placement?: Placement;
}

export default function FeedItemActionTray({
  children,
  className,
  placement = "top-right",
}: FeedItemActionTrayProps) {
  return (
    <div
      className={cn(
        // positioning
        "absolute z-10",
        placementClass[placement],
        // visible on small screens by default; hover-revealed from md and up
        "opacity-100 pointer-events-auto md:opacity-0 md:pointer-events-none md:translate-y-1",
        "transition-opacity transition-transform duration-150",
        "md:group-hover:opacity-100 md:group-hover:pointer-events-auto md:group-hover:translate-y-0",
        "md:group-focus-within:opacity-100 md:group-focus-within:pointer-events-auto md:group-focus-within:translate-y-0",
        className
      )}
    >
      <div className="flex items-center gap-1 rounded-md border border-border bg-background/80 px-1.5 py-1 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/60">
        {children}
      </div>
    </div>
  );
}
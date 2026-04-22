import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-neutral-200",
        className
      )}
    />
  );
}

// Fund card skeleton matching the actual card layout
export function FundCardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4 space-y-3">
      {/* Header: logo + name + type */}
      <div className="flex items-center gap-3">
        <Skeleton className="w-10 h-10 rounded-lg shrink-0" />
        <div className="flex-1 min-w-0 space-y-1.5">
          <Skeleton className="h-3 w-3/4" />
          <Skeleton className="h-2 w-1/2" />
        </div>
        <Skeleton className="h-5 w-14 rounded-full" />
      </div>

      {/* Sparkline area */}
      <Skeleton className="h-10 w-full rounded" />

      {/* Stats row */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-4 w-20" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-5 w-12 rounded" />
          <Skeleton className="h-5 w-12 rounded" />
          <Skeleton className="h-5 w-12 rounded" />
        </div>
      </div>

      {/* Breakdown bar */}
      <Skeleton className="h-1.5 w-full rounded-full" />
    </div>
  );
}

// Category card skeleton
export function CategoryCardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <Skeleton className="h-6 w-24" />
      <div className="flex gap-2">
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-12" />
      </div>
    </div>
  );
}

// Fun list skeleton
export function FunListSkeleton() {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-20" />
      </div>
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-3 p-2 rounded-lg">
            <Skeleton className="w-6 h-6 rounded" />
            <Skeleton className="h-3 flex-1" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}

// Stat card skeleton
export function StatCardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4 space-y-2">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-6 w-32" />
      <Skeleton className="h-3 w-16" />
    </div>
  );
}

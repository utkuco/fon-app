import { Skeleton } from "@/components/ui/skeleton";

export default function HoldingsLoading() {
  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header skeleton */}
      <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 h-16 flex items-center gap-3">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-8 flex-1 max-w-xs" />
          <div className="flex gap-2">
            <Skeleton className="h-8 w-8 rounded-lg" />
            <Skeleton className="h-8 w-8 rounded-lg" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Page header */}
        <div className="space-y-1">
          <Skeleton className="h-7 w-60" />
          <Skeleton className="h-4 w-80" />
        </div>

        {/* Holdings table skeleton */}
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <div className="p-4 border-b border-neutral-100">
            <Skeleton className="h-5 w-32" />
          </div>
          <div className="divide-y divide-neutral-100">
            {[...Array(12)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-4">
                <Skeleton className="w-8 h-8 rounded" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-2.5 w-1/2" />
                </div>
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-12" />
              </div>
            ))}
          </div>
        </div>

        {/* Pagination */}
        <div className="flex justify-center gap-2 py-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-8 w-8 rounded" />
          ))}
        </div>
      </main>
    </div>
  );
}

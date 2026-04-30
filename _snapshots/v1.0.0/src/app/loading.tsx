import { Logo } from "@/components/Logo";
import { Skeleton } from "@/components/ui/skeleton";

export default function GlobalLoading() {
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

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Category cards skeleton — 8 type pills */}
        <div className="flex gap-3 overflow-hidden">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-20 w-28 rounded-xl shrink-0" />
          ))}
        </div>

        {/* Divider */}
        <Skeleton className="h-px w-full" />

        {/* Fun lists skeleton — 2 column grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>

        {/* Divider */}
        <Skeleton className="h-px w-full" />

        {/* Filter pills */}
        <div className="flex gap-2">
          {[...Array(9)].map((_, i) => (
            <Skeleton key={i} className="h-7 w-14 rounded-full" />
          ))}
        </div>

        {/* Range sliders */}
        <div className="flex gap-4">
          <Skeleton className="h-12 flex-1 rounded-lg" />
          <Skeleton className="h-12 flex-1 rounded-lg" />
        </div>

        {/* Fund cards skeleton — first page of 50 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-xl" />
          ))}
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

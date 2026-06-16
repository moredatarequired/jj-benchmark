import Link from "next/link";
import { ArrowLeft, Filter, Search } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export function TasksPageSkeleton() {
  return (
    <div className="container mx-auto px-4 sm:px-8 lg:px-12 py-8 max-w-screen-2xl h-[100dvh] flex flex-col overflow-hidden">
      <div className="mb-6 space-y-4 shrink-0">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="group inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
            <span>Back to Leaderboard</span>
          </Link>
        </div>
        <div>
          <h1 className="text-4xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-b from-foreground to-foreground/50">
            Task
          </h1>
          <p className="text-muted-foreground max-w-2xl leading-relaxed mt-2">
            Detailed breakdown of individual task performance across different models.
          </p>
        </div>
      </div>

      {/* Filter bar skeleton */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6 p-4 rounded-xl border border-border bg-card/50 backdrop-blur-sm shadow-sm shrink-0">
        <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-secondary/50 text-muted-foreground shrink-0">
            <Filter className="w-4 h-4" />
          </div>
          <div className="flex-1 grid grid-cols-2 sm:flex sm:flex-wrap gap-2 sm:gap-4">
            <Skeleton className="h-9 w-full sm:w-[140px]" />
            <Skeleton className="h-9 w-full sm:w-[180px]" />
          </div>
        </div>
        <div className="relative w-full md:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Skeleton className="h-9 w-full" />
        </div>
      </div>

      {/* Table skeleton */}
      <div className="rounded-xl border border-border bg-card/50 backdrop-blur-sm shadow-sm overflow-hidden flex flex-col max-h-full">
        <div className="border-b border-border bg-secondary/30 px-3 sm:px-6 py-3">
          <Skeleton className="h-4 w-40" />
        </div>
        <div className="divide-y divide-border/30">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center gap-4 px-3 sm:px-6 py-3 even:bg-secondary/5"
            >
              <Skeleton className="h-4 w-[180px] md:w-[260px] shrink-0" />
              <div className="flex-1 flex items-center gap-2 overflow-hidden">
                <Skeleton className="h-6 w-16 shrink-0" />
                <Skeleton className="h-6 w-16 shrink-0" />
                <Skeleton className="h-6 w-16 shrink-0" />
                <Skeleton className="h-6 w-16 shrink-0 hidden sm:block" />
                <Skeleton className="h-6 w-16 shrink-0 hidden md:block" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

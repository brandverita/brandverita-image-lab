import { useEffect, useState } from "react";

import { supabase } from "@/integrations/supabase/client";
import type { Tables } from "@/integrations/supabase/types";

type Job = Pick<
  Tables<"generation_jobs">,
  "id" | "workflow_id" | "status" | "width" | "height" | "created_at" | "result_url"
>;

export function RecentJobs({ userId, refreshKey }: { userId: string | null; refreshKey: number }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!userId) {
      setJobs([]);
      return;
    }
    let active = true;
    setLoading(true);
    supabase
      .from("generation_jobs")
      .select("id, workflow_id, status, width, height, created_at, result_url")
      .order("created_at", { ascending: false })
      .limit(10)
      .then(({ data, error: queryError }) => {
        if (!active) return;
        if (queryError) setError(queryError.message);
        else {
          setError(null);
          setJobs(data ?? []);
        }
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [userId, refreshKey]);

  if (!userId) {
    return (
      <p className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
        Sign in to load your recent test jobs from the database.
      </p>
    );
  }

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
      >
        Could not load recent jobs: {error}
      </p>
    );
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading recent jobs…</p>;
  }

  if (jobs.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
        No test generations yet. Create your first image from the form.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Your ten most recent generation jobs</caption>
        <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">Job ID</th>
            <th scope="col" className="px-4 py-2 font-medium">Workflow</th>
            <th scope="col" className="px-4 py-2 font-medium">Status</th>
            <th scope="col" className="px-4 py-2 font-medium">Size</th>
            <th scope="col" className="px-4 py-2 font-medium">Created</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="border-t border-border">
              <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                {job.id.slice(0, 8)}
              </td>
              <td className="px-4 py-2 text-muted-foreground">{job.workflow_id}</td>
              <td className="px-4 py-2 text-foreground">{job.status}</td>
              <td className="px-4 py-2 text-muted-foreground">
                {job.width && job.height ? `${job.width} × ${job.height}` : "—"}
              </td>
              <td className="px-4 py-2 text-muted-foreground">
                {new Date(job.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

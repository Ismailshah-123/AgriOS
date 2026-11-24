import { TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

/** Shown when a route throws while rendering. Never displays the stack trace. */
export function RouteErrorPage() {
  return (
    <div className="grid min-h-dvh place-items-center bg-surface px-4">
      <EmptyState
        icon={TriangleAlert}
        title="Something went wrong"
        description="This page could not be displayed. Reload to try again."
        action={<Button onClick={() => window.location.reload()}>Reload page</Button>}
      />
    </div>
  );
}

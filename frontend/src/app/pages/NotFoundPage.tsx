import { MapPinOff } from "lucide-react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";

export function NotFoundPage() {
  return (
    <Card>
      <EmptyState
        icon={MapPinOff}
        title="Page not found"
        description="The page you are looking for does not exist or has moved."
        action={
          <Button asChild variant="secondary">
            <Link to="/">Go to Overview</Link>
          </Button>
        }
      />
    </Card>
  );
}

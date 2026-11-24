import { History } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SystemStatusCard } from "@/features/system/SystemStatusCard";

/**
 * Phase 1 shell. Scan statistics, the upload workflow and model status are added
 * in later phases from real API data; nothing on this page is simulated.
 */
export function CropDoctorDashboardPage() {
  return (
    <>
      <PageHeader
        title="Crop Doctor"
        description="Upload a crop photo to check for signs of disease. Results show how certain the system is, and uncertain cases are flagged for expert review."
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Analysis history</CardTitle>
          </CardHeader>
          <EmptyState
            icon={History}
            title="No analyses yet"
            description="Image analysis is not available yet. Your past analyses will be listed here once uploads are enabled."
          />
        </Card>
        <SystemStatusCard />
      </div>
    </>
  );
}

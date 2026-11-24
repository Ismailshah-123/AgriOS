import type { RouteObject } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { PublicOnly, RequireAuth } from "@/features/auth/guards";
import { OverviewPage } from "@/features/dashboard/OverviewPage";
import { MODULES } from "./modules";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RouteErrorPage } from "./pages/RouteErrorPage";

/*
 * Route-level code splitting (DESIGN.md section 13): only the shell and the Overview are
 * in the initial bundle; each page (and the form/validation libraries it uses) loads on
 * first visit.
 */
const page = (load: () => Promise<{ Component: React.ComponentType }>) => ({ lazy: load });

const plannedRoutes: RouteObject[] = MODULES.filter((m) => m.status === "planned").map((m) => ({
  path: m.path.slice(1),
  lazy: async () => {
    const { PlannedModulePage } = await import("@/features/modules/PlannedModulePage");
    return { Component: () => <PlannedModulePage moduleKey={m.key} /> };
  },
}));

export const routes: RouteObject[] = [
  {
    errorElement: <RouteErrorPage />,
    children: [
      {
        element: <PublicOnly />,
        children: [
          {
            path: "/login",
            ...page(async () => ({
              Component: (await import("@/features/auth/pages/LoginPage")).LoginPage,
            })),
          },
          {
            path: "/register",
            ...page(async () => ({
              Component: (await import("@/features/auth/pages/RegisterPage")).RegisterPage,
            })),
          },
        ],
      },
      {
        element: <RequireAuth />,
        children: [
          {
            path: "/",
            element: <AppShell />,
            children: [
              { index: true, element: <OverviewPage /> },
              {
                path: "farms",
                ...page(async () => ({
                  Component: (await import("@/features/farms/FarmsPage")).FarmsPage,
                })),
              },
              {
                path: "farms/:farmId",
                ...page(async () => ({
                  Component: (await import("@/features/farms/FarmDetailPage")).FarmDetailPage,
                })),
              },
              {
                path: "fields",
                ...page(async () => ({
                  Component: (await import("@/features/fields/FieldsPage")).FieldsPage,
                })),
              },
              {
                path: "crop-cycles",
                ...page(async () => ({
                  Component: (await import("@/features/crop-cycles/CropCyclesPage")).CropCyclesPage,
                })),
              },
              {
                path: "crop-doctor",
                ...page(async () => ({
                  Component: (await import("@/features/crop-health/pages/CropDoctorPage"))
                    .CropDoctorPage,
                })),
              },
              {
                path: "crop-doctor/new",
                ...page(async () => ({
                  Component: (await import("@/features/crop-health/pages/NewAssessmentPage"))
                    .NewAssessmentPage,
                })),
              },
              {
                path: "crop-doctor/cases",
                ...page(async () => ({
                  Component: (await import("@/features/crop-health/pages/CaseHistoryPage"))
                    .CaseHistoryPage,
                })),
              },
              {
                path: "crop-doctor/cases/:caseId",
                ...page(async () => ({
                  Component: (await import("@/features/crop-health/pages/CaseDetailPage"))
                    .CaseDetailPage,
                })),
              },
              {
                path: "settings",
                ...page(async () => ({
                  Component: (await import("@/features/settings/SettingsPage")).SettingsPage,
                })),
              },
              {
                path: "soil",
                ...page(async () => ({
                  Component: (await import("@/features/soil/SoilPage")).SoilPage,
                })),
              },
              {
                path: "weather",
                ...page(async () => ({
                  Component: (await import("@/features/weather/WeatherPage")).WeatherPage,
                })),
              },
              {
                path: "irrigation",
                ...page(async () => ({
                  Component: (await import("@/features/irrigation/IrrigationPage")).IrrigationPage,
                })),
              },
              {
                path: "knowledge",
                ...page(async () => ({
                  Component: (await import("@/features/knowledge/KnowledgePage")).KnowledgePage,
                })),
              },
              {
                path: "nutrients",
                ...page(async () => ({
                  Component: (await import("@/features/nutrients/NutrientsPage")).NutrientsPage,
                })),
              },
              {
                path: "economics",
                ...page(async () => ({
                  Component: (await import("@/features/economics/EconomicsPage")).EconomicsPage,
                })),
              },
              {
                path: "review",
                ...page(async () => ({
                  Component: (await import("@/features/review/ReviewPages")).ReviewQueuePage,
                })),
              },
              {
                path: "review/cases/:caseId",
                ...page(async () => ({
                  Component: (await import("@/features/review/ReviewPages")).ReviewCasePage,
                })),
              },
              {
                path: "agents",
                ...page(async () => ({
                  Component: (await import("@/features/agents/AgentsPage")).AgentsPage,
                })),
              },
              ...plannedRoutes,
              { path: "*", element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
];

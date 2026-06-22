import { useUiShell } from "@/lib/use-ui-shell";
import { LegacyLayout } from "@/legacy/LegacyLayout";
import { LegacyRoutes } from "@/legacy/LegacyRoutes";
import { ArrLayout } from "@/arr/components/ArrLayout";
import { ArrRoutes } from "@/arr/routes/ArrRoutes";

export function AppShell() {
  const { isArr } = useUiShell();

  if (isArr) {
    return (
      <ArrLayout>
        <ArrRoutes />
      </ArrLayout>
    );
  }

  return (
    <LegacyLayout>
      <LegacyRoutes />
    </LegacyLayout>
  );
}

import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { CreateCommandScheduleExpiryBlock } from "@/components/CreateCommandScheduleExpiryBlock";

export function LidarrUpdateAllCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { lidarrUpdateAllForm, setLidarrUpdateAllForm } = wizard;
  return (
    <>
      <p className="text-sm text-muted-foreground">
        Display name is fixed as{" "}
        <span className="font-medium text-foreground">Lidarr Maintenance - Artist Refresh</span>.
      </p>
      <CreateCommandScheduleExpiryBlock
        idPrefix="create-lidarr-ua"
        scheduleOverride={lidarrUpdateAllForm.schedule_override}
        onScheduleOverrideChange={(v) =>
          setLidarrUpdateAllForm((prev) => ({ ...prev, schedule_override: v }))
        }
        scheduleCron={lidarrUpdateAllForm.schedule_cron}
        onScheduleCronChange={(v) =>
          setLidarrUpdateAllForm((prev) => ({ ...prev, schedule_cron: v }))
        }
        enabled={lidarrUpdateAllForm.enabled}
        onEnabledChange={(v) => setLidarrUpdateAllForm((prev) => ({ ...prev, enabled: v }))}
        expiresAtEnabled={false}
        onExpiresAtEnabledChange={() => {}}
        expiresAt=""
        onExpiresAtChange={() => {}}
        expiresAtDeletePlaylist={false}
        onExpiresAtDeletePlaylistChange={() => {}}
        showExpiration={false}
      />
    </>
  );
}

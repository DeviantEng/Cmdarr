import { useNavigate } from "react-router-dom";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { CreatePlaylistSyncDialog } from "@/components/CreatePlaylistSyncDialog";

export function ArrAddCommandPage() {
  const navigate = useNavigate();

  return (
    <div>
      <ArrPageHeader
        title="Add New"
        description="Choose a command type and configure how it should run."
      />
      <div className="arr-page-panels">
        <CreatePlaylistSyncDialog
          embedded
          open
          onOpenChange={(open) => {
            if (!open) navigate("/commands");
          }}
          onSuccess={() => navigate("/commands")}
        />
      </div>
    </div>
  );
}

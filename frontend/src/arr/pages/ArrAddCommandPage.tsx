import { useNavigate, Link } from "react-router-dom";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { Button } from "@/components/ui/button";
import { CreatePlaylistSyncDialog } from "@/components/CreatePlaylistSyncDialog";

export function ArrAddCommandPage() {
  const navigate = useNavigate();

  return (
    <div>
      <ArrPageHeader
        title="Add New"
        description="Pick a command type, then configure how it runs."
        actions={
          <Button variant="secondary" size="sm" asChild>
            <Link to="/commands">Back to commands</Link>
          </Button>
        }
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

import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { ps } from "../shared";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";

export function ExternalPlaylistCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { formData, setFormData, validation } = wizard;
  return (
    <>
      {/* Playlist URL */}
      <div className="space-y-2">
        <Label>{ps.playlistUrlLabel}</Label>
        <div className="relative">
          <Input
            type="url"
            placeholder={ps.playlistUrlPlaceholder}
            value={formData.playlist_url}
            onChange={(e) =>
              setFormData((prev) => ({
                ...prev,
                playlist_url: e.target.value,
              }))
            }
            className={
              validation.error ? "border-destructive" : validation.isValid ? "border-green-500" : ""
            }
          />
          {validation.isValidating && (
            <Loader2 className="absolute right-3 top-3 h-4 w-4 animate-spin" />
          )}
          {validation.isValid && (
            <CheckCircle2 className="absolute right-3 top-3 h-4 w-4 text-green-500" />
          )}
          {validation.error && (
            <AlertCircle className="absolute right-3 top-3 h-4 w-4 text-destructive" />
          )}
        </div>
        {validation.error && <p className="text-sm text-destructive">{validation.error}</p>}
        {validation.metadata && (
          <div className="rounded-lg border bg-muted p-3">
            <p className="font-medium">{validation.metadata.name}</p>
            {validation.metadata.description && (
              <p className="text-sm text-muted-foreground">{validation.metadata.description}</p>
            )}
            <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
              {validation.metadata.track_count && (
                <span>{validation.metadata.track_count} tracks</span>
              )}
              {validation.metadata.source && (
                <Badge variant="outline">{validation.metadata.source}</Badge>
              )}
            </div>
          </div>
        )}
        <p className="text-xs text-muted-foreground">{ps.publicSourcesHelp}</p>
      </div>
    </>
  );
}

import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Loader2, CheckCircle2, AlertCircle, Music, Globe } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from 'sonner'

type PlaylistType = 'listenbrainz' | 'other'

interface CreatePlaylistSyncDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

interface PlaylistValidation {
  isValidating: boolean
  isValid: boolean
  error: string
  metadata: {
    name?: string
    description?: string
    track_count?: number
    source?: string
  } | null
}

export function CreatePlaylistSyncDialog({
  open,
  onOpenChange,
  onSuccess,
}: CreatePlaylistSyncDialogProps) {
  const [step, setStep] = useState<'type' | 'form'>('type')
  const [playlistType, setPlaylistType] = useState<PlaylistType>('other')
  const [formData, setFormData] = useState({
    playlist_url: '',
    playlist_types: [] as string[],
    target: 'plex',
    sync_mode: 'full',
    schedule_hours: 12,
    enabled: true,
    weekly_exploration_keep: 3,
    weekly_jams_keep: 3,
    daily_jams_keep: 3,
    cleanup_enabled: true,
    enable_artist_discovery: false,
  })
  const [validation, setValidation] = useState<PlaylistValidation>({
    isValidating: false,
    isValid: false,
    error: '',
    metadata: null,
  })
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Reset form when dialog closes
  useEffect(() => {
    if (!open) {
      setStep('type')
      setFormData({
        playlist_url: '',
        playlist_types: [],
        target: 'plex',
        sync_mode: 'full',
        schedule_hours: 12,
        enabled: true,
        weekly_exploration_keep: 3,
        weekly_jams_keep: 3,
        daily_jams_keep: 3,
        cleanup_enabled: true,
        enable_artist_discovery: false,
      })
      setValidation({
        isValidating: false,
        isValid: false,
        error: '',
        metadata: null,
      })
    }
  }, [open])

  // Debounced URL validation
  useEffect(() => {
    if (playlistType !== 'other' || !formData.playlist_url) {
      setValidation({
        isValidating: false,
        isValid: false,
        error: '',
        metadata: null,
      })
      return
    }

    const timeoutId = setTimeout(() => {
      validatePlaylistUrl()
    }, 500)

    return () => clearTimeout(timeoutId)
  }, [formData.playlist_url, playlistType])

  const validatePlaylistUrl = async () => {
    if (!formData.playlist_url) return

    setValidation((prev) => ({ ...prev, isValidating: true, error: '' }))

    try {
      const response = await api.request<{
        valid: boolean
        error?: string
        metadata?: any
      }>(`/api/commands/playlist-sync/validate-url?url=${encodeURIComponent(formData.playlist_url)}`)

      setValidation({
        isValidating: false,
        isValid: response.valid,
        error: response.error || '',
        metadata: response.metadata || null,
      })
    } catch (error) {
      setValidation({
        isValidating: false,
        isValid: false,
        error: 'Failed to validate URL',
        metadata: null,
      })
    }
  }

  const handleSelectType = (type: PlaylistType) => {
    setPlaylistType(type)
    setStep('form')
    if (type === 'listenbrainz') {
      setFormData((prev) => ({
        ...prev,
        playlist_types: ['weekly_exploration'],
      }))
    }
  }

  const handleTogglePlaylistType = (type: string) => {
    setFormData((prev) => ({
      ...prev,
      playlist_types: prev.playlist_types.includes(type)
        ? prev.playlist_types.filter((t) => t !== type)
        : [...prev.playlist_types, type],
    }))
  }

  const canSubmit = () => {
    if (playlistType === 'listenbrainz') {
      return formData.playlist_types.length > 0
    } else {
      return validation.isValid
    }
  }

  const handleSubmit = async () => {
    if (!canSubmit()) {
      toast.error('Please complete all required fields')
      return
    }

    setIsSubmitting(true)

    try {
      const payload = {
        ...formData,
        playlist_type: playlistType,
      }

      const response = await api.request<{ message: string }>(
        '/api/commands/playlist-sync/create',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      )

      toast.success(response.message || 'Playlist sync command created successfully')
      onSuccess()
      onOpenChange(false)
    } catch (error: any) {
      toast.error(error.message || 'Failed to create playlist sync command')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {step === 'type' ? 'Create Playlist Sync' : `Configure ${playlistType === 'listenbrainz' ? 'ListenBrainz' : 'External'} Playlist`}
          </DialogTitle>
          <DialogDescription>
            {step === 'type'
              ? 'Choose the type of playlist sync to create'
              : 'Configure your playlist sync settings'}
          </DialogDescription>
        </DialogHeader>

        {step === 'type' ? (
          <div className="grid gap-4 py-4">
            {/* ListenBrainz Option */}
            <button
              onClick={() => handleSelectType('listenbrainz')}
              className="flex items-start gap-4 rounded-lg border-2 border-border p-4 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900">
                <Music className="h-6 w-6 text-purple-600 dark:text-purple-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">ListenBrainz Curated</h3>
                <p className="text-sm text-muted-foreground">
                  Sync Weekly Exploration, Weekly Jams, or Daily Jams playlists
                </p>
              </div>
            </button>

            {/* External Playlist Option */}
            <button
              onClick={() => handleSelectType('other')}
              className="flex items-start gap-4 rounded-lg border-2 border-border p-4 text-left transition-colors hover:border-primary hover:bg-accent"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-100 dark:bg-green-900">
                <Globe className="h-6 w-6 text-green-600 dark:text-green-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">External Playlist</h3>
                <p className="text-sm text-muted-foreground">
                  Sync public playlists from Spotify, Deezer, or other sources
                </p>
              </div>
            </button>
          </div>
        ) : (
          <div className="space-y-4 py-4">
            {playlistType === 'listenbrainz' ? (
              <>
                {/* Playlist Types */}
                <div className="space-y-2">
                  <Label>Playlist Types</Label>
                  <div className="space-y-2">
                    {['weekly_exploration', 'weekly_jams', 'daily_jams'].map((type) => (
                      <label key={type} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={formData.playlist_types.includes(type)}
                          onChange={() => handleTogglePlaylistType(type)}
                          className="rounded border-gray-300"
                        />
                        <span className="text-sm">
                          {type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Retention Settings */}
                <div className="space-y-2">
                  <Label>Retention Settings</Label>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <Label className="text-xs">Weekly Exploration</Label>
                      <Input
                        type="number"
                        min="1"
                        max="10"
                        value={formData.weekly_exploration_keep}
                        onChange={(e) =>
                          setFormData((prev) => ({
                            ...prev,
                            weekly_exploration_keep: parseInt(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Weekly Jams</Label>
                      <Input
                        type="number"
                        min="1"
                        max="10"
                        value={formData.weekly_jams_keep}
                        onChange={(e) =>
                          setFormData((prev) => ({
                            ...prev,
                            weekly_jams_keep: parseInt(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Daily Jams</Label>
                      <Input
                        type="number"
                        min="1"
                        max="10"
                        value={formData.daily_jams_keep}
                        onChange={(e) =>
                          setFormData((prev) => ({
                            ...prev,
                            daily_jams_keep: parseInt(e.target.value),
                          }))
                        }
                      />
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Number of playlists to keep for each type (older ones will be deleted)
                  </p>
                </div>

                {/* Cleanup Toggle */}
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={formData.cleanup_enabled}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        cleanup_enabled: e.target.checked,
                      }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable playlist cleanup (delete old playlists)</span>
                </label>
              </>
            ) : (
              <>
                {/* Playlist URL */}
                <div className="space-y-2">
                  <Label>Playlist URL</Label>
                  <div className="relative">
                    <Input
                      type="url"
                      placeholder="https://open.spotify.com/playlist/..."
                      value={formData.playlist_url}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          playlist_url: e.target.value,
                        }))
                      }
                      className={
                        validation.error
                          ? 'border-destructive'
                          : validation.isValid
                          ? 'border-green-500'
                          : ''
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
                  {validation.error && (
                    <p className="text-sm text-destructive">{validation.error}</p>
                  )}
                  {validation.metadata && (
                    <div className="rounded-lg border bg-muted p-3">
                      <p className="font-medium">{validation.metadata.name}</p>
                      {validation.metadata.description && (
                        <p className="text-sm text-muted-foreground">
                          {validation.metadata.description}
                        </p>
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
                  <p className="text-xs text-muted-foreground">
                    Supports Spotify, Deezer public playlists
                  </p>
                </div>
              </>
            )}

            {/* Common Settings */}
            <div className="space-y-2">
              <Label>Target</Label>
              <Select
                value={formData.target}
                onValueChange={(value) =>
                  setFormData((prev) => ({ ...prev, target: value }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="plex">Plex</SelectItem>
                  <SelectItem value="jellyfin">Jellyfin</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Sync Mode</Label>
              <Select
                value={formData.sync_mode}
                onValueChange={(value) =>
                  setFormData((prev) => ({ ...prev, sync_mode: value }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full">Full Sync</SelectItem>
                  <SelectItem value="append">Append Only</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Schedule (Hours)</Label>
              <Input
                type="number"
                min="1"
                max="168"
                value={formData.schedule_hours}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    schedule_hours: parseInt(e.target.value),
                  }))
                }
              />
              <p className="text-xs text-muted-foreground">
                Sync every {formData.schedule_hours} hours
              </p>
            </div>

            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    enabled: e.target.checked,
                  }))
                }
                className="rounded border-gray-300"
              />
              <span className="text-sm">Enable immediately after creation</span>
            </label>

            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.enable_artist_discovery}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    enable_artist_discovery: e.target.checked,
                  }))
                }
                className="rounded border-gray-300"
              />
              <span className="text-sm">Enable artist discovery for this playlist</span>
            </label>
          </div>
        )}

        <DialogFooter>
          {step === 'form' && (
            <Button variant="outline" onClick={() => setStep('type')}>
              Back
            </Button>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          {step === 'form' && (
            <Button onClick={handleSubmit} disabled={!canSubmit() || isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Playlist Sync'
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}



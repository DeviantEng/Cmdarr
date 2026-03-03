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
import { Loader2, CheckCircle2, AlertCircle, Music, Globe, Sun } from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

type PlaylistType = 'listenbrainz' | 'other' | 'daylist'

const DEFAULT_DAYLIST_TIME_PERIODS: Record<string, { start: number; end: number }> = {
  Dawn: { start: 3, end: 5 },
  'Early Morning': { start: 6, end: 8 },
  Morning: { start: 9, end: 11 },
  Afternoon: { start: 12, end: 15 },
  Evening: { start: 16, end: 18 },
  Night: { start: 19, end: 21 },
  'Late Night': { start: 22, end: 2 },
}

function hoursFromRange(start: number, end: number): number[] {
  if (end >= start) return Array.from({ length: end - start + 1 }, (_, i) => start + i)
  return [...Array.from({ length: 24 - start }, (_, i) => start + i), ...Array.from({ length: end + 1 }, (_, i) => i)]
}

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
  const [daylistExists, setDaylistExists] = useState(false)
  const [plexAccounts, setPlexAccounts] = useState<{ id: string; name: string }[]>([])
  const [daylistForm, setDaylistForm] = useState({
    plex_history_account_id: '',
    schedule_minute: 0,
    enabled: true,
    exclude_played_days: 4,
    history_lookback_days: 30,
    max_tracks: 50,
    sonic_similar_limit: 8,
    sonic_similarity_limit: 50,
    sonic_similarity_distance: 1.0,
    historical_ratio: 0.3,
    timezone: '',
    time_periods: { ...DEFAULT_DAYLIST_TIME_PERIODS } as Record<string, { start: number; end: number }>,
  })

  // Fetch daylist exists and plex accounts when dialog opens
  useEffect(() => {
    if (!open) return
    api.request<{ exists: boolean }>('/api/commands/daylist/exists').then((r) => setDaylistExists(r.exists))
    api.request<{ accounts: { id: string; name: string }[] }>('/api/commands/plex-accounts')
      .then((r) => setPlexAccounts(r.accounts || []))
      .catch(() => setPlexAccounts([]))
  }, [open])

  // Reset form when dialog closes
  useEffect(() => {
    if (!open) {
      setStep('type')
      setPlaylistType('other')
      setFormData({
        playlist_url: '',
        playlist_types: [],
        target: 'plex',
        sync_mode: 'full',
        enabled: true,
        weekly_exploration_keep: 3,
        weekly_jams_keep: 3,
        daily_jams_keep: 3,
        cleanup_enabled: true,
        enable_artist_discovery: false,
      })
      setDaylistForm({
        plex_history_account_id: '',
        schedule_minute: 0,
        enabled: true,
        exclude_played_days: 4,
        history_lookback_days: 30,
        max_tracks: 50,
        sonic_similar_limit: 8,
        sonic_similarity_limit: 50,
        sonic_similarity_distance: 1.0,
        historical_ratio: 0.3,
        timezone: '',
        time_periods: { ...DEFAULT_DAYLIST_TIME_PERIODS },
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
    if (type === 'daylist' && daylistExists) return
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
    }
    if (playlistType === 'daylist') {
      return !!daylistForm.plex_history_account_id
    }
    return validation.isValid
  }

  const handleSubmit = async () => {
    if (!canSubmit()) {
      toast.error('Please complete all required fields')
      return
    }

    setIsSubmitting(true)

    try {
      if (playlistType === 'daylist') {
        const time_periods: Record<string, number[]> = {}
        for (const [period, { start, end }] of Object.entries(daylistForm.time_periods)) {
          time_periods[period] = hoursFromRange(start, end)
        }
        const response = await api.request<{ message: string }>(
          '/api/commands/daylist/create',
          {
            method: 'POST',
            body: JSON.stringify({
              plex_history_account_id: daylistForm.plex_history_account_id,
              schedule_minute: daylistForm.schedule_minute,
              enabled: daylistForm.enabled,
              exclude_played_days: daylistForm.exclude_played_days,
              history_lookback_days: daylistForm.history_lookback_days,
              max_tracks: daylistForm.max_tracks,
              sonic_similar_limit: daylistForm.sonic_similar_limit,
              sonic_similarity_limit: daylistForm.sonic_similarity_limit,
              sonic_similarity_distance: daylistForm.sonic_similarity_distance,
              historical_ratio: daylistForm.historical_ratio,
              timezone: daylistForm.timezone || undefined,
              time_periods,
            }),
          }
        )
        toast.success(response.message || 'Daylist command created successfully')
      } else {
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
      }
      onSuccess()
      onOpenChange(false)
    } catch (error: any) {
      toast.error(error.message || 'Failed to create command')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {step === 'type'
              ? 'Create New Command'
              : playlistType === 'daylist'
                ? 'Configure Daylist'
                : `Configure ${playlistType === 'listenbrainz' ? 'ListenBrainz' : 'External'} Playlist`}
          </DialogTitle>
          <DialogDescription>
            {step === 'type'
              ? 'Choose the type of command to create'
              : playlistType === 'daylist'
                ? 'Configure your daylist settings'
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

            {/* Daylist Option */}
            <button
              onClick={() => handleSelectType('daylist')}
              disabled={daylistExists}
              className={cn(
                'flex items-start gap-4 rounded-lg border-2 border-border p-4 text-left transition-colors',
                daylistExists
                  ? 'cursor-not-allowed opacity-50'
                  : 'hover:border-primary hover:bg-accent'
              )}
              title={daylistExists ? 'Daylist command already exists' : undefined}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900">
                <Sun className="h-6 w-6 text-amber-600 dark:text-amber-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold">Daylist</h3>
                <p className="text-sm text-muted-foreground">
                  Time-of-day playlists from Plex listening history and Sonic Analysis. Plex only. Inspired by Meloday.
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
            ) : playlistType === 'daylist' ? (
              <>
                {/* Plex Account */}
                <div className="space-y-2">
                  <Label>Plex Account (play history source)</Label>
                  <Select
                    value={daylistForm.plex_history_account_id}
                    onValueChange={(v) =>
                      setDaylistForm((prev) => ({ ...prev, plex_history_account_id: v }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select Plex account" />
                    </SelectTrigger>
                    <SelectContent>
                      {plexAccounts.map((acc) => (
                        <SelectItem key={acc.id} value={acc.id}>
                          {acc.name || `Account ${acc.id}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Plex Home managed users. Daylist uses this account&apos;s play history.
                  </p>
                </div>

                {/* Minute of hour */}
                <div className="space-y-2">
                  <Label>Run at minute of hour</Label>
                  <Select
                    value={String(daylistForm.schedule_minute)}
                    onValueChange={(v) =>
                      setDaylistForm((prev) => ({ ...prev, schedule_minute: parseInt(v, 10) }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[0, 15, 30, 45].map((m) => (
                        <SelectItem key={m} value={String(m)}>
                          :{m.toString().padStart(2, '0')} (e.g. 1:00, 1:15, 1:30, 1:45)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Daylist runs hourly. Runs only when the day period changes (Dawn, Morning, etc.).
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Exclude played (days)</Label>
                    <Input
                      type="number"
                      min={1}
                      max={14}
                      value={daylistForm.exclude_played_days}
                      onChange={(e) =>
                        setDaylistForm((prev) => ({
                          ...prev,
                          exclude_played_days: Math.max(1, Math.min(14, parseInt(e.target.value, 10) || 4)),
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground">Skip tracks played in last N days</p>
                  </div>
                  <div className="space-y-2">
                    <Label>History lookback (days)</Label>
                    <Input
                      type="number"
                      min={7}
                      max={90}
                      value={daylistForm.history_lookback_days}
                      onChange={(e) =>
                        setDaylistForm((prev) => ({
                          ...prev,
                          history_lookback_days: Math.max(7, Math.min(90, parseInt(e.target.value, 10) || 30)),
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground">Days of play history to analyze</p>
                  </div>
                  <div className="space-y-2">
                    <Label>Max tracks</Label>
                    <Input
                      type="number"
                      min={20}
                      max={100}
                      value={daylistForm.max_tracks}
                      onChange={(e) =>
                        setDaylistForm((prev) => ({
                          ...prev,
                          max_tracks: Math.max(20, Math.min(100, parseInt(e.target.value, 10) || 50)),
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Sonically similar limit</Label>
                    <Input
                      type="number"
                      min={1}
                      max={20}
                      value={daylistForm.sonic_similar_limit}
                      onChange={(e) =>
                        setDaylistForm((prev) => ({
                          ...prev,
                          sonic_similar_limit: Math.max(1, Math.min(20, parseInt(e.target.value, 10) || 8)),
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground">Max similar tracks per seed</p>
                  </div>
                  <div className="space-y-2">
                    <Label>Sonically similar playlist limit</Label>
                    <Input
                      type="number"
                      min={10}
                      max={100}
                      value={daylistForm.sonic_similarity_limit}
                      onChange={(e) =>
                        setDaylistForm((prev) => ({
                          ...prev,
                          sonic_similarity_limit: Math.max(10, Math.min(100, parseInt(e.target.value, 10) || 50)),
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Sonically similar distance</Label>
                    <Input
                      type="number"
                      min={0.1}
                      max={2}
                      step={0.1}
                      value={daylistForm.sonic_similarity_distance}
                      onChange={(e) =>
                        setDaylistForm((prev) => ({
                          ...prev,
                          sonic_similarity_distance: Math.max(0.1, Math.min(2, parseFloat(e.target.value) || 1.0)),
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Historical ratio</Label>
                    <Input
                      type="number"
                      min={0.1}
                      max={0.8}
                      step={0.1}
                      value={daylistForm.historical_ratio}
                      onChange={(e) =>
                        setDaylistForm((prev) => ({
                          ...prev,
                          historical_ratio: Math.max(0.1, Math.min(0.8, parseFloat(e.target.value) || 0.3)),
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground">Share of tracks from history (0.1–0.8)</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Timezone (optional)</Label>
                  <Input
                    placeholder="e.g. America/New_York"
                    value={daylistForm.timezone}
                    onChange={(e) =>
                      setDaylistForm((prev) => ({ ...prev, timezone: e.target.value }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">Leave empty to use scheduler timezone</p>
                </div>

                <div className="space-y-2 rounded-lg border p-4">
                  <Label>Time periods (Start–End hour, 0–23)</Label>
                  <p className="text-xs text-muted-foreground mb-2">
                    When each period runs. Late Night wraps (e.g. 22–2 = 22,23,0,1,2).
                  </p>
                  <div className="grid gap-2">
                    {Object.entries(daylistForm.time_periods).map(([period, { start, end }]) => (
                      <div key={period} className="flex items-center gap-3">
                        <span className="w-28 text-sm">{period}</span>
                        <Input
                          type="number"
                          min={0}
                          max={23}
                          className="w-16"
                          value={start}
                          onChange={(e) => {
                            const v = Math.max(0, Math.min(23, parseInt(e.target.value, 10) || 0))
                            setDaylistForm((prev) => ({
                              ...prev,
                              time_periods: {
                                ...prev.time_periods,
                                [period]: { ...prev.time_periods[period], start: v },
                              },
                            }))
                          }}
                        />
                        <span className="text-muted-foreground">–</span>
                        <Input
                          type="number"
                          min={0}
                          max={23}
                          className="w-16"
                          value={end}
                          onChange={(e) => {
                            const v = Math.max(0, Math.min(23, parseInt(e.target.value, 10) || 0))
                            setDaylistForm((prev) => ({
                              ...prev,
                              time_periods: {
                                ...prev.time_periods,
                                [period]: { ...prev.time_periods[period], end: v },
                              },
                            }))
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={daylistForm.enabled}
                    onChange={(e) =>
                      setDaylistForm((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Enable immediately after creation</span>
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

            {/* Common Settings (hidden for daylist - has its own form) */}
            {playlistType !== 'daylist' && (
            <>
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

            <p className="text-sm text-muted-foreground">
              New commands use the global schedule (Config → Scheduler). You can override per-command after creation.
            </p>

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
            </>
            )}
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
              ) : playlistType === 'daylist' ? (
                'Create Daylist'
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



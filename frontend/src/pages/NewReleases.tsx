import { useState, useEffect, useCallback } from 'react'
import { Search, ExternalLink, Disc3, Loader2, Play, Database, EyeOff, RefreshCw, Ban } from 'lucide-react'
import { api } from '@/lib/api'
import type { NewReleasePendingItem } from '@/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'

export function NewReleasesPage() {
  const [loading, setLoading] = useState(false)
  const [pending, setPending] = useState<NewReleasePendingItem[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [suggestions, setSuggestions] = useState<{ artist_mbid: string; artist_name: string }[]>([])
  const [searching, setSearching] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [batchRunning, setBatchRunning] = useState(false)
  const [commandEnabled, setCommandEnabled] = useState(false)
  const [adHocAlbumTypes, setAdHocAlbumTypes] = useState<Set<string>>(new Set(['album']))

  const toggleAdHocAlbumType = (id: string) => {
    setAdHocAlbumTypes((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next.size ? next : new Set(['album'])
    })
  }

  const fetchCommandStatus = useCallback(async () => {
    try {
      const status = await api.getNewReleasesCommandStatus()
      setCommandEnabled(status.enabled)
    } catch {
      setCommandEnabled(false)
    }
  }, [])

  const fetchPending = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getPendingReleases({ status: 'pending', limit: 200 })
      setPending(data.items)
      setTotal(data.total)
    } catch (err: any) {
      const msg = err?.message || err?.details || 'Failed to load pending'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPending()
    fetchCommandStatus()
  }, [fetchPending, fetchCommandStatus])

  const handleClear = async (item: NewReleasePendingItem) => {
    try {
      await api.clearRelease(item.id)
      setPending((prev) => prev.filter((p) => p.id !== item.id))
      setTotal((t) => Math.max(0, t - 1))
      toast.success('Cleared – will reappear on rescan')
    } catch (err: any) {
      toast.error(err?.message || 'Clear failed')
    }
  }

  const handleRecheck = async (item: NewReleasePendingItem) => {
    try {
      const res = await api.recheckRelease(item.id)
      if (res.removed) {
        setPending((prev) => prev.filter((p) => p.id !== item.id))
        setTotal((t) => Math.max(0, t - 1))
        toast.success('Found in MusicBrainz, removed')
      } else {
        toast.info('Not found. New releases can take a few minutes to appear in MusicBrainz search—try again shortly.')
      }
    } catch (err: any) {
      toast.error(err?.message || 'Recheck failed')
    }
  }

  const handleClearAll = async () => {
    if (!confirm(`Clear all ${total} pending releases? They will reappear on next scan if still not in MusicBrainz.`)) {
      return
    }
    try {
      const res = await api.clearAllPendingReleases()
      setPending([])
      setTotal(0)
      toast.success(res.cleared != null ? `Cleared ${res.cleared} items` : 'Cleared all')
    } catch (err: any) {
      toast.error(err?.message || 'Clear all failed')
    }
  }

  const handleIgnore = async (item: NewReleasePendingItem) => {
    if (!confirm(`Ignore "${item.album_title}" by ${item.artist_name}? It won't reappear. Restore from Status if needed.`)) {
      return
    }
    try {
      await api.ignoreRelease(item.id)
      setPending((prev) => prev.filter((p) => p.id !== item.id))
      setTotal((t) => Math.max(0, t - 1))
      toast.success('Ignored')
    } catch (err: any) {
      toast.error(err?.message || 'Ignore failed')
    }
  }

  const handleRunBatch = async () => {
    setBatchRunning(true)
    setError(null)
    try {
      await api.runBatch()
      toast.success('Batch scan started')
      setTimeout(fetchPending, 5000)
    } catch (err: any) {
      toast.error(err?.message || 'Run batch failed')
    } finally {
      setBatchRunning(false)
    }
  }

  const handleSyncLidarr = async () => {
    setSyncing(true)
    try {
      const res = await api.syncLidarrArtists()
      toast.success(`Synced ${res.synced ?? 0} artists`)
    } catch (err: any) {
      toast.error(err?.message || 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => {
    if (searchQuery.length < 2) {
      setSuggestions([])
      return
    }
    const t = setTimeout(() => {
      api.getLidarrArtists(searchQuery, 15).then(
        (res) => setSuggestions(res.artists.map((a) => ({ artist_mbid: a.artist_mbid, artist_name: a.artist_name }))),
        () => setSuggestions([])
      )
    }, 200)
    return () => clearTimeout(t)
  }, [searchQuery])

  const handleScanArtist = async (artistMbid?: string, artistName?: string) => {
    if (!artistMbid && !artistName) return
    const artistLabel = artistName || artistMbid || ''
    setSearching(true)
    setError(null)
    const prevCount = total
    try {
      await api.scanArtist({
        artist_mbid: artistMbid,
        artist_name: artistName,
        album_types: adHocAlbumTypes.size ? Array.from(adHocAlbumTypes) : ['album'],
      })
      toast.info(`Scanning ${artistLabel}...`)
      setSearchQuery('')
      setSuggestions([])
      setTimeout(async () => {
        const data = await api.getPendingReleases({ status: 'pending', limit: 200 })
        setPending(data.items)
        setTotal(data.total)
        if (data.total === prevCount) {
          toast.info(`No new releases found for ${artistLabel}`, { duration: 10000 })
        }
      }, 6000)
    } catch (err: any) {
      toast.error(err?.message || 'Scan failed')
    } finally {
      setSearching(false)
    }
  }

  const openHarmony = (url: string) => {
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">New Releases Discovery</h1>
        <p className="mt-2 text-muted-foreground">
          Find releases on Spotify from your Lidarr artists that are missing from MusicBrainz.
        </p>
      </div>

      {/* Actions: Run batch, Sync Lidarr, Search artist */}
      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
          <CardDescription>
            Run the next batch of artists, or search and scan a single artist. Sync Lidarr artists first for autocomplete.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={handleRunBatch}
              disabled={batchRunning || !commandEnabled}
              title={!commandEnabled ? 'Enable New Releases Discovery in Commands first' : undefined}
            >
              {batchRunning ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Run next batch
            </Button>
            <Button variant="outline" onClick={handleSyncLidarr} disabled={syncing}>
              {syncing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Database className="mr-2 h-4 w-4" />}
              Sync Lidarr artists
            </Button>
          </div>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-4">
              <span className="text-sm font-medium">Release types:</span>
              {(['album', 'ep', 'single', 'other'] as const).map((t) => (
                <label key={t} className="flex items-center gap-2 cursor-pointer text-sm">
                  <input
                    type="checkbox"
                    checked={adHocAlbumTypes.has(t)}
                    onChange={() => toggleAdHocAlbumType(t)}
                    className="rounded border-input"
                  />
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </label>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <div className="relative flex-1 min-w-[200px]">
                <Input
                placeholder="Search artist by name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && suggestions.length > 0) {
                    handleScanArtist(suggestions[0].artist_mbid, suggestions[0].artist_name)
                  }
                }}
              />
              {suggestions.length > 0 && (
                <ul className="absolute z-10 mt-1 w-full rounded-md border bg-popover py-1 shadow-md">
                  {suggestions.map((s) => (
                    <li key={s.artist_mbid}>
                      <button
                        type="button"
                        className="w-full px-3 py-2 text-left hover:bg-accent"
                        onClick={() => handleScanArtist(s.artist_mbid, s.artist_name)}
                      >
                        {s.artist_name}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              </div>
              <Button
              variant="secondary"
              onClick={() => {
                if (suggestions.length > 0) handleScanArtist(suggestions[0].artist_mbid, suggestions[0].artist_name)
              }}
              disabled={searching || suggestions.length === 0}
            >
              {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Scan artist
            </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Pending table */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <CardTitle>Pending Releases</CardTitle>
              <CardDescription>
                {total} items. Use links to open Lidarr, MusicBrainz, Spotify, or Add to MB (Harmony). Actions: Clear (reappears), Recheck (verify MB), Ignore (never show).
              </CardDescription>
            </div>
            {pending.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleClearAll}
                className="shrink-0"
              >
                Clear all
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : pending.length === 0 ? (
            <div className="flex min-h-[200px] items-center justify-center py-12">
              <div className="text-center text-muted-foreground">
                <Disc3 className="mx-auto h-12 w-12 opacity-50" />
                <p className="mt-2 font-medium">No pending releases</p>
                <p className="mt-1 text-sm">Run a batch or scan an artist to discover new releases.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {pending.map((item) => (
                <PendingRow
                  key={item.id}
                  item={item}
                  onClear={() => handleClear(item)}
                  onRecheck={() => handleRecheck(item)}
                  onIgnore={() => handleIgnore(item)}
                  onOpenHarmony={openHarmony}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function PendingRow({
  item,
  onClear,
  onRecheck,
  onIgnore,
  onOpenHarmony,
}: {
  item: NewReleasePendingItem
  onClear: () => void
  onRecheck: () => void
  onIgnore: () => void
  onOpenHarmony: (url: string) => void
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-muted/30 px-4 py-3">
      <div className="min-w-0 flex-1">
        <span className="font-medium">{item.artist_name}</span>
        <span className="mx-2 text-muted-foreground">—</span>
        <span>{item.album_title}</span>
        {item.album_type && (
          <span className="ml-2 text-xs text-muted-foreground capitalize">{item.album_type}</span>
        )}
        {item.release_date && (
          <span className="ml-2 text-sm text-muted-foreground">{item.release_date}</span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 shrink-0">
        {/* Links — open external pages */}
        <div className="flex items-center gap-1.5">
          {item.lidarr_artist_url && (
            <Button variant="outline" size="sm" asChild>
              <a href={item.lidarr_artist_url} target="_blank" rel="noopener noreferrer">
                Lidarr
              </a>
            </Button>
          )}
          {item.musicbrainz_artist_url && (
            <Button variant="outline" size="sm" asChild>
              <a href={item.musicbrainz_artist_url} target="_blank" rel="noopener noreferrer">
                MusicBrainz
              </a>
            </Button>
          )}
          {item.spotify_url && (
            <Button variant="outline" size="sm" asChild>
              <a href={item.spotify_url} target="_blank" rel="noopener noreferrer">
                Spotify
              </a>
            </Button>
          )}
          {item.harmony_url && (
            <Button variant="outline" size="sm" onClick={() => onOpenHarmony(item.harmony_url!)}>
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
              Add to MB
            </Button>
          )}
        </div>
        {/* Actions — icon-only square buttons with tooltips */}
        <div className="flex items-center gap-1 border-l pl-2 border-border/60">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={onClear}
            title="Clear for now, will reappear on rescan"
          >
            <EyeOff className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={onRecheck}
            title="Verify in MusicBrainz and remove if found"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
            onClick={onIgnore}
            title="Never show again"
          >
            <Ban className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

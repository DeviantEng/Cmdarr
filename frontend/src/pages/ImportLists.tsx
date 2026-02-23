import { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import type { ImportListMetrics } from '@/lib/types'
import { toast } from 'sonner'
import { Copy, Music, Disc } from 'lucide-react'

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatStatus(status: string): string {
  return status.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'fresh') return 'default'
  if (status === 'stale') return 'secondary'
  if (status === 'very_stale' || status === 'empty') return 'destructive'
  return 'outline'
}

export function ImportListsPage() {
  const [metrics, setMetrics] = useState<ImportListMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadMetrics()
  }, [])

  const loadMetrics = async () => {
    try {
      setError(null)
      const data = await api.getImportListMetrics()
      setMetrics(data)
    } catch (err: any) {
      const msg = err?.message || 'Failed to load import list metrics'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url)
      toast.success('URL copied to clipboard')
    } catch {
      toast.error('Failed to copy URL')
    }
  }

  const baseUrl = typeof window !== 'undefined' ? window.location.origin : ''
  const lastfmUrl = `${baseUrl}/import_lists/discovery_lastfm`
  const playlistsyncUrl = `${baseUrl}/import_lists/discovery_playlistsync`

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Import Lists</h1>
          <p className="mt-2 text-muted-foreground">
            Available import list endpoints for Lidarr integration
          </p>
        </div>
        <div className="text-center text-muted-foreground py-12">Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Import Lists</h1>
          <p className="mt-2 text-muted-foreground">
            Available import list endpoints for Lidarr integration
          </p>
        </div>
        <Card className="border-destructive">
          <CardContent className="flex min-h-[200px] flex-col items-center justify-center gap-4 p-8">
            <p className="text-lg font-medium text-destructive">Failed to Load</p>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button onClick={loadMetrics}>Try Again</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Import Lists</h1>
        <p className="mt-2 text-muted-foreground">
          Available import list endpoints for Lidarr integration and music discovery automation.
        </p>
      </div>

      <div className="space-y-6">
        {/* Last.fm Discovery */}
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Music className="h-5 w-5" />
                Last.fm Discovery
              </h2>
              {metrics?.lastfm && (
                <Badge variant={getStatusVariant(metrics.lastfm.status)}>
                  {metrics.lastfm.exists ? formatStatus(metrics.lastfm.status) : 'Not Available'}
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground mb-4">
              Similar artists discovered via Last.fm and MusicBrainz fuzzy matching
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">Endpoint URL</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={lastfmUrl}
                  className="flex-1 px-3 py-2 bg-muted border rounded-md text-sm font-mono"
                />
                <Button variant="secondary" size="sm" onClick={() => copyToClipboard(lastfmUrl)}>
                  <Copy className="h-4 w-4 mr-1" />
                  Copy
                </Button>
              </div>
            </div>
            {metrics?.lastfm?.exists && (
              <div className="mt-4 p-4 bg-muted rounded-lg">
                <h4 className="text-sm font-medium mb-3">File Statistics</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-lg font-semibold">
                      {metrics.lastfm.entry_count.toLocaleString()}
                    </div>
                    <div className="text-xs text-muted-foreground">Artists</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold">
                      {formatFileSize(metrics.lastfm.file_size)}
                    </div>
                    <div className="text-xs text-muted-foreground">File Size</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold">{metrics.lastfm.age_human}</div>
                    <div className="text-xs text-muted-foreground">Last Updated</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold">
                      {formatStatus(metrics.lastfm.status)}
                    </div>
                    <div className="text-xs text-muted-foreground">Status</div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Playlist Sync Discovery */}
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Disc className="h-5 w-5" />
                Playlist Sync Discovery
              </h2>
              {metrics?.unified && (
                <Badge variant={getStatusVariant(metrics.unified.status)}>
                  {metrics.unified.exists ? formatStatus(metrics.unified.status) : 'Not Available'}
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground mb-4">
              Artists discovered from playlist sync operations (Spotify, ListenBrainz, etc.)
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">Endpoint URL</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={playlistsyncUrl}
                  className="flex-1 px-3 py-2 bg-muted border rounded-md text-sm font-mono"
                />
                <Button variant="secondary" size="sm" onClick={() => copyToClipboard(playlistsyncUrl)}>
                  <Copy className="h-4 w-4 mr-1" />
                  Copy
                </Button>
              </div>
            </div>
            {metrics?.unified?.exists && (
              <div className="mt-4 p-4 bg-muted rounded-lg">
                <h4 className="text-sm font-medium mb-3">File Statistics</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-lg font-semibold">
                      {metrics.unified.entry_count.toLocaleString()}
                    </div>
                    <div className="text-xs text-muted-foreground">Artists</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold">
                      {formatFileSize(metrics.unified.file_size)}
                    </div>
                    <div className="text-xs text-muted-foreground">File Size</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold">{metrics.unified.age_human}</div>
                    <div className="text-xs text-muted-foreground">Last Updated</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold">
                      {formatStatus(metrics.unified.status)}
                    </div>
                    <div className="text-xs text-muted-foreground">Status</div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Lidarr Integration Guide */}
      <Card className="border-blue-500/50 bg-blue-500/5">
        <CardContent className="p-6">
          <h3 className="text-lg font-semibold mb-4">Lidarr Integration Guide</h3>
          <p className="text-muted-foreground mb-4">To add Cmdarr import lists in Lidarr:</p>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-medium">
                1
              </span>
              <span>Go to <strong>Settings → Import Lists</strong></span>
            </div>
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-medium">
                2
              </span>
              <span>Click <strong>Add → Custom List</strong></span>
            </div>
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-medium">
                3
              </span>
              <span>Set <strong>URL</strong> to one of:</span>
            </div>
            <div className="ml-9 space-y-2">
              <div className="flex items-center gap-2">
                <code className="bg-muted px-2 py-1 rounded text-sm">{lastfmUrl}</code>
                <span className="text-sm text-muted-foreground">(Last.fm similar artists)</span>
              </div>
              <div className="flex items-center gap-2">
                <code className="bg-muted px-2 py-1 rounded text-sm">{playlistsyncUrl}</code>
                <span className="text-sm text-muted-foreground">(Playlist sync discovered artists)</span>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-medium">
                4
              </span>
              <span>Configure sync interval as desired (recommend 24-48 hours)</span>
            </div>
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-medium">
                5
              </span>
              <span>Save and test the configuration</span>
            </div>
          </div>
          <div className="mt-4 p-3 bg-muted rounded-md">
            <p className="text-sm">
              <strong>Pro tip:</strong> You can add multiple import lists for different discovery sources! Each provides unique recommendations based on different algorithms.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

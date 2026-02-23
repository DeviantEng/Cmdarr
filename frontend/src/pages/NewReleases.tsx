import { useState } from 'react'
import { Search, ExternalLink, Disc3, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { NewReleaseArtist, NewReleaseAlbum } from '@/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'

const ALBUM_TYPE_OPTIONS = [
  { id: 'album', label: 'Album' },
  { id: 'ep', label: 'EP' },
  { id: 'single', label: 'Single' },
  { id: 'other', label: 'Other (compilation, appears on)' },
] as const

export function NewReleasesPage() {
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<NewReleaseArtist[] | null>(null)
  const [summary, setSummary] = useState<{
    album_types: string[]
    artists_checked: number
    artists_with_releases: number
    total_lidarr_artists: number
    skipped_in_musicbrainz?: number
    skipped_by_type?: number
    skipped_live?: number
  } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [artistLimit, setArtistLimit] = useState('10')
  const [albumTypes, setAlbumTypes] = useState<Set<string>>(new Set(['album']))

  const toggleAlbumType = (id: string) => {
    setAlbumTypes((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleScan = async () => {
    setLoading(true)
    setError(null)
    setResults(null)
    setSummary(null)

    const limit = Math.max(1, Math.min(500, parseInt(artistLimit, 10) || 10))

    try {
      const data = await api.getNewReleases({
        artist_limit: limit,
        album_types: albumTypes.size ? Array.from(albumTypes) : ['album'],
      })
      setResults(data.results)
      setSummary({
        album_types: data.album_types,
        artists_checked: data.artists_checked,
        artists_with_releases: data.artists_with_releases,
        total_lidarr_artists: data.total_lidarr_artists,
        skipped_in_musicbrainz: data.skipped_in_musicbrainz,
        skipped_by_type: data.skipped_by_type,
        skipped_live: data.skipped_live,
      })
      if (data.results.length === 0) {
        toast.info(
          `No missing releases found among ${data.artists_checked} artists scanned.`
        )
      } else {
        toast.success(
          `Found ${data.artists_with_releases} artists with releases to add`
        )
      }
    } catch (err: any) {
      const msg = err?.message || err?.details || 'Scan failed'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const openHarmony = (harmonyUrl: string) => {
    window.open(harmonyUrl, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">New Releases Discovery</h1>
        <p className="mt-2 text-muted-foreground">
          Find releases on Spotify from your Lidarr artists that are missing from
          MusicBrainz. Add them via Harmony. Data cached 14 days.
        </p>
      </div>

      {/* Scan Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Scan for Missing Releases</CardTitle>
          <CardDescription>
            Searches Spotify for releases by Lidarr artists. Excludes releases
            already in MusicBrainz (1 MB call per artist). No time filter.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-6">
            <div className="space-y-2">
              <Label htmlFor="artist-limit">Max artists to scan</Label>
              <Input
                id="artist-limit"
                type="number"
                min={1}
                max={500}
                value={artistLimit}
                onChange={(e) => setArtistLimit(e.target.value)}
                className="w-24"
              />
            </div>
            <div className="space-y-2">
              <Label>Release types</Label>
              <div className="flex flex-wrap gap-4">
                {ALBUM_TYPE_OPTIONS.map((opt) => (
                  <label
                    key={opt.id}
                    className="flex items-center gap-2 cursor-pointer text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={albumTypes.has(opt.id)}
                      onChange={() => toggleAlbumType(opt.id)}
                      className="rounded border-input"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <Button onClick={handleScan} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Scanning...
              </>
            ) : (
              <>
                <Search className="mr-2 h-4 w-4" />
                Scan for Missing Releases
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Summary */}
      {summary && (
        <Card>
          <CardHeader>
            <CardTitle>Scan Summary</CardTitle>
            <CardDescription>
              Checked {summary.artists_checked} of {summary.total_lidarr_artists}{' '}
              Lidarr artists for releases not in MusicBrainz
              {summary.album_types.length > 0 &&
                ` (types: ${summary.album_types.join(', ')})`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-lg font-medium">
              {summary.artists_with_releases} artist
              {summary.artists_with_releases !== 1 ? 's' : ''} with releases to add
            </p>
            {(summary.skipped_in_musicbrainz !== undefined ||
              summary.skipped_by_type !== undefined ||
              summary.skipped_live !== undefined) && (
              <p className="text-sm text-muted-foreground">
                Filtered out: {summary.skipped_in_musicbrainz ?? 0} in MusicBrainz
                {summary.skipped_by_type
                  ? `, ${summary.skipped_by_type} by type filter`
                  : ''}
                {summary.skipped_live ? `, ${summary.skipped_live} live` : ''}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {results && results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Missing Releases</CardTitle>
            <CardDescription>
              Click &quot;Add to MusicBrainz&quot; to open Harmony with the album
              URL pre-filled.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {results.map((artist) => (
                <ArtistReleases
                  key={artist.artist_name + artist.lidarr_mbid}
                  artist={artist}
                  onOpenHarmony={openHarmony}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty state after scan */}
      {results && results.length === 0 && !error && (
        <Card>
          <CardContent className="flex min-h-[200px] items-center justify-center py-12">
            <div className="text-center text-muted-foreground">
              <Disc3 className="mx-auto h-12 w-12 opacity-50" />
              <p className="mt-2 font-medium">No missing releases found</p>
              <p className="mt-1 text-sm">
                Try different release types or more artists. Data is cached 14 days.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

const MB_ARTIST_BASE = 'https://musicbrainz.org/artist/'

function ArtistReleases({
  artist,
  onOpenHarmony,
}: {
  artist: NewReleaseArtist
  onOpenHarmony: (url: string) => void
}) {
  const mbArtistUrl = `${MB_ARTIST_BASE}${artist.lidarr_mbid}`

  return (
    <div className="rounded-lg border p-4">
      <h3 className="font-semibold">{artist.artist_name}</h3>
      <ul className="mt-3 space-y-2">
        {artist.albums.map((album) => (
          <AlbumRow
            key={album.spotify_url}
            album={album}
            artist={artist}
            mbArtistUrl={mbArtistUrl}
            onOpenHarmony={onOpenHarmony}
          />
        ))}
      </ul>
    </div>
  )
}

function AlbumRow({
  album,
  artist,
  mbArtistUrl,
  onOpenHarmony,
}: {
  album: NewReleaseAlbum
  artist: NewReleaseArtist
  mbArtistUrl: string
  onOpenHarmony: (url: string) => void
}) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded bg-muted/50 px-3 py-2">
      <div className="min-w-0 flex-1">
        <span className="font-medium">{album.name}</span>
        {album.album_type && (
          <span className="ml-2 text-xs text-muted-foreground capitalize">
            {album.album_type}
          </span>
        )}
        <span className="ml-2 text-sm text-muted-foreground">
          {album.release_date}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2 shrink-0">
        {artist.lidarr_artist_url && (
          <Button
            variant="outline"
            size="sm"
            asChild
          >
            <a
              href={artist.lidarr_artist_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Lidarr
            </a>
          </Button>
        )}
        <Button variant="outline" size="sm" asChild>
          <a
            href={mbArtistUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            MusicBrainz
          </a>
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onOpenHarmony(album.harmony_url)}
        >
          <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
          Add to MusicBrainz
        </Button>
      </div>
    </li>
  )
}

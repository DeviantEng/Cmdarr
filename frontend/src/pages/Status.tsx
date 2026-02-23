import { useState, useEffect } from 'react'
import { Activity, CheckCircle2, XCircle, Clock, Server } from 'lucide-react'
import { api } from '@/lib/api'
import type { StatusInfo } from '@/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'

export function StatusPage() {
  const [status, setStatus] = useState<StatusInfo | null>(null)
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const loadStatus = async () => {
    try {
      const [statusData, healthData] = await Promise.all([
        api.getStatus(),
        api.healthCheck(),
      ])
      setStatus(statusData)
      setHealth(healthData)
    } catch (error) {
      toast.error('Failed to load status')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    
    const parts = []
    if (days > 0) parts.push(`${days}d`)
    if (hours > 0) parts.push(`${hours}h`)
    if (minutes > 0) parts.push(`${minutes}m`)
    
    return parts.join(' ') || '<1m'
  }

  if (loading) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Status</h1>
          <p className="mt-2 text-muted-foreground">
            System status and health information
          </p>
        </div>
        <div className="text-center text-muted-foreground">Loading status...</div>
      </div>
    )
  }

  const isHealthy = health?.status === 'healthy'

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">Status</h1>
        <p className="mt-2 text-muted-foreground">
          System status and health information
        </p>
      </div>

      {/* Overall Health */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>System Health</CardTitle>
              <CardDescription>Overall system status</CardDescription>
            </div>
            <div>
              {isHealthy ? (
                <Badge variant="default" className="flex items-center gap-1">
                  <CheckCircle2 className="h-4 w-4" />
                  Healthy
                </Badge>
              ) : (
                <Badge variant="destructive" className="flex items-center gap-1">
                  <XCircle className="h-4 w-4" />
                  Unhealthy
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{health?.message}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Last checked: {health?.timestamp ? new Date(health.timestamp).toLocaleString() : 'N/A'}
          </p>
        </CardContent>
      </Card>

      {/* System Information */}
      {status && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Application</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{status.app_name}</div>
              <p className="text-xs text-muted-foreground">Version {status.version}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Uptime</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatUptime(status.uptime_seconds)}</div>
              <p className="text-xs text-muted-foreground">Running smoothly</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Database</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold capitalize">{status.database_status}</div>
              <p className="text-xs text-muted-foreground">
                {status.database_status === 'connected' ? 'Operating normally' : 'Check connection'}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Configuration</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold capitalize">{status.configuration_status}</div>
              <p className="text-xs text-muted-foreground">
                {status.configuration_status === 'valid' ? 'All set' : 'Needs attention'}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* API Endpoints */}
      <Card>
        <CardHeader>
          <CardTitle>API Endpoints</CardTitle>
          <CardDescription>Available API endpoints</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <div className="font-medium">Health Check</div>
                <div className="text-sm text-muted-foreground">/health</div>
              </div>
              <Badge variant="outline">GET</Badge>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <div className="font-medium">Commands API</div>
                <div className="text-sm text-muted-foreground">/api/commands</div>
              </div>
              <Badge variant="outline">REST</Badge>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <div className="font-medium">Configuration API</div>
                <div className="text-sm text-muted-foreground">/api/config</div>
              </div>
              <Badge variant="outline">REST</Badge>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <div className="font-medium">WebSocket</div>
                <div className="text-sm text-muted-foreground">/ws</div>
              </div>
              <Badge variant="outline">WS</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

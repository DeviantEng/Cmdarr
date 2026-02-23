import { useState, useEffect } from 'react'
import { LayoutGrid, List, Play, Pencil, Trash2, MoreVertical, Plus, Filter, Search } from 'lucide-react'
import { api } from '@/lib/api'
import { wsClient } from '@/lib/websocket'
import type { CommandConfig } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { CreatePlaylistSyncDialog } from '@/components/CreatePlaylistSyncDialog'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

type ViewMode = 'card' | 'list'
type SortField = 'name' | 'last_run' | 'status'
type SortDirection = 'asc' | 'desc'

export function CommandsPage() {
  const [commands, setCommands] = useState<CommandConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('card')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [sortField] = useState<SortField>('name')
  const [sortDirection] = useState<SortDirection>('asc')
  const [showNewCommandDialog, setShowNewCommandDialog] = useState(false)
  const [editingCommand, setEditingCommand] = useState<CommandConfig | null>(null)

  useEffect(() => {
    loadCommands()
    
    // Connect to WebSocket for real-time updates (non-blocking)
    try {
      wsClient.connect()
      const unsubscribe = wsClient.subscribe((message) => {
        if (message.type === 'command_update' || message.type === 'execution_update') {
          loadCommands() // Refresh commands on updates
        }
      })

      return () => {
        try {
          unsubscribe()
        } catch (e) {
          console.warn('Error unsubscribing from WebSocket:', e)
        }
      }
    } catch (e) {
      console.warn('WebSocket connection failed, continuing without real-time updates:', e)
    }
  }, [])

  const loadCommands = async () => {
    try {
      setError(null)
      console.log('Loading commands...')
      const data = await api.getCommands()
      console.log('Commands loaded:', data)
      // Ensure we always have an array
      setCommands(Array.isArray(data) ? data : [])
    } catch (error: any) {
      const errorMsg = error?.message || 'Failed to load commands'
      setError(errorMsg)
      toast.error(errorMsg)
      console.error('Error loading commands:', error)
      setCommands([]) // Ensure commands is always an array
    } finally {
      setLoading(false)
    }
  }

  const handleExecute = async (commandName: string) => {
    try {
      await api.executeCommand(commandName, { triggered_by: 'manual' })
      toast.success(`Command "${commandName}" started`)
      loadCommands()
    } catch (error) {
      toast.error(`Failed to execute command`)
      console.error(error)
    }
  }

  const handleToggleEnabled = async (command: CommandConfig) => {
    try {
      await api.updateCommand(command.command_name, { enabled: !command.enabled })
      toast.success(`Command ${command.enabled ? 'disabled' : 'enabled'}`)
      loadCommands()
    } catch (error) {
      toast.error('Failed to update command')
      console.error(error)
    }
  }

  const handleEdit = (command: CommandConfig) => {
    setEditingCommand(command)
  }

  const handleDelete = async (commandName: string) => {
    if (!confirm(`Are you sure you want to delete the command "${commandName}"?`)) {
      return
    }
    toast.info('Delete functionality coming soon')
  }

  // Filter and sort commands (defensive check to ensure commands is an array)
  const safeCommands = Array.isArray(commands) ? commands : []
  const filteredCommands = safeCommands
    .filter((cmd) => {
      // Search filter
      if (searchQuery && !cmd.display_name.toLowerCase().includes(searchQuery.toLowerCase()) &&
          !cmd.command_name.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false
      }
      // Status filter
      if (statusFilter === 'enabled' && !cmd.enabled) return false
      if (statusFilter === 'disabled' && cmd.enabled) return false
      // Type filter
      if (typeFilter !== 'all' && cmd.command_type !== typeFilter) return false
      return true
    })
    .sort((a, b) => {
      let comparison = 0
      switch (sortField) {
        case 'name':
          comparison = a.display_name.localeCompare(b.display_name)
          break
        case 'last_run':
          comparison = (a.last_run || '').localeCompare(b.last_run || '')
          break
        case 'status':
          comparison = Number(b.enabled) - Number(a.enabled)
          break
      }
      return sortDirection === 'asc' ? comparison : -comparison
    })

  const commandTypes = ['all', ...Array.from(new Set(safeCommands.map(c => c.command_type).filter(Boolean)))] as string[]
  const activeFilterCount = [statusFilter !== 'all', typeFilter !== 'all', searchQuery !== ''].filter(Boolean).length

  if (loading) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Commands</h1>
          <p className="mt-2 text-muted-foreground">
            Manage and monitor your Cmdarr commands
          </p>
        </div>
        <div className="text-center text-muted-foreground">Loading commands...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Commands</h1>
          <p className="mt-2 text-muted-foreground">
            Manage and monitor your Cmdarr commands
          </p>
        </div>
        <Card className="border-destructive">
          <CardContent className="flex min-h-[200px] flex-col items-center justify-center gap-4 p-8">
            <p className="text-lg font-medium text-destructive">Failed to Load Commands</p>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button onClick={loadCommands}>Try Again</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">Commands</h1>
        <p className="mt-2 text-muted-foreground">
          Manage and monitor your Cmdarr commands
        </p>
      </div>

      {/* Controls Row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        {/* Left Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* View Toggle */}
          <div className="flex items-center rounded-lg bg-muted p-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setViewMode('card')}
              className={cn(viewMode === 'card' && 'bg-background shadow-sm')}
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setViewMode('list')}
              className={cn(viewMode === 'list' && 'bg-background shadow-sm')}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>

          {/* Search */}
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search commands..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>

          {/* Filters Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Filter className="mr-2 h-4 w-4" />
                Filter
                {activeFilterCount > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {activeFilterCount}
                  </Badge>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-64">
              <div className="p-2">
                <div className="mb-3">
                  <label className="mb-1.5 block text-sm font-medium">Status</label>
                  <Select value={statusFilter} onValueChange={(v: any) => setStatusFilter(v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="enabled">Enabled</SelectItem>
                      <SelectItem value="disabled">Disabled</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="mb-3">
                  <label className="mb-1.5 block text-sm font-medium">Type</label>
                  <Select value={typeFilter} onValueChange={setTypeFilter}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {commandTypes.map((type) => (
                        <SelectItem key={type} value={type}>
                          {type === 'all' ? 'All' : type}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => {
                    setStatusFilter('all')
                    setTypeFilter('all')
                    setSearchQuery('')
                  }}
                >
                  Clear Filters
                </Button>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Right Controls */}
        <Button onClick={() => setShowNewCommandDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Command
        </Button>
      </div>

      {/* Commands Display */}
      {filteredCommands.length === 0 ? (
        <Card>
          <CardContent className="flex min-h-[400px] flex-col items-center justify-center gap-4 py-12">
            <div className="text-center">
              <h3 className="text-xl font-semibold">
                {safeCommands.length === 0 ? 'No Commands Yet' : 'No Commands Match Filters'}
              </h3>
              <p className="mt-2 text-muted-foreground">
                {safeCommands.length === 0 
                  ? 'Get started by creating your first command' 
                  : 'Try adjusting your filters to see more commands'}
              </p>
            </div>
            {safeCommands.length === 0 && (
              <Button size="lg" onClick={() => setShowNewCommandDialog(true)}>
                <Plus className="mr-2 h-5 w-5" />
                Create Your First Command
              </Button>
            )}
          </CardContent>
        </Card>
      ) : viewMode === 'card' ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredCommands.map((command) => (
            <Card key={command.id} className="flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="text-base">{command.display_name}</CardTitle>
                    {command.description && (
                      <CardDescription className="mt-1 text-xs">{command.description}</CardDescription>
                    )}
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleExecute(command.command_name)}>
                        <Play className="mr-2 h-4 w-4" />
                        Run Now
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleEdit(command)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => handleToggleEnabled(command)}>
                        {command.enabled ? 'Disable' : 'Enable'}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => handleDelete(command.command_name)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
                <div className="flex items-center gap-2">
                  <Badge variant={command.enabled ? 'default' : 'secondary'}>
                    {command.enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                  {command.command_type && (
                    <Badge variant="outline" className="text-xs">
                      {command.command_type || 'unknown'}
                    </Badge>
                  )}
                </div>
                {command.last_run && (
                  <div className="text-xs text-muted-foreground">
                    Last run: {new Date(command.last_run).toLocaleString()}
                  </div>
                )}
                {command.last_success !== null && (
                  <div className="text-xs">
                    Status:{' '}
                    <span className={command.last_success ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                      {command.last_success ? 'Success' : 'Failed'}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium">Name</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Type</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Last Run</th>
                  <th className="px-4 py-3 text-right text-sm font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredCommands.map((command) => (
                  <tr key={command.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3">
                      <div>
                        <div className="font-medium">{command.display_name}</div>
                        {command.description && (
                          <div className="text-xs text-muted-foreground">{command.description}</div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={command.enabled ? 'default' : 'secondary'} className="text-xs">
                        {command.enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {command.command_type && (
                        <Badge variant="outline" className="text-xs">
                          {command.command_type}
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {command.last_run ? new Date(command.last_run).toLocaleString() : 'Never'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleExecute(command.command_name)}>
                            <Play className="mr-2 h-4 w-4" />
                            Run Now
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleEdit(command)}>
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => handleToggleEnabled(command)}>
                            {command.enabled ? 'Disable' : 'Enable'}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => handleDelete(command.command_name)}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* New Command Dialog */}
      <CreatePlaylistSyncDialog
        open={showNewCommandDialog}
        onOpenChange={setShowNewCommandDialog}
        onSuccess={loadCommands}
      />

      {/* Edit Command Dialog */}
      <Dialog open={!!editingCommand} onOpenChange={(open) => !open && setEditingCommand(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Command: {editingCommand?.display_name}</DialogTitle>
            <DialogDescription>
              Configure command settings and schedule
            </DialogDescription>
          </DialogHeader>
          {editingCommand && (
            <div className="space-y-4 py-4">
              <div className="grid gap-4">
                {/* Display Name */}
                <div className="space-y-2">
                  <Label>Display Name</Label>
                  <Input value={editingCommand.display_name} disabled />
                </div>

                {/* Description */}
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input value={editingCommand.description || ''} disabled />
                </div>

                {/* Enabled Status */}
                <div className="flex items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <Label>Enabled</Label>
                    <div className="text-sm text-muted-foreground">
                      Command is currently {editingCommand.enabled ? 'enabled' : 'disabled'}
                    </div>
                  </div>
                  <Badge variant={editingCommand.enabled ? 'default' : 'secondary'}>
                    {editingCommand.enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </div>

                {/* Schedule */}
                {editingCommand.schedule_hours && (
                  <div className="space-y-2">
                    <Label>Schedule (Hours)</Label>
                    <Input value={editingCommand.schedule_hours} disabled />
                    <p className="text-xs text-muted-foreground">
                      Runs every {editingCommand.schedule_hours} hours
                    </p>
                  </div>
                )}

                {/* Last Run */}
                {editingCommand.last_run && (
                  <div className="space-y-2">
                    <Label>Last Run</Label>
                    <Input value={new Date(editingCommand.last_run).toLocaleString()} disabled />
                  </div>
                )}

                {/* Last Status */}
                {editingCommand.last_success !== null && (
                  <div className="space-y-2">
                    <Label>Last Status</Label>
                    <Badge variant={editingCommand.last_success ? 'default' : 'destructive'}>
                      {editingCommand.last_success ? 'Success' : 'Failed'}
                    </Badge>
                  </div>
                )}
              </div>

              <div className="rounded-lg bg-muted p-4">
                <p className="text-sm text-muted-foreground">
                  Full command editing functionality is under development. For now, use the toggle buttons to enable/disable commands, or modify settings in the backend configuration.
                </p>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setEditingCommand(null)}>
                  Close
                </Button>
                <Button onClick={() => handleToggleEnabled(editingCommand)}>
                  {editingCommand.enabled ? 'Disable' : 'Enable'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

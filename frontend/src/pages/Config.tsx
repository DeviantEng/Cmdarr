import { useState, useEffect } from 'react'
import { Save, RotateCcw, Check, AlertCircle, Search, Eye, EyeOff } from 'lucide-react'
import { api } from '@/lib/api'
import type { ConfigSetting } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

type CategoryGroup = {
  name: string
  icon: string
  categories: string[]
}

const categoryGroups: CategoryGroup[] = [
  { name: 'Application', icon: '⚙️', categories: ['logging', 'web', 'output', 'pretty'] },
  { name: 'Music Sources', icon: '🎵', categories: ['lastfm', 'listenbrainz', 'musicbrainz', 'spotify', 'deezer'] },
  { name: 'Media Servers', icon: '📺', categories: ['plex', 'jellyfin'] },
  { name: 'Music Management', icon: '🎯', categories: ['lidarr'] },
  { name: 'Performance', icon: '⚡', categories: ['cache', 'library', 'commands'] },
  { name: 'Scheduler', icon: '🕐', categories: ['scheduler'] },
]

export function ConfigPage() {
  const [settings, setSettings] = useState<ConfigSetting[]>([])
  const [loading, setLoading] = useState(true)
  const [changedSettings, setChangedSettings] = useState<Set<string>>(new Set())
  const [activeTab, setActiveTab] = useState('application')
  const [searchQuery, setSearchQuery] = useState('')
  const [testingConnectivity, setTestingConnectivity] = useState(false)
  const [connectivityResults, setConnectivityResults] = useState<any[]>([])
  const [showConnectivityDialog, setShowConnectivityDialog] = useState(false)
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set())
  const [revealedValues, setRevealedValues] = useState<Record<string, string>>({})

  useEffect(() => {
    loadConfiguration()
  }, [])

  const loadConfiguration = async () => {
    try {
      const configData = await api.getAllConfig()
      
      // Load detailed information for each setting
      const detailedSettings: ConfigSetting[] = []
      for (const [key, value] of Object.entries(configData)) {
        try {
          const details = await api.getConfigDetails(key)
          detailedSettings.push({
            ...details,
            value: value !== null && value !== undefined ? value : details.effective_value,
          })
        } catch (error) {
          console.warn(`Failed to load details for ${key}`)
        }
      }
      
      setSettings(detailedSettings)
    } catch (error) {
      toast.error('Failed to load configuration')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleSettingChange = (key: string, value: any) => {
    setSettings((prev) =>
      prev.map((s) => (s.key === key ? { ...s, value } : s))
    )
    setChangedSettings((prev) => new Set(prev).add(key))
    if (revealedKeys.has(key)) {
      setRevealedValues((prev) => ({ ...prev, [key]: value }))
    }
  }

  const handleRevealToggle = async (key: string) => {
    if (revealedKeys.has(key)) {
      setRevealedKeys((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
      setRevealedValues((prev) => {
        const { [key]: _, ...rest } = prev
        return rest
      })
      setSettings((prev) =>
        prev.map((s) => (s.key === key ? { ...s, value: '***' } : s))
      )
      setChangedSettings((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    } else {
      try {
        const details = await api.getConfigDetails(key, { reveal: true })
        const value = details.effective_value ?? ''
        setRevealedKeys((prev) => new Set(prev).add(key))
        setRevealedValues((prev) => ({ ...prev, [key]: String(value) }))
        handleSettingChange(key, value)
      } catch {
        toast.error('Failed to load value')
      }
    }
  }

  const getSensitiveDisplayValue = (setting: ConfigSetting) => {
    if (revealedKeys.has(setting.key)) {
      return revealedValues[setting.key] ?? setting.value ?? ''
    }
    return '***'
  }

  const handleSaveAll = async () => {
    const promises = Array.from(changedSettings).map(async (key) => {
      const setting = settings.find((s) => s.key === key)
      if (!setting) return
      
      try {
        await api.updateConfigSetting(key, {
          value: setting.value,
          data_type: setting.data_type,
        })
      } catch (error) {
        throw new Error(`Failed to save ${key}`)
      }
    })

    try {
      await Promise.all(promises)
      toast.success('Configuration saved successfully')
      setChangedSettings(new Set())
      loadConfiguration()
    } catch (error: any) {
      toast.error(error.message || 'Failed to save configuration')
    }
  }

  const handleReset = () => {
    loadConfiguration()
    setChangedSettings(new Set())
    toast.info('Changes reset')
  }

  const handleTestConnectivity = async () => {
    setTestingConnectivity(true)
    setShowConnectivityDialog(true)
    
    try {
      const results = await api.testConnectivity()
      setConnectivityResults(results.results)
      
      if (results.overall_success) {
        toast.success('All connectivity tests passed!')
      } else {
        toast.warning('Some connectivity tests failed')
      }
    } catch (error) {
      toast.error('Connectivity test failed')
      console.error(error)
    } finally {
      setTestingConnectivity(false)
    }
  }

  const filteredSettings = settings.filter((setting) => {
    if (searchQuery) {
      return (
        setting.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
        setting.description.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    return true
  })

  const getSettingsByCategory = (categories: string[]) => {
    return filteredSettings.filter((s) => categories.includes(s.category))
  }

  const renderSettingInput = (setting: ConfigSetting) => {
    switch (setting.data_type) {
      case 'bool':
        return (
          <Switch
            checked={setting.value === true || setting.value === 'true'}
            onCheckedChange={(checked) => handleSettingChange(setting.key, checked)}
          />
        )
      
      case 'int':
      case 'float':
        return (
          <Input
            type="number"
            step={setting.data_type === 'float' ? '0.1' : '1'}
            value={setting.value || ''}
            onChange={(e) => handleSettingChange(setting.key, e.target.value)}
            placeholder={setting.default_value}
            className={cn(setting.is_sensitive && 'font-mono')}
          />
        )
      
      case 'dropdown':
        return (
          <Select
            value={String(setting.value || setting.default_value)}
            onValueChange={(v) => handleSettingChange(setting.key, v)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(setting.options || []).map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )
      
      case 'json':
        return (
          <Textarea
            value={setting.value || ''}
            onChange={(e) => handleSettingChange(setting.key, e.target.value)}
            placeholder={setting.default_value}
            rows={3}
            className="font-mono text-xs"
          />
        )
      
      default:
        if (setting.is_sensitive) {
          const isRevealed = revealedKeys.has(setting.key)
          return (
            <div className="flex gap-2">
              <Input
                type={isRevealed ? 'text' : 'password'}
                value={getSensitiveDisplayValue(setting)}
                onChange={(e) => handleSettingChange(setting.key, e.target.value)}
                placeholder={setting.default_value}
                className="font-mono flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => handleRevealToggle(setting.key)}
                title={isRevealed ? 'Hide' : 'Show key'}
              >
                {isRevealed ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </Button>
            </div>
          )
        }
        return (
          <Input
            type="text"
            value={setting.value || ''}
            onChange={(e) => handleSettingChange(setting.key, e.target.value)}
            placeholder={setting.default_value}
          />
        )
    }
  }

  if (loading) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Configuration</h1>
          <p className="mt-2 text-muted-foreground">
            Manage your Cmdarr configuration settings
          </p>
        </div>
        <div className="text-center text-muted-foreground">Loading configuration...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">Configuration</h1>
        <p className="mt-2 text-muted-foreground">
          Manage your Cmdarr configuration settings
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search settings..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={handleTestConnectivity}
            disabled={testingConnectivity}
          >
            <Check className="mr-2 h-4 w-4" />
            Test Connectivity
          </Button>
          <Button
            variant="outline"
            onClick={handleReset}
            disabled={changedSettings.size === 0}
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            Reset
          </Button>
          <Button onClick={handleSaveAll} disabled={changedSettings.size === 0}>
            <Save className="mr-2 h-4 w-4" />
            Save Changes
            {changedSettings.size > 0 && (
              <Badge variant="secondary" className="ml-2">
                {changedSettings.size}
              </Badge>
            )}
          </Button>
        </div>
      </div>

      {/* Tabbed Configuration */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
          {categoryGroups.map((group) => (
            <TabsTrigger
              key={group.name.toLowerCase()}
              value={group.name.toLowerCase()}
              className="text-xs sm:text-sm"
            >
              <span className="mr-1 hidden sm:inline">{group.icon}</span>
              <span className="truncate">{group.name}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        {categoryGroups.map((group) => {
          const groupSettings = getSettingsByCategory(group.categories)
          
          return (
            <TabsContent
              key={group.name.toLowerCase()}
              value={group.name.toLowerCase()}
              className="space-y-4"
            >
              {groupSettings.length === 0 ? (
                <Card className="p-8">
                  <p className="text-center text-muted-foreground">
                    No settings found in this category
                  </p>
                </Card>
              ) : (
                <div className="grid gap-4">
                  {groupSettings.map((setting) => (
                    <Card key={setting.key} className="p-4">
                      <div className="grid gap-3 sm:grid-cols-[1fr,300px] sm:gap-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <Label htmlFor={setting.key} className="text-sm font-medium">
                              {setting.key}
                            </Label>
                            {setting.is_required && (
                              <Badge variant="destructive" className="text-xs">
                                Required
                              </Badge>
                            )}
                            {setting.is_sensitive && (
                              <Badge variant="secondary" className="text-xs">
                                Sensitive
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {setting.description || 'No description available'}
                          </p>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>Category: {setting.category}</span>
                            <span>•</span>
                            <span>Type: {setting.data_type}</span>
                          </div>
                        </div>
                        <div className="flex items-start">
                          {renderSettingInput(setting)}
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>
          )
        })}
      </Tabs>

      {/* Connectivity Test Dialog */}
      <Dialog open={showConnectivityDialog} onOpenChange={setShowConnectivityDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Connectivity Test Results</DialogTitle>
            <DialogDescription>
              {testingConnectivity ? 'Testing connections...' : 'Test complete'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {connectivityResults.map((result, idx) => (
              <div
                key={idx}
                className={cn(
                  'rounded-lg border p-3',
                  result.status === 'success' && 'border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950',
                  result.status === 'warning' && 'border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950',
                  result.status === 'error' && 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950'
                )}
              >
                <div className="flex items-start gap-2">
                  <div className="mt-0.5">
                    {result.status === 'success' && <Check className="h-5 w-5 text-green-600" />}
                    {result.status === 'warning' && <AlertCircle className="h-5 w-5 text-yellow-600" />}
                    {result.status === 'error' && <AlertCircle className="h-5 w-5 text-red-600" />}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">{result.service}</div>
                    <div className="text-sm text-muted-foreground">{result.message}</div>
                    {result.error && (
                      <div className="mt-1 text-xs text-destructive">{result.error}</div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

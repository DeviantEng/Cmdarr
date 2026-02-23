import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'

export function ImportListsPage() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Import Lists</h1>
          <p className="mt-2 text-muted-foreground">
            Manage your music import lists
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Import List
        </Button>
      </div>

      {/* Content */}
      <Card>
        <CardContent className="flex min-h-[400px] items-center justify-center">
          <div className="text-center">
            <p className="text-lg font-medium">Import Lists Coming Soon</p>
            <p className="mt-2 text-sm text-muted-foreground">
              This feature is under development and will be available in a future update.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog'
import { Badge } from './ui/badge'
import { Sparkles } from 'lucide-react'

interface Release {
  version: string
  date: string
  title: string
  highlights: string[]
}

interface ChangelogData {
  releases: Release[]
  last_updated: string
}

export function WhatsNewModal() {
  const [open, setOpen] = useState(false)
  const [changelog, setChangelog] = useState<ChangelogData | null>(null)

  useEffect(() => {
    fetch('/changelog.json')
      .then(res => res.json())
      .then((data: ChangelogData) => {
        setChangelog(data)
        
        const lastSeenVersion = localStorage.getItem('lastSeenVersion')
        const latestVersion = data.releases[0]?.version
        
        if (latestVersion && lastSeenVersion !== latestVersion) {
          setOpen(true)
        }
      })
      .catch(console.error)
  }, [])

  const handleClose = () => {
    if (changelog?.releases[0]) {
      localStorage.setItem('lastSeenVersion', changelog.releases[0].version)
    }
    setOpen(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center text-2xl">
            <Sparkles className="w-6 h-6 mr-2 text-blue-500" />
            What's New
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-6 mt-4">
          {changelog?.releases.slice(0, 3).map((release) => (
            <div key={release.version} className="border-l-4 border-blue-500 pl-4">
              <div className="flex items-center space-x-2 mb-2">
                <Badge variant="default">{release.version}</Badge>
                <span className="text-sm text-muted-foreground">{release.date}</span>
              </div>
              <h3 className="text-lg font-semibold mb-2">{release.title}</h3>
              <ul className="list-disc list-inside space-y-1">
                {release.highlights.map((highlight, idx) => (
                  <li key={idx} className="text-sm text-muted-foreground">{highlight}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}

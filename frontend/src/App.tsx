import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '@/lib/theme'
import { Toaster } from '@/components/ui/sonner'
import { Layout } from '@/components/Layout'
import { CommandsPage } from '@/pages/Commands'
import { ConfigPage } from '@/pages/Config'
import { StatusPage } from '@/pages/Status'
import { ImportListsPage } from '@/pages/ImportLists'
import { NewReleasesPage } from '@/pages/NewReleases'

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="cmdarr-ui-theme">
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<CommandsPage />} />
            <Route path="/config" element={<ConfigPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/import-lists" element={<ImportListsPage />} />
            <Route path="/new-releases" element={<NewReleasesPage />} />
          </Routes>
        </Layout>
      </Router>
      <Toaster />
    </ThemeProvider>
  )
}

export default App

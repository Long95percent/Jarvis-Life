import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from '@/components/layout'
import { AmbientProvider } from '@/components/ambient'
import { KnowledgePage, SettingsPage } from '@/pages'
import { JarvisPage } from '@/pages/JarvisPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AmbientProvider>
          <Routes>
            {/* Home route redirects to Jarvis command center */}
            <Route path="/" element={<Navigate to="/jarvis" replace />} />
            <Route path="/jarvis" element={<JarvisPage />} />
            <Route element={<AppLayout />}>
              <Route path="knowledge" element={<KnowledgePage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </AmbientProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App

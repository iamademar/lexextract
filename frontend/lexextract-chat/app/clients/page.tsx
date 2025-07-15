'use client'

import { useState } from 'react'
import { ClientsList } from '@/components/ClientsList'
import { ClientForm } from '@/components/ClientForm'
import { type Client } from '@/lib/api/clients'

export default function ClientsPage() {
  const [formOpen, setFormOpen] = useState(false)
  const [editingClient, setEditingClient] = useState<Client | null>(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleCreateClient = () => {
    setEditingClient(null)
    setFormOpen(true)
  }

  const handleEditClient = (client: Client) => {
    setEditingClient(client)
    setFormOpen(true)
  }

  const handleFormSuccess = () => {
    setRefreshTrigger(prev => prev + 1)
  }

  const handleFormClose = (open: boolean) => {
    setFormOpen(open)
    if (!open) {
      setEditingClient(null)
    }
  }

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <ClientsList
        onCreateClient={handleCreateClient}
        onEditClient={handleEditClient}
        refreshTrigger={refreshTrigger}
      />
      
      <ClientForm
        client={editingClient}
        open={formOpen}
        onOpenChange={handleFormClose}
        onSuccess={handleFormSuccess}
      />
    </div>
  )
}
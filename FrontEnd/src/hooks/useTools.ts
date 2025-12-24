import { useState, useEffect, useCallback, useRef } from 'react';
import { getTools, toggleTool, type Tool } from '@/lib/api';
import { toast } from 'sonner';

export function useTools() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const initRef = useRef(false);

  const fetchTools = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await getTools();
      setTools(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch tools';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleToggle = useCallback(async (toolName: string, enable: boolean) => {
    // Optimistic update
    const previousTools = [...tools];
    setTools((prev) =>
      prev.map((tool) =>
        tool.name === toolName ? { ...tool, connected: enable } : tool
      )
    );

    try {
      await toggleTool(toolName, enable);
      toast.success(enable ? 'Tool Enabled' : 'Tool Disabled', {
        description: `${toolName} has been ${enable ? 'enabled' : 'disabled'}`,
      });
    } catch (err) {
      // Rollback on error
      setTools(previousTools);
      toast.error('Error', {
        description: `Failed to ${enable ? 'enable' : 'disable'} ${toolName}`,
      });
    }
  }, [tools]);

  useEffect(() => {
    if (!initRef.current) {
      initRef.current = true;
      fetchTools();
    }
  }, [fetchTools]);

  return { 
    tools, 
    loading, 
    error,
    toggleTool: handleToggle, 
    refetch: fetchTools 
  };
}

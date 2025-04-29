import React, { useEffect, useState } from 'react';
import { X, Bot } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../core/dialog';
import { Button } from '../core/button'; // Fixed import
import { cn } from '../../utils/utils';

const ModelsModal = ({ isOpen, onClose, onSelectModel }) => {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchModels = async () => {
      setIsLoading(true);
      setError('');
      try {
        const response = await fetch('https://open-i0or.onrender.com/api/tags');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (!Array.isArray(data)) {
          throw new Error('Invalid response: Expected an array');
        }
        setModels(data);
        if (data.length > 0) {
          setSelectedModel(data[0].name);
        }
      } catch (err) {
        console.error('Error fetching models:', err);
        setError(err.message);
        setModels([
          { name: 'gpt-4o-mini', provider: 'OpenAI', type: 'generation' },
          { name: 'deepseek-chat', provider: 'DeepSeek', type: 'generation' },
        ]);
        setSelectedModel('gpt-4o-mini');
      } finally {
        setIsLoading(false);
      }
    };
    if (isOpen) {
      fetchModels();
    }
  }, [isOpen]);

  const handleSelect = () => {
    if (selectedModel) {
      onSelectModel(selectedModel);
      localStorage.setItem('selectedModel', selectedModel);
    }
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5" />
              <DialogTitle>Select Model</DialogTitle>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="h-8 w-8"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          {error && (
            <div className="text-sm text-destructive">{error}</div>
          )}
          {isLoading ? (
            <div className="flex items-center justify-center h-20">
              <div className="w-6 h-6 rounded-full bg-primary/80 animate-pulse" />
            </div>
          ) : (
            <div className="grid gap-2">
              <label htmlFor="model-select" className="text-sm font-medium">
                Available Models
              </label>
              <select
                id="model-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className={cn(
                  'appearance-none bg-background border border-border rounded px-2 py-1 text-sm',
                  'focus:outline-none focus:ring-2 focus:ring-primary w-full'
                )}
              >
                {models.map((model) => (
                  <option key={model.name} value={model.name}>
                    {model.provider}: {model.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <Button
            onClick={handleSelect}
            disabled={isLoading || !selectedModel}
            className="bg-primary text-primary-foreground hover:bg-primary/90"
          >
            Select Model
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ModelsModal;
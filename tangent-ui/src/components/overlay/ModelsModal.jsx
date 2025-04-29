import React, { useEffect, useState } from 'react';
import { X, Bot } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../core/dialog';
import { Button } from '../core/button';
import { cn } from '../../utils/utils';

const ModelsModal = ({ isOpen, onClose, onSelectModel }) => {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen) return;

    const fetchModels = async () => {
      setError('');
      setIsLoading(true);
      try {
        const res = await fetch('https://open-i0or.onrender.com/api/models/library');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();
        if (!Array.isArray(payload.models)) throw new Error('Invalid response shape');
        setModels(payload.models);

        // default selection
        const stored = localStorage.getItem('selectedModel');
        if (stored && payload.models.some(m => m.name === stored)) {
          setSelectedModel(stored);
        } else {
          setSelectedModel(payload.models[0].name);
        }
      } catch (err) {
        console.error('Failed to fetch models:', err);
        setError('Could not load models.');
        const fallback = [
          { name: 'gpt-4o-mini', provider: 'OpenAI',  type: 'generation' },
          { name: 'deepseek-chat', provider: 'DeepSeek', type: 'generation' },
        ];
        setModels(fallback);
        setSelectedModel(fallback[0].name);
      } finally {
        setIsLoading(false);
      }
    };

    fetchModels();
  }, [isOpen]);

  const handleSelect = () => {
    if (selectedModel) {
      localStorage.setItem('selectedModel', selectedModel);
      onSelectModel(selectedModel);
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
            <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {error && <div className="text-sm text-destructive">{error}</div>}

          {isLoading ? (
            <div className="flex items-center justify-center h-20">
              <div className="w-6 h-6 rounded-full bg-primary/80 animate-pulse" />
            </div>
          ) : (
            <div className="grid gap-2">
              <span className="text-white text-sm font-medium">Available Models</span>
              <div className="flex flex-col space-y-2">
                {models.map((m) => {
                  const isActive = m.name === selectedModel;
                  return (
                    <button
                     key={m.name}
                     className={cn(
                       'w-full text-left px-3 py-2 border rounded-lg text-white',
                       isActive
                         ? 'bg-primary text-primary-foreground border-primary'
                         : 'bg-background hover:border-border'
                     )}
                     onClick={() => setSelectedModel(m.name)}
                   >
                     <span className="font-medium">{m.provider}</span>: {m.name}
                   </button>
                  );
                })}
              </div>
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

import React from 'react';
import { MousePointer, Hand, Bot } from 'lucide-react';
import { cn } from '../../utils/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../core/dropdown-menu';

const tools = [
  { id: 'select', icon: MousePointer, label: 'Select and move threads (S)' },
  { id: 'pan', icon: Hand, label: 'Pan canvas (H)' },
];

const ToolButton = ({ tool, isActive, onClick }) => {
  const Icon = tool.icon;

  return (
    <div className="relative group">
      <button
        onClick={() => onClick(tool.id)}
        className={cn(
          'p-2 rounded-lg transition-all duration-200',
          'hover:bg-secondary',
          isActive ? 'bg-primary/20 text-primary' : 'text-muted-foreground',
          'light:hover:bg-gray-100 dark:hover:bg-gray-800',
          'hextech-nordic:hover:bg-blue-900/20 hextech-nordic:active:bg-blue-800/30',
          'singed-theme:hover:bg-green-900/20 singed-theme:active:bg-green-800/30'
        )}
        title={tool.label}
      >
        <Icon className="w-5 h-5" />
      </button>
      <span
        className={cn(
          'absolute hidden group-hover:block',
          'left-14 top-1/2 -translate-y-1/2',
          'px-2 py-1 text-xs rounded whitespace-nowrap',
          'bg-popover text-popover-foreground',
          'shadow-md border border-border',
          'z-50'
        )}
      >
        {tool.label}
      </span>
    </div>
  );
};

const CanvasToolbar = ({
  activeTool,
  onToolSelect,
  theme,
  onThemeChange,
  selectedModel,
  models,
  onModelSelect,
  isModelDropdownOpen,
  setIsModelDropdownOpen,
  modelDropdownRef,
}) => {
  const handleModelSelect = (modelName) => {
    onModelSelect(modelName);
    localStorage.setItem('selectedModel', modelName);
    setIsModelDropdownOpen(false);
  };

  const themes = ['light', 'dark', 'hextech-nordic', 'singed-theme'];

  return (
    <div
      className={cn(
        'flex flex-col gap-2 p-2 rounded-xl shadow-lg',
        'bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60',
        'border border-border'
      )}
    >
      {tools.map((tool) => (
        <ToolButton
          key={tool.id}
          tool={tool}
          isActive={activeTool === tool.id}
          onClick={onToolSelect}
        />
      ))}
      <DropdownMenu
        open={isModelDropdownOpen}
        onOpenChange={setIsModelDropdownOpen}
      >
        <DropdownMenuTrigger asChild>
          <button
            className={cn(
              'p-2 rounded-lg transition-all duration-200',
              'hover:bg-secondary text-muted-foreground',
              'light:hover:bg-gray-100 dark:hover:bg-gray-800',
              'hextech-nordic:hover:bg-blue-900/20 hextech-nordic:active:bg-blue-800/30',
              'singed-theme:hover:bg-green-900/20 singed-theme:active:bg-green-800/30'
            )}
          >
            <Bot className="w-5 h-5" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent ref={modelDropdownRef}>
          {models.map((model) => (
            <DropdownMenuItem
              key={model.name}
              onClick={() => handleModelSelect(model.name)}
              className={cn(
                selectedModel === model.name && 'bg-primary/20 text-primary'
              )}
            >
              {model.provider}: {model.name}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <select
        value={theme}
        onChange={(e) => onThemeChange(e.target.value)}
        className={cn(
          'p-2 rounded-lg transition-all duration-200',
          'bg-background border border-border text-sm',
          'focus:outline-none focus:ring-2 focus:ring-primary'
        )}
      >
        {themes.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
    </div>
  );
};

export default CanvasToolbar;
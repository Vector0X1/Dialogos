import React from 'react';
import { Bot } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../core/card';
import { cn } from '../../utils/utils';

export const ModelCard = ({ model, isSelected, onSelect }) => {
  return (
    <Card
      className={cn(
        'w-full h-full flex flex-col justify-between transition-all hover:shadow-lg cursor-pointer',
        isSelected && 'bg-primary/10 border-primary'
      )}
      onClick={() => onSelect(model.name)}
    >
      <CardHeader className="p-4 flex items-start gap-2">
        <Bot className="h-5 w-5 text-primary" />
        <div>
          <CardTitle className="text-sm font-semibold">
            {model.provider}: {model.name}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="px-4 pb-4 pt-0">
        <div className="text-sm text-muted-foreground">Type: {model.type}</div>
      </CardContent>
    </Card>
  );
};
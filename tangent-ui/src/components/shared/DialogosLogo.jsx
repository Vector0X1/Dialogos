import React from 'react';
import { cn } from '../../utils/utils';

export function DialogosLogo() {
  return (
    <div
      className={cn(
        "w-[180px] h-[36px] relative rounded-lg overflow-hidden flex items-center justify-center"
      )}
    >
      <div
        className={cn(
          "font-sans text-[24px] font-bold text-foreground"
        )}
      >
        DIALOGOS
      </div>
    </div>
  );
}

export default DialogosLogo;

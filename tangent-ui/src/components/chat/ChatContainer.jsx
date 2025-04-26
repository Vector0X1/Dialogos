import React, { useState, useEffect, useRef } from 'react';
import { PanelRight, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../../utils/utils';
import { Button } from '../core/button';

const ChatContainer = ({ children, size: initialSize = 'normal', onSizeChange }) => {
  const [size, setSize] = useState(initialSize);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(0);

  const sizes = {
    collapsed: 240,
    normal: 400,
    large: 1200,
    xlarge: Math.floor(window.innerWidth * 0.73),
  };

  useEffect(() => {
    setContainerWidth(sizes[size]);
    if (onSizeChange) {
      onSizeChange(size);
    }
  }, [size, onSizeChange]);

  const handleSizeChange = (newSize) => {
    setSize(newSize);
  };

  const handleMouseDown = () => {
    setIsDragging(true);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;

    const newWidth = window.innerWidth - e.clientX;
    const closestSize = Object.entries(sizes).reduce((acc, [key, value]) => {
      return Math.abs(value - newWidth) < Math.abs(acc.value - newWidth)
        ? { key, value }
        : acc;
    }, { key: size, value: sizes[size] });

    setSize(closestSize.key);
  };

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  return (
    <div
      ref={containerRef}
      className={cn(
        "fixed inset-y-0 right-0 bg-background border-l shadow-lg transition-all duration-300",
        size === 'collapsed' ? 'w-[240px]' : ''
      )}
      style={{
        width: size !== 'collapsed' ? `${sizes[size]}px` : undefined,
      }}
    >
      <div className="absolute -left-8 top-1/2 transform -translate-y-1/2">
        <Button
          variant="outline"
          size="icon"
          onMouseDown={handleMouseDown}
          className="rounded-r-none"
        >
          {size === 'collapsed' ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
      </div>

      <div className="h-full flex flex-col">
        {children}
      </div>
    </div>
  );
};

export default ChatContainer;
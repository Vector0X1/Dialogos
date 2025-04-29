import React, { useState } from 'react';
import { Sun, Moon, Sparkles, Atom, Stars, Cloud } from 'lucide-react';
import { Button } from '../core/button';
import { motion, AnimatePresence } from 'framer-motion';

export function ThemeToggle({ theme, setTheme }) {
  const [isOpen, setIsOpen] = useState(false);

  const themes = [
   
    {
      name: 'void-theme',
      icon: Cloud,
      label: 'Void',
      className: 'text-[hsl(270,100%,60%)]'
    }
  ];

  const currentTheme = themes.find(t => t.name === theme) || themes[0];
  const Icon = currentTheme.icon;

  return (
    <div className="relative">
     

     
    </div>
  );
}
import React, { useState, useEffect } from 'react'; // 👈 Add useEffect here

// ...

export function ThemeToggle({ theme, setTheme }) {
  const [isOpen, setIsOpen] = useState(false);

  // Set the theme on initial load
  useEffect(() => {
    document.documentElement.classList.add('void-theme');
    setTheme('void-theme');
    localStorage.setItem('theme', 'void-theme');
  }, [setTheme]);

  const themes = [
    {
      name: 'void-theme',
      icon: Cloud,
      label: 'Void',
      className: 'text-[hsl(270,100%,60%)]'
    }
  ];

  const currentTheme = themes[0];
  const Icon = currentTheme.icon;

  return (
    <div className="relative">
      {/* You can render a static button or skip rendering a toggle at all */}
      <Button
        variant="outline"
        size="icon"
        className="w-8 h-8 transition-colors void-pulse"
        disabled // optional: disables button click
      >
        <Icon className={`h-4 w-4 ${currentTheme.className}`} />
        <span className="sr-only">Void Theme Active</span>
      </Button>
    </div>
  );
}

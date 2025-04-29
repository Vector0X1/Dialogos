import React, { useEffect } from 'react';
import { IntegratedDashboard } from './components//layout/IntegratedDashboard';
import VisualizationProvider from './components/providers/VisualizationProvider';
import OnboardingTour from './components/overlay/OnboardingTour';

import './styles/Global.css';

function App() {
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove(
      'light',
      'dark',
      'hextech-nordic',
      'singed-theme',
      'celestial-theme'
    ); // Clean up old themes
    root.classList.add('void-theme'); // Apply void theme
    localStorage.setItem('theme', 'void-theme'); // Persist if needed
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <VisualizationProvider>
        <OnboardingTour />
        <IntegratedDashboard />
      </VisualizationProvider>
    </div>
  );
}

export default App;

import React, { useEffect, useState } from 'react';

export default function MobileBlocker() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => {
      const mobileUA = /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
      const narrowScreen = window.innerWidth < 768;
      setIsMobile(mobileUA || narrowScreen);
    };
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  if (!isMobile) return null;

  return (
    <div
      className="
        fixed inset-0 z-[9999] flex items-center justify-center
        bg-white/50 dark:bg-black/50
        backdrop-blur-md
        p-6 text-center
      "
    >
      <div className="max-w-sm bg-white/80 dark:bg-black/80 rounded-lg p-6 shadow-lg">
        <h1 className="text-2xl font-bold mb-2 text-gray-900 dark:text-gray-100">
          Please run app on desktop
        </h1>
        <p className="text-lg text-gray-700 dark:text-gray-200">
          This application is only supported on desktop devices.
        </p>
      </div>
    </div>
  );
}

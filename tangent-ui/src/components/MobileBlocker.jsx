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
        bg-black/47 dark:bg-black/50
        backdrop-blur-md
        p-6 text-center
      "
    >
      <div className=" ">
        <h1 className="text-2xl font-bold mb-2 text-white-900 dark:text-gray-100">
          Please run app on desktop
        </h1>
       
      </div>
    </div>
  );
}

// src/shared/MobileBlocker.jsx
import React, { useState, useEffect } from 'react';

const MobileBlocker = () => {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const ua = navigator.userAgent || navigator.vendor || window.opera;
    // simple mobile regex
    if (/android|iphone|ipad|iPod|mobile/i.test(ua)) {
      setIsMobile(true);
    }
  }, []);

  // not on mobile → nothing to do
  if (!isMobile) return null;

  // fullscreen blocker
  return (
    <div
      className="fixed inset-0 bg-white z-[9999] flex items-center justify-center p-4 text-center"
    >
      <p className="text-2xl font-semibold text-gray-800">
        Please run this app on desktop.
      </p>
    </div>
  );
};

export default MobileBlocker;

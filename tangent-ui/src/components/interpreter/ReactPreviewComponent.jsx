import React, { useEffect, useState } from "react";
import {
  SandpackProvider,
  SandpackPreview,
  SandpackLayout,
  SandpackCodeViewer
} from "@codesandbox/sandpack-react";
import { dracula } from "@codesandbox/sandpack-themes";

const baseFiles = {
  "/index.html": `
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <script src="https://cdn.tailwindcss.com"></script>
    <title>Preview</title>
  </head>
  <body style="margin:0;padding:1rem;">
    <div id="root"></div>
  </body>
</html>
`,
};

export function ReactPreviewComponent({ code }) {
  const [error, setError] = useState(null);
  const processedCode = code.trim();
  const [key, setKey] = useState(0);

  useEffect(() => {
    setError(null);
    setKey(prev => prev + 1);
  }, [processedCode]);

  const handleError = (err) => {
    setError(err.message);
    console.error("Preview error:", err);
  };

  const files = {
    "/App.js": processedCode,
    "/index.js": `
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);`,
    ...baseFiles
  };

  if (error) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4">
        <div className="text-sm font-medium text-destructive mb-2">Error in preview:</div>
        <pre className="text-xs font-mono text-destructive whitespace-pre-wrap">{error}</pre>
      </div>
    );
  }

  return (
    <div className="relative" onClick={e => e.stopPropagation()}>
      <SandpackProvider
        key={key}
        template="react"
        theme={dracula}
        files={files}
        customSetup={{
          entry: "/index.js",
          environment: "create-react-app",
          dependencies: {
            "react": "^18.0.0",
            "react-dom": "^18.0.0",
            "uuid": "^9.0.0",
            // Added Three.js and related libraries
            "three": "^0.160.0",
            "@react-three/fiber": "^8.15.0",
            "@react-three/drei": "^9.92.0",
            "@types/three": "^0.160.0",
            // Add any other libraries you need here
            "@react-three/postprocessing": "^2.15.0",
            "leva": "^0.9.35"  // Optional: for GUI controls
          }
        }}
        options={{
          autorun: true,
          recompileMode: "immediate",
          bundlerTimeoutInterval: 60000, // Increased timeout for larger dependencies
          externalResources: ["https://cdn.tailwindcss.com"],
          showErrorOverlay: false,
        }}
      >
        <SandpackLayout>
          <div className="flex flex-col gap-4 w-full" onClick={e => e.stopPropagation()}>
            <SandpackCodeViewer
              className="scrollable"
              showTabs={false}
              showLineNumbers={true}
              showInlineErrors={false}
              wrapContent
              code={processedCode}
              style={{
                height: 'auto',
                maxHeight: '400px',
                minHeight: '100px',
                borderRadius: '8px',
                overflowY: 'auto',
                overflowX: 'hidden',
                padding: '8px',
                cursor: 'text',
              }}
              onWheel={(e) => {
                const container = e.currentTarget;
                const isScrollable = container.scrollHeight > container.clientHeight;

                if (isScrollable) {
                  const isAtTop = container.scrollTop === 0 && e.deltaY < 0;
                  const isAtBottom =
                    container.scrollTop + container.clientHeight ===
                      container.scrollHeight && e.deltaY > 0;

                  if (isAtTop || isAtBottom) {
                    e.stopPropagation();
                  }
                }
              }}
            />

            <SandpackPreview
              showOpenInCodeSandbox={false}
              showRefreshButton={true}
              onError={handleError}
              style={{
                width: "100%",
                height: "300px",
                border: "1px solid #ccc",
                borderRadius: "8px",
                overflow: "hidden",
              }}
            />
          </div>
        </SandpackLayout>
      </SandpackProvider>
    </div>
  );
}

export default ReactPreviewComponent;
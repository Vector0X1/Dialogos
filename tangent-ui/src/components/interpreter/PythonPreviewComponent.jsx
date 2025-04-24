import React, { useState, useEffect, useMemo } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-python";
// If you use a Prism theme (like `prism-tomorrow.css`), import it, too
// import "prismjs/themes/prism-tomorrow.css"; 

export function PythonPreviewComponent({ code }) {
  const [pyodide, setPyodide] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [output, setOutput] = useState("");
  const [error, setError] = useState("");
  const [hasPlot, setHasPlot] = useState(false);

  // 1) Highlight the code only once code changes
  const highlightedCode = useMemo(() => {
    return Prism.highlight(code, Prism.languages.python, "python");
  }, [code]);

  const needsMatplotlib = code.includes("import matplotlib");
  const needsNumpy = code.includes("import numpy") || code.includes("from numpy") || code.includes("np.");

  // 2) Initialize Pyodide w/ optional packages 
  useEffect(() => {
    async function initPyodide() {
      try {
        const pyodideInstance = await window.loadPyodide({
          indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/",
        });
        const packagesToLoad = [];
        if (needsMatplotlib) packagesToLoad.push("matplotlib", "matplotlib-pyodide");
        if (needsNumpy) packagesToLoad.push("numpy");

        if (packagesToLoad.length > 0) {
          await pyodideInstance.loadPackage(packagesToLoad);
        }

        setPyodide(pyodideInstance);
      } catch (err) {
        console.error("Failed to initialize Python environment:", err);
        setError("Failed to initialize Python environment");
      }
    }

    // Only init if not already loaded
    if (!pyodide) {
      initPyodide();
    }
  }, [pyodide, needsMatplotlib, needsNumpy]);

  // 3) The "Run" button logic
  const handleRun = async () => {
    if (!pyodide) return;
    setIsRunning(true);
    setError("");
    setOutput("");
    setHasPlot(false);

    try {
      // Reset stdout/stderr
      pyodide.runPython(`
        import sys
        from io import StringIO
        sys.stdout = StringIO()
        sys.stderr = StringIO()
      `);

      // Clear existing plots if needed
      if (needsMatplotlib) {
        pyodide.runPython(`
          import matplotlib.pyplot as plt
          plt.clf()
        `);
      }

      // Execute code
      await pyodide.runPython(code);

      // If using matplotlib, check if any figures exist
      if (needsMatplotlib) {
        const figureCount = pyodide.runPython(`len(plt.get_fignums())`);
        if (figureCount > 0) {
          setHasPlot(true);
          // Force rendering
          pyodide.runPython(`
            import matplotlib_pyodide
            import js
            canvas = js.document.getElementById('pyodide-plot-canvas')
            if canvas:
              matplotlib_pyodide.html5_canvas_backend.set_canvas(canvas)
            plt.gcf().canvas.draw()
            plt.show()
          `);
        }
      }

      // Get stdout & stderr
      const stdOut = pyodide.runPython("sys.stdout.getvalue()");
      const stdErr = pyodide.runPython("sys.stderr.getvalue()");
      setOutput(stdOut);
      if (stdErr) {
        setError(stdErr);
      }
    } catch (err) {
      console.error("Error running Python code:", err);
      setError(err.message || "Unknown error");
    } finally {
      setIsRunning(false);
    }
  };

  // 4) Render the UI: 
  //    - a <pre><code> block with Prism highlighting
  //    - a "Run Python" button
  //    - your stdout, stderr, and optional matplotlib canvas
  return (
    <div className="border rounded p-4 bg-background relative">
      <div className="flex items-center justify-between mb-3">
        <button
          onClick={handleRun}
          disabled={!pyodide || isRunning}
          className="px-3 py-1.5 bg-primary text-primary-foreground rounded disabled:opacity-50"
        >
          {isRunning ? "Running..." : "Run Python"}
        </button>
      </div>

      {/* Show the highlighted code */}
      <pre className="bg-muted p-4 rounded-md overflow-x-auto">
        <code
          className="language-python text-sm font-mono"
          dangerouslySetInnerHTML={{ __html: highlightedCode }}
        />
      </pre>

      {/* Output */}
      {output && (
        <div className="mt-2 bg-muted/50 p-2 rounded">
          <div className="font-semibold text-xs mb-1">Output:</div>
          <pre className="whitespace-pre-wrap text-sm">{output}</pre>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-2 bg-destructive/10 p-2 rounded">
          <div className="font-semibold text-xs mb-1 text-destructive">Error:</div>
          <pre className="whitespace-pre-wrap text-sm text-destructive">{error}</pre>
        </div>
      )}

      {/* Plot canvas */}
      {hasPlot && (
        <div className="mt-4 border rounded p-4 bg-background">
          <canvas id="pyodide-plot-canvas" className="w-full" style={{ minHeight: "300px" }} />
        </div>
      )}
    </div>
  );
}

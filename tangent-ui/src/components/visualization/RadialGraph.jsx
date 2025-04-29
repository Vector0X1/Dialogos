import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Search, RefreshCw, Maximize2, Minimize2 } from 'lucide-react';
import { Input } from '../core/input';
import { Button } from '../core/button';
import { Badge } from '../index';
import ForceGraph2D from 'react-force-graph-2d';

const VisualizationPanel = ({
  nodes = [],
  focusOnMessage,
  handleRefresh,
  onCenterNode,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef(null);
  const fgRef = useRef();
  const [panelSize, setPanelSize] = useState({ width: 0, height: 0 });

  const nodeStats = {
    chats: nodes?.length || 0,
    topics: 0,
  };

  const centerX = 0;
  const centerY = 0;
  const radiusStep = 80;

  const graphData = React.useMemo(() => {
    if (!nodes.length) return { nodes: [], links: [] };

    const mainNode = nodes.find((n) => n.type === 'main') || nodes[0];
    const centerNode = {
      id: mainNode.id.toString(),
      label: 'Main',
      x: centerX,
      y: centerY,
      fx: centerX,
      fy: centerY,
    };

    const otherNodes = nodes
      .filter((n) => n.id !== mainNode.id)
      .map((node, i, arr) => {
        const angle = (i / arr.length) * 2 * Math.PI;
        const radius = radiusStep * 1.5;
        return {
          id: node.id.toString(),
          label: node.messages?.[0]?.content.slice(0, 20) || `Node ${node.id}`,
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        };
      });

    const links = nodes
      .filter((n) => n.parentId)
      .map((n) => ({ source: n.parentId.toString(), target: n.id.toString() }));

    return { nodes: [centerNode, ...otherNodes], links };
  }, [nodes]);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        setPanelSize({ width, height });
      }
    };

    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, [isFullscreen]);

  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
      const timeout = setTimeout(() => {
        fgRef.current.zoomToFit(400, 40);
      }, 300);
      return () => clearTimeout(timeout);
    }
  }, [graphData, panelSize]);

  const toggleFullscreen = async () => {
    if (!containerRef.current) return;
    try {
      if (!document.fullscreenElement) {
        await containerRef.current.requestFullscreen();
        setIsFullscreen(true);
      } else {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch (error) {
      console.error('Error toggling fullscreen:', error);
    }
  };

  return (
    <div
      ref={containerRef}
      className={`h-[85vh] w-full flex flex-col rounded-lg border border-border bg-background ${isFullscreen ? 'h-screen rounded-none border-none' : ''}`}
    >
      <div className="p-4 border-b border-border">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-8"
            placeholder="Search conversations and topics..."
          />
        </div>
      </div>

      <div className="flex-1 relative">
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={fgRef}
            graphData={graphData}
            backgroundColor="#0a0a0a"
            nodeLabel="label"
            nodeAutoColorBy="id"
            linkDirectionalParticles={2}
            linkDirectionalParticleSpeed={0.003}
            enableNodeDrag={false}
            cooldownTicks={80}
            onEngineStop={() => fgRef.current?.zoomToFit(400, 40)}
            onNodeClick={(node) => focusOnMessage?.(parseInt(node.id), 0)}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const fontSize = 10 / globalScale;
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.fillStyle = 'white';
              ctx.beginPath();
              ctx.arc(node.x, node.y, 3, 0, 2 * Math.PI);
              ctx.fill();
              if (globalScale > 1.5) {
                ctx.fillText(node.label, node.x + 5, node.y + 5);
              }
            }}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
            <p>No visualization data available.</p>
            <Button onClick={handleRefresh} className="ml-4">
              Refresh
            </Button>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-border space-y-3 bg-background">
        <div className="flex justify-between gap-2">
          <Badge variant="outline" className="h-6 bg-background/80 backdrop-blur">
            <span className="px-2 text-xs text-muted-foreground">Chats: {nodeStats.chats}</span>
          </Badge>
          <Badge variant="outline" className="h-6 bg-background/80 backdrop-blur">
            <span className="px-2 text-xs text-muted-foreground">Topics: {nodeStats.topics}</span>
          </Badge>
        </div>

        <div className="flex gap-1 justify-between">
          <Button size="sm" variant="outline" className="gap-2 flex-1" onClick={handleRefresh}>
            <RefreshCw className="h-3 w-3" />
            Refresh
          </Button>
          <Button size="sm" variant="secondary" onClick={toggleFullscreen}>
            {isFullscreen ? <Minimize2 className="h-3 w-3" /> : <Maximize2 className="h-3 w-3" />}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default VisualizationPanel;

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Search, RefreshCw, Maximize2, Minimize2, RotateCcw } from 'lucide-react';
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
  const [hoveredNode, setHoveredNode] = useState(null);

  const centerX = 0;
  const centerY = 0;

  const baseRadius = 60;
  const radiusMultiplier = Math.min(1 + nodes.length / 1200, 2.5);
  const radiusStep = baseRadius * radiusMultiplier;

  const graphData = React.useMemo(() => {
    if (!nodes.length) return { nodes: [], links: [] };

    // Apply search filter if searchTerm is provided
    const filteredNodes = searchTerm
      ? nodes.filter((node) =>
          node.messages?.[0]?.content.toLowerCase().includes(searchTerm.toLowerCase())
        )
      : nodes;

    if (!filteredNodes.length) return { nodes: [], links: [] };

    const mainNode = filteredNodes.find((n) => n.type === 'main') || filteredNodes[0];
    const centerNode = {
      id: mainNode.id.toString(),
      label: 'Main',
      branch: 'main',
      x: centerX,
      y: centerY,
      // Removed fx and fy to allow movement
    };

    const otherNodes = filteredNodes
      .filter((n) => n.id !== mainNode.id)
      .map((node, i, arr) => {
        const angle = (i / arr.length) * 2 * Math.PI;
        const radius = radiusStep;
        return {
          id: node.id.toString(),
          label: node.messages?.[0]?.content.slice(0, 20) || `Node ${node.id}`,
          branch: node.branch || 'default',
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
          // Removed fx and fy to allow movement
        };
      });

    const links = filteredNodes
      .filter((n) => n.parentId)
      .map((n) => ({ source: n.parentId.toString(), target: n.id.toString() }));

    const result = { nodes: [centerNode, ...otherNodes], links };
    console.log('Graph Data:', result);
    return result;
  }, [nodes, searchTerm]);

  const nodeStats = useMemo(() => ({
    chats: graphData.nodes?.length || 0,
    topics: graphData.nodes?.filter((n) => n.type === 'topic')?.length || 0,
  }), [graphData]);

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
      fgRef.current.zoomToFit(400, 20);
    }
  }, [graphData]);

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

  const recenterGraph = () => {
    if (fgRef.current && graphData.nodes.length > 0) {
      fgRef.current.zoomToFit(400, 20);
    }
  };

  return (
    <div
      ref={containerRef}
      className={`min-h-[50vh] w-full flex flex-col rounded-lg border border-border bg-background ${isFullscreen ? 'h-screen rounded-none border-none' : ''}`}
      style={{ overflowY: 'auto' }}
    >
      <div className="p-4 border-b border-border flex-shrink-0">
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

      <div
        className="flex-1 relative w-full"
        style={{ minHeight: '300px', position: 'relative', overflow: 'hidden' }}
      >
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={fgRef}
            graphData={graphData}
            width={panelSize.width}
            height={panelSize.height}
            backgroundColor="#0a0a0a"
            nodeLabel="label"
            nodeAutoColorBy="branch"
            linkDirectionalParticles={0}
            enableNodeDrag={false}
            cooldownTicks={Infinity} // Run simulation continuously for wobbling
            d3VelocityDecay={0.9} // Smooth, slow movement
            d3Force={(engine) => {
              // Repulsive force (nodes push away from each other)
              engine
                .force('charge', engine.force('charge') || engine.forceManyBody())
                .strength(-10); // Weak repulsion

              // Centering force (keep nodes around the center)
              engine
                .force('center', engine.force('center') || engine.forceCenter(centerX, centerY))
                .strength(0.05); // Gentle pull to center

              // Attractive force for links (keep connected nodes close)
              engine
                .force('link', engine.force('link') || engine.forceLink())
                .distance(20) // Short link distance for tight clustering
                .strength(0.1); // Weak attraction

              // Small random forces for wobbling
              engine
                .force('x', engine.force('x') || engine.forceX())
                .strength(() => 0.005 * (Math.random() - 0.5)); // Random small x-force
              engine
                .force('y', engine.force('y') || engine.forceY())
                .strength(() => 0.005 * (Math.random() - 0.5)); // Random small y-force
            }}
            onNodeClick={(node) => {
              if (focusOnMessage) {
                focusOnMessage(parseInt(node.id), 0);
              }
            }}
            onNodeHover={(node) => setHoveredNode(node)}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const isHovered = node === hoveredNode;
              const nodeSize = isHovered ? 4 : 3;
              const fontSize = 8 / globalScale;
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.fillStyle = node.color || 'white';
              ctx.beginPath();
              ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
              ctx.fill();
              if (globalScale > 2 || isHovered) {
                ctx.fillStyle = 'white';
                ctx.fillText(node.label, node.x + 5, node.y + 5);
              }
            }}
            linkWidth={0.5}
            linkColor={() => 'rgba(255, 255, 255, 0.2)'}
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

      <div className="p-4 border-t border-border space-y-3 bg-background flex-shrink-0 sticky bottom-0">
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
          <Button size="sm" variant="outline" className="gap-2 flex-1" onClick={recenterGraph}>
            <RotateCcw className="h-3 w-3" />
            Recenter
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
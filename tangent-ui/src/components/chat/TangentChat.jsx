import React, { useState, useRef, useEffect, useCallback } from 'react';
import { BranchNode } from '../visualization/BranchNode';
import ChatInterface from './ChatInterface';
import CanvasToolbar from '../navigation/CanvasToolbar';
import ChatContainer from './ChatContainer';
import FloatingInput from '../shared/FloatingInput';
import { MessageNavigator } from '../navigation/MessageNavigator';
import { ModelStatus } from '../shared/ModelStatus';
import { cn } from "../../utils/utils";
import { useVisualization } from '../providers/VisualizationProvider';
import ChatBranchPanel from './ChatBranchPanel';
import ChatPersistenceManager from './ChatPersistenceManager';

// Utility function for retrying fetch requests with timeout
async function fetchWithRetry(url, options, retries = 3, delay = 2000, timeout = 30000) {
  for (let i = 0; i < retries; i++) {
    try {
      // Create a timeout promise
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      options.signal = controller.signal;

      const response = await fetch(url, options);
      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
      }
      return response;
    } catch (error) {
      if (i === retries - 1) throw error;
      console.log(`Retrying... (${i + 1}/${retries}) - Error: ${error.message}`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
}

export function GridBackground({ translate, scale, className }) {
  const gridSize = 20;
  const viewWidth = window.innerWidth;
  const viewHeight = window.innerHeight;
  const offsetX = (translate.x % (gridSize * scale)) / scale;
  const offsetY = (translate.y % (gridSize * scale)) / scale;

  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{
        transform: `translate(${offsetX}px, ${offsetY}px)`,
      }}
    >
      <defs>
        <pattern
          id="grid"
          width={gridSize}
          height={gridSize}
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M 20 0 L 0 0 0 20"
            fill="none"
            className={cn("stroke-[1.2]", className)}
          />
        </pattern>
      </defs>
      <rect
        x="-20"
        y="-20"
        width={viewWidth + 40}
        height={viewHeight + 40}
        fill="url(#grid)"
      />
    </svg>
  );
}

const defaultTemplate = {
  id: 'template',
  type: 'template',
  title: 'New Branch',
  systemPrompt: '',
  x: 50,
  y: 150,
  messages: []
};

const systemPrompt = `You are a helpful AI assistant. When responding:
1. For brief responses ("briefly", "quick", "short"):
   - Use maximum 3 sentences
   - Focus on core concepts only

2. For comprehensive responses ("tell me everything", "explain in detail"):
   - Write at least 6-8 paragraphs
   - Cover fundamentals, history, types, applications
   - Include specific examples and use cases
   - Explain technical concepts in depth
   - Break down complex topics into subtopics
   - Discuss current trends and future implications

3. For unspecified length:
   - Provide 4-5 sentences
   - Balance detail and brevity

4. For React-related tasks:
   - Focus on functional components and hooks (e.g., \`useState\`, \`useEffect\`).
   - Assume the user works with an environment that supports modern React (version 18 or higher) and includes support for live previews and error handling.
   - Components should be styled using a lightweight, utility-first CSS framework (such as Tailwind CSS) unless otherwise specified.
   - Responses should account for ease of testing and previewing components, ensuring a smooth developer experience.

5. Always adapt your response length and content style based on explicit or implicit length cues in the user's question.`;

const TangentChat = ({
  initialConversation,
  isPanelCollapsed = false,
  nodes,
  setNodes,
  activeChat,
  setActiveChat
}) => {
  const [selectedNodePosition, setSelectedNodePosition] = useState(null);
  const [temperature, setTemperature] = useState(0.7);
  const { handleRefresh, theme, setTheme } = useVisualization();
  const [activeResponses, setActiveResponses] = useState(new Map());
  const [containerWidth, setContainerWidth] = useState(400);
  const [expandedMessages, setExpandedMessages] = useState(new Set());
  const [selectedNode, setSelectedNode] = useState(initialConversation?.id || 1);
  const [focusedMessageIndex, setFocusedMessageIndex] = useState(0);
  const [expandedNodes, setExpandedNodes] = useState(new Set([initialConversation?.id]));
  const [inputValue, setInputValue] = useState('');
  const [activeTool, setActiveTool] = useState('pan');
  const [scale, setScale] = useState(1);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const [models, setModels] = useState([]);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const modelDropdownRef = useRef(null);
  const [selectedModel, setSelectedModel] = useState('');
  const [chatContainerSize, setChatContainerSize] = useState('normal');
  const [activeContext, setActiveContext] = useState({
    messages: [],
    systemPrompt: '',
    parentChain: []
  });
  const [dragState, setDragState] = useState({
    isDragging: false,
    nodeId: null,
    startPos: { x: 0, y: 0 },
    nodeStartPos: { x: 0, y: 0 }
  });
  const [streamingMessage, setStreamingMessage] = useState("");
  const [continuationCount, setContinuationCount] = useState(0);
  const lastResponseTime = useRef(null);
  const [showQuickInput, setShowQuickInput] = useState(true);
  const [quickInputPosition, setQuickInputPosition] = useState({
    x: window.innerWidth / 2 - 192,
    y: window.innerHeight - 90
  });
  const [activeThreadId, setActiveThreadId] = useState(initialConversation?.id || 1);
  const [contentHeight, setContentHeight] = useState(0);
  const canvasRef = useRef(null);
  const nodesRef = useRef(nodes);
  const transformRef = useRef({ scale, translate });
  const contentRef = useRef(null);
  const [error, setError] = useState(null); // Added state for error handling

  // Add states for ChatBranchPanel
  const [chatType, setChatType] = useState('chatgpt');
  const [branchData, setBranchData] = useState(null);
  const [chatName, setChatName] = useState(activeChat?.title || `Chat_${Date.now()}`);
  const [messageCounter, setMessageCounter] = useState(0); // Counter for unique message IDs

  nodesRef.current = nodes;

  const PANNING_SENSITIVITY = 0.42;
  const ZOOM_SENSITIVITY = 0.0012;

  const getChatContainerWidth = useCallback(() => {
    const widths = {
      collapsed: 240,
      normal: 400,
      large: 1200,
      xlarge: Math.floor(window.innerWidth * 0.73)
    };
    return widths[chatContainerSize] || widths.normal;
  }, [chatContainerSize]);

  const getFullMessageHistory = useCallback((nodeId) => {
    const currentNode = nodes.find(n => n.id === nodeId);
    if (!currentNode) return [];

    if (currentNode.type === 'main' || !currentNode.parentId) {
      return currentNode.messages;
    }

    if (currentNode.contextMessages) {
      return currentNode.contextMessages;
    }

    return currentNode.messages;
  }, [nodes]);

  const syncMessageWithBackend = async (message, nodeId) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;

    const branchId = node.type === 'main' ? '0' : `branch_${node.id}`;
    const parentMessageId = node.parentMessageIndex !== undefined
      ? nodes.find(n => n.id === node.parentId)?.messages[node.parentMessageIndex]?.timestamp
      : null;

    // Generate a unique message_id
    const uniqueMessageId = `${chatName}_${messageCounter}`;
    setMessageCounter(prev => prev + 1);

    const backendMessage = {
      type: 'chatgpt',
      chat_name: chatName,
      branch_id: branchId,
      message_id: uniqueMessageId,
      text: message.content,
      timestamp: message.timestamp,
      parent_message: parentMessageId,
    };

    try {
      const response = await fetch('https://open-i0or.onrender.com/api/messages/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(backendMessage),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to sync message with backend');
      }
    } catch (err) {
      console.error('Error syncing message:', err);
    }
  };

  const handleSelectChat = (chatData) => {
    const newNodes = chatData.nodes.map((node, index) => ({
      id: node.id,
      type: index === 0 ? 'main' : 'branch',
      title: node.title || `Chat_${Date.now()}`,
      messages: node.messages.map(msg => ({
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp,
      })),
      x: node.x || 50 + (index * 400),
      y: node.y || 150,
      parentId: node.parentId,
      parentMessageIndex: node.parentMessageIndex,
      contextMessages: node.contextMessages,
    }));
    setNodes(newNodes);
    setActiveChat({ id: chatData.id, title: chatData.title });
    setChatName(chatData.title);

    // Sync loaded messages with backend
    newNodes.forEach(async (node) => {
      const messagesToSync = node.contextMessages || node.messages;
      for (const message of messagesToSync) {
        await syncMessageWithBackend(message, node.id);
      }
    });
  };

  const handleDataUpdate = (newData) => {
    setBranchData(newData);
  };

  useEffect(() => {
    transformRef.current = { scale, translate };
  }, [scale, translate]);

  useEffect(() => {
    if (!contentRef.current) return;

    const height = contentRef.current.getBoundingClientRect().height;
    setContentHeight(height);

    if (height > window.innerHeight) {
      const overflow = height - window.innerHeight;
      setTranslate(prev => ({
        ...prev,
        y: -overflow + 200
      }));
    }
  }, [nodes]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('light', 'dark', 'hextech-nordic', 'singed-theme');
    root.classList.add(theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    if (initialConversation && Array.isArray(initialConversation)) {
      const updatedNodes = initialConversation.map((node) => ({
        ...node,
        x: node.x ?? selectedNodePosition?.x ?? 400,
        y: node.y ?? selectedNodePosition?.y ?? 100,
      }));
      setNodes(updatedNodes);
      setExpandedNodes(new Set(updatedNodes.map((node) => node.id)));
      setSelectedNode(updatedNodes[0]?.id || 1);
    }
  }, [initialConversation, selectedNodePosition, setNodes]);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetch('https://open-i0or.onrender.com/api/models');
        const data = await response.json();
        const fetchedModels = [
          { name: data.generation_model },
          { name: data.embedding_model }
        ].filter(model => model.name !== "Not Set");
        setModels(fetchedModels);

        const savedModel = localStorage.getItem('selectedModel');
        if (savedModel && fetchedModels.some(model => model.name === savedModel)) {
          setSelectedModel(savedModel);
        } else if (fetchedModels.length > 0) {
          const lastModel = fetchedModels[fetchedModels.length - 1].name;
          setSelectedModel(lastModel);
          localStorage.setItem('selectedModel', lastModel);
        }
      } catch (error) {
        console.error('Error fetching models:', error);
      }
    };
    fetchModels();
  }, []);

  const handleToggleMessageExpand = useCallback((messageIndex) => {
    setExpandedMessages(prev => {
      const next = new Set(prev);
      if (next.has(messageIndex)) {
        next.delete(messageIndex);
      } else {
        next.add(messageIndex);
      }
      return next;
    });
  }, []);

  const handleToolSelect = useCallback((tool) => {
    setActiveTool(tool);
  }, []);

  const handleThemeChange = useCallback((newTheme) => {
    setTheme(newTheme);
  }, [setTheme]);

  const focusOnMessage = useCallback((nodeId, messageIndex, zoomInClose = false) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;

    const canvasRect = canvasRef.current?.getBoundingClientRect();
    if (!canvasRect) return;

    const messageOffset = messageIndex * 120;
    const messageY = node.y + 300 + messageOffset;

    const centerX = canvasRect.width / 2;
    const centerY = canvasRect.height / 2;

    const newTranslateX = centerX - (node.x + 128) * scale;
    const newTranslateY = centerY - messageY * scale;

    setTranslate({
      x: newTranslateX,
      y: newTranslateY
    });

    setScale(zoomInClose ? 2 : scale);

    if (!expandedNodes.has(nodeId)) {
      setExpandedNodes(prev => new Set([...prev, nodeId]));
    }

    setSelectedNode(nodeId);
    setFocusedMessageIndex(messageIndex);
  }, [nodes, scale, expandedNodes]);

  const handleInputChange = (e) => {
    const newValue = e.target ? e.target.value : e;
    setInputValue(newValue);
  };

  const createPreviewBranch = ({ parentId, code, language, position, messageIndex }) => {
    return {
      id: Date.now() + Math.random(),
      type: 'preview',
      title: `${language.toUpperCase()} Preview`,
      parentId,
      parentMessageIndex: messageIndex,
      x: position.x,
      y: position.y,
      messages: [{
        role: 'assistant',
        content: code,
        language,
        isPreview: true,
        timestamp: new Date().toISOString()
      }]
    };
  };

  const handleSendMessage = async (nodeId, message) => {
    if (!message || typeof message !== 'string') {
      console.error('Invalid message:', message);
      return;
    }
    if (!message.trim()) return;

    const currentNode = nodes.find(n => n.id === nodeId);
    if (!currentNode) {
      console.error('Node not found:', nodeId);
      return;
    }

    setInputValue('');
    setError(null); // Clear any previous errors

    const newMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
      context: determineMessageContext(message),
    };
    setNodes(prevNodes => prevNodes.map(node =>
      node.id === nodeId
        ? {
            ...node,
            messages: [...node.messages, newMessage],
            contextMessages: node.type === 'branch'
              ? [...(node.contextMessages || []), newMessage]
              : undefined,
          }
        : node
    ));

    await syncMessageWithBackend(newMessage, nodeId);

    setActiveResponses(prev => new Map(prev).set(nodeId, true));

    try {
      const conversationContext = currentNode.type === 'branch'
        ? [...(currentNode.contextMessages || []), newMessage]
        : [...currentNode.messages];


        const payload = {
          prompt: message
        };
      console.log('Sending payload to /api/generate:', payload);

      const response = await fetchWithRetry(
        'https://open-i0or.onrender.com/api/generate',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        3, // Number of retries
        2000, // Increased delay between retries (ms)
        30000 // Timeout after 30 seconds
      );

      console.log('Response status:', response.status);
      const data = await response.json();
      console.log('Received response from /api/generate:', data);

      const accumulatedResponse = data.response || 'No response received';

      const finalMessage = {
        role: 'assistant',
        content: accumulatedResponse,
        timestamp: new Date().toISOString(),
      };

      setNodes(prevNodes => prevNodes.map(node => {
        if (node.id !== nodeId) return node;
        return {
          ...node,
          messages: [
            ...node.messages.filter(m => m.role !== 'assistant' || !m.isStreaming),
            finalMessage,
          ],
          contextMessages: node.type === 'branch'
            ? [...(node.contextMessages || []), finalMessage]
            : undefined,
          streamingContent: null,
        };
      }));

      await syncMessageWithBackend(finalMessage, nodeId);

      const codeBlockRegex = /```(python)([\s\S]*?)```/g;
      const matches = [...accumulatedResponse.matchAll(codeBlockRegex)];

      if (matches.length > 0) {
        const previewBranches = matches.map((match, index) => {
          const [, language, code] = match;
          const cleanCode = code.trim();

          const position = {
            x: currentNode.x + 400,
            y: currentNode.y + index * 300,
          };

          return createPreviewBranch({
            parentId: nodeId,
            code: cleanCode,
            language,
            position,
            messageIndex: currentNode.messages.length + 1,
          });
        });

        setNodes(prev => [...prev, ...previewBranches]);
      }
    } catch (error) {
      console.error('Error in handleSendMessage:', error);
      let errorMessage = 'Failed to generate response. Please try again.';
      if (error.message.includes('Missing OPENAI_API_KEY')) {
        errorMessage = 'Backend configuration error: Missing API key.';
      } else if (error.message.includes('HTTP error')) {
        errorMessage = `Backend error: ${error.message}`;
      } else if (error.name === 'AbortError') {
        errorMessage = 'Request timed out. The server might be starting up—please try again in a moment.';
      }
      setError(errorMessage);
      setNodes(prevNodes => prevNodes.map(node =>
        node.id === nodeId ? { ...node, streamingContent: null } : node
      ));
    } finally {
      setActiveResponses(prev => {
        const next = new Map(prev);
        next.delete(nodeId);
        return next;
      });
    }
  };

  const determineMessageContext = (content) => {
    const pythonIndicators = ['python', 'def ', 'import ', 'print('];
    const reactIndicators = ['react', 'jsx', 'component', 'useState'];

    if (pythonIndicators.some(i => content.toLowerCase().includes(i))) return 'python';
    if (reactIndicators.some(i => content.toLowerCase().includes(i))) return 'react';
    return 'text';
  };

  const wrapCodeInComponent = (code) => {
    if (!code.includes('export default') && !code.includes('function')) {
      return `
import React, { useState } from 'react';

export default function PreviewComponent() {
  ${code}
  return (
    <div className="p-4">
      <button onClick={handleClick} className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
        Click me!
      </button>
      <p className="mt-2">Count: {count}</p>
    </div>
  );
}`;
    }
    return code;
  };

  const handleFloatingInputSend = (message) => {
    handleSendMessage(selectedNode, message);
  };

  const handleUpdateTitle = (nodeId, newTitle) => {
    setNodes(prevNodes => prevNodes.map(node =>
      node.id === nodeId ? { ...node, title: newTitle } : node
    ));
  };

  const buildConversationContext = (node) => {
    let context = {
      messages: [],
      parentChain: []
    };

    let currentNode = node;
    while (currentNode) {
      context.parentChain.unshift(currentNode.id);
      if (currentNode.parentId) {
        const parentNode = nodes.find(n => n.id === currentNode.parentId);
        if (parentNode) {
          const relevantMessages = parentNode.messages.slice(0, currentNode.parentMessageIndex + 1);
          context.messages.unshift(...relevantMessages);
          currentNode = parentNode;
        } else {
          break;
        }
      } else {
        break;
      }
    }

    context.messages.push(...node.messages);
    return context;
  };

  const onCreateBranch = async (parentNodeId, messageIndex, position = null) => {
    const parentNode = nodes.find(n => n.id === parentNodeId);
    if (!parentNode) return;

    const branchPosition = calculateBranchPosition(parentNode, messageIndex, nodes);

    const newNode = createBranch(
      parentNode,
      defaultTemplate,
      nodes,
      messageIndex,
      branchPosition
    );

    const branchContext = buildConversationContext(newNode);
    setActiveContext(branchContext);

    setNodes(prevNodes => [...prevNodes, newNode]);
    setSelectedNode(newNode.id);

    const messagesToSync = newNode.contextMessages || newNode.messages;
    for (const message of messagesToSync) {
      await syncMessageWithBackend(message, newNode.id);
    }
  };

  const screenToCanvas = useCallback((screenX, screenY) => {
    const { scale, translate } = transformRef.current;
    return {
      x: (screenX - translate.x) / scale,
      y: (screenY - translate.y) / scale
    };
  }, []);

  const handleDragStart = useCallback((e, node) => {
    if (node.type === 'main') return;

    e.preventDefault();
    e.stopPropagation();

    const canvasPos = screenToCanvas(e.clientX, e.clientY);

    setDragState({
      isDragging: true,
      nodeId: node.id,
      startPos: canvasPos,
      nodeStartPos: { x: node.x, y: node.y }
    });
  }, [screenToCanvas]);

  const handleDrag = useCallback((e) => {
    if (!dragState.isDragging) return;

    const currentPos = screenToCanvas(e.clientX, e.clientY);

    const deltaX = currentPos.x - dragState.startPos.x;
    const deltaY = currentPos.y - dragState.startPos.y;

    setNodes(prevNodes =>
      prevNodes.map(node =>
        node.id === dragState.nodeId
          ? {
              ...node,
              x: dragState.nodeStartPos.x + deltaX,
              y: dragState.nodeStartPos.y + deltaY
            }
          : node
      )
    );
  }, [dragState, screenToCanvas]);

  const handleDragEnd = useCallback(() => {
    setDragState({
      isDragging: false,
      nodeId: null,
      startPos: { x: 0, y: 0 },
      nodeStartPos: { x: 0, y: 0 }
    });
  }, []);

  const getSiblingBranches = useCallback((nodeId) => {
    const currentNode = nodes.find(n => n.id === nodeId);
    if (!currentNode || !currentNode.parentId) return [];

    return nodes.filter(n =>
      n.id !== nodeId &&
      n.parentId === currentNode.parentId &&
      n.parentMessageIndex === currentNode.parentMessageIndex
    ).sort((a, b) => a.y - b.y);
  }, [nodes]);

  const handleCanvasMouseDown = useCallback((e) => {
    if (e.button !== 0) return;

    const target = e.target;
    const isBackground = target === canvasRef.current ||
      target.classList.contains('grid-background');

    if (activeTool === 'pan' || (activeTool === 'select' && (e.ctrlKey || e.metaKey || isBackground))) {
      e.preventDefault();
      setIsPanning(true);
      setLastMousePos({ x: e.clientX, y: e.clientY });
    }
  }, [activeTool]);

  const handleDeleteNode = (nodeId) => {
    const nodesToDelete = new Set([nodeId]);
    let foundMore = true;

    while (foundMore) {
      foundMore = false;
      nodes.forEach(node => {
        if (node.parentId && nodesToDelete.has(node.parentId) && !nodesToDelete.has(node.id)) {
          nodesToDelete.add(node.id);
          foundMore = true;
        }
      });
    }

    setNodes(nodes.filter(node => !nodesToDelete.has(node.id)));
    if (selectedNode && nodesToDelete.has(selectedNode)) {
      setSelectedNode(1);
    }
  };

  const handleWheel = useCallback((e) => {
    if (e.target.closest('.scrollable')) {
      return;
    }
    e.preventDefault();

    const { scale: currentScale, translate: currentTranslate } = transformRef.current;
    const rect = canvasRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (e.ctrlKey || e.metaKey) {
      const delta = -e.deltaY * ZOOM_SENSITIVITY;
      const zoom = Math.exp(delta);
      const newScale = Math.min(Math.max(0.1, currentScale * zoom), 5);
      const mouseBeforeZoom = screenToCanvas(mouseX, mouseY);
      const scaleDiff = newScale - currentScale;

      const newTranslate = {
        x: currentTranslate.x - mouseBeforeZoom.x * scaleDiff,
        y: currentTranslate.y - mouseBeforeZoom.y * scaleDiff
      };

      setScale(newScale);
      setTranslate(newTranslate);
    } else {
      const dx = e.deltaX * PANNING_SENSITIVITY;
      const dy = e.deltaY * PANNING_SENSITIVITY;

      setTranslate(prev => ({
        x: prev.x - dx,
        y: prev.y - dy
      }));
    }
  }, [screenToCanvas]);

  const calculateBranchPosition = (parentNode, messageIndex, existingNodes) => {
    const BASE_SPACING_X = 300;
    const BASE_SPACING_Y = 200;
    const MESSAGE_HEIGHT = 120;

    const baseX = parentNode.x + BASE_SPACING_X;
    const baseY = parentNode.y + (messageIndex * MESSAGE_HEIGHT);

    const siblingBranches = existingNodes.filter(node =>
      node.parentId === parentNode.id && node.parentMessageIndex === messageIndex
    );

    const verticalOffset = siblingBranches.length * BASE_SPACING_Y;

    return {
      x: baseX,
      y: baseY + verticalOffset,
    };
  };

  const centerCanvas = useCallback(() => {
    if (!canvasRef.current) return;

    const calculateExpandedBounds = (nodes, expandedNodes) => {
      return nodes.reduce((bounds, node) => {
        const nodeWidth = 400;
        let nodeHeight = 80;

        if (expandedNodes.has(node.id) && node.messages) {
          nodeHeight += node.messages.reduce((height, msg) => {
            return height + (msg.content.length > 150 ? 160 : 120) + 16;
          }, 0);
        }

        return {
          minX: Math.min(bounds.minX, node.x),
          maxX: Math.max(bounds.maxX, node.x + nodeWidth),
          minY: Math.min(bounds.minY, node.y),
          maxY: Math.max(bounds.maxY, node.y + nodeHeight)
        };
      }, {
        minX: Infinity,
        maxX: -Infinity,
        minY: Infinity,
        maxY: -Infinity
      });
    };

    const viewport = {
      width: canvasRef.current.clientWidth,
      height: canvasRef.current.clientHeight
    };

    const bounds = calculateExpandedBounds(nodes, expandedNodes);
    if (!bounds || bounds.minX === Infinity) return;

    const PADDING = 100;
    const contentWidth = bounds.maxX - bounds.minX + (PADDING * 2);
    const contentHeight = bounds.maxY - bounds.minY + (PADDING * 2);

    const chatContainerWidth = getChatContainerWidth();
    const availableWidth = viewport.width - chatContainerWidth;

    const scaleX = (availableWidth * 0.9) / contentWidth;
    const scaleY = (viewport.height * 0.9) / contentHeight;
    const newScale = Math.min(Math.min(scaleX, scaleY), 1);

    const centerX = bounds.minX + (contentWidth / 2);
    const centerY = bounds.minY + (contentHeight / 2);

    const newTranslate = {
      x: (availableWidth / 2) - (centerX * newScale) + (PADDING * newScale),
      y: (viewport.height / 2) - (centerY * newScale) + (PADDING * newScale)
    };

    setScale(newScale);
    setTranslate(newTranslate);
  }, [nodes, expandedNodes, getChatContainerWidth]);

  const organizeNodesIntoStack = useCallback(() => {
    const LEVEL_HORIZONTAL_SPACING = 500;
    const MESSAGE_VERTICAL_SPACING = 120;
    const BRANCH_VERTICAL_PADDING = 50;
    const INITIAL_OFFSET_X = 200;
    const INITIAL_OFFSET_Y = 100;

    const rootNode = nodes.find(node => node.type === 'main');
    if (!rootNode) return;

    const branchesByMessage = new Map();
    nodes.forEach(node => {
      if (node.type === 'branch' && node.parentId === rootNode.id) {
        const messageIndex = node.parentMessageIndex || 0;
        if (!branchesByMessage.has(messageIndex)) {
          branchesByMessage.set(messageIndex, []);
        }
        branchesByMessage.get(messageIndex).push(node);
      }
    });

    const getMessageY = (messageIndex) => {
      return INITIAL_OFFSET_Y + (messageIndex * MESSAGE_VERTICAL_SPACING);
    };

    const processNode = (node, level, branchGroup = null) => {
      let x = INITIAL_OFFSET_X + (level * LEVEL_HORIZONTAL_SPACING);
      let y;

      if (node.type === 'main') {
        y = INITIAL_OFFSET_Y;
      } else {
        const messageY = getMessageY(node.parentMessageIndex);
        const branchesAtMessage = branchesByMessage.get(node.parentMessageIndex) || [];
        const branchIndex = branchesAtMessage.findIndex(b => b.id === node.id);
        y = messageY + (branchIndex * BRANCH_VERTICAL_PADDING);
      }

      const updatedNode = {
        ...node,
        x,
        y
      };

      const childBranches = nodes.filter(n => n.parentId === node.id);
      const processedChildren = childBranches.map((child, index) => {
        return processNode(child, level + 1, {
          parentY: y,
          index,
          total: childBranches.length
        });
      });

      return {
        node: updatedNode,
        children: processedChildren
      };
    };

    const processedStructure = processNode(rootNode, 0);

    const flattenStructure = (structure) => {
      const nodes = [structure.node];
      structure.children.forEach(child => {
        nodes.push(...flattenStructure(child));
      });
      return nodes;
    };

    const newNodes = flattenStructure(processedStructure);
    setNodes(newNodes);

    if (canvasRef.current) {
      const canvasRect = canvasRef.current.getBoundingClientRect();
      const bounds = {
        minX: Math.min(...newNodes.map(n => n.x)),
        maxX: Math.max(...newNodes.map(n => n.x)),
        minY: Math.min(...newNodes.map(n => n.y)),
        maxY: Math.max(...newNodes.map(n => n.y))
      };

      const structureWidth = bounds.maxX - bounds.minX + 800;
      const structureHeight = bounds.maxY - bounds.minY + 400;
      const structureCenterX = (bounds.minX + bounds.maxX) / 2;
      const structureCenterY = (bounds.minY + bounds.maxY) / 2;

      const scaleX = (canvasRect.width * 0.8) / structureWidth;
      const scaleY = (canvasRect.height * 0.8) / structureHeight;
      const newScale = Math.min(Math.min(scaleX, scaleY), 1);

      setScale(newScale);
      setTranslate({
        x: (canvasRect.width / 2) - (structureCenterX * newScale),
        y: (canvasRect.height / 2) - (structureCenterY * newScale)
      });
    }
  }, [nodes, setNodes]);

  const NODE_WIDTH = 400;
  const NODE_HEADER_HEIGHT = 80;
  const MESSAGE_PADDING = 16;

  const getConnectionPoints = (sourceNode, targetNode, expandedNodes) => {
    const isSourceExpanded = expandedNodes.has(sourceNode.id);
    const messageIndex = targetNode.parentMessageIndex || 0;

    const sourceY = isSourceExpanded
      ? sourceNode.y + NODE_HEADER_HEIGHT + (messageIndex * 120)
      : sourceNode.y + NODE_HEADER_HEIGHT / 2;
    const sourceX = sourceNode.x + NODE_WIDTH;

    const targetY = targetNode.y + NODE_HEADER_HEIGHT / 2;
    const targetX = targetNode.x;

    return {
      x1: sourceX,
      y1: sourceY,
      x2: targetX,
      y2: targetY
    };
  };

  const calculateNodesBounds = (nodes) => {
    if (!nodes.length) return null;

    return nodes.reduce((bounds, node) => {
      const nodeWidth = 256;
      const nodeHeight = 100;

      return {
        minX: Math.min(bounds.minX, node.x),
        maxX: Math.max(bounds.maxX, node.x + nodeWidth),
        minY: Math.min(bounds.minY, node.y),
        maxY: Math.max(bounds.maxY, node.y + nodeHeight)
      };
    }, {
      minX: Infinity,
      maxX: -Infinity,
      minY: Infinity,
      maxY: -Infinity
    });
  };

  const calculateIdealScale = (bounds, viewport, padding = 100) => {
    if (!bounds) return 1;

    const contentWidth = bounds.maxX - bounds.minX + padding * 2;
    const contentHeight = bounds.maxY - bounds.minY + padding * 2;

    const chatContainerWidth = getChatContainerWidth();
    const scaleX = (viewport.width - chatContainerWidth) / contentWidth;
    const scaleY = viewport.height / contentHeight;

    return Math.min(Math.min(scaleX, scaleY), 1);
  };

  const calculateCenteringTranslation = (bounds, viewport, scale, padding = 100) => {
    if (!bounds) return { x: 0, y: 0 };

    const contentWidth = (bounds.maxX - bounds.minX + padding * 2) * scale;
    const contentHeight = (bounds.maxY - bounds.minY + padding * 2) * scale;

    const chatContainerWidth = getChatContainerWidth();
    const availableWidth = viewport.width - chatContainerWidth;

    const x = (availableWidth / 2) - (bounds.minX * scale) - (contentWidth / 2) + padding * scale;
    const y = (viewport.height / 2) - (bounds.minY * scale) - (contentHeight / 2) + padding * scale;

    return { x, y };
  };

  const getBezierPath = (points) => {
    const { x1, y1, x2, y2 } = points;

    const controlOffset = Math.abs(x2 - x1) * 0.4;

    const cp1x = x1 + controlOffset;
    const cp1y = y1;
    const cp2x = x2 - controlOffset;
    const cp2y = y2;

    return `M ${x1},${y1} C ${cp1x},${cp1y} ${cp2x},${cp2y} ${x2},${y2}`;
  };

  const Connection = ({ sourceNode, targetNode, expandedNodes }) => {
    if (!sourceNode || !targetNode) return null;

    const points = getConnectionPoints(sourceNode, targetNode, expandedNodes);
    const path = getBezierPath(points);
    const opacity = expandedNodes.has(sourceNode.id) ? 1 : 0.5;

    return (
      <path
        d={path}
        className="stroke-primary dark:stroke-primary"
        style={{
          opacity,
          transition: 'all 0.2s ease-in-out'
        }}
        strokeWidth="2"
        fill="none"
      />
    );
  };

  const calculateMessageOffset = (messageIndex) => {
    const BASE_OFFSET = 80;
    const MESSAGE_HEIGHT = 120;
    const MESSAGE_PADDING = 16;
    return BASE_OFFSET + (messageIndex * (MESSAGE_HEIGHT + MESSAGE_PADDING));
  };

  const createBranch = (parentNode, template, nodes, messageIndex, position = null) => {
    const NODE_SPACING = 400;
    const newId = nodes.length > 0 ? Math.max(...nodes.map(n => n.id)) + 1 : 1;
    const contextMessages = parentNode.messages.slice(0, messageIndex + 1);

    const defaultPosition = {
      x: position?.x ?? parentNode.x + NODE_SPACING,
      y: position?.y ?? parentNode.y + calculateMessageOffset(messageIndex)
    };

    const adjustedPosition = adjustNodePosition(defaultPosition, nodes, NODE_SPACING);

    return {
      id: newId,
      messages: [parentNode.messages[messageIndex]],
      x: adjustedPosition.x,
      y: adjustedPosition.y,
      type: 'branch',
      title: template.title || `Branch ${newId}`,
      parentId: parentNode.id,
      systemPrompt: template.systemPrompt,
      collapsed: true,
      parentMessageIndex: messageIndex,
      contextMessages: contextMessages
    };
  };

  const adjustNodePosition = (position, nodes, spacing) => {
    const OVERLAP_THRESHOLD = spacing / 2;
    let adjustedPosition = { ...position };
    let hasOverlap;

    do {
      hasOverlap = false;
      for (const node of nodes) {
        const distance = Math.sqrt(
          Math.pow(node.x - adjustedPosition.x, 2) +
          Math.pow(node.y - adjustedPosition.y, 2)
        );

        if (distance < OVERLAP_THRESHOLD) {
          hasOverlap = true;
          adjustedPosition.x += spacing / 2;
          adjustedPosition.y += spacing / 4;
          break;
        }
      }
    } while (hasOverlap);

    return adjustedPosition;
  };

  const handleSelect = (nodeId) => {
    setSelectedNode(nodeId);
    setActiveThreadId(nodeId);
  };

  const getConnectedBranches = (nodeId, messageIndex) => {
    const currentNode = nodes.find(n => n.id === nodeId);
    if (!currentNode) return { left: [], right: [], parent: null };

    const parent = currentNode.parentId ? nodes.find(n => n.id === currentNode.parentId) : null;
    const parentPosition = parent ? getNodePosition(currentNode, parent) : null;

    const children = nodes.filter(n =>
      n.parentId === currentNode.id &&
      n.parentMessageIndex === messageIndex
    );

    const leftBranches = children.filter(n => n.x < currentNode.x)
      .sort((a, b) => b.x - a.x);
    const rightBranches = children.filter(n => n.x >= currentNode.x)
      .sort((a, b) => a.x - b.x);

    return {
      left: leftBranches,
      right: rightBranches,
      parent: parent ? { node: parent, position: parentPosition } : null
    };
  };

  const handleNavigation = useCallback((direction) => {
    const currentNode = nodes.find(n => n.id === selectedNode);
    if (!currentNode) return;

    const branches = getConnectedBranches(selectedNode, focusedMessageIndex);
    const siblingBranches = getSiblingBranches(selectedNode);

    switch (direction) {
      case 'up': {
        if (focusedMessageIndex > 0) {
          focusOnMessage(selectedNode, focusedMessageIndex - 1);
        } else {
          const siblingAbove = siblingBranches.reverse().find(n => n.y < currentNode.y);
          if (siblingAbove) {
            const siblingMessages = siblingAbove.messages.length;
            focusOnMessage(siblingAbove.id, Math.max(0, siblingMessages - 1));
          }
        }
        break;
      }

      case 'down': {
        if (focusedMessageIndex < currentNode.messages.length - 1) {
          focusOnMessage(selectedNode, focusedMessageIndex + 1);
        } else {
          const siblingBelow = siblingBranches.find(n => n.y > currentNode.y);
          if (siblingBelow) {
            focusOnMessage(siblingBelow.id, 0);
          }
        }
        break;
      }

      case 'left': {
        if (branches.parent?.position === 'left') {
          focusOnMessage(branches.parent.node.id, currentNode.parentMessageIndex);
        } else if (branches.left.length > 0) {
          const currentIndex = branches.left.findIndex(n => n.id === selectedNode);
          const nextIndex = currentIndex === -1 ? 0 : (currentIndex + 1) % branches.left.length;
          focusOnMessage(branches.left[nextIndex].id, 0);
        }
        break;
      }

      case 'right': {
        if (branches.parent?.position === 'right') {
          focusOnMessage(branches.parent.node.id, currentNode.parentMessageIndex);
        } else if (branches.right.length > 0) {
          const currentIndex = branches.right.findIndex(n => n.id === selectedNode);
          const nextIndex = currentIndex === -1 ? 0 : (currentIndex + 1) % branches.right.length;
          focusOnMessage(branches.right[nextIndex].id, 0);
        }
        break;
      }
    }
  }, [nodes, selectedNode, focusedMessageIndex, focusOnMessage, getConnectedBranches, getSiblingBranches]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      const isTyping = document.activeElement.tagName === 'INPUT' ||
        document.activeElement.tagName === 'TEXTAREA' ||
        document.activeElement.closest('.chat-interface');

      if (isTyping) return;

      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        setQuickInputPosition({ x: e.clientX, y: e.clientY });
        setShowQuickInput(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (document.activeElement.tagName === 'INPUT' ||
        document.activeElement.tagName === 'TEXTAREA') return;

      if (!selectedNode) return;

      const currentNode = nodes.find(n => n.id === selectedNode);
      if (!currentNode) return;

      const isShiftPressed = e.shiftKey;
      const branches = getConnectedBranches(selectedNode, focusedMessageIndex);
      const siblingBranches = getSiblingBranches(selectedNode);

      switch (e.key.toLowerCase()) {
        case 'w': {
          if (focusedMessageIndex > 0) {
            focusOnMessage(selectedNode, focusedMessageIndex - 1, isShiftPressed);
          } else {
            const siblingAbove = siblingBranches.reverse().find(n => n.y < currentNode.y);
            if (siblingAbove) {
              const siblingMessages = siblingAbove.messages.length;
              focusOnMessage(siblingAbove.id, Math.max(0, siblingMessages - 1), isShiftPressed);
            }
          }
          break;
        }

        case 's': {
          if (focusedMessageIndex < currentNode.messages.length - 1) {
            focusOnMessage(selectedNode, focusedMessageIndex + 1, isShiftPressed);
          } else {
            const siblingBelow = siblingBranches.find(n => n.y > currentNode.y);
            if (siblingBelow) {
              focusOnMessage(siblingBelow.id, 0, isShiftPressed);
            }
          }
          break;
        }

        case 'a': {
          if (branches.parent?.position === 'left') {
            focusOnMessage(branches.parent.node.id, currentNode.parentMessageIndex, isShiftPressed);
          } else if (branches.left.length > 0) {
            const currentIndex = branches.left.findIndex(n => n.id === selectedNode);
            const nextIndex = currentIndex === -1 ? 0 : (currentIndex + 1) % branches.left.length;
            focusOnMessage(branches.left[nextIndex].id, 0, isShiftPressed);
          }
          break;
        }

        case 'd': {
          if (branches.parent?.position === 'right') {
            focusOnMessage(branches.parent.node.id, currentNode.parentMessageIndex, isShiftPressed);
          } else if (branches.right.length > 0) {
            const currentIndex = branches.right.findIndex(n => n.id === selectedNode);
            const nextIndex = currentIndex === -1 ? 0 : (currentIndex + 1) % branches.right.length;
            focusOnMessage(branches.right[nextIndex].id, 0, isShiftPressed);
          }
          break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedNode, focusedMessageIndex, nodes, focusOnMessage, getConnectedBranches, getSiblingBranches]);

  const getNodePosition = (sourceNode, targetNode) => {
    return targetNode.x < sourceNode.x ? 'left' : 'right';
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      const isTyping = document.activeElement.tagName === 'INPUT' ||
        document.activeElement.tagName === 'TEXTAREA';

      if (isTyping && !e.ctrlKey && !e.metaKey) {
        return;
      }

      switch (e.key.toLowerCase()) {
        case 'c':
          centerCanvas();
          break;
        case 'o':
          if (!e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            organizeNodesIntoStack();
          }
          break;
        case 'g':
          setActiveTool('select');
          break;
        case 'h':
          setActiveTool('pan');
          break;
        case 's':
          setActiveTool('select');
          break;
        case ' ':
          if (activeTool === 'pan') {
            setActiveTool('pan');
          }
          break;
      }
    };

    const handleKeyUp = (e) => {
      const isTyping = document.activeElement.tagName === 'INPUT' ||
        document.activeElement.tagName === 'TEXTAREA';

      if (!isTyping && e.key === ' ' && activeTool === 'pan') {
        setActiveTool('select');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [centerCanvas, organizeNodesIntoStack, activeTool, isModelDropdownOpen]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.addEventListener('wheel', handleWheel, { passive: false });

    return () => {
      canvas.removeEventListener('wheel', handleWheel, { passive: false });
    };
  }, [handleWheel]);

  const handleToggleExpand = useCallback((nodeId) => {
    setExpandedNodes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  }, []);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (dragState.isDragging) {
        handleDrag(e);
      } else if (isPanning) {
        const dx = (e.clientX - lastMousePos.x) * PANNING_SENSITIVITY;
        const dy = (e.clientY - lastMousePos.y) * PANNING_SENSITIVITY;

        setTranslate(prev => ({
          x: prev.x + dx,
          y: prev.y + dy
        }));

        setLastMousePos({ x: e.clientX, y: e.clientY });
      }
    };

    const handleMouseUp = () => {
      if (dragState.isDragging) {
        handleDragEnd();
      }
      setIsPanning(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragState, isPanning, handleDrag, handleDragEnd, lastMousePos]);

  return (
    <div className="relative flex h-full bg-background overflow-hidden">
      {/* Display error message in the UI */}
      {error && (
        <div className="fixed top-4 right-4 bg-red-500 text-white p-4 rounded-lg z-50">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}
      <ChatPersistenceManager
        nodes={nodes}
        setNodes={setNodes}
        activeChat={activeChat}
        setActiveChat={setActiveChat}
        onSelectChat={handleSelectChat}
      />
      <ChatBranchPanel
        chatType={chatType}
        setChatType={setChatType}
        onDataUpdate={handleDataUpdate}
        onSelectChat={handleSelectChat}
      />
      <div
        ref={canvasRef}
        className={cn(
          "absolute inset-0 overflow-hidden select-none",
          isPanning ? "cursor-grabbing" : activeTool === "pan" ? "cursor-grab" : "cursor-default"
        )}
        onMouseDown={handleCanvasMouseDown}
        style={{ touchAction: 'none', marginLeft: '20vw' }}
      >
        <GridBackground
          translate={translate}
          scale={scale}
          className="stroke-border dark:stroke-border"
        />
        <div
          className="fixed bottom-20 z-10"
          style={{
            left: isPanelCollapsed ? '1rem' : 'calc(20vw + 1rem)'
          }}
        >
          <CanvasToolbar
            activeTool={activeTool}
            onToolSelect={handleToolSelect}
            theme={theme}
            onThemeChange={handleThemeChange}
            selectedModel={selectedModel}
            models={models}
            onModelSelect={setSelectedModel}
            isModelDropdownOpen={isModelDropdownOpen}
            setIsModelDropdownOpen={setIsModelDropdownOpen}
            modelDropdownRef={modelDropdownRef}
          />
        </div>
        <div
          className="fixed bottom-1 mx-2 z-10 flex gap-2 right: 10px width: -webkit-fill-available justify-content: space-around"
          style={{
            left: isPanelCollapsed ? '1rem' : 'calc(20vw + 1rem)'
          }}
        >
          <MessageNavigator
            currentNode={nodes.find(n => n.id === selectedNode)}
            currentIndex={focusedMessageIndex}
            totalMessages={nodes.find(n => n.id === selectedNode)?.messages.length || 0}
            onNavigate={handleNavigation}
            branches={getConnectedBranches(selectedNode, focusedMessageIndex)}
            isMessageExpanded={expandedMessages.has(focusedMessageIndex)}
            onToggleExpand={handleToggleMessageExpand}
          />
          <ModelStatus
            selectedModel={selectedModel}
            isStreaming={activeResponses.size > 0}
          />
        </div>
        {showQuickInput && (
          <FloatingInput
            position={quickInputPosition}
            onChange={handleInputChange}
            onSend={handleFloatingInputSend}
            value={inputValue}
            onClose={() => setShowQuickInput(false)}
          />
        )}
        <div
          ref={contentRef}
          className="absolute inset-0 z-0"
          style={{
            transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})`,
            transformOrigin: '0 0',
          }}
        >
          <svg
            className="absolute"
            style={{
              width: '100%',
              height: '100%',
              overflow: 'visible',
              pointerEvents: 'none'
            }}
          >
            {nodes.map((node) => {
              if (!node.parentId) return null;
              const parent = nodes.find(n => n.id === node.parentId);
              if (!parent) return null;
              return (
                <Connection
                  key={`connection-${parent.id}-${node.id}`}
                  sourceNode={parent}
                  targetNode={node}
                  expandedNodes={expandedNodes}
                />
              );
            })}
          </svg>
          {nodes.map((node) => (
            <BranchNode
              key={`node-${node.id}-${node.branchId || '0'}`}
              node={node}
              nodes={nodes}
              isExpanded={expandedNodes.has(node.id)}
              isSelected={selectedNode === node.id}
              onToggleExpand={() => handleToggleExpand(node.id)}
              onSelect={() => handleSelect(node.id)}
              onDelete={() => handleDeleteNode(node.id)}
              onDragStart={handleDragStart}
              onCreateBranch={onCreateBranch}
              selectedModel={selectedModel}
              currentMessageIndex={node.id === selectedNode ? focusedMessageIndex : null}
              branchId={node.branchId || '0'}
              expandedMessages={expandedMessages}
              onToggleMessageExpand={handleToggleMessageExpand}
              onUpdateTitle={handleUpdateTitle}
              isActiveThread={node.id === activeThreadId}
              onFocusMessage={focusOnMessage}
              getConnectedBranches={getConnectedBranches}
            />
          ))}
        </div>
      </div>
      <ChatContainer>
  <ModelStatus
    selectedModel={selectedModel}
    isStreaming={activeResponses.size > 0}
  />
  <ChatInterface
    node={nodes.find(n => n.id === selectedNode)}
    messages={getFullMessageHistory(selectedNode)}
    onSendMessage={handleSendMessage}
    onCreateBranch={onCreateBranch}
    isExpanded={expandedNodes.has(selectedNode)}
    isLoading={activeResponses.has(selectedNode)}
    streamingContent={nodes.find(n => n.id === selectedNode)?.streamingContent}
    containerWidth={getChatContainerWidth()}
    onSizeChange={setChatContainerSize}
    isPanelCollapsed={isPanelCollapsed}
    input={inputValue}            {/* <-- ADD THIS */}
    onInputChange={handleInputChange}  {/* <-- ADD THIS */}
  />
</ChatContainer>


    </div>
  );
};

export default TangentChat;
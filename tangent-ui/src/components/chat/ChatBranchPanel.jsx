// src/components/chat/ChatBranchPanel.jsx

import React, { useState, useEffect, useCallback } from 'react';
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow';
import 'reactflow/dist/style.css';
import { cn } from '../../utils/utils';

// Custom node component with animations
const CustomNode = ({ data, selected }) => {
  return (
    <div
      className={cn(
        "px-4 py-2 rounded-lg shadow-md border-2 transition-all duration-300 ease-in-out",
        "transform hover:scale-105 hover:shadow-xl",
        selected
          ? "border-blue-500 bg-blue-100 dark:bg-blue-900 animate-pulse"
          : "border-gray-300 bg-white dark:bg-gray-800",
        "animate-node-entry" // Entry animation class
      )}
      style={{ minWidth: '150px', maxWidth: '200px' }}
    >
      <div className="text-sm font-medium text-gray-800 dark:text-gray-200">
        {data.label}
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
        {data.timestamp}
      </div>
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

// Inline CSS for animations
const styles = `
  @keyframes nodeEntry {
    0% {
      opacity: 0;
      transform: scale(0.8);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }

  @keyframes dashdraw {
    to {
      stroke-dashoffset: 0;
    }
  }

  .animate-node-entry {
    animation: nodeEntry 0.5s ease-out forwards;
  }

  .react-flow__edge-path {
    stroke-dasharray: 5;
    stroke-dashoffset: 100;
    animation: dashdraw 2s linear infinite;
  }
`;

const ChatBranchPanel = ({ chatType, setChatType, onDataUpdate, onSelectChat }) => {
  const [branchedChats, setBranchedChats] = useState({});
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedChat, setSelectedChat] = useState(null);
  const [availableChats, setAvailableChats] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);

  // Inject animation styles into the document
  useEffect(() => {
    const styleSheet = document.createElement("style");
    styleSheet.type = "text/css";
    styleSheet.innerText = styles;
    document.head.appendChild(styleSheet);
    return () => {
      document.head.removeChild(styleSheet);
    };
  }, []);

  // Fetch available chats (using mock data for now)
  const fetchChats = useCallback(async () => {
    const mockChats = {
      success: true,
      chats: [
        { id: "chat_1", title: "Chat 1" },
        { id: "chat_2", title: "Chat 2" },
      ],
    };
    setAvailableChats(mockChats.chats);
  }, []);

  // Fetch branching data for the selected chat type (using mock data)
  const fetchBranchedMessages = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const mockData = {
      branched_chats: {
        chat_1: {
          main_branch: [
            {
              message_id: "msg1",
              text: "Hello, how can I help you?",
              timestamp: "2025-04-25T10:00:00Z",
              role: "assistant",
            },
            {
              message_id: "msg2",
              text: "Tell me about React Flow",
              timestamp: "2025-04-25T10:01:00Z",
              role: "user",
            },
          ],
          branches: {
            branch_1: {
              parent_message: { message_id: "msg2" },
              branch_messages: [
                {
                  message_id: "msg3",
                  text: "React Flow is a library for building node-based UIs.",
                  timestamp: "2025-04-25T10:02:00Z",
                  role: "assistant",
                },
              ],
            },
          },
        },
      },
      stats: {
        total_chats_analyzed: 1,
        total_branched_chats: 1,
        total_messages_processed: 3,
      },
    };

    setBranchedChats(mockData.branched_chats || {});
    setStats(mockData.stats || null);
    onDataUpdate(mockData);

    // Transform mock data into nodes and edges
    const newNodes = [];
    const newEdges = [];
    let nodeIdCounter = 0;

    Object.entries(mockData.branched_chats || {}).forEach(([chatName, chatData], chatIndex) => {
      const { main_branch, branches } = chatData;

      // Add main branch nodes with animation delay
      main_branch.forEach((msg, msgIndex) => {
        const nodeId = `main-${chatName}-${msg.message_id}-${nodeIdCounter++}`;
        newNodes.push({
          id: nodeId,
          type: 'custom',
          data: {
            label: msg.text.slice(0, 50) + (msg.text.length > 50 ? '...' : ''),
            timestamp: new Date(msg.timestamp).toLocaleTimeString(),
            chatName,
            branchId: '0',
            message: msg,
          },
          position: { x: 0, y: (chatIndex * 400) + (msgIndex * 100) },
          style: { animationDelay: `${msgIndex * 0.2}s` }, // Stagger entry animation
        });

        // Connect main branch nodes with custom edge animation
        if (msgIndex > 0) {
          const prevNodeId = `main-${chatName}-${main_branch[msgIndex - 1].message_id}-${nodeIdCounter - 2}`;
          newEdges.push({
            id: `edge-${prevNodeId}-${nodeId}`,
            source: prevNodeId,
            target: nodeId,
            animated: true,
            style: {
              stroke: '#888',
              strokeWidth: 2,
            },
          });
        }
      });

      // Add branch nodes
      Object.entries(branches).forEach(([branchId, branchData], branchIndex) => {
        const { parent_message, branch_messages } = branchData;
        if (!parent_message) return;

        const parentNodeId = newNodes.find(
          (node) => node.data.message.message_id === parent_message.message_id
        )?.id;
        if (!parentNodeId) return;

        branch_messages.forEach((msg, msgIndex) => {
          const nodeId = `branch-${chatName}-${branchId}-${msg.message_id}-${nodeIdCounter++}`;
          newNodes.push({
            id: nodeId,
            type: 'custom',
            data: {
              label: msg.text.slice(0, 50) + (msg.text.length > 50 ? '...' : ''),
              timestamp: new Date(msg.timestamp).toLocaleTimeString(),
              chatName,
              branchId,
              message: msg,
            },
            position: { x: (branchIndex + 1) * 250, y: (chatIndex * 400) + (msgIndex * 100) },
            style: { animationDelay: `${(msgIndex + main_branch.length) * 0.2}s` },
          });

          if (msgIndex === 0) {
            newEdges.push({
              id: `edge-${parentNodeId}-${nodeId}`,
              source: parentNodeId,
              target: nodeId,
              animated: true,
              style: {
                stroke: '#ff5555',
                strokeWidth: 2,
              },
            });
          } else {
            const prevNodeId = `branch-${chatName}-${branchId}-${branch_messages[msgIndex - 1].message_id}-${nodeIdCounter - 2}`;
            newEdges.push({
              id: `edge-${prevNodeId}-${nodeId}`,
              source: prevNodeId,
              target: nodeId,
              animated: true,
              style: {
                stroke: '#888',
                strokeWidth: 2,
              },
            });
          }
        });
      });
    });

    setNodes(newNodes);
    setEdges(newEdges);
    setIsLoading(false);
  }, [chatType, onDataUpdate]);

  useEffect(() => {
    fetchChats();
    fetchBranchedMessages();
  }, [fetchChats, fetchBranchedMessages]);

  const handleChatTypeChange = (e) => {
    setChatType(e.target.value);
  };

  const handleChatSelect = async (chat) => {
    setSelectedChat(chat.id);
    try {
      const response = await fetch(`https://open-i0or.onrender.com/api/chats/load/${chat.id}`);
      const data = await response.json();
      if (data.success) {
        onSelectChat(data.data);
      } else {
        setError('Failed to load chat');
      }
    } catch (err) {
      setError('Error loading chat: ' + err.message);
    }
  };

  const handleNodeClick = (event, node) => {
    const { chatName, branchId, message } = node.data;
    const chatData = branchedChats[chatName];
    if (!chatData) return;

    const branchMessages = branchId === '0' ? chatData.main_branch : chatData.branches[branchId]?.branch_messages || [];

    onSelectChat({
      id: chatName,
      title: chatName,
      nodes: [
        {
          id: 1,
          type: 'main',
          title: chatName,
          messages: branchMessages,
          x: 50,
          y: 150,
        },
      ],
    });
  };

  return (
    <div className="fixed left-0 top-0 h-full w-[20vw] bg-gray-100 dark:bg-gray-900 p-4 overflow-y-auto shadow-lg">
      <h2 className="text-xl font-bold text-gray-800 dark:text-gray-200 mb-4">Chat Branches</h2>

      {/* Chat Type Selector */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Chat Type
        </label>
        <select
          value={chatType}
          onChange={handleChatTypeChange}
          className="w-full p-2 border rounded-md bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200"
        >
          <option value="chatgpt">ChatGPT</option>
          <option value="claude">Claude</option>
        </select>
      </div>

      {/* Available Chats */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-2">Available Chats</h3>
        {availableChats.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">No chats available</p>
        ) : (
          <ul className="space-y-2">
            {availableChats.map((chat) => (
              <li key={chat.id}>
                <button
                  onClick={() => handleChatSelect(chat)}
                  className={cn(
                    "w-full text-left p-2 rounded-md transition-colors",
                    selectedChat === chat.id
                      ? "bg-blue-500 text-white"
                      : "bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600"
                  )}
                >
                  {chat.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Node Graph Visualization */}
      <div className="relative h-[60vh] w-full">
        {isLoading ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading...</p>
        ) : error ? (
          <p className="text-sm text-red-500">{error}</p>
        ) : nodes.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">No branches to display</p>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={handleNodeClick}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            maxZoom={2}
            defaultViewport={{ x: 0, y: 0, zoom: 1 }}
            className="bg-gray-200 dark:bg-gray-800 rounded-lg"
          >
            <Background color="#aaa" gap={16} />
            <Controls />
            <MiniMap nodeColor={(node) => (node.data.branchId === '0' ? '#1a73e8' : '#ff5555')} />
          </ReactFlow>
        )}
      </div>

      {/* Stats (Optional) */}
      {stats && (
        <div className="mt-4">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-2">Stats</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Total Chats: {stats.total_chats_analyzed}
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Branched Chats: {stats.total_branched_chats}
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Total Messages: {stats.total_messages_processed}
          </p>
        </div>
      )}
    </div>
  );
};

export default ChatBranchPanel;
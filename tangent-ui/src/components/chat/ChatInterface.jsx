import React, { useEffect, useRef } from 'react';
import { Send } from 'lucide-react';
import { ScrollArea } from '../core/scroll-area';
import { Input } from '../core/input';
import { Button } from '../core/button';
import { ChatMessage } from './ChatMessage';
import { cn } from '../../utils/utils';

const ChatInterface = ({
  messages,
  input,
  isLoading,
  onInputChange,
  onSend,
  streamingMessage,
  continuationCount,
  activeNode,
  expandedMessages,
  onToggleMessageExpand,
}) => {
  const scrollRef = useRef(null);
  const messageEndRef = useRef(null);

  const scrollToBottom = () => {
    if (messageEndRef.current) {
      messageEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  const handleSend = () => {
    if (input.trim() && !isLoading) {
      onSend(activeNode.id, input);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-4">
          {messages.map((message, index) => {
            const isExpanded = !expandedMessages.has(index);
            return (
              <ChatMessage
                key={`${message.role}-${index}`}
                message={{
                  ...message,
                  isStreaming: message.isStreaming || (index === messages.length - 1 && streamingMessage),
                  content: index === messages.length - 1 && streamingMessage ? streamingMessage : message.content,
                  continuationCount: index === messages.length - 1 ? continuationCount : message.continuationCount,
                }}
                isCollapsed={isExpanded}
                onClick={() => onToggleMessageExpand(index)}
              />
            );
          })}
          <div ref={messageEndRef} />
        </div>
      </ScrollArea>

      <div className="p-4 border-t">
        <div className="flex items-center gap-2">
          <Input
            value={input}
            onChange={onInputChange}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            className="flex-1"
            disabled={isLoading}
          />
          <Button onClick={handleSend} disabled={isLoading || !input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
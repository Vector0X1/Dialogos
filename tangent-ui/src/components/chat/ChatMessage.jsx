import React, { useState, useEffect, useRef } from 'react';
import { Check, ChevronDown, Send, Loader2, ChevronUp, Sparkles, Play, Pause } from 'lucide-react';
import { cn } from '../../utils/utils';

const API_URL = 'https://api.elevenlabs.io/v1/text-to-speech';
const TTS_CHUNK_SIZE = 1024;

const splitIntoSentences = (text) => {
  return text.match(/[^.!?\n]+[.!?\n]+/g) || [text];
};

const createChunks = (sentences, maxChunkSize = TTS_CHUNK_SIZE) => {
  const chunks = [];
  let currentChunk = '';

  for (const sentence of sentences) {
    if ((currentChunk + sentence).length > maxChunkSize && currentChunk) {
      chunks.push(currentChunk.trim());
      currentChunk = '';
    }
    currentChunk += sentence;
  }

  if (currentChunk) {
    chunks.push(currentChunk.trim());
  }

  return chunks;
};

const renderContinuationIndicator = (message) => {
  if (!message.continuationCount) return null;

  return (
    <div className="text-xs font-medium text-muted-foreground mt-2 flex items-center gap-2">
      <div className="flex gap-1">
        {[...Array(message.continuationCount)].map((_, i) => (
          <Sparkles key={i} className="w-3 h-3 text-primary" />
        ))}
      </div>
      {message.continuationCount > 1 &&
        `${message.continuationCount} continuations`}
    </div>
  );
};

export const ChatMessage = ({
  message,
  isCollapsed,
  onClick,
  voiceId = "21m00Tcm4TlvDq8ikWAM",
  apiKey = "----"
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentChunkIndex, setCurrentChunkIndex] = useState(0);
  const [audioQueue, setAudioQueue] = useState([]);
  const [playbackProgress, setPlaybackProgress] = useState(0);
  const audioRef = useRef(null);
  const chunksRef = useRef([]);

  const needsCollapse = message.content?.length > 150;
  const isStreaming = message.isStreaming || false;
  const isTranscribing = message.isTranscribing || false;

  const generateSpeechForChunk = async (text) => {
    try {
      const response = await fetch(`${API_URL}/${voiceId}`, {
        method: 'POST',
        headers: {
          'Accept': 'audio/mpeg',
          'Content-Type': 'application/json',
          'xi-api-key': apiKey
        },
        body: JSON.stringify({
          text,
          model_id: "eleven_monolingual_v1",
          voice_settings: {
            stability: 0.5,
            similarity_boost: 0.5
          }
        })
      });

      if (!response.ok) {
        throw new Error('Failed to generate speech');
      }

      const audioBlob = await response.blob();
      return URL.createObjectURL(audioBlob);
    } catch (error) {
      console.error('Error generating speech for chunk:', error);
      return null;
    }
  };

  const handlePlayPause = async () => {
    if (isPlaying) {
      audioRef.current?.pause();
      setIsPlaying(false);
      setCurrentChunkIndex(0);
      setAudioQueue([]);
      setPlaybackProgress(0);
    } else {
      setIsPlaying(true);

      if (chunksRef.current.length === 0) {
        const sentences = splitIntoSentences(message.content);
        chunksRef.current = createChunks(sentences);
      }

      if (audioQueue.length === 0) {
        const audioUrl = await generateSpeechForChunk(chunksRef.current[0]);
        if (audioUrl) {
          setAudioQueue([audioUrl]);
          playChunk(audioUrl);
        }
      }
    }
  };

  const playChunk = (audioUrl) => {
    if (audioRef.current) {
      audioRef.current.src = audioUrl;
      audioRef.current.play();
    }
  };

  const handleAudioEnd = async () => {
    if (audioQueue[0]) {
      URL.revokeObjectURL(audioQueue[0]);
    }

    const nextChunkIndex = currentChunkIndex + 1;
    if (nextChunkIndex < chunksRef.current.length) {
      setCurrentChunkIndex(nextChunkIndex);

      const nextAudioUrl = await generateSpeechForChunk(chunksRef.current[nextChunkIndex]);
      if (nextAudioUrl) {
        setAudioQueue([nextAudioUrl]);
        playChunk(nextAudioUrl);
      }

      setPlaybackProgress(Math.round((nextChunkIndex / chunksRef.current.length) * 100));
    } else {
      setIsPlaying(false);
      setCurrentChunkIndex(0);
      setAudioQueue([]);
      setPlaybackProgress(0);
    }
  };

  useEffect(() => {
    return () => {
      audioQueue.forEach(url => URL.revokeObjectURL(url));
      setAudioQueue([]);
    };
  }, [audioQueue]);

  return (
    <div className={cn(
      "relative group flex gap-3 items-start",
      message.role === "user" ? "justify-end" : "justify-start"
    )}>
      <div
        className={cn(
          "relative max-w-[80%] rounded-lg px-4 py-2 text-sm",
          message.role === "user"
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
          isStreaming && "animate-pulse"
        )}
        onClick={onClick}
      >
        {isStreaming ? (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Generating...</span>
          </div>
        ) : isTranscribing ? (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Transcribing...</span>
          </div>
        ) : (
          <>
            {needsCollapse && isCollapsed ? (
              <div className="flex items-center gap-2 cursor-pointer">
                <span className="line-clamp-2">{message.content}</span>
                <ChevronDown className="h-4 w-4" />
              </div>
            ) : (
              <div className="whitespace-pre-wrap">
                {message.content}
                {needsCollapse && (
                  <div className="flex justify-end mt-2">
                    <ChevronUp className="h-4 w-4 cursor-pointer" />
                  </div>
                )}
              </div>
            )}
            {renderContinuationIndicator(message)}
          </>
        )}
      </div>

      {message.role === "assistant" && !isStreaming && !isTranscribing && (
        <button
          onClick={handlePlayPause}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-2 rounded-full hover:bg-muted"
        >
          {isPlaying ? (
            <Pause className="h-4 w-4" />
          ) : (
            <Play className="h-4 w-4" />
          )}
        </button>
      )}

      <audio
        ref={audioRef}
        onEnded={handleAudioEnd}
        onError={(e) => console.error("Audio playback error:", e)}
      />

      {isPlaying && (
        <div className="absolute bottom-0 left-0 w-full h-1 bg-muted">
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${playbackProgress}%` }}
          />
        </div>
      )}
    </div>
  );
};

export default ChatMessage;
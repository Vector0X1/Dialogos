import React, { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Button, Input } from "../index";

const ChatUI = ({ topic, model, onBack }) => {
  const [messages, setMessages] = useState([
    { role: "system", content: `You are now discussing: ${topic}` },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [useFallback, setUseFallback] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const newMessages = [...messages, { role: "user", content: input }];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      let apiUrl = useFallback ? "https://open-i0or.onrender.com/api/generate" : "http://localhost:11434/api/chat";
      let payload = useFallback
        ? { prompt: newMessages.map(msg => `${msg.role === 'user' ? 'Human' : 'Assistant'}: ${msg.content}`).join('\n') + '\n\nHuman: ' + input + '\n\nAssistant:', model: model || "gpt-4o-mini" }
        : { model: model || "qwen2.5-coder:7b", messages: newMessages, stream: false };

      const response = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }

      const data = await response.json();
      let responseContent = useFallback ? data.response || data.message?.content : data.message?.content;

      if (responseContent) {
        setMessages([
          ...newMessages,
          { role: "assistant", content: responseContent },
        ]);
      } else {
        throw new Error("No response content received");
      }
    } catch (error) {
      console.error("Error during chat:", error);
      let errorMessage = "Failed to send message. Please try again.";

      if (error.message.includes("Failed to fetch") && !useFallback) {
        setUseFallback(true);
        try {
          const fallbackResponse = await fetch("https://open-i0or.onrender.com/api/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              prompt: newMessages.map(msg => `${msg.role === 'user' ? 'Human' : 'Assistant'}: ${msg.content}`).join('\n') + '\n\nHuman: ' + input + '\n\nAssistant:',
              model: model || "gpt-4o-mini",
            }),
          });

          if (!fallbackResponse.ok) {
            throw new Error(`HTTP error! Status: ${fallbackResponse.status}`);
          }

          const fallbackData = await fallbackResponse.json();
          const responseContent = fallbackData.response || fallbackData.message?.content;

          if (responseContent) {
            setMessages([
              ...newMessages,
              { role: "assistant", content: responseContent },
            ]);
            return;
          }
        } catch (fallbackError) {
          errorMessage = "Request to the local server was blocked, and the fallback server also failed. " +
                         "This might be due to an ad blocker or browser extension. " +
                         "Please disable ad blockers, try Incognito Mode, or ensure the local server (Ollama) is running on http://localhost:11434.";
        }
      }

      setMessages([
        ...newMessages,
        { role: "assistant", content: errorMessage },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">{topic}</h2>
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="h-5 w-5" />
          Back
        </Button>
      </div>
      <div className="border rounded-lg p-4 h-96 overflow-y-auto">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`mb-4 ${msg.role === "user" ? "text-right" : "text-left"}`}
          >
            <div
              className={`inline-block px-4 py-2 rounded-lg ${
                msg.role === "user" ? "bg-primary text-white" : "bg-gray-200 text-black"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="text-left">
            <div className="inline-block px-4 py-2 rounded-lg bg-gray-200 text-black">
              Typing...
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          onKeyPress={(e) => {
            if (e.key === "Enter") {
              sendMessage();
            }
          }}
        />
        <Button onClick={sendMessage} disabled={loading}>
          Send
        </Button>
      </div>
    </div>
  );
};

export default ChatUI;
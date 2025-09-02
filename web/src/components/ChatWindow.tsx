import React from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatWindowProps {
  messages: Message[];
}

export default function ChatWindow({ messages }: ChatWindowProps) {
  return (
    <div className="panel" style={{ flex: 1, padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
      {messages.map((msg, idx) => (
        <div
          key={idx}
          className={`chat-bubble ${msg.role}`}
          dangerouslySetInnerHTML={{ __html: msg.content }}
        />
      ))}
    </div>
  );
}

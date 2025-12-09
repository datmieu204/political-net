# chatbot/serve_app.py

from typing import List, Dict, Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from langserve import add_routes
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field

from chatbot.graph.graph import build_chatgraph

# 1) Build compiled graph (Runnable[dict, dict])
graph = build_chatgraph()


# 2) Định nghĩa schema I/O cho API (Pydantic v2 models)
class ChatbotInput(BaseModel):
    """Input schema cho chatbot"""
    user_input: str = Field(..., description="Câu hỏi của người dùng")
    

class ChatbotOutput(BaseModel):
    """Output schema cho chatbot"""
    assistant_output: str = Field(default="", description="Câu trả lời của chatbot")


# 3) Bọc graph.invoke thành RunnableLambda + khai báo type
def invoke_chatbot(inp) -> dict:
    """Invoke chatbot và trả về output formatted"""
    # Handle both dict and Pydantic model input
    if isinstance(inp, dict):
        user_input = inp.get("user_input", "")
    else:
        user_input = inp.user_input
    
    result = graph.invoke({
        "user_input": user_input,
        "history": [],
    })
    return {
        "assistant_output": result.get("assistant_output", ""),
    }

chatbot_runnable = RunnableLambda(invoke_chatbot).with_types(
    input_type=ChatbotInput,
    output_type=ChatbotOutput,
)

# 4) Tạo FastAPI app
app = FastAPI(
    title="PoliticalNet Chatbot API",
    version="0.1.0",
    description="Chatbot hỏi đáp về chính trị gia Việt Nam với hỗ trợ multi-hop reasoning"
)

# CORS middleware để cho phép frontend truy cập
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 5) Add LangServe routes với playground enabled
add_routes(
    app,
    chatbot_runnable,
    path="/chat",
    enable_feedback_endpoint=True,
    enable_public_trace_link_endpoint=True,
)


# 6) Custom chat UI tại trang chủ
CHAT_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PoliticalNet Chatbot</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .chat-container {
            width: 100%;
            max-width: 800px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .chat-header {
            background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 20px 25px;
            text-align: center;
        }
        .chat-header h1 { font-size: 1.5rem; margin-bottom: 5px; }
        .chat-header p { font-size: 0.9rem; opacity: 0.9; }
        .chat-messages {
            height: 450px;
            overflow-y: auto;
            padding: 20px;
            background: #f8fafc;
        }
        .message {
            margin-bottom: 15px;
            display: flex;
            flex-direction: column;
        }
        .message.user { align-items: flex-end; }
        .message.assistant { align-items: flex-start; }
        .message-content {
            max-width: 80%;
            padding: 12px 18px;
            border-radius: 18px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .user .message-content {
            background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            border-bottom-right-radius: 5px;
        }
        .assistant .message-content {
            background: white;
            color: #1e293b;
            border: 1px solid #e2e8f0;
            border-bottom-left-radius: 5px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .message-time {
            font-size: 0.75rem;
            color: #94a3b8;
            margin-top: 4px;
            padding: 0 5px;
        }
        .chat-input-container {
            display: flex;
            padding: 20px;
            background: white;
            border-top: 1px solid #e2e8f0;
            gap: 10px;
        }
        .chat-input {
            flex: 1;
            padding: 12px 18px;
            border: 2px solid #e2e8f0;
            border-radius: 25px;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }
        .chat-input:focus { border-color: #7c3aed; }
        .send-button {
            padding: 12px 25px;
            background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .send-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(124, 58, 237, 0.4);
        }
        .send-button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .typing-indicator {
            display: none;
            padding: 12px 18px;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            margin-bottom: 15px;
        }
        .typing-indicator.show { display: inline-block; }
        .typing-indicator span {
            display: inline-block;
            width: 8px;
            height: 8px;
            margin: 0 2px;
            background: #94a3b8;
            border-radius: 50%;
            animation: typing 1s infinite;
        }
        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
        }
        .example-queries {
            padding: 15px 20px;
            background: #f1f5f9;
            border-top: 1px solid #e2e8f0;
        }
        .example-queries p {
            font-size: 0.85rem;
            color: #64748b;
            margin-bottom: 8px;
        }
        .example-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .example-btn {
            padding: 6px 12px;
            background: white;
            border: 1px solid #cbd5e1;
            border-radius: 15px;
            font-size: 0.8rem;
            color: #475569;
            cursor: pointer;
            transition: all 0.2s;
        }
        .example-btn:hover {
            background: #7c3aed;
            color: white;
            border-color: #7c3aed;
        }
        .links {
            text-align: center;
            padding: 10px;
            background: #f8fafc;
            border-top: 1px solid #e2e8f0;
        }
        .links a {
            color: #7c3aed;
            text-decoration: none;
            margin: 0 10px;
            font-size: 0.85rem;
        }
        .links a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>🏛️ PoliticalNet Chatbot</h1>
            <p>Hỏi đáp về chính trị gia Việt Nam</p>
        </div>
        <div class="chat-messages" id="chatMessages">
            <div class="message assistant">
                <div class="message-content">Xin chào! Tôi là chatbot hỗ trợ hỏi đáp về chính trị gia Việt Nam. Bạn có thể hỏi tôi về tiểu sử, quê quán, các chức vụ,... của các chính trị gia.</div>
            </div>
        </div>
        <div class="example-queries">
            <p>💡 Câu hỏi mẫu:</p>
            <div class="example-buttons">
                <button class="example-btn" onclick="setExample('Nguyễn Phú Trọng sinh năm bao nhiêu?')">Năm sinh</button>
                <button class="example-btn" onclick="setExample('Những ai có cùng quê với Nguyễn Phú Trọng?')">Cùng quê</button>
                <button class="example-btn" onclick="setExample('Ai là người tiền nhiệm của Tô Lâm ở chức vụ Chủ tịch nước?')">Tiền nhiệm</button>
                <button class="example-btn" onclick="setExample('Phạm Minh Chính từng giữ những chức vụ gì?')">Chức vụ</button>
            </div>
        </div>
        <div class="chat-input-container">
            <input type="text" class="chat-input" id="chatInput" placeholder="Nhập câu hỏi của bạn..." onkeypress="handleKeyPress(event)">
            <button class="send-button" id="sendButton" onclick="sendMessage()">Gửi</button>
        </div>
        <div class="links">
            <a href="/docs" target="_blank">📄 API Docs</a>
            <a href="/chat/playground" target="_blank">🎮 LangServe Playground</a>
        </div>
    </div>

    <script>
        const chatMessages = document.getElementById('chatMessages');
        const chatInput = document.getElementById('chatInput');
        const sendButton = document.getElementById('sendButton');
        let history = [];

        function setExample(text) {
            chatInput.value = text;
            chatInput.focus();
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }

        function addMessage(content, isUser) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.textContent = content;
            
            const timeDiv = document.createElement('div');
            timeDiv.className = 'message-time';
            timeDiv.textContent = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
            
            messageDiv.appendChild(contentDiv);
            messageDiv.appendChild(timeDiv);
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function showTyping() {
            const typingDiv = document.createElement('div');
            typingDiv.id = 'typingIndicator';
            typingDiv.className = 'typing-indicator show';
            typingDiv.innerHTML = '<span></span><span></span><span></span>';
            chatMessages.appendChild(typingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function hideTyping() {
            const typingDiv = document.getElementById('typingIndicator');
            if (typingDiv) typingDiv.remove();
        }

        async function sendMessage() {
            const message = chatInput.value.trim();
            if (!message) return;

            // Disable input
            chatInput.disabled = true;
            sendButton.disabled = true;
            chatInput.value = '';

            // Add user message
            addMessage(message, true);
            showTyping();

            try {
                const response = await fetch('/chat/invoke', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        input: {
                            user_input: message,
                            history: history
                        }
                    })
                });

                const data = await response.json();
                hideTyping();

                if (data.output) {
                    const assistantOutput = data.output.assistant_output || data.output;
                    addMessage(assistantOutput, false);
                    
                    // Update history
                    history.push({ role: 'user', content: message });
                    history.push({ role: 'assistant', content: assistantOutput });
                    
                    // Keep only last 10 exchanges
                    if (history.length > 20) {
                        history = history.slice(-20);
                    }
                } else {
                    addMessage('Xin lỗi, có lỗi xảy ra. Vui lòng thử lại.', false);
                }
            } catch (error) {
                hideTyping();
                console.error('Error:', error);
                addMessage('Xin lỗi, không thể kết nối đến server. Vui lòng thử lại.', false);
            }

            // Enable input
            chatInput.disabled = false;
            sendButton.disabled = false;
            chatInput.focus();
        }
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def root():
    """Trang chủ với giao diện chat"""
    return CHAT_HTML


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "PoliticalNet LangServe is running"}

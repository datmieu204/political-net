// Lấy element
const chatContainer = document.querySelector(".chatbot-popup");
const chatBody = document.querySelector(".chat-body");
const messageInput = document.querySelector(".message-input");
const sendMessageButton = document.querySelector("#send-message");
const fileUploadButton = document.querySelector("#file-upload");
const fileInput = document.querySelector("#file-input");
const closeChatbotButton = document.querySelector("#close-chatbot");

// Key lưu lịch sử
const STORAGE_KEY = "chat_history_v1";

// SVG avatar bot
const BOT_AVATAR_SVG = `
  <svg
    class="bot-avatar"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 1024 1024"
  >
    <path
      d="M738.3 287.6H285.7c-59 0-106.8 47.8-106.8 106.8v303.1c0 59 47.8 106.8 106.8 106.8h81.5v111.1c0 .7.8 1.1 1.4.7l166.9-110.6 41.8-.8h117.4l43.6-.4c59 0 106.8-47.8 106.8-106.8V394.5c0-59-47.8-106.9-106.8-106.9zM351.7 448.2c0-29.5 23.9-53.5 53.5-53.5s53.5 23.9 53.5 53.5-23.9 53.5-53.5 53.5-53.5-23.9-53.5-53.5zm157.9 267.1c-67.8 0-123.8-47.5-132.3-109h264.6c-8.6 61.5-64.5 109-132.3 109zm110-213.7c-29.5 0-53.5-23.9-53.5-53.5s23.9-53.5 53.5-53.5 53.5 23.9 53.5 53.5-23.9 53.5-53.5 53.5zM867.2 644.5V453.1h26.5c19.4 0 35.1 15.7 35.1 35.1v121.1c0 19.4-15.7 35.1-35.1 35.1h-26.5zM95.2 609.4V488.2c0-19.4 15.7-35.1 35.1-35.1h26.5v191.3h-26.5c-19.4 0-35.1-15.7-35.1-35.1zM561.5 149.6c0 23.4-15.6 43.3-36.9 49.7v44.9h-30v-44.9c-21.4-6.5-36.9-26.3-36.9-49.7 0-28.6 23.3-51.9 51.9-51.9s51.9 23.3 51.9 51.9z"
    ></path>
  </svg>
`;

// ===== Lịch sử chat =====
const loadChatHistory = () => {
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved ? JSON.parse(saved) : [];
};

const saveChatHistory = () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
};

// dạng: { html, classes }
let chatHistory = loadChatHistory();

// Tạo bubble element
const createMessageElement = (html, classes) => {
  const div = document.createElement("div");
  div.classList.add("message", classes);
  div.innerHTML = html;
  return div;
};

// Render lịch sử chat
const renderChatHistory = () => {
  chatBody.innerHTML = "";
  chatHistory.forEach((msg) => {
    const el = createMessageElement(msg.html, msg.classes);
    chatBody.appendChild(el);
  });
  chatBody.scrollTop = chatBody.scrollHeight;
};

// Nếu chưa có lịch sử -> thêm câu chào
if (!chatHistory.length) {
  const greetingHtml = `
    ${BOT_AVATAR_SVG}
    <div class="message-text">
      Xin chào, tôi có thể giúp gì cho bạn?
    </div>
  `;
  chatHistory.push({ html: greetingHtml, classes: "message-bot" });
  saveChatHistory();
}
renderChatHistory();

// ===== Bot typing + mock API =====
const addBotThinking = () => {
  const html = `
    ${BOT_AVATAR_SVG}
    <div class="message-text">
      <div class="thinking-indicator">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
      </div>
    </div>
  `;
  const div = createMessageElement(html, "message-bot");
  chatBody.appendChild(div);
  chatBody.scrollTop = chatBody.scrollHeight;
  return div;
};

const callMockAPI = async (thinkingDiv) => {
  try {
    const res = await fetch("https://dummyjson.com/quotes/random");
    const data = await res.json();
    const reply = data.quote || "Bot đang lỗi nhẹ, thử lại sau nha 🙂";

    const botHtml = `
      ${BOT_AVATAR_SVG}
      <div class="message-text">${reply}</div>
    `;

    thinkingDiv.innerHTML = botHtml;

    chatHistory.push({ html: botHtml, classes: "message-bot" });
    saveChatHistory();
  } catch (err) {
    const errorHtml = `
      ${BOT_AVATAR_SVG}
      <div class="message-text">Lỗi API mock: ${err.message}</div>
    `;
    thinkingDiv.innerHTML = errorHtml;

    chatHistory.push({ html: errorHtml, classes: "message-bot" });
    saveChatHistory();
  }

  chatBody.scrollTop = chatBody.scrollHeight;
};

// ===== Gửi text =====
const sendTextMessage = () => {
  const msg = messageInput.value.trim();
  if (!msg) return;

  const userHtml = `<div class="message-text">${msg}</div>`;
  const userBubble = createMessageElement(userHtml, "message-user");
  chatBody.appendChild(userBubble);
  chatBody.scrollTop = chatBody.scrollHeight;

  chatHistory.push({ html: userHtml, classes: "message-user" });
  saveChatHistory();

  messageInput.value = "";
  messageInput.focus();

  const thinkingDiv = addBotThinking();
  callMockAPI(thinkingDiv);
};

// Enter để gửi
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendTextMessage();
  }
});

// Nút gửi
sendMessageButton.addEventListener("click", (e) => {
  e.preventDefault();
  sendTextMessage();
});

// ===== Upload file =====
fileUploadButton.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    let html = "";

    if (file.type.startsWith("image/")) {
      html = `
        <div class="message-text">
          <div style="font-size:0.8rem;opacity:0.8;margin-bottom:4px;">
            📎 ${file.name}
          </div>
          <img src="${e.target.result}" style="max-width:190px;border-radius:12px;display:block;">
        </div>
      `;
    } else {
      html = `
        <div class="message-text">
          📎 ${file.name}
        </div>
      `;
    }

    const fileBubble = createMessageElement(html, "message-user");
    chatBody.appendChild(fileBubble);
    chatBody.scrollTop = chatBody.scrollHeight;

    chatHistory.push({ html, classes: "message-user" });
    saveChatHistory();

    const thinkingDiv = addBotThinking();
    callMockAPI(thinkingDiv);
  };

  reader.readAsDataURL(file);
  fileInput.value = "";
});

// ===== Gập / mở chat =====
closeChatbotButton.addEventListener("click", () => {
  chatContainer.classList.toggle("is-collapsed");
});

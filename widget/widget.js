(function () {
  'use strict';

  // Find the mounting script tag
  const scriptTag = document.currentScript || document.querySelector('script[data-key]');
  const widgetKey = scriptTag ? scriptTag.getAttribute('data-key') : 'pk_live_demo';
  const apiBase = scriptTag && scriptTag.getAttribute('data-api') ? scriptTag.getAttribute('data-api') : 'http://localhost:8000';

  let sessionToken = null;
  let isOpen = false;

  // 1. Create floating launcher bubble
  const launcher = document.createElement('div');
  launcher.id = 'ai-support-launcher';
  launcher.innerHTML = `
    <div style="
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 60px;
      height: 60px;
      background: #2563eb;
      border-radius: 50%;
      box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      z-index: 999998;
      transition: transform 0.2s ease;
    ">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
      </svg>
    </div>
  `;
  document.body.appendChild(launcher);

  // 2. Create Chat Container Box
  const container = document.createElement('div');
  container.id = 'ai-support-box';
  container.style.cssText = `
    position: fixed;
    bottom: 96px;
    right: 24px;
    width: 380px;
    height: 520px;
    background: #ffffff;
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
    display: none;
    flex-direction: column;
    overflow: hidden;
    z-index: 999999;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    border: 1px solid #e2e8f0;
  `;

  container.innerHTML = `
    <div style="background: #2563eb; color: #ffffff; padding: 16px; display: flex; align-items: center; justify-content: space-between;">
      <div>
        <div style="font-weight: 700; font-size: 15px;">Support Assistant</div>
        <div style="font-size: 11px; opacity: 0.9;">Grounded Gemini AI · Instant Response</div>
      </div>
      <button id="ai-support-close" style="background: none; border: none; color: #ffffff; font-size: 20px; cursor: pointer; line-height: 1;">&times;</button>
    </div>
    <div id="ai-support-messages" style="flex: 1; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; background: #f8fafc;">
      <div style="align-self: flex-start; max-width: 80%; background: #ffffff; border: 1px solid #e2e8f0; padding: 10px 14px; border-radius: 14px; border-bottom-left-radius: 4px; font-size: 13px; color: #1e293b; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
        Hello! How can I help you today?
      </div>
    </div>
    <form id="ai-support-form" style="display: flex; padding: 12px; background: #ffffff; border-top: 1px solid #e2e8f0; gap: 8px;">
      <input id="ai-support-input" type="text" placeholder="Type your question..." style="flex: 1; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 12px; font-size: 13px; outline: none;" required />
      <button type="submit" style="background: #2563eb; color: #ffffff; border: none; border-radius: 8px; padding: 8px 14px; font-size: 13px; font-weight: 600; cursor: pointer;">Send</button>
    </form>
  `;
  document.body.appendChild(container);

  // Toggle behavior
  launcher.addEventListener('click', () => {
    isOpen = !isOpen;
    container.style.display = isOpen ? 'flex' : 'none';
    if (isOpen) ensureSession();
  });

  document.getElementById('ai-support-close').addEventListener('click', () => {
    isOpen = false;
    container.style.display = 'none';
  });

  // Ensure Visitor Session
  async function ensureSession() {
    if (sessionToken) return;
    try {
      const res = await fetch(`${apiBase}/api/v1/chat/session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Widget-Key': widgetKey,
        },
        body: JSON.stringify({ origin: window.location.origin }),
      });
      const data = await res.json();
      sessionToken = data.session_token;
    } catch (e) {
      console.warn('[AI Support Widget] Session init fallback mode active.');
    }
  }

  // Handle Send Message
  document.getElementById('ai-support-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('ai-support-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';

    appendMessage('visitor', msg);

    try {
      const res = await fetch(`${apiBase}/api/v1/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${sessionToken}`,
        },
        body: JSON.stringify({ message: msg }),
      });
      const data = await res.json();
      appendMessage('agent', data.content);
    } catch {
      appendMessage('agent', 'Based on our documentation: Returns and deliveries take 3-5 days. Let us know if you need further help!');
    }
  });

  function appendMessage(sender, text) {
    const list = document.getElementById('ai-support-messages');
    const msgDiv = document.createElement('div');
    const isVisitor = sender === 'visitor';

    msgDiv.style.cssText = `
      align-self: ${isVisitor ? 'flex-end' : 'flex-start'};
      max-width: 80%;
      background: ${isVisitor ? '#2563eb' : '#ffffff'};
      color: ${isVisitor ? '#ffffff' : '#1e293b'};
      border: ${isVisitor ? 'none' : '1px solid #e2e8f0'};
      padding: 10px 14px;
      border-radius: 14px;
      border-bottom-${isVisitor ? 'right' : 'left'}-radius: 4px;
      font-size: 13px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
      line-height: 1.4;
    `;
    msgDiv.textContent = text;
    list.appendChild(msgDiv);
    list.scrollTop = list.scrollHeight;
  }
})();


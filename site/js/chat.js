/* NewCo Charts - AI Chat Panel */

window.NewCoChat = {
  workerUrl: null,
  messages: [],
  isOpen: false,

  init(options) {
    this.workerUrl = options.workerUrl;
    this.buildUI();
    this.bindEvents();
  },

  buildUI() {
    // Toggle button
    const toggle = document.createElement('button');
    toggle.className = 'chat-toggle';
    toggle.id = 'chat-toggle';
    toggle.innerHTML = '&#x1f4ac;';
    toggle.title = 'Chat with Claude about this data';
    document.body.appendChild(toggle);

    // Chat panel
    const panel = document.createElement('div');
    panel.className = 'chat-panel';
    panel.id = 'chat-panel';
    panel.innerHTML =
      '<div class="chat-header">' +
        '<span class="chat-header-icon">&#x2728;</span>' +
        'Ask Claude about the data' +
      '</div>' +
      '<div class="chat-messages" id="chat-messages">' +
        '<div class="chat-msg system">Ask questions about the charts, trends, and what the data means for the AI employment thesis.</div>' +
      '</div>' +
      '<div class="chat-input-row">' +
        '<textarea class="chat-input" id="chat-input" placeholder="Ask about the data..." rows="1"></textarea>' +
        '<button class="chat-send" id="chat-send">Send</button>' +
      '</div>';
    document.body.appendChild(panel);
  },

  bindEvents() {
    const toggle = document.getElementById('chat-toggle');
    const panel = document.getElementById('chat-panel');
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');

    toggle.addEventListener('click', () => {
      this.isOpen = !this.isOpen;
      panel.classList.toggle('open', this.isOpen);
      toggle.classList.toggle('open', this.isOpen);
      toggle.innerHTML = this.isOpen ? '&#x2715;' : '&#x1f4ac;';
      if (this.isOpen) input.focus();
    });

    sendBtn.addEventListener('click', () => this.send());

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.send();
      }
    });

    // Auto-resize textarea
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 80) + 'px';
    });
  },

  getContext() {
    const ctx = {};

    // Current view mode and horizon from NewCoControls
    if (window.NewCoControls) {
      ctx.mode = NewCoControls.mode;
      ctx.horizon = NewCoControls.horizon;
    }

    // Build a recent data summary from the loaded data
    if (window.NewCoCharts && NewCoCharts.data) {
      const lines = [];
      NewCoCharts.data.series.forEach(series => {
        if (!series.data || series.data.length === 0) return;
        const recent = series.data.slice(-6);
        const vals = recent.map(d =>
          d.date.slice(0, 7) + ': ' + (d.value != null ? d.value.toFixed(1) : 'N/A')
        ).join(', ');
        lines.push(series.name + ' — ' + vals);
      });
      ctx.dataSummary = lines.join('\n');
    }

    return ctx;
  },

  async send() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    input.style.height = 'auto';

    // Add user message
    this.messages.push({ role: 'user', content: text });
    this.appendMessage('user', text);

    // Show typing indicator
    this.setTyping(true);

    const sendBtn = document.getElementById('chat-send');
    sendBtn.disabled = true;

    try {
      const resp = await fetch(this.workerUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: this.messages,
          context: this.getContext()
        })
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: 'Request failed' }));
        throw new Error(err.error || 'Request failed');
      }

      const data = await resp.json();
      this.messages.push({ role: 'assistant', content: data.reply });
      this.appendMessage('assistant', data.reply);

    } catch (err) {
      this.appendMessage('system', 'Error: ' + err.message);
    } finally {
      this.setTyping(false);
      sendBtn.disabled = false;
      input.focus();
    }
  },

  appendMessage(role, text) {
    const container = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = 'chat-msg ' + role;

    if (role === 'assistant') {
      // Basic markdown-like formatting
      msg.innerHTML = this.formatReply(text);
    } else {
      msg.textContent = text;
    }

    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
  },

  setTyping(visible) {
    let el = document.getElementById('chat-typing');
    if (!el) {
      el = document.createElement('div');
      el.className = 'chat-typing';
      el.id = 'chat-typing';
      el.textContent = 'Claude is thinking...';
      document.getElementById('chat-messages').appendChild(el);
    }
    el.classList.toggle('visible', visible);
    if (visible) {
      el.parentNode.scrollTop = el.parentNode.scrollHeight;
    }
  },

  formatReply(text) {
    // Escape HTML first
    const div = document.createElement('div');
    div.textContent = text;
    let html = div.innerHTML;

    // Bold: **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Line breaks to paragraphs
    html = html.split('\n\n').map(p => '<p>' + p.replace(/\n/g, '<br>') + '</p>').join('');

    return html;
  }
};

(() => {
  const api = window.StockMindAPI;
  const storageKey = 'stockmind.agent.activeSessionId';
  const elements = {
    conversationList: document.getElementById('conversationList'),
    conversationState: document.getElementById('conversationState'),
    conversationPanel: document.getElementById('conversationPanel'),
    newConversation: document.getElementById('newConversation'),
    chatLog: document.getElementById('chatLog'),
    chatState: document.getElementById('chatState'),
    chatForm: document.getElementById('chatForm'),
    chatInput: document.getElementById('chatInput'),
    sendButton: document.getElementById('sendButton'),
    apiError: document.getElementById('apiError'),
  };

  let sessions = [];
  let activeSessionId = null;
  let busy = false;

  function showError(error) {
    elements.apiError.textContent = error.message || 'Ocurrió un error al comunicarse con el servidor.';
    elements.apiError.hidden = false;
  }

  function clearError() {
    elements.apiError.textContent = '';
    elements.apiError.hidden = true;
  }

  function setSessionId(sessionId) {
    activeSessionId = sessionId || null;
    if (activeSessionId) {
      localStorage.setItem(storageKey, activeSessionId);
    } else {
      localStorage.removeItem(storageKey);
    }
  }

  function formatDate(value) {
    if (!value) return 'Sin mensajes';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Fecha no disponible';
    return new Intl.DateTimeFormat('es-CO', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
  }

  function makeMessage(role, content) {
    const message = document.createElement('article');
    const isUser = role === 'user';
    message.className = `chat-message ${isUser ? 'user' : 'assistant'}`;
    message.setAttribute('aria-label', isUser ? 'Mensaje del usuario' : 'Mensaje del agente');

    const label = document.createElement('span');
    label.className = 'message-label';
    label.textContent = isUser ? 'Tú' : 'Agente';

    const text = document.createElement('p');
    text.className = 'message-text';
    text.textContent = content ?? '';

    message.append(label, text);
    return message;
  }

  function appendAssistantMessage(content) {
    setChatState('');
    elements.chatLog.append(makeMessage('assistant', content));
    elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
  }

  function setChatState(message, isError = false) {
    elements.chatState.textContent = message;
    elements.chatState.classList.toggle('is-error', isError);
    elements.chatState.hidden = !message;
  }

  function renderMessages(messages) {
    elements.chatLog.replaceChildren();
    if (!messages.length) {
      setChatState('Esta conversación aún no tiene mensajes.');
      return;
    }

    setChatState('');
    messages.forEach((message) => {
      if (message.role === 'user' || message.role === 'assistant') {
        elements.chatLog.append(makeMessage(message.role, message.content));
      }
    });
    elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
  }

  function renderConversationList() {
    elements.conversationList.replaceChildren();
    if (!sessions.length) {
      const empty = document.createElement('p');
      empty.className = 'conversation-empty';
      empty.textContent = 'No hay conversaciones todavía.';
      elements.conversationList.append(empty);
      return;
    }

    sessions.forEach((session) => {
      const item = document.createElement('article');
      item.className = 'conversation-item';
      item.classList.toggle('is-active', session.external_id === activeSessionId);

      const openButton = document.createElement('button');
      openButton.type = 'button';
      openButton.className = 'conversation-open';
      openButton.disabled = busy;
      openButton.setAttribute('aria-current', session.external_id === activeSessionId ? 'page' : 'false');

      const title = document.createElement('span');
      title.className = 'conversation-title';
      title.textContent = session.title || 'Nueva conversación';

      const date = document.createElement('time');
      date.className = 'conversation-date';
      const lastMessageAt = session.last_message_at || session.updated_at || session.created_at;
      date.dateTime = lastMessageAt || '';
      date.textContent = formatDate(lastMessageAt);

      openButton.append(title, date);
      openButton.addEventListener('click', () => openSession(session.external_id));

      const actions = document.createElement('div');
      actions.className = 'conversation-actions';
      const renameButton = document.createElement('button');
      renameButton.type = 'button';
      renameButton.className = 'text-button';
      renameButton.textContent = 'Renombrar';
      renameButton.disabled = busy;
      renameButton.addEventListener('click', () => renameSession(session));

      const archiveButton = document.createElement('button');
      archiveButton.type = 'button';
      archiveButton.className = 'text-button archive-button';
      archiveButton.textContent = 'Archivar';
      archiveButton.disabled = busy;
      archiveButton.addEventListener('click', () => archiveSession(session));

      actions.append(renameButton, archiveButton);
      item.append(openButton, actions);
      elements.conversationList.append(item);
    });
  }

  async function loadSessions() {
    elements.conversationState.textContent = 'Cargando conversaciones…';
    elements.conversationState.hidden = false;
    elements.conversationList.replaceChildren();
    try {
      const result = await api.get('/agent/sessions?status=active&limit=100&offset=0');
      sessions = result.data || [];
      elements.conversationState.hidden = true;
      renderConversationList();
    } catch (error) {
      elements.conversationState.textContent = 'No se pudieron cargar las conversaciones.';
      showError(error);
      throw error;
    }
  }

  async function loadMessages(sessionId, fallbackMessage = null) {
    setChatState('Cargando mensajes…');
    elements.chatLog.replaceChildren();
    try {
      const result = await api.get(`/agent/sessions/${encodeURIComponent(sessionId)}/messages?limit=500`);
      if (activeSessionId !== sessionId) return;
      const messages = result.data || [];
      renderMessages(messages);
      if (fallbackMessage && (
        fallbackMessage.id == null
        || !messages.some((message) => message.id === fallbackMessage.id)
      )) {
        appendAssistantMessage(fallbackMessage.content);
      }
    } catch (error) {
      if (error.status === 404 && activeSessionId === sessionId) {
        setSessionId(null);
        renderConversationList();
        elements.chatLog.replaceChildren();
        setChatState('La conversación ya no existe. Inicia una nueva.');
        await refreshSessions().catch(showError);
      } else {
        setChatState('No se pudieron cargar los mensajes.');
        if (fallbackMessage) appendAssistantMessage(fallbackMessage.content);
        showError(error);
      }
    }
  }

  async function openSession(sessionId) {
    if (busy || sessionId === activeSessionId) return;
    clearError();
    setSessionId(sessionId);
    renderConversationList();
    await loadMessages(sessionId);
    if (window.matchMedia('(max-width: 760px)').matches) {
      elements.conversationPanel.open = false;
    }
  }

  async function refreshSessions() {
    await loadSessions();
    renderConversationList();
  }

  async function createConversation() {
    if (busy) return;
    clearError();
    elements.newConversation.disabled = true;
    try {
      const result = await api.post('/agent/sessions', { title: 'Nueva conversación' });
      const session = result.data;
      setSessionId(session.external_id);
      await refreshSessions();
      renderMessages([]);
      renderConversationList();
      elements.chatInput.focus();
      if (window.matchMedia('(max-width: 760px)').matches) {
        elements.conversationPanel.open = false;
      }
    } catch (error) {
      showError(error);
    } finally {
      elements.newConversation.disabled = false;
    }
  }

  async function renameSession(session) {
    if (busy) return;
    const proposedTitle = window.prompt('Nuevo título para la conversación:', session.title || '');
    if (proposedTitle === null) return;
    const title = proposedTitle.trim();
    if (!title) {
      showError(new Error('El título no puede estar vacío.'));
      return;
    }

    clearError();
    try {
      await api.patch(`/agent/sessions/${encodeURIComponent(session.external_id)}`, { title });
      await refreshSessions();
    } catch (error) {
      showError(error);
    }
  }

  async function archiveSession(session) {
    if (busy || !window.confirm(`¿Archivar "${session.title || 'Nueva conversación'}"?`)) return;
    clearError();
    try {
      await api.patch(`/agent/sessions/${encodeURIComponent(session.external_id)}`, { status: 'archived' });
      if (activeSessionId === session.external_id) {
        setSessionId(null);
        elements.chatLog.replaceChildren();
        setChatState('Conversación archivada. Inicia una nueva para continuar.');
      }
      await refreshSessions();
    } catch (error) {
      showError(error);
    }
  }

  async function restoreLastSession() {
    const savedSessionId = localStorage.getItem(storageKey);
    if (!savedSessionId) {
      setChatState('Elige una conversación o inicia una nueva.');
      return;
    }

    try {
      const result = await api.get(`/agent/sessions/${encodeURIComponent(savedSessionId)}`);
      const session = result.data;
      if (session.status !== 'active') {
        setSessionId(null);
        setChatState('Elige una conversación o inicia una nueva.');
        return;
      }
      setSessionId(session.external_id);
      renderConversationList();
      await loadMessages(session.external_id);
    } catch (error) {
      if (error.status === 404) {
        setSessionId(null);
        setChatState('La conversación anterior ya no existe. Inicia una nueva.');
      } else {
        showError(error);
        setChatState('No se pudo validar la conversación anterior.');
      }
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    const messageText = elements.chatInput.value.trim();
    if (!messageText || busy) return;

    clearError();
    busy = true;
    elements.chatInput.disabled = true;
    elements.sendButton.disabled = true;
    elements.newConversation.disabled = true;
    renderConversationList();
    elements.chatLog.append(makeMessage('user', messageText));
    elements.chatInput.value = '';
    setChatState('El agente está respondiendo…');

    const requestedSessionId = activeSessionId;
    try {
      const payload = { message: messageText };
      if (requestedSessionId) payload.session_id = requestedSessionId;
      const result = await api.post('/agent/chat', payload);
      const response = result.data || {};
      if (response.session_id) setSessionId(response.session_id);
      else if (requestedSessionId) setSessionId(requestedSessionId);
      const responseText = response.response ?? response.content;
      const fallbackMessage = typeof responseText === 'string'
        ? { id: response.message_id, content: responseText }
        : null;
      if (fallbackMessage) appendAssistantMessage(fallbackMessage.content);

      await refreshSessions();
      if (activeSessionId) {
        await loadMessages(activeSessionId, fallbackMessage);
      } else {
        renderMessages([]);
      }
      if (response.warning) showError(new Error(response.warning));
    } catch (error) {
      setChatState('');
      showError(error);
    } finally {
      busy = false;
      elements.chatInput.disabled = false;
      elements.sendButton.disabled = false;
      elements.newConversation.disabled = false;
      renderConversationList();
      elements.chatInput.focus();
    }
  }

  async function init() {
    if (!api) {
      showError(new Error('No se pudo cargar el cliente de API.'));
      return;
    }

    elements.newConversation.addEventListener('click', createConversation);
    elements.chatForm.addEventListener('submit', sendMessage);

    const isMobile = window.matchMedia('(max-width: 760px)');
    elements.conversationPanel.open = !isMobile.matches;
    isMobile.addEventListener('change', (event) => {
      elements.conversationPanel.open = !event.matches;
    });

    try {
      await loadSessions();
    } catch {
      setChatState('No se pudo cargar el historial.');
      return;
    }
    await restoreLastSession();
    renderConversationList();
  }

  init();
})();

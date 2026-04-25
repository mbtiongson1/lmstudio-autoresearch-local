// LM Studio AutoResearch Frontend

class AutoResearchAgent {
    constructor() {
        this.taskId = null;
        this.ws = null;
        this.isRunning = false;
        this.models = [];
        this.setupEventListeners();
        this.refreshModels();
    }

    setupEventListeners() {
        document.getElementById('start-btn').addEventListener('click', () => this.startResearch());
        document.getElementById('reset-btn').addEventListener('click', () => this.reset());
        document.getElementById('refresh-models-btn').addEventListener('click', () => this.refreshModels());
        
        // History navigation
        document.getElementById('nav-history').addEventListener('click', () => this.toggleHistory());
        document.getElementById('history-search').addEventListener('input', (e) => this.loadHistory(e.target.value));
        document.getElementById('nav-home').addEventListener('click', () => this.toggleHome());
    }

    toggleHistory() {
        document.getElementById('history-section').classList.remove('hidden');
        document.getElementById('model-section').classList.add('hidden');
        this.loadHistory();
    }
    
    toggleHome() {
        document.getElementById('history-section').classList.add('hidden');
        document.getElementById('model-section').classList.remove('hidden');
    }

    async loadHistory(query = '') {
        const historyList = document.getElementById('history-list');
        historyList.innerHTML = '<div class="text-sm">Loading history...</div>';
        
        try {
            const url = query ? `/api/history?query=${encodeURIComponent(query)}` : '/api/history';
            const response = await fetch(url);
            const sessions = await response.json();
            
            if (sessions.length === 0) {
                historyList.innerHTML = '<div class="text-sm text-slate-500">No sessions found.</div>';
                return;
            }
            
            historyList.innerHTML = '';
            sessions.forEach(s => {
                const el = document.createElement('div');
                el.className = 'glass-card p-4 rounded-lg cursor-pointer hover:bg-slate-800 transition-all';
                el.innerHTML = `
                    <div class="flex justify-between items-start">
                        <div class="text-sm font-medium text-slate-200">${s.topic}</div>
                        <button class="delete-btn text-xs text-red-400 hover:text-red-300">Delete</button>
                    </div>
                    <div class="text-[10px] text-slate-500 mt-1">${new Date(s.created_at).toLocaleString()}</div>
                `;
                el.addEventListener('click', () => this.viewSession(s.task_id));
                el.querySelector('.delete-btn').addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.deleteSession(s.task_id);
                });
                historyList.appendChild(el);
            });
        } catch (e) {
            historyList.innerHTML = '<div class="text-sm text-red-400">Error loading history.</div>';
        }
    }

    async viewSession(taskId) {
        try {
            const response = await fetch(`/api/history/${taskId}`);
            const data = await response.json();
            
            // Switch to home view
            this.toggleHome();
            this.clearOutput();
            document.getElementById('topic-input').value = data.topic;
            document.getElementById('status-section').style.display = 'none';
            document.getElementById('answer-section').style.display = 'block';
            document.getElementById('final-answer').innerHTML = data.final_answer + 
                `<br><br><button class="copy-btn bg-slate-700 px-3 py-1 rounded text-xs text-white">Copy Answer</button>`;
            
            document.querySelector('.copy-btn').addEventListener('click', () => {
                navigator.clipboard.writeText(data.final_answer);
                alert('Answer copied to clipboard!');
            });
        } catch (e) {
            console.error('Error loading session details', e);
        }
    }

    async deleteSession(taskId) {
        if (!confirm('Are you sure you want to delete this session?')) return;
        await fetch(`/api/history/${taskId}`, { method: 'DELETE' });
        this.loadHistory();
    }

    async refreshModels() {
        const listContainer = document.getElementById('models-list');
        const refreshBtn = document.getElementById('refresh-models-btn');
        
        refreshBtn.classList.add('spinning');
        listContainer.innerHTML = '<div class="loading-spinner">Refreshing models...</div>';

        try {
            const response = await fetch('/api/models');
            if (!response.ok) throw new Error('Failed to fetch models');
            
            const data = await response.json();
            this.models = data.models || [];
            this.renderModels();
            
            // Update current model display in footer
            const loadedModel = this.models.find(m => m.loaded_instances && m.loaded_instances.length > 0);
            if (loadedModel) {
                document.getElementById('model-name').textContent = loadedModel.key;
            } else {
                document.getElementById('model-name').textContent = 'None';
            }
        } catch (error) {
            console.error('Error fetching models:', error);
            listContainer.innerHTML = `<div class="loading-spinner" style="color: var(--error-color)">Error: ${error.message}</div>`;
        } finally {
            refreshBtn.classList.remove('spinning');
        }
    }

    renderModels() {
        const listContainer = document.getElementById('models-list');
        listContainer.innerHTML = '';

        if (this.models.length === 0) {
            listContainer.innerHTML = '<div class="text-slate-500 italic text-sm text-center py-10">No models found in LM Studio</div>';
            return;
        }

        // Categorize models
        const loadedModels = this.models.filter(m => m.loaded_instances && m.loaded_instances.length > 0);
        const offlineModels = this.models.filter(m => !m.loaded_instances || m.loaded_instances.length === 0);

        const renderSection = (title, models) => {
            if (models.length === 0) return '';
            
            let html = `<div class="space-y-4">
                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mb-4">${title}</h3>
                <div class="space-y-3">`;
            
            models.forEach(model => {
                const isLoaded = model.loaded_instances && model.loaded_instances.length > 0;
                const sizeGB = (model.size_bytes / (1024 ** 3)).toFixed(2);
                
                html += `
                    <div class="model-card ${isLoaded ? 'loaded' : ''} p-4 rounded-xl border border-white/5 bg-slate-900/40 hover:bg-slate-800/60 transition-all">
                        <div class="flex justify-between items-start mb-2">
                            <div class="overflow-hidden">
                                <span class="block text-sm font-semibold text-slate-200 truncate" title="${model.display_name}">${model.display_name}</span>
                                <span class="block text-[10px] text-slate-500 uppercase tracking-wider">${model.architecture || 'gguf'} • ${sizeGB} GB</span>
                            </div>
                            <span class="text-[9px] px-2 py-0.5 rounded-full ${isLoaded ? 'bg-brand-cyan/20 text-brand-cyan border border-brand-cyan/30' : 'bg-slate-800 text-slate-500 border border-white/5'}">
                                ${isLoaded ? 'LOADED' : 'OFFLINE'}
                            </span>
                        </div>
                        <div class="flex items-center justify-between mt-4">
                            <span class="text-[10px] text-slate-400 font-mono">${model.max_context_length} ctx</span>
                            <div class="flex gap-2">
                                ${isLoaded 
                                    ? `<button class="text-[10px] px-3 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors" onclick="agent.unloadModel('${model.loaded_instances[0].id}')">Unload</button>`
                                    : `<button class="text-[10px] px-3 py-1 rounded bg-brand-cyan/10 text-brand-cyan hover:bg-brand-cyan/20 transition-colors" onclick="agent.loadModel('${model.key}')">Load</button>`
                                }
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += `</div></div>`;
            return html;
        };

        let containerHtml = '';
        containerHtml += renderSection('Loaded Models', loadedModels);
        containerHtml += renderSection('Available Models', offlineModels);
        
        listContainer.innerHTML = containerHtml;
    }

    async loadModel(key) {
        try {
            const container = document.getElementById('model-loading-progress-container');
            const bar = document.getElementById('model-loading-bar');
            const text = document.getElementById('model-loading-text');
            
            container.classList.remove('hidden');
            bar.style.width = '30%';
            text.textContent = `Loading ${key.split('/').pop()}...`;

            const response = await fetch('/api/models/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    model: key,
                    echo_load_config: true
                })
            });

            bar.style.width = '100%';

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to load model');
            }
            
            await this.refreshModels();
        } catch (error) {
            console.error('Error loading model:', error);
            alert(`Error loading model: ${error.message}`);
            this.refreshModels(); // Reset UI
        } finally {
            document.getElementById('model-loading-progress-container').classList.add('hidden');
            document.getElementById('model-loading-bar').style.width = '0%';
        }
    }

    async unloadModel(instanceId) {
        try {
            const response = await fetch('/api/models/unload', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ instance_id: instanceId })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to unload model');
            }
            
            await this.refreshModels();
        } catch (error) {
            console.error('Error unloading model:', error);
            alert(`Error unloading model: ${error.message}`);
            this.refreshModels();
        }
    }

    async startResearch() {
        const topicInput = document.getElementById('topic-input');
        const maxTurnsInput = document.getElementById('max-turns');
        const topic = topicInput.value.trim();
        const maxTurns = parseInt(maxTurnsInput.value) || 8;

        if (!topic) {
            alert('Please enter a research topic');
            return;
        }

        this.isRunning = true;
        this.disableInputs(true);
        this.clearOutput();

        try {
            // Start research via API
            const response = await fetch('/api/research', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    topic: topic,
                    max_turns: maxTurns
                })
            });

            const data = await response.json();
            this.taskId = data.task_id;

            // Display status section
            document.getElementById('status-section').style.display = 'block';
            document.getElementById('topic-display').textContent = topic;
            this.updateProgress(0, maxTurns);

            // Connect to WebSocket
            this.connectWebSocket(this.taskId);
        } catch (error) {
            console.error('Error starting research:', error);
            this.addOutput('error', `Error: ${error.message}`);
            this.isRunning = false;
            this.disableInputs(false);
        }
    }

    connectWebSocket(taskId) {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const wsUrl = `${protocol}://${window.location.host}/ws/research/${taskId}`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
        };

        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
            } catch (error) {
                console.error('Error parsing message:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.addOutput('error', 'WebSocket connection error');
        };

        this.ws.onclose = () => {
            console.log('WebSocket closed');
        };
    }

    handleMessage(message) {
        if (message.type === 'action') {
            const { turn, action, content } = message;
            this.addOutput(action, `Turn ${turn}: ${content}`);
            this.updateProgress(turn, 8);
        } else if (message.type === 'complete') {
            this.showFinalAnswer(message.answer);
            this.isRunning = false;
            this.disableInputs(false);
        } else if (message.type === 'error') {
            this.addOutput('error', `Error: ${message.content}`);
            this.isRunning = false;
            this.disableInputs(false);
        } else if (message.type === 'status') {
            this.updateStatus(message.status);
        }
    }

    addOutput(type, content) {
        const container = document.getElementById('output-container');

        // Remove placeholder on first message
        const placeholder = container.querySelector('.output-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        const line = document.createElement('div');
        line.className = `output-line ${type}`;

        const actionSpan = document.createElement('span');
        actionSpan.className = 'output-action';
        // Map types to better labels if needed
        const label = type === 'think' ? 'THOUGHT' : type.toUpperCase();
        actionSpan.textContent = `[${label}]`;

        line.appendChild(actionSpan);
        line.appendChild(document.createTextNode(content));

        container.appendChild(line);
        container.scrollTop = container.scrollHeight; // Auto-scroll to bottom
    }

    updateProgress(current, max) {
        document.getElementById('turn-display').textContent = current;
        const percentage = (current / max) * 100;
        document.getElementById('progress-bar').style.width = `${percentage}%`;
    }

    updateStatus(status) {
        const badge = document.getElementById('status-badge');
        const toggle = document.getElementById('status-toggle');
        const dot = document.getElementById('status-toggle-dot');
        
        badge.textContent = status.toUpperCase();
        
        // Reset classes
        badge.classList.remove('text-slate-500', 'text-brand-cyan', 'text-red-400', 'text-green-400');
        toggle.classList.remove('bg-slate-700', 'bg-brand-cyan/20');
        dot.classList.remove('left-1', 'right-1', 'bg-slate-500', 'bg-brand-cyan', 'active-glow');

        if (status === 'completed' || status === 'finished') {
            badge.classList.add('text-green-400');
            toggle.classList.add('bg-slate-700');
            dot.classList.add('left-1', 'bg-slate-500');
        } else if (status === 'error' || status === 'failed') {
            badge.classList.add('text-red-400');
            toggle.classList.add('bg-slate-700');
            dot.classList.add('left-1', 'bg-slate-500');
        } else if (status === 'idle') {
            badge.classList.add('text-slate-500');
            toggle.classList.add('bg-slate-700');
            dot.classList.add('left-1', 'bg-slate-500');
        } else {
            // Running / Researching
            badge.classList.add('text-brand-cyan');
            toggle.classList.add('bg-brand-cyan/20');
            dot.classList.add('right-1', 'bg-brand-cyan', 'active-glow');
        }
    }

    showFinalAnswer(answer) {
        const answerSection = document.getElementById('answer-section');
        document.getElementById('final-answer').textContent = answer;
        answerSection.style.display = 'block';

        // Scroll to answer
        answerSection.scrollIntoView({ behavior: 'smooth' });

        // Update status
        this.updateStatus('completed');
    }

    clearOutput() {
        const container = document.getElementById('output-container');
        container.innerHTML = '<div class="output-placeholder opacity-50 italic">&gt;_ Research in progress...</div>';
    }

    disableInputs(disabled) {
        document.getElementById('topic-input').disabled = disabled;
        document.getElementById('max-turns').disabled = disabled;
        const startBtn = document.getElementById('start-btn');
        startBtn.disabled = disabled;

        if (disabled) {
            startBtn.innerHTML = '<span class="loading mr-2"></span> Researching...';
            this.updateStatus('researching');
        } else {
            startBtn.innerHTML = 'Start Research';
            // Don't set status to idle here as it might have finished or errored
        }
    }

    reset() {
        // Close WebSocket
        if (this.ws) {
            this.ws.close();
        }

        // Reset UI
        this.taskId = null;
        this.isRunning = false;
        this.disableInputs(false);
        this.clearOutput();

        document.getElementById('status-section').style.display = 'none';
        document.getElementById('answer-section').style.display = 'none';
        document.getElementById('topic-input').value = '';
        document.getElementById('max-turns').value = '8';
        document.getElementById('topic-input').focus();
    }
}

// Initialize agent when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.agent = new AutoResearchAgent();
    document.getElementById('topic-input').focus();
});

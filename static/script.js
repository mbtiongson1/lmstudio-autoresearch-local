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
            listContainer.innerHTML = '<div class="output-placeholder">No models downloaded</div>';
            return;
        }

        this.models.forEach(model => {
            const isLoaded = model.loaded_instances && model.loaded_instances.length > 0;
            const card = document.createElement('div');
            card.className = `model-card ${isLoaded ? 'loaded' : ''}`;

            const sizeGB = (model.size_bytes / (1024 ** 3)).toFixed(2);
            
            card.innerHTML = `
                <div class="model-header">
                    <div>
                        <span class="model-name">${model.display_name}</span>
                        <span class="model-type">${model.type} | ${model.architecture || 'gguf'}</span>
                    </div>
                    <span class="model-badge ${isLoaded ? 'loaded' : ''}">${isLoaded ? 'LOADED' : 'OFFLINE'}</span>
                </div>
                <div class="model-info-row">
                    <span>${model.quantization?.name || 'Unknown'} • ${sizeGB} GB • ${model.max_context_length} ctx</span>
                </div>
                <div class="model-actions">
                    ${isLoaded 
                        ? `<button class="btn btn-secondary btn-sm" onclick="agent.unloadModel('${model.loaded_instances[0].id}')">Unload</button>`
                        : `<button class="btn btn-primary btn-sm" onclick="agent.loadModel('${model.key}')">Load</button>`
                    }
                </div>
            `;
            listContainer.appendChild(card);
        });
    }

    async loadModel(key) {
        try {
            // Find the button and show loading state
            const buttons = document.querySelectorAll(`.model-card button`);
            buttons.forEach(btn => {
                if (btn.textContent === 'Load' && btn.closest('.model-card').querySelector('.model-name').textContent.includes(key.split('/').pop())) {
                    btn.disabled = true;
                    btn.innerHTML = '<span class="loading"></span> Loading...';
                }
            });

            const response = await fetch('/api/models/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    model: key,
                    echo_load_config: true
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to load model');
            }
            
            await this.refreshModels();
        } catch (error) {
            console.error('Error loading model:', error);
            alert(`Error loading model: ${error.message}`);
            this.refreshModels(); // Reset UI
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
        actionSpan.textContent = type.toUpperCase();

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
        badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        badge.classList.remove('completed', 'error');

        if (status === 'completed') {
            badge.classList.add('completed');
        } else if (status === 'error') {
            badge.classList.add('error');
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
        container.innerHTML = '<div class="output-placeholder">Research in progress...</div>';
    }

    disableInputs(disabled) {
        document.getElementById('topic-input').disabled = disabled;
        document.getElementById('max-turns').disabled = disabled;
        document.getElementById('start-btn').disabled = disabled;

        if (disabled) {
            document.getElementById('start-btn').innerHTML = '<span class="loading"></span> Running...';
        } else {
            document.getElementById('start-btn').innerHTML = 'Start Research';
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

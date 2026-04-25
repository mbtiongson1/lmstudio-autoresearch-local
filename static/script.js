// LM Studio AutoResearch Frontend

class AutoResearchAgent {
    constructor() {
        this.taskId = null;
        this.ws = null;
        this.isRunning = false;
        this.setupEventListeners();
    }

    setupEventListeners() {
        document.getElementById('start-btn').addEventListener('click', () => this.startResearch());
        document.getElementById('reset-btn').addEventListener('click', () => this.reset());
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

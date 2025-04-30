<div align="center">
  <h1>🧠 Dialogos</h1>
  <h3>A branching thought-canvas for AI conversations powered by OpenAI & DeepSeek</h3>
</div>

<hr />

<h2>What is this?</h2>

<p>
  <strong>Dialogos</strong> is a dynamic interface for exploring and managing complex AI conversations. Each conversation branch is treated as a thread of thought — one you can fork, compare, archive, or revive.
</p>

<p>
  It’s designed to go <strong>beyond chat</strong>, giving you a <strong>tool for thinking</strong>, experimenting, and mapping how your ideas evolve with AI.
</p>

<h2>🧩 What it does</h2>
<ul>
  <li>🌟 <strong>Resurrect & Continue</strong>: Seamlessly resume conversations even after reaching context limits.</li>
  <li>🌿 <strong>Branch & Explore</strong>: Fork any message and try multiple directions without losing your original path.</li>
  <li>☁️ <strong>Hosted LLMs</strong>: Powered by OpenAI and DeepSeek — no local models or Ollama setup required.</li>
  <li>🧠 <strong>Topic Clustering</strong>: Automatically groups chats by theme, so you can track and revisit ideas more easily.</li>
  <li>📜 <strong>Archive Compatibility</strong>: Works with exported chat files from Claude and ChatGPT.</li>
</ul>

<blockquote><em>Think of Dialogos as your <strong>AI memory palace</strong>, a place to map out not just what you say — but what you could have said.</em></blockquote>

<h2>🛠️ Project Structure</h2>

<pre><code>
Dialogos-api
├── src
│   ├── app.py                # Entry point of the Flask app
│   ├── config.py             # Configuration settings
│   ├── models.py             # Data models and in-memory stores
│   ├── tasks.py              # Background task orchestration
│   ├── utils.py              # Utility helpers
│   ├── routes                # Modular API route definitions
│   │   ├── api.py            # Main API routes (OpenAI/DeepSeek calls etc.)
│   │   ├── chats.py
│   │   ├── messages.py
│   │   ├── states.py
│   │   └── topics.py
│   └── services              # Core service logic
│       ├── background_processor.py
│       ├── clustering.py
│       ├── data_processing.py
│       ├── embedding.py
│       ├── reflection.py
│       └── topic_generation.py
├── requirements.txt
└── README.md
</code></pre>

<h2>🚀 Getting Started</h2>

<h3>1. Clone the Repo</h3>
<pre><code>git clone https://github.com/itsPreto/Dialogos.git
cd Dialogos
</code></pre>

<h3>2. Install Backend (OpenAI + DeepSeek)</h3>
<pre><code>cd Dialogos-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
</code></pre>

<blockquote><strong>Note:</strong> Make sure you have Python 3.10+ installed.</blockquote>

<h3>3. Set Your API Keys</h3>
<p>Create a <code>.env</code> file in <code>Dialogos-api/</code> with:</p>
<pre><code>OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_API_KEY=your-deepseek-key-if-used
EMBEDDING_MODEL=your-embedding-model-name
GENERATION_MODEL=your-generation-model-name
</code></pre>

<h3>4. Start the Backend</h3>
<pre><code>cd src
python3 app.py
</code></pre>

<p>The backend will start at: <code>http://localhost:5001/api</code></p>

<h3>5. Frontend Setup</h3>
<pre><code>cd simplified-ui
npm install
npm start
</code></pre>
<blockquote>If you get any missing package errors, install them manually with <code>npm install &lt;pkg-name&gt;</code>.</blockquote>

<h2>🔌 Supported API Endpoints</h2>

<table>
  <tr><th>Route</th><th>Description</th></tr>
  <tr><td><code>POST /api/process</code></td><td>Upload and begin processing exported chat JSON</td></tr>
  <tr><td><code>GET /api/process/status/&lt;task_id&gt;</code></td><td>Check background task progress</td></tr>
  <tr><td><code>POST /api/generate</code></td><td>Generate text using OpenAI or DeepSeek</td></tr>
  <tr><td><code>GET /api/topics</code></td><td>Get all clustered conversation topics</td></tr>
  <tr><td><code>GET /api/models</code></td><td>View active model config</td></tr>
  <tr><td><code>POST /api/embeddings</code></td><td>Generate embeddings for given texts</td></tr>
</table>

<h2>🤝 Contributing</h2>

<p>Pull requests are welcome! Got ideas for features like real-time chat syncing, more LLM integrations, or timeline views? Open an issue or fork it and send a PR.</p>

<hr />

<div align="center">
  <p>🧬 Licensed under Apache 2.0 — see LICENSE for details</p>
  <p>💬 Join the conversation in our (Discord coming soon)</p>
</div>

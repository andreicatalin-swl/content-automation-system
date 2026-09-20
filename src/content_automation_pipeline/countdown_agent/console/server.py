import inspect
import json
import queue
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Final

from content_automation_pipeline.artifacts.artifact import Kind
from content_automation_pipeline.countdown_agent.graphs.graph import Graph
from content_automation_pipeline.countdown_agent.states.state import State

_HOST: Final[str] = '127.0.0.1'
_PORT: Final[int] = 8765
_EVENT_PREFIX: Final[str] = '@@EVENT@@ '
_NODES: Final[list[str]] = [
    'generate_script',
    'evaluate_generated_script',
    'find_media',
    'evaluate_found_media',
    'download_media',
    'evaluate_downloaded_media',
    'edit_video',
    'evaluate_edited_video',
]

_ARTIFACT_ROOT: Final[str] = 'playground/artifacts'
_CATEGORY: Final[str] = 'playground'

# The smallest brief that still drives every node and still exports, since the template wants ten entries
_INSTRUCTIONS: Final[dict[str, str]] = {
    'generation_instructions': (
        'Write the script for a countdown video about the 10 most famous rap songs of all time.\n\n'
        'title1 is Top 10 and title2 is Rap Songs. The subheading is empty. The username is @countdown.\n\n'
        'Use exactly 10 entries. The first entry is the 10th pick and the last entry is the top one.\n\n'
        'Every entry is one line holding only the song name.'
    ),
    'script_evaluation_instructions': 'Pass anything.',
    'media_finding_instructions': (
        'Search YouTube for the music video of the song named in the entry.\n\n'
        'Use the same link for the video and for the audio, with the same start timestamp.\n\n'
        'Give one entry for every entry of the script, in the same order.\n\n'
        'Every link is the full address of a single YouTube video, never a playlist and never a channel.\n\n'
        'Every timestamp and every duration is a plain number of seconds, and every duration is 10.'
    ),
    'found_media_evaluation_instructions': 'Pass anything.',
    'downloaded_media_evaluation_instructions': 'Pass anything.',
    'edited_video_evaluation_instructions': 'Pass anything.',
}

_RUN: Final[dict[str, Any]] = {
    'runs': 1,
    'delay_seconds': 0,
    'on_failure': 'stop',
    'max_retries': 1,
    'recursion_limit': 60,
}

# Runs one graph in its own process, so every line the pipeline writes lands on one pipe
_RUNNER: Final[str] = '''
import json
import sys
from pathlib import Path

from content_automation_pipeline.artifacts.artifact import Kind
from content_automation_pipeline.artifacts.artifact_manager import ArtifactManager
from content_automation_pipeline.countdown_agent.graphs.graph import Graph
from content_automation_pipeline.countdown_agent.states.state import State

PREFIX = '@@EVENT@@ '

def emit(payload):
    sys.stdout.write(PREFIX + json.dumps(payload) + '\\n')
    sys.stdout.flush()

config = json.loads(sys.stdin.read())

arguments = {}

for name, value in config['graph'].items():
    if name.endswith('artifact_root'):
        arguments[name.replace('artifact_root', 'artifact_manager')] = ArtifactManager(Path(value))
    elif name.endswith('kind'):
        arguments[name] = Kind(value)
    elif name.endswith('max_calls'):
        arguments[name] = int(value)
    else:
        arguments[name] = value

graph = Graph(**arguments)

state = State(**config['instructions'])
settings = {'recursion_limit': config['recursion_limit']}
final = None

for mode, chunk in graph.get_compiled_state_graph().stream(
    state, settings, stream_mode=['updates', 'values'],
):
    if mode == 'updates':
        for name in chunk:
            emit({'type': 'node', 'name': name})
    else:
        final = chunk

def field(name):
    if final is None:
        return None
    value = final.get(name) if isinstance(final, dict) else getattr(final, name, None)
    return None if value is None else repr(value)

emit({
    'type': 'result',
    'script': field('script'),
    'media_links': field('media_links'),
    'media_files': field('media_files'),
    'video': field('video'),
    'evaluation': field('evaluation'),
})
'''

def _parameters() -> list[dict[str, Any]]:
    # The graph is the source of truth for what can be tuned, so the form is built from its signature
    parameters: list[dict[str, Any]] = []

    for name, parameter in inspect.signature(Graph.__init__).parameters.items():
        if name == 'self':
            continue

        # An artifact manager cannot come off a form, so its root is asked for instead
        if name.endswith('artifact_manager'):
            parameters.append({
                'name': name.replace('artifact_manager', 'artifact_root'),
                'kind': 'text',
                'default': _ARTIFACT_ROOT,
            })
            continue

        default = parameter.default
        if isinstance(default, Kind):
            parameters.append({
                'name': name,
                'kind': 'choice',
                'default': default.value,
                'choices': [member.value for member in Kind],
            })
        elif isinstance(default, int):
            parameters.append({'name': name, 'kind': 'number', 'default': default})
        else:
            # The graph leaves this one to the caller, so the console supplies a working value
            parameters.append({'name': name, 'kind': 'text', 'default': _CATEGORY})

    return parameters

def _instruction_fields() -> list[str]:
    return [name for name, field in State.model_fields.items() if field.is_required()]

class _Broadcaster:
    def __init__(self) -> None:
        self._clients: list[queue.Queue[str]] = []
        self._lock = threading.Lock()
        self._history: list[dict[str, Any]] = []

    def subscribe(self) -> queue.Queue[str]:
        client: queue.Queue[str] = queue.Queue()

        with self._lock:
            for event in self._history[-500:]:
                client.put(json.dumps(event))
            self._clients.append(client)

        return client

    def unsubscribe(self, client: queue.Queue[str]) -> None:
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)

    def send(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event)

        with self._lock:
            self._history.append(event)
            self._history = self._history[-2000:]
            clients = list(self._clients)

        for client in clients:
            client.put(payload)

class _Session:
    def __init__(
        self,
        broadcaster: _Broadcaster,
    ) -> None:
        self._broadcaster = broadcaster
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[str] | None = None
        self._stopping = False

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, config: dict[str, Any]) -> bool:
        if self.running:
            return False

        self._stopping = False
        self._thread = threading.Thread(target=self._loop, args=(config,), daemon=True)
        self._thread.start()

        return True

    def stop(self) -> None:
        self._stopping = True
        process = self._process

        if process is not None and process.poll() is None:
            process.terminate()

    def _loop(self, config: dict[str, Any]) -> None:
        runs = int(config['runs'])
        on_failure = config['on_failure']
        max_retries = int(config['max_retries'])
        delay = float(config['delay_seconds'])
        started = time.monotonic()
        succeeded = 0
        failed = 0

        self._broadcaster.send({'type': 'session', 'state': 'started', 'runs': runs})

        run = 0
        while run < runs and not self._stopping:
            run += 1
            attempt = 0

            while not self._stopping:
                attempt += 1
                self._broadcaster.send({
                    'type': 'run',
                    'state': 'started',
                    'run': run,
                    'runs': runs,
                    'attempt': attempt,
                })

                ok = self._run_once(config)

                if ok:
                    succeeded += 1
                    self._broadcaster.send({'type': 'run', 'state': 'succeeded', 'run': run})
                    break

                if self._stopping:
                    break

                retrying = on_failure == 'retry' and attempt <= max_retries
                self._broadcaster.send({
                    'type': 'run',
                    'state': 'failed',
                    'run': run,
                    'retrying': retrying,
                })

                if retrying:
                    continue

                failed += 1
                if on_failure == 'stop':
                    self._stopping = True

                break

            if delay and run < runs and not self._stopping:
                self._broadcaster.send({'type': 'log', 'line': f'waiting {delay:.0f}s before the next run'})
                time.sleep(delay)

        self._broadcaster.send({
            'type': 'session',
            'state': 'finished',
            'succeeded': succeeded,
            'failed': failed,
            'elapsed': round(time.monotonic() - started, 1),
        })

    def _run_once(self, config: dict[str, Any]) -> bool:
        payload = json.dumps({
            'graph': {parameter['name']: config[parameter['name']] for parameter in _parameters()},
            'recursion_limit': int(config['recursion_limit']),
            'instructions': config['instructions'],
        })

        process = subprocess.Popen(
            [sys.executable, '-u', '-c', _RUNNER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
        )
        self._process = process

        if process.stdin is not None:
            process.stdin.write(payload)
            process.stdin.close()

        if process.stdout is not None:
            for line in process.stdout:
                line = line.rstrip('\n')

                if line.startswith(_EVENT_PREFIX):
                    self._broadcaster.send(json.loads(line[len(_EVENT_PREFIX):]))
                    continue

                self._broadcaster.send({'type': 'log', 'line': line})

        code = process.wait()
        self._process = None

        if code:
            self._broadcaster.send({'type': 'log', 'line': f'the run exited with code {code}'})

        return code == 0

_PAGE: Final[str] = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Countdown Agent</title>
<style>
:root {
  --bg: #0b0d12; --panel: #12151d; --panel-2: #171b25; --line: #242a38;
  --text: #e6e9f0; --muted: #8b93a7; --accent: #6ea8fe; --ok: #58d68d;
  --warn: #f5b041; --err: #ec7063; --radius: 12px;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 system-ui, -apple-system, Segoe UI, sans-serif;
}
header {
  display: flex; align-items: center; gap: 14px; padding: 14px 20px;
  border-bottom: 1px solid var(--line); background: var(--panel); position: sticky; top: 0; z-index: 5;
}
header h1 { font-size: 15px; margin: 0; font-weight: 600; letter-spacing: .3px; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--muted); }
.dot.on { background: var(--ok); box-shadow: 0 0 10px var(--ok); }
.spacer { flex: 1; }
button {
  font: inherit; color: var(--text); background: var(--panel-2); border: 1px solid var(--line);
  padding: 8px 14px; border-radius: 9px; cursor: pointer; transition: .15s;
}
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { opacity: .4; cursor: not-allowed; }
button.primary { background: var(--accent); color: #07101f; border-color: var(--accent); font-weight: 600; }
button.danger { border-color: var(--err); color: var(--err); }
main { display: grid; grid-template-columns: minmax(340px, 420px) 1fr; gap: 16px; padding: 16px; align-items: start; }
@media (max-width: 900px) { main { grid-template-columns: 1fr; } }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; }
.panel > h2 {
  margin: 0; padding: 11px 14px; font-size: 12px; text-transform: uppercase;
  letter-spacing: .7px; color: var(--muted); border-bottom: 1px solid var(--line); font-weight: 600;
}
.body { padding: 14px; display: grid; gap: 12px; }
label { display: grid; gap: 5px; font-size: 12px; color: var(--muted); }
input, select, textarea {
  font: inherit; color: var(--text); background: var(--bg); border: 1px solid var(--line);
  border-radius: 8px; padding: 8px 10px; width: 100%; resize: vertical;
}
input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); }
textarea { min-height: 72px; font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
details { border-top: 1px solid var(--line); }
details > summary {
  padding: 11px 14px; cursor: pointer; font-size: 12px; text-transform: uppercase;
  letter-spacing: .7px; color: var(--muted); font-weight: 600;
}
.rail { display: flex; flex-wrap: wrap; gap: 6px; padding: 14px; }
.chip {
  font-size: 11px; padding: 5px 9px; border-radius: 999px; border: 1px solid var(--line);
  color: var(--muted); background: var(--panel-2); transition: .2s;
}
.chip.done { color: var(--ok); border-color: var(--ok); }
.chip.active { color: var(--accent); border-color: var(--accent); animation: pulse 1.2s infinite; }
@keyframes pulse { 50% { opacity: .5; } }
.bar { height: 3px; background: var(--panel-2); }
.bar > i { display: block; height: 100%; width: 0; background: var(--accent); transition: width .3s; }
.stats { display: flex; gap: 18px; padding: 12px 14px; border-top: 1px solid var(--line); flex-wrap: wrap; }
.stat { display: grid; gap: 2px; }
.stat b { font-size: 17px; font-weight: 600; }
.stat span { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
#log {
  margin: 0; padding: 12px 14px; height: calc(100vh - 300px); min-height: 280px; overflow: auto;
  font-family: ui-monospace, Consolas, monospace; font-size: 12px; line-height: 1.55; white-space: pre-wrap;
  word-break: break-word; background: #080a0e;
}
#log div.warn { color: var(--warn); }
#log div.err { color: var(--err); }
#log div.ok { color: var(--ok); }
#log div.muted { color: var(--muted); }
.row { display: flex; gap: 8px; align-items: center; }
.tag { font-size: 11px; color: var(--muted); }
</style>
</head>
<body>
<header>
  <div class="dot" id="dot"></div>
  <h1>Countdown Agent</h1>
  <span class="tag" id="phase">idle</span>
  <div class="spacer"></div>
  <button id="reset">Reset to defaults</button>
  <button id="copy">Copy log</button>
  <button id="clear">Clear log</button>
  <button id="stop" class="danger" disabled>Stop</button>
  <button id="start" class="primary">Start</button>
</header>

<main>
  <div>
    <section class="panel">
      <h2>Run control</h2>
      <div class="body">
        <div class="grid2">
          <label>Runs<input id="runs" type="number" min="1" value="1"></label>
          <label>Delay between runs (s)<input id="delay_seconds" type="number" min="0" value="0"></label>
        </div>
        <div class="grid2">
          <label>If a run raises
            <select id="on_failure">
              <option value="stop">Stop everything</option>
              <option value="continue">Skip to next run</option>
              <option value="retry">Retry, then skip</option>
            </select>
          </label>
          <label>Max retries<input id="max_retries" type="number" min="0" value="1"></label>
        </div>
        <label>Recursion limit<input id="recursion_limit" type="number" min="1" value="60"></label>
      </div>
      <details open>
        <summary>Graph parameters</summary>
        <div class="body" id="parameters"></div>
      </details>
      <details>
        <summary>Instructions</summary>
        <div class="body" id="instructions"></div>
      </details>
    </section>
  </div>

  <div>
    <section class="panel">
      <h2>Progress</h2>
      <div class="bar"><i id="fill"></i></div>
      <div class="rail" id="rail"></div>
      <div class="stats">
        <div class="stat"><b id="s_run">0 / 0</b><span>run</span></div>
        <div class="stat"><b id="s_ok">0</b><span>succeeded</span></div>
        <div class="stat"><b id="s_fail">0</b><span>failed</span></div>
        <div class="stat"><b id="s_time">0s</b><span>elapsed</span></div>
        <div class="stat"><b id="s_attempt">1</b><span>attempt</span></div>
      </div>
    </section>
    <section class="panel" style="margin-top:16px">
      <h2>Console</h2>
      <pre id="log"></pre>
    </section>
  </div>
</main>

<script>
const CONFIG = __CONFIG__;
const $ = (id) => document.getElementById(id);
const log = $('log');
let started = 0, timer = null, autoscroll = true;

const pretty = (name) => name.replace(/_/g, ' ').replace(/\\b\\w/g, (c) => c.toUpperCase());

for (const p of CONFIG.parameters) {
  const label = document.createElement('label');
  label.textContent = pretty(p.name);
  let input;
  if (p.kind === 'choice') {
    input = document.createElement('select');
    for (const choice of p.choices) {
      const option = document.createElement('option');
      option.value = choice; option.textContent = choice;
      input.append(option);
    }
  } else {
    input = document.createElement('input');
    input.type = p.kind === 'number' ? 'number' : 'text';
    if (p.kind === 'number') input.min = '1';
  }
  input.id = p.name;
  input.value = p.default;
  label.append(input);
  $('parameters').append(label);
}

for (const name of CONFIG.instructions) {
  const label = document.createElement('label');
  label.textContent = pretty(name);
  const area = document.createElement('textarea');
  area.id = name;
  area.value = CONFIG.defaults[name] || '';
  label.append(area);
  $('instructions').append(label);
}

for (const node of CONFIG.nodes) {
  const chip = document.createElement('span');
  chip.className = 'chip'; chip.id = 'n_' + node; chip.textContent = pretty(node);
  $('rail').append(chip);
}

function line(text, cls) {
  const div = document.createElement('div');
  if (cls) div.className = cls;
  div.textContent = text;
  log.append(div);
  while (log.childElementCount > 4000) log.firstChild.remove();
  if (autoscroll) log.scrollTop = log.scrollHeight;
}

log.addEventListener('scroll', () => {
  autoscroll = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
});

function classify(text) {
  if (/ - ERROR - |^ERROR|Traceback|failed:/.test(text)) return 'err';
  if (/ - WARNING - |^WARNING/.test(text)) return 'warn';
  if (/ - DEBUG - /.test(text)) return 'muted';
  return '';
}

function resetRail() {
  for (const node of CONFIG.nodes) $('n_' + node).className = 'chip';
  $('fill').style.width = '0';
}

function collect() {
  const config = { instructions: {} };
  for (const key of ['runs', 'delay_seconds', 'on_failure', 'max_retries', 'recursion_limit']) {
    config[key] = $(key).value;
  }
  for (const p of CONFIG.parameters) config[p.name] = $(p.name).value;
  for (const name of CONFIG.instructions) config.instructions[name] = $(name).value;
  return config;
}

function reset() {
  for (const [key, value] of Object.entries(CONFIG.run)) $(key).value = value;
  for (const p of CONFIG.parameters) $(p.name).value = p.default;
  for (const name of CONFIG.instructions) $(name).value = CONFIG.defaults[name];
}

reset();

$('start').onclick = async () => {
  const response = await fetch('/start', { method: 'POST', body: JSON.stringify(collect()) });
  if (!response.ok) line('a session is already running', 'warn');
};
$('stop').onclick = () => fetch('/stop', { method: 'POST' });
$('clear').onclick = () => { log.textContent = ''; };
$('copy').onclick = () => navigator.clipboard.writeText(log.textContent);
$('reset').onclick = () => {
  reset();
  line('parameters reset to their defaults', 'ok');
};

function busy(on) {
  $('start').disabled = on;
  $('stop').disabled = !on;
  $('dot').className = on ? 'dot on' : 'dot';
  $('phase').textContent = on ? 'running' : 'idle';
  if (on) {
    started = Date.now();
    timer = setInterval(() => { $('s_time').textContent = Math.round((Date.now() - started) / 1000) + 's'; }, 500);
  } else if (timer) {
    clearInterval(timer); timer = null;
  }
}

const stream = new EventSource('/events');
stream.onmessage = (message) => {
  const event = JSON.parse(message.data);

  if (event.type === 'log') return line(event.line, classify(event.line));

  if (event.type === 'node') {
    const chip = $('n_' + event.name);
    if (chip) chip.className = 'chip done';
    const index = CONFIG.nodes.indexOf(event.name);
    const next = CONFIG.nodes[index + 1];
    if (next) $('n_' + next).className = 'chip active';
    $('fill').style.width = Math.round(((index + 1) / CONFIG.nodes.length) * 100) + '%';
    return;
  }

  if (event.type === 'result') {
    line('--- result ---', 'ok');
    for (const [key, value] of Object.entries(event)) {
      if (key !== 'type' && value) line(key + ': ' + value, 'ok');
    }
    return;
  }

  if (event.type === 'run') {
    if (event.state === 'started') {
      resetRail();
      $('n_' + CONFIG.nodes[0]).className = 'chip active';
      $('s_run').textContent = event.run + ' / ' + event.runs;
      $('s_attempt').textContent = event.attempt;
      line('=== run ' + event.run + ' of ' + event.runs + ', attempt ' + event.attempt + ' ===', 'ok');
    } else if (event.state === 'succeeded') {
      $('s_ok').textContent = Number($('s_ok').textContent) + 1;
      line('=== run ' + event.run + ' succeeded ===', 'ok');
    } else {
      $('s_fail').textContent = Number($('s_fail').textContent) + 1;
      line('=== run ' + event.run + ' failed' + (event.retrying ? ', retrying' : '') + ' ===', 'err');
    }
    return;
  }

  if (event.type === 'session') {
    if (event.state === 'started') {
      $('s_ok').textContent = '0'; $('s_fail').textContent = '0';
      busy(true);
    } else {
      busy(false);
      resetRail();
      line('=== session finished: ' + event.succeeded + ' succeeded, ' + event.failed
        + ' failed, ' + event.elapsed + 's ===', 'ok');
    }
  }
};
</script>
</body>
</html>
'''

class _Handler(BaseHTTPRequestHandler):
    broadcaster: _Broadcaster
    session: _Session

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path == '/':
            config = json.dumps({
                'parameters': _parameters(),
                'instructions': _instruction_fields(),
                'defaults': {name: _INSTRUCTIONS.get(name, '') for name in _instruction_fields()},
                'run': _RUN,
                'nodes': _NODES,
            })
            self._respond(_PAGE.replace('__CONFIG__', config).encode('utf-8'), 'text/html; charset=utf-8')
            return

        if self.path == '/events':
            self._stream()
            return

        self.send_error(404)

    def do_POST(self) -> None:
        if self.path == '/start':
            length = int(self.headers.get('Content-Length', 0))
            config = json.loads(self.rfile.read(length) or b'{}')
            started = self.session.start(config)
            self._respond(json.dumps({'started': started}).encode(), 'application/json', 200 if started else 409)
            return

        if self.path == '/stop':
            self.session.stop()
            self._respond(b'{"stopped": true}', 'application/json')
            return

        self.send_error(404)

    def _respond(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self) -> None:
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()

        client = self.broadcaster.subscribe()

        try:
            while True:
                try:
                    payload = client.get(timeout=15)
                    self.wfile.write(f'data: {payload}\n\n'.encode())
                except queue.Empty:
                    self.wfile.write(b': ping\n\n')

                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.broadcaster.unsubscribe(client)

def main() -> None:
    broadcaster = _Broadcaster()
    _Handler.broadcaster = broadcaster
    _Handler.session = _Session(broadcaster)

    server = ThreadingHTTPServer((_HOST, _PORT), _Handler)
    address = f'http://{_HOST}:{_PORT}'
    print(f'countdown agent console on {address}')
    webbrowser.open(address)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('stopping')

if __name__ == '__main__':
    main()

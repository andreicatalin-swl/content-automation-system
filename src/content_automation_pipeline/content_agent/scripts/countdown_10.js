'use strict';

// Edits the countdown template in Premiere Pro and exports it.
//
// Usage: node countdown_10.js '<payload json>' '<output video path>'
//   payload.script      : { username, title1, title2, subheading, entries: [{ line }] }
//   payload.media_files : [{ audio, video }]  (absolute paths, forward slashes)
//
// Every edit runs as ExtendScript inside Premiere over the ExtendScript Debugger's native bridge,
// so Premiere renders the export itself and no Adobe Media Encoder install is needed.

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');

// Hardcoded values that cannot be overridden by the caller
const TEMPLATE_PATH = 'E:\\Adobe Premiere Pro 2020 Projects\\My Projects\\Templates\\Countdown 10.prproj';
const PRESET_PATH = 'C:\\Program Files\\Adobe\\Adobe Premiere Pro 2020\\MediaIO\\systempresets\\4E49434B_48323634\\01 - Match Source - High bitrate.epr';
const ENTRY_COUNT = 10;
const VIDEO_TRACK_INDEX = 0; // V1
const AUDIO_TRACK_INDEX = 0; // A1
const MOGRT_TRACK_INDEX = 2; // V3
const WORK_AREA_ENTIRE_SEQUENCE = 0;

const CONNECT_TIMEOUT_MS = 5 * 60 * 1000;
const PROJECT_LOAD_TIMEOUT_MS = 10 * 60 * 1000;
const EVAL_TIMEOUT_MS = 2 * 60 * 1000;
const EXPORT_TIMEOUT_MS = 60 * 60 * 1000;
const POLL_INTERVAL_MS = 50;
const PROBE_INTERVAL_MS = 2000;

function log(message) {
    process.stderr.write(`[edit_video] ${message}\n`);
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

// ============================================================================================
// Bridge to the ExtendScript Debugger's native addon
// ============================================================================================

// The extension's version changes on update, so the folder is resolved rather than hardcoded
function findCoreLibPath() {
    const extensionsDir = path.join(os.homedir(), '.vscode', 'extensions');
    const candidates = fs.readdirSync(extensionsDir)
        .filter((name) => name.indexOf('adobe.extendscript-debug-') === 0)
        .sort();

    if (candidates.length === 0) {
        throw new Error('the Adobe ExtendScript Debugger extension is not installed');
    }

    const arch = (process.arch === 'x64' || process.arch === 'arm64') ? 'x64' : 'win32';
    return path.join(extensionsDir, candidates[candidates.length - 1], 'lib', 'esdebugger-core', 'win', arch, 'esdcorelibinterface.node');
}

function findPremiereSpecifier(core) {
    const result = core.esdGetInstalledApplicationSpecifiers();
    if (result.status !== 0) {
        throw new Error(`could not list installed applications, status=${result.status}`);
    }

    const specifier = result.specifiers.filter((name) => name.indexOf('premierepro') === 0).sort().pop();
    if (!specifier) {
        throw new Error('Premiere Pro is not installed');
    }

    return specifier;
}

// Sends one command and pumps the session until the matching response arrives
async function sendAndWait(core, specifier, body, timeoutMs) {
    const sent = core.esdSendDebugMessage(specifier, body, false, timeoutMs);
    if (!sent || sent.status !== 0) {
        throw new Error(`could not send to ${specifier}, status=${sent && sent.status}`);
    }

    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
        let matched = null;
        // A throw inside this callback unwinds through the addon's native frames and takes the
        // whole process down, so nothing in here is allowed to fail
        core.esdPumpSession((reason, message) => {
            try {
                if (message && message.serialNumber === sent.serialNumber) {
                    matched = { reason, message };
                }
            } catch (error) {
                // The message was not one we can read, so it cannot be the response we want
            }
        });

        if (matched) {
            if (matched.reason !== 3) {
                throw new Error(`request failed with reason=${matched.reason}: ${matched.message.body}`);
            }
            return matched.message.body;
        }

        await sleep(POLL_INTERVAL_MS);
    }

    throw new Error('timed out waiting for a response');
}

// The engine name differs per app and version, so it is read off the connect response
async function connect(core, specifier) {
    const deadline = Date.now() + CONNECT_TIMEOUT_MS;

    while (Date.now() < deadline) {
        try {
            const body = await sendAndWait(core, specifier, '<connect/>', PROBE_INTERVAL_MS);
            const match = /<engine\s+name="([^"]+)"/.exec(body);
            if (match) {
                return match[1];
            }
        } catch (error) {
            // Premiere is not accepting connections yet
        }

        await sleep(PROBE_INTERVAL_MS);
    }

    throw new Error('could not connect to Premiere Pro');
}

function wrapWithCDATA(source) {
    return `<![CDATA[${source.split(']]>').join(']]]]><![CDATA[>')}]]>`;
}

function parseEvalResult(body) {
    const error = /<error[^>]*>([\s\S]*?)<\/error>/.exec(body);
    if (error) {
        throw new Error(`ExtendScript error: ${error[1]}`);
    }

    const cdata = /<value[^>]*><!\[CDATA\[([\s\S]*?)\]\]><\/value>/.exec(body);
    if (cdata) {
        return cdata[1];
    }

    const plain = /<value[^>]*>([\s\S]*?)<\/value>/.exec(body);
    return plain ? plain[1] : '';
}

// Every snippet returns either 'OK...' or 'ERROR: ...', because a raw ExtendScript throw only
// surfaces as an opaque 'Unknown error exception' with no detail
async function evaluate(core, specifier, engine, source, timeoutMs) {
    const body = await sendAndWait(core, specifier, `<eval engine="${engine}"><source>${wrapWithCDATA(source)}</source></eval>`, timeoutMs);
    const value = parseEvalResult(body);

    if (value.indexOf('ERROR:') === 0) {
        throw new Error(value.slice('ERROR:'.length).trim());
    }

    return value;
}

// ============================================================================================
// ExtendScript snippets
// ============================================================================================

function jsxProjectName() {
    return `(function () {
    try {
        if (!app || !app.project || !app.project.activeSequence) { return 'ERROR: not loaded'; }
        return 'OK ' + app.project.name;
    } catch (e) {
        return 'ERROR: ' + e.toString();
    }
})()`;
}

// saveAs switches app.project to the copy in place, so the template itself is never touched
function jsxSaveAsCopy(copyPath) {
    return `(function () {
    try {
        var result = app.project.saveAs(${JSON.stringify(copyPath)});
        if (!(result === 0 || result === true)) { return 'ERROR: saveAs returned ' + result; }
        return 'OK ' + app.project.name;
    } catch (e) {
        return 'ERROR: ' + e.toString();
    }
})()`;
}

// The video and audio come from different sources, so they must not share a project item:
// relinking one would otherwise silently relink the other too
function jsxCheckTracks() {
    return `(function () {
    try {
        var sequence = app.project.activeSequence;
        if (!sequence) { return 'ERROR: no active sequence'; }

        var video = sequence.videoTracks[${VIDEO_TRACK_INDEX}];
        var audio = sequence.audioTracks[${AUDIO_TRACK_INDEX}];
        var graphics = sequence.videoTracks[${MOGRT_TRACK_INDEX}];
        if (!video) { return 'ERROR: V${VIDEO_TRACK_INDEX + 1} not found'; }
        if (!audio) { return 'ERROR: A${AUDIO_TRACK_INDEX + 1} not found'; }
        if (!graphics) { return 'ERROR: V${MOGRT_TRACK_INDEX + 1} not found'; }

        if (video.clips.numItems < ${ENTRY_COUNT}) { return 'ERROR: V${VIDEO_TRACK_INDEX + 1} has ' + video.clips.numItems + ' clips, expected ${ENTRY_COUNT}'; }
        if (audio.clips.numItems < ${ENTRY_COUNT}) { return 'ERROR: A${AUDIO_TRACK_INDEX + 1} has ' + audio.clips.numItems + ' clips, expected ${ENTRY_COUNT}'; }
        if (graphics.clips.numItems < 1) { return 'ERROR: V${MOGRT_TRACK_INDEX + 1} has no clips'; }

        for (var i = 0; i < ${ENTRY_COUNT}; i++) {
            var videoItem = video.clips[i].projectItem;
            var audioItem = audio.clips[i].projectItem;
            if (!videoItem) { return 'ERROR: V${VIDEO_TRACK_INDEX + 1} clip ' + i + ' has no project item'; }
            if (!audioItem) { return 'ERROR: A${AUDIO_TRACK_INDEX + 1} clip ' + i + ' has no project item'; }
            if (videoItem.nodeId === audioItem.nodeId) {
                return 'ERROR: V${VIDEO_TRACK_INDEX + 1} and A${AUDIO_TRACK_INDEX + 1} clip ' + i + ' share one project item, so they cannot be relinked separately';
            }
        }

        return 'OK';
    } catch (e) {
        return 'ERROR: ' + e.toString();
    }
})()`;
}

// changeMediaPath on the existing project item is the only relink that keeps effects and transitions
function jsxRelink(trackCollection, trackIndex, paths) {
    return `(function () {
    try {
        var sequence = app.project.activeSequence;
        var track = sequence.${trackCollection}[${trackIndex}];
        var paths = ${JSON.stringify(paths)};

        for (var i = 0; i < paths.length; i++) {
            var item = track.clips[i].projectItem;
            var result = item.changeMediaPath(paths[i], true);
            if (!(result === 0 || result === true)) {
                return 'ERROR: changeMediaPath returned ' + result + ' for clip ' + i;
            }
        }

        return 'OK ' + paths.length;
    } catch (e) {
        return 'ERROR: ' + e.toString();
    }
})()`;
}

// Only AE-authored MOGRTs expose their text this way, and getValue hands back a JSON string
function jsxSetMogrtText(fields) {
    return `(function () {
    try {
        var sequence = app.project.activeSequence;
        var clip = sequence.videoTracks[${MOGRT_TRACK_INDEX}].clips[0];
        var component = clip.getMGTComponent();
        if (!component) { return 'ERROR: the clip on V${MOGRT_TRACK_INDEX + 1} is not an Essential Graphics template'; }

        var fields = ${JSON.stringify(fields)};
        var properties = component.properties;
        var applied = 0;

        for (var f = 0; f < fields.length; f++) {
            var wanted = fields[f].name.toLowerCase();
            var property = null;

            for (var p = 0; p < properties.numItems; p++) {
                var candidate = properties[p];
                if (candidate.displayName && candidate.displayName.toLowerCase() === wanted) {
                    property = candidate;
                    break;
                }
            }

            if (!property) { return 'ERROR: no property named ' + fields[f].name; }

            var data = JSON.parse(property.getValue());
            data.textEditValue = fields[f].text;
            data.fontTextRunLength = [fields[f].text.length];
            property.setValue(JSON.stringify(data), true);
            applied++;
        }

        return 'OK ' + applied;
    } catch (e) {
        return 'ERROR: ' + e.toString();
    }
})()`;
}

// exportAsMediaDirect renders inside Premiere itself, unlike encodeSequence which needs Media Encoder
function jsxExport(outputPath, presetPath) {
    return `(function () {
    try {
        var sequence = app.project.activeSequence;
        var result = sequence.exportAsMediaDirect(${JSON.stringify(outputPath)}, ${JSON.stringify(presetPath)}, ${WORK_AREA_ENTIRE_SEQUENCE});
        if (!(result === 0 || result === true || result === 'No Error')) {
            return 'ERROR: exportAsMediaDirect returned ' + result;
        }
        return 'OK';
    } catch (e) {
        return 'ERROR: ' + e.toString();
    }
})()`;
}

// ============================================================================================
// Premiere Pro
// ============================================================================================

// Premiere's documented /C es.processFile launch flag is unreliable, so the project is opened
// through its file association instead
function openTemplate() {
    return new Promise((resolve, reject) => {
        execFile('cmd', ['/c', 'start', '', TEMPLATE_PATH], (error) => (error ? reject(error) : resolve()));
    });
}

// The project takes a variable amount of time to load, so readiness is polled rather than slept on
async function waitForProject(core, specifier, engine, expectedName) {
    const deadline = Date.now() + PROJECT_LOAD_TIMEOUT_MS;

    while (Date.now() < deadline) {
        try {
            const value = await evaluate(core, specifier, engine, jsxProjectName(), PROBE_INTERVAL_MS);
            if (value.slice('OK '.length) === expectedName) {
                return;
            }
        } catch (error) {
            // The project is still loading, or a different one is still open
        }

        await sleep(PROBE_INTERVAL_MS);
    }

    throw new Error(`${expectedName} did not finish loading`);
}

// ============================================================================================
// Editing
// ============================================================================================

function validate(payload) {
    if (!payload || !payload.script || !payload.media_files) {
        throw new Error('the payload needs a script and media files');
    }

    const entries = payload.script.entries;
    if (!entries || entries.length !== ENTRY_COUNT) {
        throw new Error(`the script has ${entries ? entries.length : 0} entries, expected exactly ${ENTRY_COUNT}`);
    }

    if (payload.media_files.length !== ENTRY_COUNT) {
        throw new Error(`there are ${payload.media_files.length} media files, expected exactly ${ENTRY_COUNT}`);
    }

    for (const media of payload.media_files) {
        if (!fs.existsSync(media.video)) { throw new Error(`no video at ${media.video}`); }
        if (!fs.existsSync(media.audio)) { throw new Error(`no audio at ${media.audio}`); }
    }
}

// The countdown runs from 10 down to 1, so the first entry fills the "Top 10" field
function buildTextFields(script) {
    const fields = [
        { name: 'Title 1', text: script.title1 },
        { name: 'Title 2', text: script.title2 },
        { name: 'Subtitle Text', text: script.subheading },
    ];

    for (let i = 0; i < ENTRY_COUNT; i++) {
        fields.push({ name: `Top ${ENTRY_COUNT - i} Text`, text: script.entries[i].line });
    }

    return fields;
}

// The copy stays next to the template, because rebuilding the directory in ExtendScript was
// observed to drop the separator after the drive letter
function buildCopyPath() {
    const separator = Math.max(TEMPLATE_PATH.lastIndexOf('\\'), TEMPLATE_PATH.lastIndexOf('/'));
    const directory = TEMPLATE_PATH.slice(0, separator + 1);
    const suffix = Math.random().toString(36).slice(2, 10);

    return `${directory}Countdown 10 ${suffix}.prproj`;
}

async function main() {
    const payload = JSON.parse(process.argv[2]);
    const outputPath = process.argv[3];

    validate(payload);
    log(`editing ${ENTRY_COUNT} entries into ${outputPath}`);

    const core = require(findCoreLibPath());
    const initialized = core.esdInitialize('content-automation-pipeline', process.pid);
    if (initialized.status !== 0 && initialized.status !== 11) {
        throw new Error(`could not initialize the bridge, status=${initialized.status}`);
    }

    try {
        const specifier = findPremiereSpecifier(core);
        log(`opening the template in ${specifier}`);
        await openTemplate();

        const engine = await connect(core, specifier);
        log(`connected to the ${engine} engine`);

        await waitForProject(core, specifier, engine, path.basename(TEMPLATE_PATH));
        log('the template finished loading');

        const copyPath = buildCopyPath();
        await evaluate(core, specifier, engine, jsxSaveAsCopy(copyPath), EVAL_TIMEOUT_MS);
        log(`working in ${copyPath}`);

        await evaluate(core, specifier, engine, jsxCheckTracks(), EVAL_TIMEOUT_MS);

        await evaluate(core, specifier, engine, jsxRelink('videoTracks', VIDEO_TRACK_INDEX, payload.media_files.map((media) => media.video)), EVAL_TIMEOUT_MS);
        log(`relinked V${VIDEO_TRACK_INDEX + 1}`);

        await evaluate(core, specifier, engine, jsxRelink('audioTracks', AUDIO_TRACK_INDEX, payload.media_files.map((media) => media.audio)), EVAL_TIMEOUT_MS);
        log(`relinked A${AUDIO_TRACK_INDEX + 1}`);

        await evaluate(core, specifier, engine, jsxSetMogrtText(buildTextFields(payload.script)), EVAL_TIMEOUT_MS);
        log(`set the text on V${MOGRT_TRACK_INDEX + 1}`);

        log('exporting, this renders inside Premiere and takes a while');
        await evaluate(core, specifier, engine, jsxExport(outputPath, PRESET_PATH), EXPORT_TIMEOUT_MS);

        // Every call in this API has been observed returning something other than its documented
        // value, so the export is confirmed against the file system instead
        if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
            throw new Error(`the export reported success but wrote nothing to ${outputPath}`);
        }

        log(`exported ${fs.statSync(outputPath).size} bytes`);
        process.stdout.write(JSON.stringify({ video_path: outputPath, project_path: copyPath }));
    } finally {
        core.esdCleanup();
    }
}

main().catch((error) => {
    log(`failed: ${error.message}`);
    process.exit(1);
});

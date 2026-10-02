// A stand-in for the `vscode` module, enough for GemDB Code's setup to run in
// plain Node: its first-run preparation and its Start command.
//
// What setup actually depends on is real here -- commands, progress, messages,
// settings with the extension's own declared defaults, its output channel.
// Everything else (status bar, tree view, notebooks, the MCP provider) becomes
// a harmless no-op, because a headless setup has nothing to show them on.
// Telemetry is a no-op too: nothing is sent anywhere.
//
// A message with buttons is answered as dismissed. Setup asks one such
// question, whether to configure shared memory, and only when it is not
// configured yet -- CI runs GemDB's own script for that first.

const path = require('path');
const fs = require('fs');

// Anything: callable, constructible, and every property is another Anything
// unless something assigned it (a status bar item's text, say). Not thenable,
// so `await anything` resolves to it rather than hanging.
function anything() {
  const fn = function () { return anything(); };
  const assigned = {};
  return new Proxy(fn, {
    get(target, prop) {
      if (prop in assigned) return assigned[prop];
      if (prop === 'then') return undefined;
      if (prop === Symbol.toPrimitive) return () => '';
      if (prop === Symbol.iterator) return function* () {};
      if (prop === 'dispose') return () => {};
      return anything();
    },
    set(target, prop, value) { assigned[prop] = value; return true; },
    defineProperty(target, prop, descriptor) { assigned[prop] = descriptor.value; return true; },
    apply() { return anything(); },
    construct() { return anything(); },
  });
}

const disposable = () => ({ dispose() {} });
const event = () => () => disposable();

const registry = new Map();
const commands = {
  async execute(id, ...args) {
    const fn = registry.get(id);
    if (!fn) throw new Error(`no command ${id} was registered`);
    return fn(...args);
  },
};

function uri(fsPath) {
  return {
    scheme: 'file', fsPath, path: fsPath,
    toString: () => `file://${fsPath}`,
    with: () => uri(fsPath),
  };
}

function memento() {
  const values = new Map();
  return {
    get: (key, fallback) => (values.has(key) ? values.get(key) : fallback),
    update: async (key, value) => { values.set(key, value); },
    keys: () => [...values.keys()],
    setKeysForSync() {},
  };
}

function settingsDefaults(packageJSON) {
  const declared = packageJSON.contributes && packageJSON.contributes.configuration;
  const groups = Array.isArray(declared) ? declared : declared ? [declared] : [];
  const defaults = {};
  for (const group of groups) {
    for (const [key, spec] of Object.entries(group.properties || {})) {
      if ('default' in spec) defaults[key] = spec.default;
    }
  }
  return defaults;
}

function makeVscode(packageJSON, extensionPath) {
  const defaults = settingsDefaults(packageJSON);
  const say = (level) => async (message) => {
    console.log(`[GemDB ${level}] ${message}`);
    return undefined;              // a button nobody pressed
  };

  class EventEmitter {
    constructor() { this.event = () => disposable(); }
    fire() {}
    dispose() {}
  }
  class Disposable {
    constructor(fn) { this.fn = fn; }
    dispose() { if (this.fn) this.fn(); }
    static from(...ds) { return new Disposable(() => ds.forEach((d) => d && d.dispose && d.dispose())); }
  }
  class Plain { constructor(...args) { Object.assign(this, { args }); } }

  const api = {
    commands: {
      registerCommand(id, fn) { registry.set(id, fn); return disposable(); },
      executeCommand: async (id, ...args) => (registry.has(id) ? registry.get(id)(...args) : undefined),
      getCommands: async () => [...registry.keys()],
    },
    window: {
      showInformationMessage: say('info'),
      showWarningMessage: say('warning'),
      showErrorMessage: say('error'),
      showQuickPick: async () => undefined,
      showInputBox: async () => undefined,
      withProgress: (options, task) => task(
        { report: (p) => p && p.message && console.log(`[GemDB progress] ${p.message}`) },
        { isCancellationRequested: false, onCancellationRequested: () => disposable() }),
      createOutputChannel: (name) => {
        const line = (s) => console.log(`[${name}] ${s}`);
        return {
          name, appendLine: line, append: line, info: line, warn: line, error: line,
          debug: line, trace: line, clear() {}, show() {}, hide() {}, dispose() {},
          replace: line, logLevel: 2, onDidChangeLogLevel: event(),
        };
      },
      createStatusBarItem: () => anything(),
      registerTreeDataProvider: () => disposable(),
      createTerminal: () => anything(),
      showNotebookDocument: async () => undefined,
      onDidCloseTerminal: event(),
      onDidChangeWindowState: event(),
      activeTextEditor: undefined,
      activeNotebookEditor: undefined,
      state: { focused: false },
    },
    workspace: {
      getConfiguration: (section) => ({
        get(key, fallback) {
          const full = section ? `${section}.${key}` : key;
          return full in defaults ? defaults[full] : fallback;
        },
        has: (key) => (section ? `${section}.${key}` : key) in defaults,
        inspect: () => undefined,
        update: async () => {},
      }),
      workspaceFolders: undefined,
      textDocuments: [],
      isTrusted: true,
      onDidChangeConfiguration: event(),
      onDidRenameFiles: event(),
      onDidCloseNotebookDocument: event(),
      openNotebookDocument: async () => anything(),
      fs: anything(),
    },
    env: {
      appName: 'headless', uiKind: 1, sessionId: 'headless', machineId: 'headless',
      remoteName: undefined, language: 'en', isTelemetryEnabled: false,
      onDidChangeTelemetryEnabled: event(),
      openExternal: async () => false,
      clipboard: { writeText: async () => {}, readText: async () => '' },
      createTelemetryLogger: () => ({
        logUsage() {}, logError() {}, dispose() {}, isUsageEnabled: false, isErrorsEnabled: false,
        onDidChangeEnableStates: event(),
      }),
    },
    extensions: {
      getExtension: (id) => (id === `${packageJSON.publisher}.${packageJSON.name}`
        ? { id, packageJSON, extensionPath, extensionUri: uri(extensionPath), isActive: true, exports: {} }
        : undefined),
      all: [],
      onDidChange: event(),
    },
    lm: { registerMcpServerDefinitionProvider: () => disposable() },
    debug: { registerDebugAdapterDescriptorFactory: () => disposable(), breakpoints: [] },
    notebooks: { createNotebookController: () => anything() },
    l10n: { t: (s) => s },
    Uri: { file: uri, parse: (s) => ({ ...uri(s), toString: () => s }), joinPath: (u, ...p) => uri(path.join(u.fsPath, ...p)) },
    EventEmitter,
    Disposable,
    ThemeIcon: Plain, ThemeColor: Plain, TreeItem: Plain, MarkdownString: Plain,
    NotebookCellOutput: Plain, NotebookCellData: Plain, NotebookData: Plain,
    NotebookCellOutputItem: { text: (...a) => new Plain(...a), error: (...a) => new Plain(...a) },
    McpHttpServerDefinition: Plain, CancellationTokenSource: class {
      constructor() { this.token = { isCancellationRequested: false, onCancellationRequested: () => disposable() }; }
      cancel() { this.token.isCancellationRequested = true; }
      dispose() {}
    },
    DebugAdapterInlineImplementation: Plain, SourceBreakpoint: Plain,
    InputBoxValidationSeverity: { Info: 1, Warning: 2, Error: 3 },
    ProgressLocation: { SourceControl: 1, Window: 10, Notification: 15 },
    StatusBarAlignment: { Left: 1, Right: 2 },
    ConfigurationTarget: { Global: 1, Workspace: 2, WorkspaceFolder: 3 },
    NotebookCellKind: { Markup: 1, Code: 2 },
    TreeItemCollapsibleState: { None: 0, Collapsed: 1, Expanded: 2 },
    ViewColumn: { Active: -1, Beside: -2, One: 1 },
    ExtensionMode: { Production: 1, Development: 2, Test: 3 },
    UIKind: { Desktop: 1, Web: 2 },
  };

  // Anything setup never touches still has to exist when the bundle reads it:
  // a call a release adds to a namespace defined here (1.5.4's
  // window.createTreeView, say). A whole name has to be defined above, not
  // left to this: the bundle copies the module's own properties when it loads
  // it, so a name this object does not have is undefined there, not a no-op.
  const orAnything = (object) => new Proxy(object, {
    get(target, prop) { return prop in target ? target[prop] : anything(); },
  });
  for (const name of ['commands', 'window', 'workspace', 'env', 'extensions', 'lm', 'notebooks', 'debug']) {
    api[name] = orAnything(api[name]);
  }
  return orAnything(api);
}

function makeContext(vscode, packageJSON, extensionPath, storage) {
  fs.mkdirSync(storage, { recursive: true });
  return {
    subscriptions: [],
    extensionPath,
    extensionUri: vscode.Uri.file(extensionPath),
    globalStorageUri: vscode.Uri.file(storage),
    storageUri: vscode.Uri.file(storage),
    logUri: vscode.Uri.file(storage),
    globalState: memento(),
    workspaceState: memento(),
    secrets: { get: async () => undefined, store: async () => {}, delete: async () => {}, onDidChange: event() },
    environmentVariableCollection: {
      description: '', persistent: true,
      replace() {}, append() {}, prepend() {}, get() {}, delete() {}, clear() {}, forEach() {},
      getScoped() { return this; },
    },
    extensionMode: 1,
    extension: { id: `${packageJSON.publisher}.${packageJSON.name}`, packageJSON, extensionPath },
    asAbsolutePath: (p) => path.join(extensionPath, p),
  };
}

module.exports = { makeVscode, makeContext, commands };

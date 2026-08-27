/**
 * The desktop shell, ported from World Bible's and deliberately thinner.
 *
 * Electron owns the window; the PyInstaller exe owns everything else. This file
 * starts the backend, waits for its PATHFINDERGM_READY line, points a window at the
 * URL that line carries, and makes sure the backend dies when the window does.
 *
 * The two failure modes it exists to prevent, unchanged from World Bible:
 *   - a window opening on a URL nothing is serving yet, which shows the user a
 *     connection error and looks like a broken install;
 *   - a Python process outliving the window, holding the port, so the next launch
 *     binds somewhere else and the user's bookmark quietly stops mattering.
 *
 * What was NOT ported, and why:
 *   - electron-updater: this repo has no release pipeline to update from yet. Thin
 *     beats speculative.
 *   - the running-jobs quit guard: a model turn in flight is lost on quit, but the
 *     campaign is saved at every resolved turn, so the cost is one unanswered
 *     sentence rather than an hour of generation. Worth revisiting if that changes.
 */

const { app, BrowserWindow, dialog, nativeTheme, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const readline = require('readline');

const READY = 'PATHFINDERGM_READY';
/** No migrations and no collectstatic — a onefile unpack plus Django setup. */
const STARTUP_TIMEOUT_MS = 60_000;

let backend = null;
let backendUrl = null;
let mainWindow = null;
let quitting = false;

const isPackaged = app.isPackaged;
const projectRoot = path.join(__dirname, '..');

/**
 * Packaged, the backend is the PyInstaller exe shipped beside the app. In
 * development it is this machine's Python running the same entry point, so the
 * shell being debugged is the shell that ships.
 */
function backendCommand() {
  if (isPackaged) {
    return {
      command: path.join(process.resourcesPath, 'backend', 'PathfinderGM.exe'),
      args: [],
    };
  }
  const python = process.env.PATHFINDERGM_PYTHON || 'python';
  return { command: python, args: [path.join(projectRoot, 'desktop.py')] };
}

function startBackend() {
  return new Promise((resolve, reject) => {
    const { command, args } = backendCommand();

    // --no-browser: the shell IS the browser. --watch-stdin: stdin closing is how
    // the backend is told to stop — the graceful half; the kill in stopBackend is
    // the axe for a backend that ignores it.
    backend = spawn(command, [...args, '--no-browser', '--watch-stdin'], {
      cwd: isPackaged ? process.resourcesPath : projectRoot,
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    });

    const failFast = setTimeout(() => {
      reject(new Error(
        'The game server did not start within 60 seconds. This usually means the ' +
        'data folder is not writable, or an antivirus is holding the unpack.'
      ));
    }, STARTUP_TIMEOUT_MS);

    readline.createInterface({ input: backend.stdout }).on('line', (line) => {
      if (line.startsWith(READY)) {
        clearTimeout(failFast);
        backendUrl = line.slice(READY.length).trim();
        resolve(backendUrl);
      } else {
        console.log('[backend]', line);
      }
    });

    let stderrTail = '';
    readline.createInterface({ input: backend.stderr }).on('line', (line) => {
      // Kept so a crash can report the actual reason rather than an exit code.
      stderrTail = `${stderrTail}\n${line}`.split('\n').slice(-25).join('\n');
      console.error('[backend]', line);
    });

    backend.on('error', (err) => {
      clearTimeout(failFast);
      reject(new Error(`Could not start the game server (${command}): ${err.message}`));
    });

    backend.on('exit', (code) => {
      backend = null;
      if (quitting) return;
      clearTimeout(failFast);
      reject(new Error(`The game server stopped unexpectedly (exit ${code}).${stderrTail}`));
    });
  });
}

/**
 * Close stdin first — the backend's --watch-stdin thread shuts the server down
 * cleanly and removes its portfile, which is what marks the exit as clean. The
 * delayed kill is for a backend that never noticed; on Windows kill() alone can
 * orphan the PyInstaller child, which is exactly the port-holding ghost the
 * prove_build harness once left behind, so taskkill takes the whole tree.
 */
function stopBackend() {
  if (!backend) return;
  quitting = true;
  const child = backend;
  try {
    child.stdin.end();
  } catch (err) {
    /* already gone */
  }
  setTimeout(() => {
    if (!child || child.killed || child.exitCode !== null) return;
    if (process.platform === 'win32') {
      spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true });
    } else {
      child.kill('SIGKILL');
    }
  }, 3000);
}

function createWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1000,
    minHeight: 640,
    backgroundColor: '#16100b',   // the grimoire's leather, so no white flash
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      // The page is our own Django app, but it renders model-generated text;
      // there is no reason for it to reach Node.
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.loadURL(url);

  // Anything genuinely external (the OGL links, World Bible's repo) belongs in the
  // real browser.
  mainWindow.webContents.setWindowOpenHandler(({ url: target }) => {
    shell.openExternal(target);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, target) => {
    if (!target.startsWith(backendUrl)) {
      event.preventDefault();
      shell.openExternal(target);
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

function showStartupFailure(error) {
  dialog.showErrorBox(
    'Pathfinder GM could not start',
    `${error.message}\n\nIf this keeps happening, the log is in your Pathfinder GM ` +
    'data folder under logs\\pathfindergm.log.'
  );
  app.exit(1);
}

// One window per player. The backend can run twice (the port fallback exists for
// exactly that), but two shells on one campaign directory is two writers on one
// save file. The lock is taken BEFORE the whenReady handler is registered, and the
// ordering is load-bearing: with the handler registered first, a denied second
// instance still reached startBackend while app.quit() was tearing down, spawned a
// backend, and abandoned it — two orphaned servers holding 8917 were found an hour
// later by a packaging test that could not bind it.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    // The grimoire is dark in every scheme; a system-light title bar on top of it
    // reads as somebody else's window. Same fix as World Bible's.
    nativeTheme.themeSource = 'dark';
    try {
      const url = await startBackend();
      createWindow(url);
    } catch (error) {
      showStartupFailure(error);
    }
  });
}

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') app.quit();
  // The hard floor. Measured on a real user close: the window went away and FOUR
  // shell processes plus a live backend stayed — the child's stdio pipes and the
  // delayed-kill timer kept the main process alive, the lingering family held the
  // single-instance lock, and the next launch quit as a "second instance" of a game
  // nobody could see. A single-window game may never outlive its window by more
  // than the backend's grace period.
  setTimeout(() => app.exit(0), 4500);
});

app.on('before-quit', stopBackend);
// Covers a hard exit path where before-quit never fires.
process.on('exit', stopBackend);

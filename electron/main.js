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
 *   - the running-jobs quit guard: a model turn in flight is lost on quit, but the
 *     campaign is saved at every resolved turn, so the cost is one unanswered
 *     sentence rather than an hour of generation. Worth revisiting if that changes.
 *
 * electron-updater WAS on that list — "this repo has no release pipeline to update
 * from yet. Thin beats speculative." It has one now: tagged releases carrying the
 * installer, from v0.1.4 on. See `wireUpdates` at the bottom for what it does and,
 * more to the point, what it refuses to do without being asked.
 */

const { app, BrowserWindow, dialog, nativeTheme, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const readline = require('readline');

const READY = 'PATHFINDERGM_READY';
/**
 * No migrations and no collectstatic — a onefile unpack plus Django setup. 60s was
 * the first value, and it fired on a real launch, 2026-09-04: the unpack took 61
 * seconds on a disk busy with something else, READY arrived one second after the
 * shell had put up "could not start", and a running game sat behind an error box.
 * The window is on screen from the first second now (see createWindow), so a slow
 * start LOOKS like a slow start; this is only for a backend that never comes.
 */
const STARTUP_TIMEOUT_MS = 180_000;
/** How long a first paint may take before the window is shown regardless. */
const SHOW_ANYWAY_MS = 5_000;

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

/**
 * What the window shows before the backend answers: the leather, the name, and
 * the honest word "starting". Inline, because nothing is being served yet.
 */
const STARTING_PAGE = 'data:text/html;charset=utf-8,' + encodeURIComponent(
  '<!doctype html><title>Pathfinder GM</title>'
  + '<body style="margin:0;height:100vh;display:flex;align-items:center;'
  + 'justify-content:center;background:#16100b;color:#c9b48a;'
  + 'font:20px Georgia,serif;letter-spacing:.04em">'
  + '<div style="text-align:center"><div style="font-size:34px;margin-bottom:.6em">'
  + 'Pathfinder GM</div><div style="opacity:.75">Starting the game… the first '
  + 'launch on a slow disk can take a minute.</div></div></body>'
);

function createWindow() {
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

  // Shown on first paint, and failing that, shown anyway. Measured 2026-09-04: the
  // backend answered every route but `/`, whose view was parked on a hung git call;
  // the page never painted, `ready-to-show` never fired, and the user double-clicked
  // twice — once as administrator — and saw nothing. A hidden window is a window the
  // user cannot even close. Electron's own guidance for a slow first paint is to show
  // at once on a `backgroundColor` matching the app; this keeps the flash-free first
  // paint for the normal case and puts the leather on screen within a few seconds
  // for the abnormal one, where the page's own error is then visible.
  const showAnyway = setTimeout(() => {
    if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) mainWindow.show();
  }, SHOW_ANYWAY_MS);
  mainWindow.once('ready-to-show', () => { clearTimeout(showAnyway); mainWindow.show(); });
  // A main-frame load that fails outright (backend gone between READY and here) is a
  // startup failure with a reason, not a blank window. -3 is ERR_ABORTED, which a
  // navigation superseding another raises and which is not a failure.
  mainWindow.webContents.on('did-fail-load', (event, code, description, target, isMainFrame) => {
    if (!isMainFrame || code === -3) return;
    showStartupFailure(new Error(`The game's page failed to load (${description}, ${target}).`));
  });
  // The starting page first; the game's URL replaces it the moment READY arrives
  // (`showGame`). Created BEFORE the backend is spawned, so the user has a window —
  // one they can close — from the first second, however long the unpack takes.
  mainWindow.loadURL(STARTING_PAGE);

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

function showGame(url) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.loadURL(url);
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
      createWindow();
      const url = await startBackend();
      showGame(url);
      // After the game is on screen, never before it. An update check is a network
      // call that can hang for its own timeout, and nothing about it is worth putting
      // between a player and the thing they double-clicked.
      wireUpdates();
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

/**
 * Updates: offered, never applied behind the player's back.
 *
 * `autoDownload` and `autoInstallOnAppQuit` are both OFF. That is the whole design, and
 * it is the same shape as everything else in this app: it finds out what is missing,
 * says so in words, and offers a button. A 115 MB download that starts itself on a
 * metered connection, or a version that changes underneath somebody mid-campaign, is
 * the opposite of that.
 *
 * WHAT IS AND IS NOT VERIFIED, stated plainly because the app is unsigned and will stay
 * that way. `latest.yml` is fetched from GitHub over TLS and carries a SHA-512 of the
 * installer, which electron-updater checks after downloading — so a network attacker
 * cannot substitute a binary. What is absent is the Authenticode check: with no signing
 * certificate there is no publisher name to compare against, so a release published by
 * somebody who had taken the GitHub account would be installed. That is the same trust
 * already placed in the releases page by anyone downloading from it by hand; automating
 * it widens who is affected, which is the honest reason the install stays a button.
 *
 * Failures are logged and never shown. Being offline, GitHub being down, or a rate limit
 * are all normal, and none of them is worth a box in front of somebody's game.
 */
function wireUpdates() {
  // Unpackaged there is no `app-update.yml`, and electron-updater throws rather than
  // shrugging — `prove_shell.py` runs the dev shell and would fail on it.
  if (!isPackaged) return;
  // The provers launch the packaged shell to watch its lifecycle, not to talk to
  // GitHub. Set by `tools/prove_shell.py`.
  if (process.env.PATHFINDER_GM_NO_UPDATE) return;

  let updater;
  try {
    ({ autoUpdater: updater } = require('electron-updater'));
  } catch (error) {
    // The dependency is named in `build.files`; if it is ever dropped from the asar
    // this is the line that says so, in the log, rather than a blank window.
    console.error('[update] electron-updater is not in the build:', error.message);
    return;
  }

  updater.autoDownload = false;
  updater.autoInstallOnAppQuit = false;
  updater.logger = { info: console.log, warn: console.warn, error: console.error,
                     debug: () => {} };

  updater.on('error', (error) => {
    console.error('[update]', error && error.message ? error.message : error);
  });

  updater.on('update-available', async (info) => {
    const { response } = await dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: 'A new version of Pathfinder GM',
      message: `Version ${info.version} is out. You have ${app.getVersion()}.`,
      detail: 'The download is about 115 MB. Nothing is installed until you say so, ' +
              'and your characters, campaigns and worlds are not touched by it.',
      buttons: ['Download it', 'Not now'],
      defaultId: 0,
      cancelId: 1,
    });
    if (response !== 0) return;
    updater.downloadUpdate().catch((error) => {
      console.error('[update] download failed:', error.message);
    });
  });

  updater.on('download-progress', (p) => {
    // In the title bar rather than a progress dialog: the player can carry on playing
    // while it downloads, and a modal would stop them.
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.setTitle(`Pathfinder GM — downloading update ${Math.round(p.percent)}%`);
    }
  });

  updater.on('update-downloaded', async (info) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.setTitle('Pathfinder GM');
    }
    const { response } = await dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: 'Ready to install',
      message: `Version ${info.version} is downloaded.`,
      detail: 'Installing closes the game. Anything you have played is already saved — ' +
              'the campaign is written at the end of every turn.',
      buttons: ['Install and restart', 'Next time I close it'],
      defaultId: 0,
      cancelId: 1,
    });
    if (response === 0) {
      // `quitAndInstall` quits the app, so `before-quit` fires and the backend is
      // stopped the same way it is on any other exit. That ordering is why the backend
      // does not outlive this.
      updater.quitAndInstall();
    } else {
      updater.autoInstallOnAppQuit = true;
    }
  });

  updater.checkForUpdates().catch((error) => {
    console.error('[update] check failed:', error.message);
  });
}

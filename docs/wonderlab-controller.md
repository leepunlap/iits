# Controller connection in the Wonder Lab editors

**Where.** Every Wonder Lab editor loads the same frame (`studio-<hash>/lab-frame.html`, built from
`~/wonderlab-studio/src`), so one control appears in all of them: the L4 lesson pages and the teachers'
遊樂場. It sits in the editor's own top menu bar, after the menus:
`主控板 [UC-Mind100 ▾] [USB 埠 ▾] [連接] [斷開] 未連接`. In the bar it inherits the bar's colour, so it
reads correctly in any theme; if the bar is ever missing it falls back to a floating control at the
bottom left.

The port list holds the ports this page already has permission for. **Web Serial cannot enumerate
ports that were never granted**, so a fresh browser shows `未授權任何埠` plus `＋ 選擇新的埠…`, which
opens the browser's own chooser (filtered to the UC-Mind bridges). Once a board has been granted it
appears in the list with its bridge name (`CH340:7523 (最近使用)`) and can be picked without the
chooser again. `斷開` closes the session and stays disabled until something is connected.

**What it does.** Choosing a model and pressing 連接 asks the browser for a serial port through the
chooser, filtered to the USB bridges a UC-Mind kit uses (CH340/CP210x/FTDI/Arduino/Espressif — the same
`UCMake_PORT_FILTERS` the hardware lab uses), opens it and identifies what answered:

| choice | expected firmware | protocol |
|---|---|---|
| UC-Mind100 | ESP32 | Firmata @57600 |
| UC-Mind300 | AVR/Uno | vendor CLI @115200 (`A…` commands) |

The firmware on a board is not always the one its model implies, so each choice tries its own protocol
first and then the other, and reports what actually answered (`已連接 · firmata` / `已連接 · cli`).
Nothing here flashes a board.

**Reuse.** `src/ucmake-connect.js` imports the L2/L3 protocol modules — `ucmake/firmata.js` and
`ucmake/ucmake_cli.js`, copied from `UCMake-re/lab-device` — rather than reimplementing them. They ship
inside the studio folder, so the import is same-origin and needs no CDN or extra host.

**Build.** `tools/build.mjs` copies a fixed list of our files into the bundle; new modules must be added
there or they will be silently missing at runtime. `ucmake-connect.js` and the two `ucmake/*.js` are in
that list now.

**Verified.** `check_library_import.mjs` boots the real frame headlessly and asserts the bar exists, that
it offers both models, that the button reads 連接, that it starts disconnected, and that the connection
module imports. It cannot press the button: `navigator.serial.requestPort()` needs a user gesture and a
board, so the handshake itself is verified on hardware, by hand.

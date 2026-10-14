# Moving IITS development to another Mac

Two machines matter, and which is which decides everything:

| machine | role | what lives there |
|---|---|---|
| **NUC** (`nuc`, 192.168.48.24) | **the server** | nginx + both portals, the lesson AI service, the deployed lesson sites, the sprite/stage library, the firmware images, `~/iits-repo`, `~/iits-lessons-build`, `~/wonderlab-src`, `~/wonderlab-studio`, `~/wlab-fw` |
| **your Mac** | **the client** | DSH + the chats, Chrome (the headless checks), the workspace on OneDrive, the SSH keys, `~/wonderlab-l23-spike`, `~/.ucmake-build`, the UCMake app |

Almost everything runs on the NUC over SSH, so moving the client is mostly: **DSH + the chats + the SSH keys + a few brew packages**. Nothing needs to be reinstalled on the server.

## 1. DSH and the conversations

1. Install **DeepSeek Harness 0.2.0-rc.2** (the version in use).
2. Copy the state that makes conversations continue:

```
rsync -a ~/.dsh/sessions   newmac:~/.dsh/       # 87 MB - every past conversation
rsync -a ~/.dsh/profiles   newmac:~/.dsh/       # model profiles
```

`~/.dsh` is 717 MB in total (attachments 243 MB, caches, runtimes). **Sessions and profiles are the part worth carrying**; the rest rebuilds itself. Treat `~/.dsh` as secret — it holds credentials.

3. The workspace `/Volumes/OneDrive/03_Academia/IITS` arrives with OneDrive. It contains the docs, `UCMake-re/lab-device` (the protocol + flasher sources) and the curriculum.

## 2. Tooling the checks need

```
brew install node pnpm zstd
# and Google Chrome: the layout checks drive it headlessly
```

Current versions here: node **v26.7.0**, pnpm, zstd, python3 via Homebrew. `arduino-cli` is **only on the NUC** — that is where firmware is compiled.

## 3. Access to the NUC

```
rsync -a ~/.ssh newmac:~/.ssh     # id_rsa + config with the `nuc` host entry
ssh nuc 'echo ok'                 # must work before anything else does
```

With that, every workflow in this project works unchanged: the lesson build, deploys, the live checks, `build_lessons_site.py`, nginx, the services.

## 4. Mac-only trees worth copying

| path | size | what |
|---|---|---|
| `~/wonderlab-l23-spike` | 29 MB | the L2/L3 spike: `device.py`, evidence, firmware images (`wlab.ino.bin`, `lcd_direct_UC300.ino.hex`) |
| `~/.ucmake-build` | 17 MB | UCMake's own generated sketch + build |
| `~/src/ucmake-studio` | 97 MB | OpenBlock studio checkout (optional) |
| `/Applications/UCMakeDesktop-INT.app` | — | needed if you still connect with UCMake |

## 5. The risk to fix BEFORE moving

Two trees on the NUC are **not under version control at all**:

```
~/wonderlab-studio     # the editor source every lesson and the playground loads
~/wonderlab-src        # lab.js / lab.css, the pane layout, the engine build
```

They exist only as files on that one machine, and they are the source for live student software. Initialise a repo, add a `.gitignore` for `node_modules/` and `dist/`, and push somewhere — then a new Mac can simply clone them. `~/iits-lessons-build` is a repo but has **no remote**, so it is a single point of failure too.

## 6. Verify the new machine

```
ssh nuc 'echo ok'                                     # 1. the server
cd /Volumes/OneDrive/03_Academia/IITS/UCMake-re/lab-device
node check_portal_layout.mjs                          # 2. Chrome + node + the live portals
node check_lesson_index.mjs /tmp/l4idx                # 3. the lesson index scroll
node check_library_import.mjs                         # 4. the editor frame
```

The layout checks fetch the deployed page themselves; the lesson-lab check needs the AI service tunnel:

```
ssh -f -N -L 18811:127.0.0.1:8811 nuc
```

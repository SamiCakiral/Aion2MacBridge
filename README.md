# Aion2MacBridge

**Run AION 2 on Apple Silicon Macs using CrossOver, Rosetta, and your native Steam session.**

I tried everything to play AION 2 on my Mac. Since I couldn't find a solution that worked on my setup, I kept researching and experimenting with the help of AI until I could launch the game and play. Here is my patch and the guide to reproduce that setup.

This project builds on [NotProton](https://github.com/NotProtonNot/NotProton). It adds a local build of the loader patch for the Intel engine and scripts that explicitly select Rosetta while using your Mac's existing Steam session. **No extra copy of the game is required.**

## What has been verified

The repository owner confirmed playing on the following configuration on October 9, 2026:

| Component | Tested configuration |
| --- | --- |
| Mac | Apple Silicon M4 Max, 64 GB RAM |
| macOS | 27.0, build 26A428 |
| CrossOver Preview | 27.0.0.41069, October 6, 2026 archive |
| NotProton | 1.0.3; patch sources at commit `599ebf6a4cfa52b46c03299170ccbde8f8fe2205` |
| Game | AION 2 on Steam, App ID `3393110` |
| Runtime | CrossOver x86_64 engine through Rosetta, with native Steam signed in |

Steam API initialization and its signed-in state were also verified. The ARM/FEX route used during the first attempts failed; selecting the Intel route and preparing its Steam bridge allowed the game to launch successfully. This does not establish a single cause for every ARM failure or guarantee compatibility with every Mac or future update.

**The scripts below are a cleaned-up version of the working prototype.** The rebuilt patch matches the prototype binary; the complete fresh-install procedure still needs confirmation on other machines. No game files or anti-cheat files are replaced.

## Requirements

1. An Apple Silicon Mac with Rosetta installed.
2. A legitimate installation of CrossOver Preview **27.0.0.41069, dated October 6, 2026**. The builder rejects other DLLs because the patch is version-specific. Get CrossOver from [CodeWeavers](https://www.codeweavers.com/preview/).
3. [NotProton](https://github.com/NotProtonNot/NotProton), installed and configured with that CrossOver engine. Its support directory must contain `runners/current` and `bridge`, including `bridge/x86_64-unix/lsteamclient.so`.
4. **Native Steam for macOS**, already signed in, with AION 2 installed and the NotProton compatibility tool selected for the game. Handle any terms or sign-in prompts yourself in Steam.
5. Python 3.10 or newer, Apple's command-line tools (`xcode-select --install`), and LLVM tools providing `ld.lld` and `llvm-objcopy`.

With Homebrew, install the LLVM tools using `brew install llvm lld`. If the executables are in different directories, add both directories to `PATH` and omit `--llvm-bin` below. The original experiment used `ld.lld` and `llvm-objcopy` from llvm-mingw 20261006; output produced with another compiler may differ and will be reported.

## 1. Download the scripts and build the patch

```sh
git clone https://github.com/SamiCakiral/Aion2MacBridge.git
cd Aion2MacBridge
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python build_patch.py --llvm-bin "$(brew --prefix llvm)/bin"
```

If `ld.lld` was installed separately, use this instead:

```sh
export PATH="$(brew --prefix llvm)/bin:$(brew --prefix lld)/bin:$PATH"
.venv/bin/python build_patch.py
```

The original CrossOver DLL stays in the application and is not modified during this step. The patched DLL is built **locally on your Mac** at `build/ntdll.dll`; it is not distributed on GitHub.

The expected SHA-256 hash of the tested output is:

```text
e5ef486376a9c2cac9ff0cac8867c96a8c85f725174363f754b92ca23f6fab56
```

If the builder reports a different result, do not treat it as the verified binary. Check your toolchain versions before launching the game. The launcher also rejects patches whose hash differs from the working build.

## 2. Prepare the small dedicated bottle

Close games and applications using the **same NotProton engine** before this step. Keep native Steam signed in. Do not open Windows Steam: another sign-in to the same account can replace the native session.

```sh
.venv/bin/python bridge.py setup
```

This creates `~/Library/Application Support/Aion2MacBridge/pfx`, initializes Wine, and installs the Steam bridge components already supplied by NotProton. The prototype used approximately **511 MiB**, excluding the game; actual space requirements may vary. It neither copies nor downloads AION 2 and refuses to reinitialize an existing bottle.

If the game is already installed in a CrossOver bottle but is missing from your native Steam library, make it accessible to native Steam before continuing. On the tested machine, `Steam/steamapps/common/AION2` was a symbolic link to the existing CrossOver installation. That link alone does not register the game with Steam: check that native Steam recognizes the installation before starting any installation or download. These scripts do not automatically change that registration.

## 3. Play

With native Steam open and signed in, run:

```sh
.venv/bin/python bridge.py capture
.venv/bin/python bridge.py launch
```

The first command requests a launch from Steam and captures its fresh authentication parameters in a private local file. It then restores the original NotProton script. If Steam displays a dialog, handle it during this step, then run `capture` again if necessary.

The second command starts **your existing game installation** using CrossOver's Intel engine and the native Steam bridge. Keep this terminal open while playing. Repeat both commands for each new session: launch parameters expire and must not be reused the next day.

The capture contains temporary authentication data. **Never publish the local state directory, launch arguments, or private logs.** None of those files are stored in this repository.

## How it works and how to restore the original files

The script temporarily stages two files in the NotProton engine: the patched x64 `ntdll.dll` and the x64 `lsteamclient.so` library. The dedicated bottle receives the Steam bridge. The game is then executed directly by `lib/wine/x86_64-unix/wine`, bypassing automatic ARM selection.

The engine files are backed up before modification and restored on normal exit, terminal interruption, and handled errors. **Do not run other applications with this engine while playing.** A power loss or forced termination may prevent automatic restoration. After closing the game, run:

```sh
.venv/bin/python bridge.py recover
```

Recovery uses a persistent local backup. It does not delete the bottle or game saves. Do not run `recover` during a game session.

To use different paths, pass `--runner`, `--bridge`, `--prefix`, `--state`, or `--patch`. Use the same options for `setup`, `capture`, `launch`, and `recover`. See `bridge.py --help` and `build_patch.py --help`. Do not use an existing ARM bottle as `--prefix`: the bottle must be initialized with the Intel engine.

## Troubleshooting

- **Steam does not provide a launch:** check its window and confirm that NotProton is selected for AION 2. An earlier launch may still be active; stop it through Steam before running `capture` again. Do not sign out of your account.
- **Unsupported DLL:** check the exact CrossOver Preview version and use its original x64 DLL to build the patch.
- **Unfinished transaction:** close the game, then run `recover` with the same paths.
- **Bottle already exists:** do not rerun `setup`; use `capture`, then `launch`. If the initial setup failed, preserve its logs and investigate before recreating the bottle.
- **Crash:** local logs are stored in `~/Library/Application Support/Aion2MacBridge/state`. Inspect them locally and remove identifiers and authentication parameters from any excerpts you share.

## Credits and license

The Steam bridge and loader detour come from **NotProton**, without which this solution would not exist. This repository contributes the Intel patch build with an explicit Windows calling convention and the scripts that orchestrate the configuration that worked for AION 2.

See [NOTICE.md](NOTICE.md) for the upstream commit and file provenance. Code is distributed under **GPL-3.0**; see [LICENSE](LICENSE). CrossOver, Steam, Rosetta, and AION 2 remain external dependencies.

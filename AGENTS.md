# Agent Guidelines

- Never use `getattr` or `setattr`.
- Use type hints.
- Write clean code. If you're writing many `if` statements, you're probably doing it wrong.
- Avoid keyword-only `*` in method/function signatures unless explicitly requested.
- Before you commit, run pre-commit `ruff-format`, then commit and push the changes (use a dedicated branch for each session). If pre-commit returns errors, fix them. For pre-commit to work, `cd` into the current project and activate the environment.
- Ensure git hooks can resolve `python`: run commit/pre-commit commands with the project venv first on `PATH`, e.g. `PATH=\"$(poetry env info -p)/bin:$PATH\" poetry run pre-commit run ruff-format --files <files>` and `PATH=\"$(poetry env info -p)/bin:$PATH\" git commit -m \"<message>\"`.

## App Run + GUI Interaction Notes

- Launch the app demo with `DISPLAY=desktop:0 poetry run python demo.py`.
- For GUI pytests where you want to see windows on the running X server, force the display and Qt platform:
  - `DISPLAY=desktop:0 QT_QPA_PLATFORM=xcb poetry run pytest <test> -vv -s`
- Screenshot the X server via a tiny PyQt6 script using `QGuiApplication` + `primaryScreen().grabWindow(0)`.
- Best practice for clicks:
  - Ensure window focus (`xdotool windowactivate --sync <id>`).
  - Use `--clearmodifiers` and/or explicit `mousedown`/`mouseup`.
  - If a button ignores clicks, try small coordinate offsets or absolute screen coords.
  - Keyboard fallback: tab to focus, then `Return` or `space`.

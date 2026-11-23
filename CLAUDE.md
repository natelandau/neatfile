# neatfile

CLI that normalizes filenames and files them into project folders. Code: `src/neatfile/`. Tests: `tests/`.

## Checks

Run every check through duty, not the tool directly (`pytest`, `typos`, `prek`, `ruff`, `ty`). gate-cache wraps the test, typos, and prek duties, and a direct run neither reads nor writes its shared pass markers.

| Check | Command |
| --- | --- |
| Tests with coverage | `uv run duty test` |
| All linters, including the format check | `uv run duty lint` |

- Extra pytest arguments (`uv run duty test -k name`) bypass the cache and always run.
- A gate that prints `already passed on` passed on this content. Treat it as passed; do not rerun the tool to confirm.
- Before adding, changing, or scoping a gate in `duties.py`, run `uv run gate-cache --skill` and follow it.
- If the tests start reading a tracked path outside `TEST_GATE_PATHS` in `duties.py`, add the path there in the same change.

## Tests

- Tests run in random order. To reproduce an order-dependent failure, rerun with the printed seed: `uv run duty test --randomly-seed=N`.
- An autouse fixture in `tests/conftest.py` resets settings to `src/neatfile/default_config.toml` before each test. Replace `SettingsManager._instance` only through `monkeypatch`, so the shared instance comes back.
- The first test run downloads the similarity model to `.cache/models` and needs network access.

## Code

- `neatfile.settings` is a global Dynaconf instance with untyped attributes. Before narrowing a setting (`match`, `assert_never`), assign it to a typed local.
- To add a setting, add it to `src/neatfile/default_config.toml`, add its `Validator` in `SettingsManager.initialize` (`src/neatfile/config.py`), and document it in the README sample configuration.
- Import cappa's functions as `from cappa.base import command, invoke`, not as `cappa.command` or `cappa.invoke`. ty resolves those names to cappa's submodules.

## Manual runs

Run the CLI only against the sandbox that `uv run duty dev-setup` builds in `.development/`, never against real files. The CLI loads `.development/dev-config.toml` automatically. Add `-n` (dry run) to preview changes.

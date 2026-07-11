# TODO

Tracked follow-ups for `sparcli`. Ordered by priority.

1. After the first PyPI publish, verify the README badges and image links resolve. The PyPI version and Python-versions badges populate only once the package is live, and the screenshots load via absolute `raw.githubusercontent.com` URLs, which resolve only after the repository is pushed to `github.com/cgroening/py-sparcli` (branch `main`).
2. Keep the README screenshots (`images/screenshot-1.png`, `screenshot-2.png`) in sync with the output/input showcases when widgets or their default styling change. They are colored captures of `output_readme.py` and `prompt_readme.py`; the inline ASCII blocks remain the deterministic reference.
3. Consider mirroring this documentation/metadata polish to the Rust `sparcli` port (README badges, `CONTRIBUTING`/`SECURITY`/`CODE_OF_CONDUCT`, `Cargo.toml` metadata) to keep the two ports in parity.

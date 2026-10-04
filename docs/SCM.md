# Software configuration management (Exp 7)

* **Repository:** Git. `main` always holds released, tested code.
* **Branching:** one `feature/*` branch per sprint module, merged into `develop` with `--no-ff`, `develop` merged into `main` at each release.
* **Tags:** annotated tags `v0.2.0` ... `v1.0.0`, one per sprint (see CHANGELOG.md).
* **Commits:** imperative subject line, grouped by module (see `git log --graph --oneline`).
* **Ignored:** virtualenv, SQLite database, uploaded images, caches (`.gitignore`).
* **Change control:** a change is accepted only if `pytest` passes; the traceability matrix is updated when a requirement changes.
* **Baselines:** each tag is a baseline; reproduce one with `git checkout v0.5.0`.

# Contributing to Iragi

Thank you for your interest in contributing to **Iragi**! To maintain code quality, robustness, and stability, all contributions are subject to automated DevOps quality gates.

---

## 1. Automated CI Quality Gates

Every Pull Request automatically triggers GitHub Actions CI. **Your PR will be rejected if:**
1. Any unit or integration test fails (`pytest`).
2. Sphinx documentation generation produces broken references or build errors (`sphinx-build`).
3. Packaging integrity checks fail (`python -m build` & `twine check`).
4. Undocumented public modules, functions, or classes are introduced.

---

## 2. Development Standards

- **Python Version:** Python 3.10 to 3.14+
- **Sphinx Documentation:** Every module, function, class, and method must include Sphinx-style docstrings with parameter definitions, return types, and at least one reproducible usage example.
- **Isolation:** Modules must remain loosely coupled (`scan` and `pdf` engines must run independently without hard mutual dependencies).
- **Security:** Never commit credentials, `.env` files, or temporary artifacts.

---

## 3. Local Verification Before Pushing

Before opening a PR, run the local scripts in `bin/`:

```bash
# 1. Run tests
./bin/test

# 2. Verify documentation compilation
./bin/docs --clean

# 3. Verify packaging
./bin/build
```

<!-- Pull Request Template -->

## Description

Please include a concise summary of the change, the motivated problem, and relevant context.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## DevOps & Quality Checklist

Before submitting this PR, verify that all checks pass locally:

- [ ] My code follows the project style guidelines.
- [ ] All functions and classes are documented using **Sphinx format**.
- [ ] At least one usage example is added to the documentation/docstrings.
- [ ] I have added tests that prove my fix is effective or that my feature works (`./bin/test`).
- [ ] New and existing tests pass locally with pytest.
- [ ] Documentation compiles without errors (`./bin/docs --clean`).
- [ ] Package builds cleanly (`./bin/build`).
- [ ] No `.env`, secrets, or temporary files are tracked.

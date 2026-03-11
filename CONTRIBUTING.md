# Contributing to GoodQ4All

Thank you for your interest in contributing to GoodQ4All! We're excited to build this local-first, privacy-preserving multimodal intelligence system together.

## 🌟 Ways to Contribute

- **Report Bugs** – Open issues with detailed reproduction steps
- **Suggest Features** – Share ideas for new capabilities
- **Improve Documentation** – Help make the project more accessible
- **Submit Code** – Fix bugs or implement new features
- **Test & Validate** – Run the pipeline and report your results

## 🚀 Getting Started

### 1. Fork & Clone

```bash
# Fork on GitHub, then:
git clone https://github.com/YOUR_USERNAME/goodq4all.git
cd goodq4all
```

### 2. Set Up Development Environment

Follow the [Installation Guide](docs/guides/install/INSTALL.md) and the
[bootstrap installer guide](docs/bootstrap/INSTALL_BOOTSTRAP.md) to set up:
- the baseline Conda environment from `environment.yml`
- optional WSL2 audio acceleration
- optional GPU acceleration for `GPU_ENHANCED`
- model caches downloaded on demand

### 3. Create a Feature Branch

```bash
git checkout -b feature/your-amazing-feature
```

## 📋 Code Standards

### Python Style
- **Formatter:** Black (`black .`)
- **Linting:** Flake8 for PEP 8 compliance
- **Type Hints:** Required for all new functions
- **Docstrings:** Google-style docstrings for public APIs

Example:
```python
def process_scene(scene_data: Dict[str, Any], config: Config) -> SceneBundle:
    """Process a single scene with multimodal analysis.
    
    Args:
        scene_data: Dictionary containing scene metadata and paths
        config: Configuration object with processing parameters
        
    Returns:
        SceneBundle with extracted entities and embeddings
        
    Raises:
        ProcessingError: If any analysis step fails critically
    """
    pass
```

### Logging
- Use the project's existing module-level logging conventions
- Log levels: DEBUG for detailed traces, INFO for milestones, WARNING for recoverable issues, ERROR for failures
- Include context: scene IDs, file paths, timestamps

### Testing
- Add unit tests for new utilities (`tests/unit/`)
- Integration tests for pipeline changes (`tests/integration/`)
- Document test data requirements

## 🔄 Contribution Workflow

### 1. Make Your Changes
- Keep commits atomic and focused
- Write clear commit messages
- Test thoroughly on your local setup

### 2. Commit with Clear Messages

```bash
git commit -m "feat: Add emotion detection to audio pipeline

- Integrate Wav2Vec2 emotion classifier
- Add 8-class emotion output to result.json
- Update audio processing documentation"
```

**Commit Prefixes:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code restructuring without behavior change
- `test:` Add or update tests
- `chore:` Maintenance tasks

### 3. Push and Open Pull Request

```bash
git push origin feature/your-amazing-feature
```

Open a PR on GitHub with:
- **Clear title** describing the change
- **Description** explaining the problem and solution
- **Testing notes** showing how you validated the change
- **Screenshots/logs** if applicable

### 4. Code Review Process
- Maintainers will review within 48-72 hours
- Address feedback in new commits
- Once approved, your PR will be merged

## 🐛 Reporting Bugs

**Great bug reports include:**
1. **System specs** – OS, GPU, CUDA version, Python version
2. **Reproduction steps** – Exact commands that trigger the issue
3. **Expected vs Actual** – What should happen vs what does happen
4. **Logs** – Relevant excerpts from runtime logs or step telemetry
5. **Configuration** – Any custom settings in `configs/config.local.yaml`

Use the repository issue tracker on GitHub.

## 💡 Feature Requests

We love new ideas! When suggesting features:
- **Use Case** – Describe the problem you're trying to solve
- **Proposed Solution** – How you envision it working
- **Alternatives** – Other approaches you considered
- **Impact** – Who would benefit from this feature

## 🧪 Testing Guidelines

### Local Testing
Before submitting a PR:

```bash
# Unit suite configured by pytest.ini
python -m pytest -q

# Docs/public-surface drift checks
python scripts/docs/doc_drift_lint.py

# Bootstrap/install readiness checks
scripts/bootstrap_validate.bat
```

### Integration Testing
For changes affecting the pipeline:
1. Use the smallest scoped runtime validation that matches the change
2. Prefer targeted smoke checks over full ingestion reruns
3. Validate persisted artifacts only when the change touches runtime behavior
4. Document any non-default environment assumptions in the PR notes

## 📚 Documentation Standards

When updating documentation:
- Keep the README focused on getting started
- Move detailed guides to `docs/`
- Use clear section headers
- Include code examples
- Update the Table of Contents

## 🔐 Security Considerations

- **Never commit credentials** – Use `.env` files (gitignored)
- **Validate inputs** – Sanitize file paths and user data
- **Log safely** – Avoid logging sensitive information
- **Dependencies** – Use the public baseline in `environment.yml` and the role-specific lockfiles under `envs/locks/`

## 🤝 Community Guidelines

- **Be respectful** – Assume good intent, provide constructive feedback
- **Be patient** – Maintainers are volunteers
- **Be collaborative** – Help others learn and grow
- **Be inclusive** – Welcome contributors of all skill levels

## 📞 Getting Help

- **GitHub Issues** – For bugs and feature requests
- **Discussions** – For questions and community support
- **Security** – Do not post secrets or private data in public issues

## 🎖️ Recognition

Contributors will be recognized in:
- Project README contributors section
- Release notes
- Project documentation

Thank you for making GoodQ4All better! 🚀

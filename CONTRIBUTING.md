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

Follow the [Installation Guide](README.md#installation) to set up:
- Python environment (goodq_core)
- WSL2 audio stack
- GPU dependencies (CUDA 12.8+)
- Required models

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
- Use the project's logging framework (`common/logging_setup.py`)
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
4. **Logs** – Relevant excerpts from `logs/ingestion.log` or `logs/watchdog.log`
5. **Configuration** – Any custom settings in `config.yaml`

Use the [Issue Template](https://github.com/jbmiller10/goodq4all/issues/new) on GitHub.

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
# Run ingestion on a small test video
python -m cli.run_ingestion --input-dir samples/ingestion/ --max-scenes 5

# Check logs for errors
cat logs/ingestion.log | grep ERROR

# Verify database writes
python -m cli.query_memory --list-videos
```

### Integration Testing
For changes affecting the pipeline:
1. Test with sample video (5-10 scenes)
2. Verify all output artifacts exist
3. Check database entries in memory.db and knowledge_graph.db
4. Validate Qdrant vector insertion

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
- **Dependencies** – Use pinned versions in `requirements.txt`

## 🤝 Community Guidelines

- **Be respectful** – Assume good intent, provide constructive feedback
- **Be patient** – Maintainers are volunteers
- **Be collaborative** – Help others learn and grow
- **Be inclusive** – Welcome contributors of all skill levels

## 📞 Getting Help

- **GitHub Issues** – For bugs and feature requests
- **Discussions** – For questions and community support
- **Email** – contact@goodq4all.org (for security issues)

## 🎖️ Recognition

Contributors will be recognized in:
- Project README contributors section
- Release notes
- Project documentation

Thank you for making GoodQ4All better! 🚀

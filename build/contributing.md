# Contributing to EM Tools

Thank you for your interest in contributing to EM Tools! This document provides guidelines and information for contributors.

## Table of Contents

- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Community Guidelines](#community-guidelines)

## How Can I Contribute?

### 🐛 Report Bugs

Report bugs by [opening an issue](https://github.com/zalmoxes-laran/EM-blender-tools/issues/new) with:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Blender version, EM Tools version)
- Screenshots or error messages

### 💡 Suggest Features

Suggest enhancements by:
1. Checking if the feature is already in our [ROADMAP.md](ROADMAP.md)
2. [Opening an issue](https://github.com/zalmoxes-laran/EM-blender-tools/issues/new) with:
   - Clear use case description
   - Why this feature would be useful
   - Possible implementation approach

### 🔧 Submit Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit with a descriptive message (`git commit -m 'Add amazing feature'`)
5. Push to your fork (`git push origin feature/amazing-feature`)
6. Open a Pull Request

### 📖 Improve Documentation

- Fix typos or clarify existing documentation
- Add missing documentation
- Create tutorials or examples
- Translate documentation

## Development Setup

### Prerequisites

- Blender 4.0+
- Python 3.11
- Git
- Visual Studio Code (recommended)
- Blender Development extension for VSCode

### Setting Up Your Environment

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR-USERNAME/EM-blender-tools.git
   cd EM-blender-tools
   ```

2. **Install Dependencies**
   ```bash
   python scripts/setup_development.py
   ```

3. **Configure for Development**
   ```bash
   python scripts/switch_dev_mode.py dev
   ```

4. **Open in VSCode**
   ```bash
   code .
   ```

5. **Start Blender Development**
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Run `Blender: Start`

See [Development Guide](docs/installation.rst#development-setup) for detailed instructions.

## Code Style

### Python Code

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Use descriptive variable names
- Maximum line length: 120 characters
- Use type hints where appropriate

### Documentation

- Add docstrings to all functions and classes
- Use Google-style docstrings:
  ```python
  def function_name(param1: str, param2: int) -> bool:
      """Short description of function.
      
      Args:
          param1: Description of param1
          param2: Description of param2
          
      Returns:
          Description of return value
          
      Raises:
          ValueError: If param2 is negative
      """
  ```

### Commit Messages

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- First line should be 50 characters or less
- Reference issues and pull requests

Example:
```
Add support for multiple graph import

- Allow users to import multiple GraphML files
- Add graph switching in UI
- Update documentation

Fixes #123
```

## Pull Request Process

1. **Before Submitting**
   - Update documentation if needed
   - Add tests for new functionality
   - Ensure all tests pass
   - Update CHANGELOG.md with your changes

2. **PR Description**
   - Clear description of changes
   - Link to related issues
   - Screenshots for UI changes
   - Testing instructions

3. **Review Process**
   - Address review feedback
   - Keep PR up to date with main branch
   - Be patient - reviews may take time

4. **After Merge**
   - Delete your feature branch
   - Update your local main branch

## Issue Guidelines

### Bug Reports

Use the bug report template and include:
- Clear, descriptive title
- Steps to reproduce
- Expected behavior
- Actual behavior
- System information
- Error messages or logs

### Feature Requests

Use the feature request template and include:
- Clear, descriptive title
- Problem description
- Proposed solution
- Alternative solutions considered
- Additional context

### Good First Issues

Look for issues labeled `good first issue` - these are great for newcomers!

## Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive criticism
- No harassment or discrimination

### Communication Channels

- **GitHub Issues**: Bug reports, feature requests
- **Pull Requests**: Code contributions
- **Telegram Group**: [Join here](https://t.me/UserGroupEM)
- **Email**: emanuel.demetrescu@cnr.it

### Getting Help

- Check documentation first
- Search existing issues
- Ask in Telegram group
- Create a new issue if needed

## Recognition

Contributors will be:
- Listed in the [Contributors](https://github.com/zalmoxes-laran/EM-blender-tools/graphs/contributors) page
- Mentioned in release notes
- Credited in documentation

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 License.

---

Thank you for contributing to EM Tools! 🎉

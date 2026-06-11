# Pre-commit Hooks

This project includes pre-commit hooks to ensure code quality before commits.

## Setup

### Option 1: Simple Script (Recommended)

The `pre-commit` script runs automatically if placed in `.git/hooks/`:

```bash
# Copy the pre-commit hook
cp pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Option 2: Pre-commit Framework

For more advanced checks using the pre-commit framework:

```bash
# Install pre-commit
pip install pre-commit

# Install the hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

## What Gets Checked

The pre-commit hook performs essential checks only:

1. **Sensitive Files** - Prevents committing `.env` files (CRITICAL)
2. **Merge Conflicts** - Detects unresolved merge conflict markers
3. **Ruff Format** - Ensures code is properly formatted
4. **Ruff Lint** - Checks for linting issues and auto-fixes when possible
5. **Large Files** - Warns if files >1MB are being committed

## Using Pre-commit Framework

The `.pre-commit-config.yaml` includes:

- **File Checks**: trailing whitespace, end-of-file, YAML/JSON validation
- **Code Formatting**: Ruff (fast Python formatter - replaces Black)
- **Import Sorting**: Ruff (replaces isort)
- **Linting**: Ruff (replaces flake8)
- **Security**: bandit (security vulnerability scanner)

### Ruff Configuration

Ruff is configured via `ruff.toml` with:
- Line length: 120 characters
- Python version: 3.12
- Auto-fix enabled for most rules
- Test-specific ignores for common patterns

To format code manually:
```bash
ruff format .
```

To lint and auto-fix:
```bash
ruff check --fix .
```

## Skipping Checks

To skip pre-commit checks (not recommended):

```bash
git commit --no-verify
```

## CI/CD Integration

GitHub Actions workflow (`.github/workflows/pre-commit.yml`) runs pre-commit checks on:
- Pull requests
- Pushes to main/master/develop branches

## Troubleshooting

### Hook not running

Make sure the hook is executable:
```bash
chmod +x .git/hooks/pre-commit
```

### Tests taking too long

Set `SKIP_TESTS=1` environment variable or modify the hook to skip tests by default.

### Pre-commit framework issues

Update hooks:
```bash
pre-commit autoupdate
```


# envsync

A powerful CLI tool for managing multi-environment configuration files with encryption, validation, and templating.

## Features

- 🔐 **Encryption** - Secure sensitive configuration values using AES encryption
- 📝 **Templating** - Use variables in .env/.json/.yaml/.toml files with substitution
- ✅ **Validation** - Validate configurations against JSON Schema or custom rules
- 📊 **Diff** - Compare environments, files, and snapshots
- 📸 **Snapshots** - Create point-in-time snapshots and roll back
- 📤 **Export** - Export to multiple formats (JSON, YAML, TOML, .env)
- 📥 **Import** - Import from existing configuration files
- 🔄 **Render** - Render template files with environment variables

## Installation

```bash
# From source
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Quick Start

### 1. Initialize envsync

```bash
envsync init
```

This creates the configuration directory and a default template.

### 2. Create an Environment

```bash
envsync env create development
```

### 3. Set Variables

```bash
# Set a regular variable
envsync env set development DATABASE_URL "postgresql://user:pass@localhost:5432/devdb"

# Set an encrypted sensitive variable
envsync env set development API_KEY "secret-api-key-123" --encrypted

# Set with type and description
envsync env set development PORT 8000 --type int --description "Server port"
```

### 4. View Environment

```bash
# Show variables in table format
envsync env show development

# Show with decrypted sensitive values
envsync env show development --decrypt

# Export to JSON format
envsync env export development --format json
```

### 5. Validate Configuration

```bash
# Validate against the default template
envsync env validate development

# Validate against a custom template
envsync env validate development --template production

# Validate with custom rules
envsync env validate development --rules ./validation-rules.json
```

### 6. Compare Environments

```bash
# Compare two environments
envsync diff env development production

# Show unified diff format
envsync diff env development production --format unified

# Compare with a file
envsync diff file development ./config/.env
```

### 7. Create and Restore Snapshots

```bash
# Create a snapshot of all environments
envsync snapshot create "before-deployment" --description "v1.0 deployment"

# List snapshots
envsync snapshot list

# Restore from snapshot
envsync snapshot restore <snapshot-id>
```

### 8. Render Templates

```bash
# Render a template file with environment variables
envsync env render development ./templates/config.yaml.tpl ./output/config.yaml
```

## Command Reference

### Environment Commands

| Command | Description |
|---------|-------------|
| `envsync env create <name>` | Create a new environment |
| `envsync env list` | List all environments |
| `envsync env show <name>` | Show environment variables |
| `envsync env set <env> <key> <value>` | Set an environment variable |
| `envsync env get <env> <key>` | Get an environment variable |
| `envsync env delete <name>` | Delete an environment |
| `envsync env import <env> <file>` | Import variables from a file |
| `envsync env export <env>` | Export environment variables |
| `envsync env validate <env>` | Validate environment |
| `envsync env render <env> <template> <output>` | Render a template file |

### Template Commands

| Command | Description |
|---------|-------------|
| `envsync template create <name>` | Create a new template |
| `envsync template list` | List all templates |
| `envsync template show <name>` | Show template details |
| `envsync template delete <name>` | Delete a template |
| `envsync template export <name>` | Export a template |
| `envsync template add-variable` | Add a variable to a template |
| `envsync template remove-variable` | Remove a variable from a template |
| `envsync template init-default` | Initialize default template |

### Snapshot Commands

| Command | Description |
|---------|-------------|
| `envsync snapshot create <name>` | Create a snapshot |
| `envsync snapshot list` | List all snapshots |
| `envsync snapshot show <id>` | Show snapshot details |
| `envsync snapshot restore <id>` | Restore from a snapshot |
| `envsync snapshot delete <id>` | Delete a snapshot |
| `envsync snapshot export <id>` | Export snapshot environments |

### Diff Commands

| Command | Description |
|---------|-------------|
| `envsync diff env <env1> <env2>` | Compare two environments |
| `envsync diff file <env> <file>` | Compare environment with a file |
| `envsync diff snapshot <env> <id>` | Compare with snapshot version |
| `envsync diff template <env> [template]` | Compare with template |

### Utility Commands

| Command | Description |
|---------|-------------|
| `envsync init` | Initialize envsync |
| `envsync status` | Show status summary |
| `envsync encrypt <value>` | Encrypt a value |
| `envsync decrypt <value>` | Decrypt a value |
| `envsync rotate-key` | Rotate encryption key |

## Templating System

envsync supports powerful template rendering with variable substitution.

### Template Syntax

```yaml
# Template file (config.yaml.tpl)
database:
  url: "{{ DATABASE_URL }}"
  pool_size: {{ DATABASE_POOL_SIZE | default(10) }}

server:
  host: "{{ HOST | default(0.0.0.0) }}"
  port: {{ PORT | default(8000) }}
  debug: {{ DEBUG | default(false) }}

api:
  key: "{{ API_KEY }}"
  secret: "{{ API_SECRET }}"
```

### Supported Features

- **Basic substitution**: `{{ VARIABLE_NAME }}`
- **Default values**: `{{ VARIABLE_NAME | default('default_value') }}`
- **Nested variables**: Variables can reference other variables
- **Cross-format support**: Works with JSON, YAML, TOML, and .env files

### Rendering a Template

```bash
# Render template with development environment variables
envsync env render development ./templates/config.yaml.tpl ./config.yaml
```

## Validation System

envsync provides two validation mechanisms:

### 1. Template-based Validation

Templates define variable schemas with types, patterns, and requirements.

```bash
# Create a template with validation rules
envsync template create production

# Add a variable with pattern validation
envsync template add-variable production DATABASE_URL \
  --type url \
  --required \
  --description "Database connection URL"

# Add with regex pattern
envsync template add-variable production API_KEY \
  --type string \
  --required \
  --sensitive \
  --pattern "^sk-[A-Za-z0-9]{32}$"
```

### 2. Custom Validation Rules

Create a rules file (e.g., `validation-rules.json`):

```json
[
  {
    "field": "DATABASE_URL",
    "rule": "contains",
    "value": "postgresql",
    "message": "Must use PostgreSQL database"
  },
  {
    "field": "PORT",
    "rule": "min",
    "value": 1024,
    "message": "Port must be above 1024"
  },
  {
    "field": "LOG_LEVEL",
    "rule": "one_of",
    "value": ["DEBUG", "INFO", "WARNING", "ERROR"],
    "message": "Invalid log level"
  },
  {
    "field": "API_KEY",
    "rule": "min_length",
    "value": 32,
    "message": "API key must be at least 32 characters"
  }
]
```

Validate with custom rules:

```bash
envsync env validate production --rules ./validation-rules.json
```

### Supported Validation Rules

| Rule | Description | Example |
|------|-------------|---------|
| `min_length` | Minimum string length | `{"rule": "min_length", "value": 5}` |
| `max_length` | Maximum string length | `{"rule": "max_length", "value": 100}` |
| `min` | Minimum numeric value | `{"rule": "min", "value": 1024}` |
| `max` | Maximum numeric value | `{"rule": "max", "value": 65535}` |
| `equals` | Exact match | `{"rule": "equals", "value": "production"}` |
| `contains` | Contains substring | `{"rule": "contains", "value": "https"}` |
| `not_contains` | Does not contain substring | `{"rule": "not_contains", "value": "localhost"}` |
| `one_of` | One of allowed values | `{"rule": "one_of", "value": ["dev", "prod"]}` |
| `regex` | Matches regex pattern | `{"rule": "regex", "value": "^[A-Z0-9]+$"}` |

## Encryption

envsync uses Fernet (AES) encryption to protect sensitive configuration values.

### Key Management

```bash
# Encrypt a value manually
envsync encrypt "my-secret-value"

# Decrypt a value
envsync decrypt "gAAAAABk..."

# Rotate encryption key (WARNING: requires re-encrypting all values)
envsync rotate-key
```

### Automatic Encryption

Variables marked as sensitive in templates are automatically encrypted when set:

```bash
# API_KEY is marked as sensitive in the template
# It will be encrypted automatically
envsync env set production API_KEY "secret-key"
```

Or encrypt explicitly:

```bash
envsync env set production API_KEY "secret-key" --encrypted
```

## Import/Export

### Import from Existing Files

```bash
# Import from a .env file
envsync env import development ./.env --create

# Import from JSON
envsync env import development ./config.json

# Merge with existing variables (default)
envsync env import development ./additional.env

# Replace all variables
envsync env import development ./full-config.env --no-merge
```

### Export to Various Formats

```bash
# Export as .env
envsync env export production --format env --output ./.env

# Export as JSON
envsync env export production --format json --output ./config.json

# Export as YAML
envsync env export production --format yaml --output ./config.yaml

# Export decrypted sensitive values
envsync env export production --decrypt --output ./.env
```

## Configuration Location

By default, envsync stores configuration in:

- `~/.config/envsync/` - Main configuration directory
- `~/.config/envsync/environments/` - Environment configurations
- `~/.config/envsync/templates/` - Template definitions
- `~/.config/envsync/snapshots/` - Snapshot metadata
- `~/.config/envsync/snapshot_data/` - Snapshot data
- `~/.config/envsync/encryption_key` - Encryption key

## Examples

### Example Workflow

```bash
# 1. Initialize
envsync init

# 2. Create environments
envsync env create development
envsync env create production

# 3. Import existing configs
envsync env import development ./dev.env --create
envsync env import production ./prod.env --create

# 4. Set sensitive values
envsync env set development API_KEY "dev-key-123" --encrypted
envsync env set production API_KEY "prod-key-456" --encrypted

# 5. Validate
envsync env validate development
envsync env validate production

# 6. Compare
envsync diff env development production

# 7. Create snapshot before deployment
envsync snapshot create "pre-deployment"

# 8. Render configuration files
envsync env render development ./templates/app.tpl ./app/.env
envsync env render production ./templates/app.tpl ./app/.env.prod
```

### Example Template File

```json
{
  "name": "production",
  "description": "Production environment template",
  "variables": {
    "ENVIRONMENT": {
      "type": "string",
      "description": "Environment identifier",
      "default": "production"
    },
    "DEBUG": {
      "type": "bool",
      "description": "Debug mode flag",
      "default": "false"
    },
    "DATABASE_URL": {
      "type": "url",
      "description": "PostgreSQL connection URL"
    },
    "DATABASE_POOL_SIZE": {
      "type": "int",
      "description": "Database connection pool size",
      "default": "10"
    },
    "REDIS_URL": {
      "type": "url",
      "description": "Redis connection URL"
    },
    "API_KEY": {
      "type": "string",
      "description": "External API key",
      "pattern": "^[A-Za-z0-9_-]{32,}$"
    },
    "API_SECRET": {
      "type": "string",
      "description": "External API secret"
    },
    "LOG_LEVEL": {
      "type": "string",
      "description": "Logging level",
      "default": "INFO"
    },
    "PORT": {
      "type": "int",
      "description": "Server port",
      "default": "8000"
    },
    "HOST": {
      "type": "string",
      "description": "Server host",
      "default": "0.0.0.0"
    },
    "SSL_ENABLED": {
      "type": "bool",
      "description": "Enable SSL/TLS",
      "default": "true"
    },
    "CORS_ORIGINS": {
      "type": "string",
      "description": "Allowed CORS origins",
      "default": "https://example.com"
    }
  },
  "required": ["DATABASE_URL", "API_KEY", "API_SECRET"],
  "sensitive": ["DATABASE_URL", "REDIS_URL", "API_KEY", "API_SECRET"]
}
```

## Development

### Running Tests

```bash
# Run all tests
pytest src/envsync/tests/

# Run with coverage
pytest src/envsync/tests/ --cov=envsync

# Run specific test file
pytest src/envsync/tests/test_config.py -v
```

### Code Quality

```bash
# Format code
black src/envsync/

# Lint
flake8 src/envsync/

# Type check
mypy src/envsync/
```

## License

MIT License - see [LICENSE](LICENSE) file.

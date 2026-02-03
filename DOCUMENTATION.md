# Complete Documentation Guide

This document provides an overview of all available documentation for the PageSpeed Insights Audit Tool.

## 📚 Documentation Structure

### Quick Start & Installation
- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes with minimal setup
- **[INSTALL.md](INSTALL.md)** - Detailed installation guide with troubleshooting
- **[README.md](README.md)** - Complete user documentation and usage guide

### Core Documentation
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture, design patterns, sequence diagrams
- **[docs/API.md](docs/API.md)** - Complete API reference for programmatic usage
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Local development setup and contribution guide
- **[docs/README.md](docs/README.md)** - Documentation index and navigation guide

### Configuration & Operations
- **[CACHE_GUIDE.md](CACHE_GUIDE.md)** - Caching configuration (Redis and file backends)
- **[SECURITY.md](SECURITY.md)** - Security features and best practices (detailed)
- **[SECURITY_QUICK_REFERENCE.md](SECURITY_QUICK_REFERENCE.md)** - Security quick reference
- **[VALIDATION.md](VALIDATION.md)** - URL validation and data quality checks
- **[PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md)** - Performance benchmarks and tuning

### Monitoring & Troubleshooting
- **[METRICS_GUIDE.md](METRICS_GUIDE.md)** - Metrics collection and monitoring
- **[ERROR_HANDLING_GUIDE.md](ERROR_HANDLING_GUIDE.md)** - Error handling patterns
- **[ERROR_REFERENCE.md](ERROR_REFERENCE.md)** - Error types and resolution strategies
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions

### Developer Resources
- **[AGENTS.md](AGENTS.md)** - Agent development guide with commands and tech stack
- **[TEST_GUIDE.md](TEST_GUIDE.md)** - Testing guide and conventions

## 🎯 Documentation by Use Case

### For New Users
1. **First Time Setup**: [QUICKSTART.md](QUICKSTART.md) → [INSTALL.md](INSTALL.md)
2. **Basic Usage**: [README.md](README.md) § Usage
3. **Configuration**: [CACHE_GUIDE.md](CACHE_GUIDE.md), [SECURITY.md](SECURITY.md)

### For Developers
1. **Setup Environment**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) § Local Setup
2. **Understand Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
3. **API Reference**: [docs/API.md](docs/API.md)
4. **Write Code**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) § Development Workflow
5. **Write Tests**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) § Testing

### For Operators
1. **Install & Configure**: [INSTALL.md](INSTALL.md)
2. **Security Setup**: [SECURITY.md](SECURITY.md)
3. **Performance Tuning**: [PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md)
4. **Monitoring**: [METRICS_GUIDE.md](METRICS_GUIDE.md)
5. **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### For API Users
1. **API Reference**: [docs/API.md](docs/API.md)
2. **Code Examples**: [docs/API.md](docs/API.md) § Usage Examples
3. **Error Handling**: [docs/API.md](docs/API.md) § Error Handling
4. **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 📊 Performance & Benchmarks

### Key Performance Metrics

**Processing Speed** (with 3 workers and cache):
- **Cold run**: ~5.6 hours for 100 URLs
- **Warm run**: ~3.3 minutes for 100 URLs
- **Cache hit rate**: 85-95% after 24 hours

**Optimization Improvements** (v2.0 vs v1.0):
- Default timeout: 900s → 600s (33% faster)
- Cypress wait time: 5-15s → 2s (60-87% faster)
- Instance reuse with pooling (~30% faster warm starts)
- Incremental spreadsheet updates (real-time visibility)

**Scalability**:
- 1 Worker: ~6 URLs/hour (no cache), ~60 URLs/hour (cached)
- 3 Workers: ~18 URLs/hour (no cache), ~180 URLs/hour (cached)
- 5 Workers: ~30 URLs/hour (no cache), ~300 URLs/hour (cached)

See [PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md) for detailed benchmarks and [README.md](README.md) § Performance Benchmarks for usage examples.

## 🔐 Security Features

- **Service Account Validation**: Automatic validation of Google Cloud credentials
- **URL Filtering**: Whitelist/blacklist patterns for URL access control
- **Rate Limiting**: Per-spreadsheet rate limiting (60 requests/minute)
- **Audit Trail**: JSONL-based modification logging
- **Input Validation**: Comprehensive URL validation (format, DNS, redirects)
- **Data Quality Checks**: Duplicate detection and empty URL checks

See [SECURITY.md](SECURITY.md) for complete security documentation.

## 🚀 Concurrency Examples

### Basic Concurrent Processing

```bash
# Recommended: 3 workers for most audits
python run_audit.py --tab "My Tab" --concurrency 3
```

### By Audit Size

```bash
# Small audits (<50 URLs): 1-2 workers
python run_audit.py --tab "Small Audit" --concurrency 1

# Medium audits (50-200 URLs): 3 workers
python run_audit.py --tab "Medium Audit" --concurrency 3

# Large audits (200+ URLs): 5 workers
python run_audit.py --tab "Large Audit" --concurrency 5
```

### Resource Usage

| Workers | CPU Usage | RAM Usage | Recommended For |
|---------|-----------|-----------|-----------------|
| 1 | 15-25% | 2GB | Small audits, debugging |
| 3 | 40-60% | 4GB | Most audits (recommended) |
| 5 | 70-90% | 8GB | Large audits, powerful machines |

See [README.md](README.md) § Concurrency Examples for advanced patterns.

## 🔧 API Documentation

### Generate HTML API Docs

```bash
# Install pdoc (if not installed)
pip install pdoc

# Generate API documentation
python generate_api_docs.py

# Open generated documentation
# Opens: api_docs/index.html
```

### Core Modules

- **tools.sheets.sheets_client** - Google Sheets API wrapper
- **tools.qa.cypress_runner** - Cypress automation with pooling
- **tools.cache.cache_manager** - Multi-backend caching
- **tools.metrics.metrics_collector** - Prometheus metrics
- **tools.utils.url_validator** - URL validation and normalization
- **tools.security.*** - Security modules (auth, rate limiting, filtering)

See [docs/API.md](docs/API.md) for complete API reference.

## 🏗️ Architecture Overview

### System Layers

```
┌─────────────────────────────────────┐
│     CLI Interface Layer             │
│  (run_audit.py, list_tabs.py)      │
└─────────────────────────────────────┘
              │
┌─────────────────────────────────────┐
│   Orchestration Layer               │
│ (ThreadPoolExecutor, Signals)       │
└─────────────────────────────────────┘
              │
┌─────────────────────────────────────┐
│   Business Logic Layer              │
│ (Validation, Analysis, Results)     │
└─────────────────────────────────────┘
              │
┌─────────────────────────────────────┐
│   Infrastructure Layer              │
│ (Sheets API, Cache, Security)       │
└─────────────────────────────────────┘
              │
┌─────────────────────────────────────┐
│   External Services                 │
│ (Google Sheets, PageSpeed Insights) │
└─────────────────────────────────────┘
```

### Key Design Patterns

- **Singleton**: Cache manager, metrics collector
- **Factory**: Cache backend selection
- **Circuit Breaker**: Service protection
- **Object Pool**: Cypress instance reuse
- **Strategy**: Progressive timeout, cache backends
- **Observer**: Metrics collection, audit trail

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## 📝 Code Examples

### Basic Programmatic Usage

```python
from tools.sheets import sheets_client
from tools.qa import cypress_runner

# Authenticate
service = sheets_client.authenticate('service-account.json')

# Read URLs
urls = sheets_client.read_urls(spreadsheet_id, 'My Tab', service=service)

# Analyze URL
result = cypress_runner.run_analysis(urls[0][1])

# Write results
updates = [(2, 'F', 'passed'), (2, 'G', 'passed')]
sheets_client.batch_write_psi_urls(spreadsheet_id, 'My Tab', updates, service=service)
```

### With Caching

```python
from tools.cache.cache_manager import get_cache_manager

cache = get_cache_manager(enabled=True)

# Check cache
result = cache.get('https://example.com')
if result:
    print("Cache hit!")
else:
    # Run analysis
    result = cypress_runner.run_analysis('https://example.com')
    # Cache result
    cache.set('https://example.com', result)
```

See [docs/API.md](docs/API.md) § Usage Examples for more examples.

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tools --cov=run_audit --cov-report=html

# Using convenience scripts
.\run_tests.ps1  # Windows
./run_tests.sh   # Unix/Linux
make test        # Make (Unix/Linux)
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) § Testing for testing guide.

## 🤝 Contributing

1. Read [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
2. Set up local environment
3. Follow [code style guidelines](docs/DEVELOPMENT.md#code-style)
4. Write tests for new features
5. Submit pull request

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) § Contributing for full guidelines.

## 🆘 Getting Help

### Quick Links

- **Issues?** → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Errors?** → [ERROR_REFERENCE.md](ERROR_REFERENCE.md)
- **API?** → [docs/API.md](docs/API.md)
- **Setup?** → [INSTALL.md](INSTALL.md)
- **Performance?** → [PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md)

### Documentation Search

1. Check [docs/README.md](docs/README.md) for documentation index
2. Use Ctrl+F to search within documents
3. Review [docs/API.md](docs/API.md) § Usage Examples
4. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 📅 Documentation Maintenance

When making code changes:

1. **Update relevant documentation files**
2. **Add code examples** to [docs/API.md](docs/API.md)
3. **Update architecture docs** if design changes
4. **Regenerate API docs**: `python generate_api_docs.py`
5. **Test all code examples** in documentation
6. **Update CHANGELOG.md** with breaking changes

---

**Documentation Version**: 2.0  
**Last Updated**: 2024-02-03  
**Maintained**: Alongside code in git repository

### Rules About Tech Stack and Versions

#### Python Version

- **Python 3.13** (3.14 is not yet supported by pydantic-core/PyO3)
- Compatible range: Python 3.11 - 3.13

#### Package Manager

- **uv** package manager (not pip)
- Use `uv sync` for dependency installation
- Use `uv run` to execute scripts

#### Features

- User input number of notebooks to fetch (1-50, default: 10)
- Export options: **TXT** or **TOON** file format
- Metadata caching: Competition/dataset metadata is cached for 24 hours
- Incremental notebook download: Use cached metadata + download new top N notebooks
- Custom Kaggle credentials: Users can upload their own `kaggle.json` file
-

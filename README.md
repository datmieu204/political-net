# Hướng dẫn chạy chi tiết

1. Cài đặt uv: pip install uv / cài uv theo hướng dẫn tại link https://docs.astral.sh/uv/getting-started/installation/

2. Đồng bộ phiên bản uv với phiên bản trong file uv.lock:
```bash
uv sync
``` 

3. Chạy môi trường:
```bash
.venvScripts/activate  # Trên Windows
source .venv/bin/activate  # Trên macOS/Linux
```

# Thành phần chính

```
political-net
│
├───algorithm
│   │   __init__.py
│   │   graph_builder.py
├───crawl
│   │   __init__.py
│   │   alias.py
│   │   crawl_names.py
│   │   crawl_politicians.py
├───algorithm
│   │   app.py
├───data
│   │   database
│   │   mess
│   │   processed
│   │   raw
├───utils
│   │   __init__.py
│   │   config.py
│   │   external.py
│   │   queue_based_async_logger.py
│   
│   main.py
│   .gitignore
│   .python-version
│   requirements.txt
│   uv.lock
│   pyproject.toml
```
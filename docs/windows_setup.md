# Windows Development Setup

Use Python 3.11 or 3.12 for this project. Python 3.14 is not recommended yet because several FastAPI/LangGraph dependencies may not publish compatible wheels immediately.

## 1. Create a Virtual Environment

From the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If Python 3.12 is not installed, install it from:

```text
https://www.python.org/downloads/windows/
```

## 2. Check the Environment

```powershell
python scripts\dev_check.py
```

Expected result: every check prints `PASS`.

If `python_version` fails, confirm that the virtual environment is using Python 3.11 or 3.12:

```powershell
python --version
```

If an import fails, reinstall dependencies inside the active virtual environment:

```powershell
python -m pip install -r requirements.txt
```

## 3. Run the API and Overlay

```powershell
$env:STS_KB_PATH="data\public_full_data.json"
uvicorn api.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Health check:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health
```

## 4. Run the Bridge Demo

In another terminal with the same virtual environment activated:

```powershell
python scripts\bridge_demo_player.py --delay 3 --loops 1
```

The overlay should update as each state and recommendation is pushed.

## 5. Common Problems

### `ModuleNotFoundError: No module named 'anyio'`

The FastAPI dependency tree is incomplete. Activate the virtual environment and reinstall:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\dev_check.py
```

### Wrong Python version

If `python --version` shows 3.14, recreate the environment with Python 3.12:

```powershell
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

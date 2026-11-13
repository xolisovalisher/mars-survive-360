# Installation guide

## Requirements
* Windows 10/11, Linux or macOS; 4 GB RAM (8 GB recommended); ~1.5 GB disk (packages) + 0.2 GB for the real DEM.
* Python **3.10–3.13** (https://www.python.org/downloads/ — on Windows tick **"Add python.exe to PATH"**).
* A modern browser (Chrome, Edge, Firefox). Internet is needed for package install, NASA Trek basemap tiles and the
  optional DEM download; the app itself runs locally.

## Windows (double-click)
1. Unzip `MARS_SURVIVE_360_FINAL_v1.0.0.zip` to a folder **without** special characters, e.g. `C:\MARS_SURVIVE_360`.
2. Run `scripts\setup_windows.bat` once. It checks Python, creates `.venv`, installs `requirements.txt`, copies
   `.env.example` → `.env` and runs `check_system.py`. Log: `logs\setup.log`.
3. Run `scripts\start_windows.bat`. It picks a free port (8501…), opens the browser and writes errors to
   `logs\start_errors.log`. Close the window to stop.
4. Optional: `.venv\Scripts\python scripts\download_data.py` — real Jezero DEM (≈87 MB).
5. Optional REST API: `scripts\start_api_windows.bat` → http://localhost:8601/docs

## Linux / macOS
```bash
bash scripts/setup_linux.sh
bash scripts/start_linux.sh
.venv/bin/python scripts/download_data.py      # optional real DEM
.venv/bin/python main.py api                    # optional REST API
```

## Optional features
`pip install -r requirements-optional.txt` → `spiceypy` (SPICE geometry, put kernels in `spice_kernels/` or upload
them in module 12), `ultralytics` (YOLO; large), `anthropic` (free-form questions in the AI assistant, needs
`ANTHROPIC_API_KEY` in `.env`).

## Offline DEM
If the download is blocked (proxy/firewall): open the URL printed by `download_data.py` in a browser, save the
`.tif`, then `python scripts/download_data.py --local path\to\M20_JezeroCrater_CTXDEM_20m.tif` — or use module 04
→ *Local file* / *Upload*.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `Python ... not found` | reinstall Python with "Add to PATH", reopen the terminal |
| `pip install` fails | check internet/proxy; corporate proxy: `set HTTPS_PROXY=http://proxy:port` before setup |
| `rasterio` install error on old Python | use Python 3.11–3.13 (wheels available) |
| Map shows no basemap | the browser cannot reach trek.nasa.gov; layers computed from the DEM still work |
| PDF shows a "font not found" note for zh/ja/ko | install a CJK font (Windows has one by default) |
| Port busy | `start_windows.bat` picks the next free port automatically |
| Anything else | module **26 System Diagnostics** (libraries, modules, data, logs, tests) and `logs/app.log` |

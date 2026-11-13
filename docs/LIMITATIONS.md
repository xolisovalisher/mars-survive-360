# Limitations (read before using any number)

**General.** MARS SURVIVE 360 is a hackathon prototype for decision support and education. Models are simplified;
results are not certified astronaut-safety guidance and must not be used for real operations.

## Data
* Screenshots/tests in this package were produced on the **SYNTHETIC DEM** (no NASA server access while building).
  The real DEM workflow is implemented; run `scripts/download_data.py` on your machine.
* 50 m analysis grid: boulders, small scarps and sand ripples are invisible; real local slopes are steeper.
* CTX DEM vertical accuracy is metres to tens of metres; errors propagate into slopes and hazards.
* Science target coordinates other than the landing site are approximate and labelled "verify".

## Models
* Walking/metabolic model uses Earth data (Minetti, Tobler) scaled to Mars gravity with an assumed suit factor 1.6.
* Rover parameters are illustrative; thermal and night loads are simplified.
* Relay orbiters are synthetic two-body circular orbits, not real ephemerides; availability numbers are illustrative.
* Link-budget presets are illustrative; multipath, antenna patterns and dust storms are simplified.
* Navigation sensors are simulated; real wheel slip on sand can be much worse.
* Radiation: GCR scaling with elevation only; solar particle events are not modelled.
* Hazard rules are thresholds on terrain metrics, not a validated classifier.
* **Traversability ML model:** labels come from DEM rules (weak supervision), not from human annotation or rover
  outcomes; it learns to reproduce those rules from the neighbourhood. Scores on the SYNTHETIC DEM (F1 ≈ 0.97)
  are optimistic and will be lower on real terrain. Retrain after loading the real DEM.
* **Space weather:** DONKI observes from Earth's side; the EVA flag is a heuristic, not a dose forecast.
* **Perseverance traverse:** a rover drove there — this is evidence for a 1-tonne wheeled vehicle, not proof that
  a suited astronaut can walk it. Raw images are uncalibrated.
* Heuristic computer vision is **not a trained model**. YOLO results appear only with real trained weights
  (`ultralytics` not bundled).
* Without NAIF kernels the analytic Mars24 algorithm is used (Ls accuracy ~0.01°).
* The AI route assistant explains only computed numbers; free-form questions need `ANTHROPIC_API_KEY` (optional).

* **Globe (module 02):** the bundled NASA texture has ≈10 km/px — individual craters smaller than ~30 km are not
  visible on the globe; crater-scale detail comes from the DEM hillshade inside the yellow frame. The sharper Mars Trek
  texture (≈5 km/px) could not be downloaded from the build machine; the stitching code was tested with injected
  tiles, and the Trek EPSG:4326 tiling (2^(z+1) × 2^z tiles) is assumed from the 2-D map, which uses the same service.
  deck.gl draws the globe with Earth's radius: angles (lat/lon) are exact, marker sizes are visual only. Site names
  are shown as numbers on the globe (deck.gl's text layer does not render in its globe view) and in full beside it.

## Software
* Translations (17 languages besides English) were produced with AI assistance and should be reviewed by native speakers.
* PDF reports: Chinese/Japanese/Korean need a system CJK font (Windows: Microsoft YaHei / Yu Gothic / Malgun;
  Linux: Noto Sans CJK). If none is found the PDF says so; the HTML report always renders.
* Windows `.bat` scripts were written for Windows 10/11 but could not be executed in the Linux build environment;
  the same steps were tested on Linux (`setup_linux.sh`, `start_linux.sh`).
* Single-user local app: settings (theme, paths) are global for the running server.
* The upload widget's own text ("Drag and drop", "200MB per file") comes from Streamlit and stays in English.

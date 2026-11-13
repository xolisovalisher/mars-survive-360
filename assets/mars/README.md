# Mars global texture (bundled, always available offline)

`mars_viking_clrmosaic_925m_2048x1024_lon0-360.jpg`

* **Data:** Mars Viking Colour Mosaic (global, 925 m/px), Viking Orbiter red and violet filters —
  NASA / USGS Astrogeology. Source product:
  https://planetarymaps.usgs.gov/mosaic/Mars_Viking_ClrMosaic_global_925m.tif
* **Licence:** public domain (work of the U.S. Government — USGS/NASA). No use constraints.
* **This copy:** 2048 × 1024 px equirectangular, planetocentric latitude, longitude 0° → 360° East (left edge 0°E).
  Downsampled copy redistributed in the BSD-licensed `planetary-coverage` package of ESA's Juice SOC
  (`planetary_coverage/maps/data/Mars.jpg`, README states the USGS source above), obtained from PyPI because the
  build environment could not reach NASA/USGS servers.
* **Check done:** Olympus Mons (18.65°N 226.2°E), Hellas (42.4°S 70.5°E), Argyre (49.7°S 316°E), Valles Marineris
  (13.9°S 300.8°E), Syrtis Major and Jezero (18.44°N 77.45°E, west rim of Isidis) fall on the right features —
  see `tests/unit/test_globe.py`.

When the computer is online, module 02 can replace it with a sharper texture stitched from NASA Mars Trek tiles
(Viking MDIM 2.1 colour mosaic, 4096 × 2048); that copy is cached in `data/cache/` and the bundled texture remains the
fallback.

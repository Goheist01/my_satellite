"""
Curated catalog of public Earth Observation satellites.

This is the hand-curated source of truth for Stage 1. Every NORAD ID below
was cross-checked against Wikipedia / CEOS / SatNOGS / CelesTrak-adjacent
sources on 2026-08-07 -- not pulled from memory. When you add more entries,
verify the NORAD ID the same way; a wrong ID means satellite.js will
propagate the wrong object entirely.

Fields:
    norad_id      int   -- NORAD/SATCAT catalog number (used to fetch TLE)
    name          str   -- display name
    agency        str   -- owning/operating agency or partnership
    launch_year   int
    data_type     str   -- short sensor/data category, used for lattice grouping
    description   str   -- one line, plain language, for the tap-to-open panel
    status_note   str   -- optional; only set for satellites in a notable
                           transitional state (e.g. winding down). Empty string
                           if nothing noteworthy.

Deliberately excluded (do not re-add without a reason):
    - Landsat 7 (NORAD 25682): decommissioned June 2025
    - NOAA-19 (NORAD 33591): decommissioned August 2025
    - GOES-17: in-orbit backup only, not a primary data source
    - Sentinel-1B: lost power/failed 2021, never restored
"""

SATELLITES = [
    # --- NASA EOS flagships ---
    {
        "norad_id": 25994,
        "name": "Terra",
        "agency": "NASA",
        "launch_year": 1999,
        "data_type": "Multispectral optical & thermal",
        "description": "Flagship NASA Earth Observing System satellite carrying MODIS and ASTER for land, cloud, and aerosol monitoring.",
        "status_note": "In final mission phase; instruments being wound down ahead of a planned 2027 end of science.",
    },
    {
        "norad_id": 27424,
        "name": "Aqua",
        "agency": "NASA",
        "launch_year": 2002,
        "data_type": "Multispectral optical & microwave",
        "description": "Studies the global water cycle -- precipitation, evaporation, and clouds -- via MODIS and AIRS instruments.",
        "status_note": "Nearing planned end of mission (2026-2027).",
    },
    # --- Landsat program (NASA/USGS) ---
    {
        "norad_id": 39084,
        "name": "Landsat 8",
        "agency": "NASA / USGS",
        "launch_year": 2013,
        "data_type": "Multispectral optical",
        "description": "Part of the longest continuous land-imaging record in existence, capturing 30m resolution imagery of every landmass.",
        "status_note": "",
    },
    {
        "norad_id": 49260,
        "name": "Landsat 9",
        "agency": "NASA / USGS",
        "launch_year": 2021,
        "data_type": "Multispectral optical",
        "description": "Newest Landsat satellite, flying in tandem with Landsat 8 to nearly double global land-imaging revisit frequency.",
        "status_note": "",
    },
    # --- NOAA / JPSS weather & VIIRS ---
    {
        "norad_id": 37849,
        "name": "Suomi NPP",
        "agency": "NASA / NOAA",
        "launch_year": 2011,
        "data_type": "VIIRS imaging & atmospheric sounding",
        "description": "Bridging mission that pioneered the VIIRS sensor now used across the JPSS weather satellite series.",
        "status_note": "",
    },
    {
        "norad_id": 43013,
        "name": "NOAA-20",
        "agency": "NOAA",
        "launch_year": 2017,
        "data_type": "VIIRS imaging & atmospheric sounding",
        "description": "First operational JPSS satellite, providing daily global imagery and data for weather forecasting.",
        "status_note": "",
    },
    {
        "norad_id": 54234,
        "name": "NOAA-21",
        "agency": "NOAA",
        "launch_year": 2022,
        "data_type": "VIIRS imaging & atmospheric sounding",
        "description": "Second JPSS satellite, flying alongside NOAA-20 and Suomi NPP for global polar-orbit weather coverage.",
        "status_note": "",
    },
    # --- GOES geostationary weather ---
    {
        "norad_id": 41866,
        "name": "GOES-16",
        "agency": "NOAA / NASA",
        "launch_year": 2016,
        "data_type": "Geostationary weather imaging",
        "description": "Continuously watches North and South America for storms, wildfires, and lightning from geostationary orbit.",
        "status_note": "Now serves as an in-orbit backup after GOES-19 took over the GOES-East slot in 2025.",
    },
    {
        "norad_id": 51850,
        "name": "GOES-18",
        "agency": "NOAA / NASA",
        "launch_year": 2022,
        "data_type": "Geostationary weather imaging",
        "description": "Operates as GOES-West, watching the Pacific Ocean, Hawaii, Alaska, and the western United States.",
        "status_note": "",
    },
    {
        "norad_id": 60133,
        "name": "GOES-19",
        "agency": "NOAA / NASA",
        "launch_year": 2024,
        "data_type": "Geostationary weather imaging",
        "description": "Newest GOES satellite, now operating as GOES-East, the primary weather eye on the Americas' Atlantic side.",
        "status_note": "",
    },
    # --- Copernicus Sentinel-1 (SAR) ---
    {
        "norad_id": 39634,
        "name": "Sentinel-1A",
        "agency": "ESA",
        "launch_year": 2014,
        "data_type": "SAR (radar) imaging",
        "description": "All-weather, day-or-night radar imaging satellite for flood mapping, sea-ice tracking, and ship detection.",
        "status_note": "",
    },
    {
        "norad_id": 62261,
        "name": "Sentinel-1C",
        "agency": "ESA",
        "launch_year": 2024,
        "data_type": "SAR (radar) imaging",
        "description": "Replacement for the failed Sentinel-1B, restoring the Sentinel-1 constellation's twice-weekly global radar coverage.",
        "status_note": "",
    },
    {
        "norad_id": 66315,
        "name": "Sentinel-1D",
        "agency": "ESA",
        "launch_year": 2025,
        "data_type": "SAR (radar) imaging",
        "description": "Latest addition to the Sentinel-1 radar constellation, launched to further shorten global revisit time.",
        "status_note": "",
    },
    # --- Copernicus Sentinel-2 (optical) ---
    {
        "norad_id": 40697,
        "name": "Sentinel-2A",
        "agency": "ESA",
        "launch_year": 2015,
        "data_type": "Multispectral optical",
        "description": "High-resolution optical imager for agriculture, forestry, and land-cover mapping across 13 spectral bands.",
        "status_note": "",
    },
    {
        "norad_id": 42063,
        "name": "Sentinel-2B",
        "agency": "ESA",
        "launch_year": 2017,
        "data_type": "Multispectral optical",
        "description": "Twin to Sentinel-2A, doubling revisit frequency for the Copernicus optical land-monitoring mission.",
        "status_note": "",
    },
    {
        "norad_id": 60989,
        "name": "Sentinel-2C",
        "agency": "ESA",
        "launch_year": 2024,
        "data_type": "Multispectral optical",
        "description": "Third-generation Sentinel-2 satellite, extending the optical land-imaging mission's data record toward 2034.",
        "status_note": "",
    },
    # --- Copernicus Sentinel-3 (ocean/land colour + altimetry) ---
    {
        "norad_id": 41335,
        "name": "Sentinel-3A",
        "agency": "ESA / EUMETSAT",
        "launch_year": 2016,
        "data_type": "Ocean & land colour, altimetry",
        "description": "Measures sea-surface temperature, ocean colour, and land surface temperature for climate and marine monitoring.",
        "status_note": "",
    },
    {
        "norad_id": 43437,
        "name": "Sentinel-3B",
        "agency": "ESA / EUMETSAT",
        "launch_year": 2018,
        "data_type": "Ocean & land colour, altimetry",
        "description": "Twin to Sentinel-3A, doubling coverage for global ocean and land surface monitoring.",
        "status_note": "",
    },
    # --- Copernicus atmospheric & altimetry ---
    {
        "norad_id": 42969,
        "name": "Sentinel-5P",
        "agency": "ESA",
        "launch_year": 2017,
        "data_type": "Atmospheric chemistry",
        "description": "Maps air quality daily worldwide, tracking pollutants like NO2, ozone, and methane city by city.",
        "status_note": "",
    },
    {
        "norad_id": 46984,
        "name": "Sentinel-6 Michael Freilich",
        "agency": "ESA / NASA / NOAA / EUMETSAT",
        "launch_year": 2020,
        "data_type": "Radar altimetry (sea level)",
        "description": "Measures global sea-surface height to within centimeters, continuing a multi-decade sea-level rise record.",
        "status_note": "",
    },
    # --- JAXA ALOS (L-band SAR) ---
    {
        "norad_id": 39766,
        "name": "ALOS-2",
        "agency": "JAXA",
        "launch_year": 2014,
        "data_type": "SAR (L-band radar) imaging",
        "description": "Japanese radar satellite used extensively for disaster response, forest monitoring, and land deformation tracking.",
        "status_note": "",
    },
    {
        "norad_id": 60182,
        "name": "ALOS-4",
        "agency": "JAXA",
        "launch_year": 2024,
        "data_type": "SAR (L-band radar) imaging",
        "description": "Successor to ALOS-2 with a wider radar swath, used for infrastructure monitoring and disaster response.",
        "status_note": "",
    },
    # --- Other public EO missions ---
    {
        "norad_id": 40376,
        "name": "SMAP",
        "agency": "NASA",
        "launch_year": 2015,
        "data_type": "Soil moisture (L-band radiometer)",
        "description": "Maps global soil moisture and freeze/thaw state, supporting drought monitoring and agricultural forecasting.",
        "status_note": "",
    },
    {
        "norad_id": 43613,
        "name": "ICESat-2",
        "agency": "NASA",
        "launch_year": 2018,
        "data_type": "Laser altimetry (ice & land elevation)",
        "description": "Fires a green laser 10,000 times per second to measure ice sheet, sea ice, and forest canopy height.",
        "status_note": "",
    },
    {
        "norad_id": 40336,
        "name": "CBERS-4",
        "agency": "CNSA / INPE (China-Brazil)",
        "launch_year": 2014,
        "data_type": "Multispectral optical",
        "description": "Joint China-Brazil satellite providing free optical imagery widely used for Amazon deforestation monitoring.",
        "status_note": "",
    },
]

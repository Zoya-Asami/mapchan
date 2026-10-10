# mapchan

A lightweight Python tool for visualising GPX tracks using different map projections. It uses only the Python standard library and exports SVG and PNG images in a ZIP archive.

## Projections

- Web Mercator (EPSG:3857)
- Equirectangular projection
- Chinese 1963 latitudinally equal-differential polyconic projection
- Albers equal-area conic projection (China; central meridian 110°E, standard parallels 25°N and 47°N)

## Requirements

Python 3.x. No third-party packages are required.

## Usage

```bash
python mapchan.py example.gpx
```

Choose projections from the interactive menu, or specify them on the command line:

```bash
python mapchan.py example.gpx --projection webmercator
python mapchan.py example.gpx --projection webmercator albers_china
python mapchan.py example.gpx --projection all
```

The output is a ZIP archive named after the input GPX file, containing the selected SVG and PNG maps.

## Getting GPX files

- **OpenStreetMap GPS Traces:** Download publicly available GPS tracks from [OSM GPS Traces](https://www.openstreetmap.org/traces).
- **OpenRailwayMap:** Use [OpenRailwayMap](https://www.openrailwaymap.org/) to explore railway infrastructure mapped in OpenStreetMap. For railway geometry data, query OSM data with [Overpass Turbo](https://overpass-turbo.eu/) and convert the coordinates to GPX; the rendered map itself is not a GPX download service.
- **gpx.studio:** Use the [online GPX editor](https://gpx.studio/zh/app) to create, edit, merge or trim tracks, then export them as GPX.
- **OpenStreetMap Export:** The [OSM Export page](https://www.openstreetmap.org/export) provides map data for a selected area; it does not directly export ready-made GPX tracks.

Check the relevant service's terms and data attribution requirements before reusing downloaded data.

## Scope

mapchan is a lightweight visualisation tool, not a professional GIS or surveying application. Projection implementations—especially the Chinese 1963 projection—may require further validation for precise cartographic use.

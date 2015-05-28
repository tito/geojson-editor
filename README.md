# Geojson editor

## Installation

    pip install --upgrade kivy-garden
    pip install concurrent requests
    garden install --app mapview

## Start

    python main.py yourgeojson.geojson

Or with a custom mbtiles:

    python main.py -- -m custom.mbtiles yourgeojson.geojson

## Usage

- double-click anywhere on the map to start creating a polygon
- then double-one click on the = one point into the polygon
- click-move on a dot = move a point of the polygon
- double-click on a dot = remove the dot
- click "Finish" to add the polygon back into the geojson

- double-click on a current geojson polygon to edit it

- click on Save to save the result into the loaded geojson

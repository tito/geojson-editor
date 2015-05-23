import json
from kivy.garden.mapview import MapView, Coordinate
from kivy.garden.mapview.mapview.mbtsource import MBTilesMapSource
from kivy.garden.mapview.mapview.geojson import GeoJsonMapLayer
from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.lang import Builder
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty

Builder.load_string("""
<Editor>:
    cols: 1
    GridLayout:
        id: layout
        rows: 1
        size_hint_y: None
        height: dp(48)
        padding: "2dp"
        spacing: "2dp"
        top: root.top
        Button:
            size_hint_x: None
            width: dp(100)
            text: "Finish" if root.is_editing else root.mode
            on_release: root.switch_mode()

        BoxLayout:
            padding: "1dp"
            TextInput:
                disabled: not root.is_editing
                text: root.title
                on_text: root.title = self.text

        Button:
            size_hint_x: None
            width: self.texture_size[0] + dp(24)
            text: "Save to {}".format(root.geojson_fn)
            on_release: root.save_geojson()

    MapView:
        id: mapview
        map_source: root.map_source
        snap_to_zoom: False

""")


class Editor(GridLayout):
    current_path = None
    current_layer = None
    mode = StringProperty("polygon")
    is_editing = BooleanProperty(False)
    map_source = ObjectProperty()
    geojson_fn = StringProperty()
    title = StringProperty()

    def __init__(self, **kwargs):
        super(Editor, self).__init__(**kwargs)
        self.current_layer = GeoJsonMapLayer()
        self.result_layer = GeoJsonMapLayer()
        self.result_layer.geojson = kwargs["geojson"]
        self.geojson_fn = kwargs["geojson_fn"]
        self.ids.mapview.add_widget(self.current_layer)
        self.ids.mapview.add_widget(self.result_layer)

    def on_touch_down(self, touch):
        if self.ids.mapview.collide_point(*touch.pos):
            if touch.is_double_tap and not self.is_editing:
                feature = self.select_feature(*touch.pos)
                if feature:
                    self.edit_feature(feature)
                else:
                    self.forward_to_object(touch)
                return True
            elif self.is_editing:
                return self.forward_to_object(touch)
            elif not self.is_editing:
                print self.select_feature(*touch.pos)
            return self.ids.mapview.on_touch_down(touch)
        return super(Editor, self).on_touch_down(touch)

    def switch_mode(self):
        if self.is_editing:
            self.finalize_object()
            return
        self.mode = "line" if self.mode == "polygon" else "polygon"

    def forward_to_object(self, touch):
        mapview = self.ids.mapview
        if not self.is_editing:
            self.is_editing = True
            self.current_path = []
        else:
            coord = mapview.get_latlon_at(*touch.pos)
            self.current_path.append(coord)
            self._update_geojson()
        return True

    def finalize_object(self):
        if self.current_path:
            geojson = self.current_layer.geojson
            if "properties" not in geojson:
                geojson["properties"] = {"title": self.title}
            else:
                geojson["properties"]["title"] = self.title
            self.result_layer.geojson["features"].append(geojson)
            self.ids.mapview.trigger_update(True)
        self.current_path = None
        self.is_editing = False
        self.title = ""
        self._update_geojson()

    def save_geojson(self):
        with open(self.geojson_fn, "wb") as fd:
            json.dump(self.result_layer.geojson, fd)

    def _update_geojson(self):
        geometry = {"type": ""}
        if self.current_path:
            if self.mode == "polygon":
                geometry["coordinates"] = [[[c.lon, c.lat]
                                            for c in self.current_path]]
                geometry["type"] = "Polygon"
            else:
                geometry["coordinates"] = [[c.lon, c.lat]
                                           for c in self.current_path]
                geometry["type"] = "LineString"
        geojson = {"type": "Feature", "properties": {}, "geometry": geometry}
        self.current_layer.geojson = geojson

    def point_inside_polygon(self, x, y, poly):
        n = len(poly)
        inside = False
        p1x, p1y = poly[0]
        for i in range(n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def select_feature(self, x, y):
        coord = self.ids.mapview.get_latlon_at(x, y)
        for feature in self.result_layer.geojson["features"]:
            if feature["type"] != "Feature":
                continue
            geometry = feature["geometry"]
            if geometry["type"] == "Polygon":
                if self.point_inside_polygon(coord.lon, coord.lat, geometry["coordinates"][0]):
                    return feature

    def edit_feature(self, feature):
        self.result_layer.geojson["features"].remove(feature)
        self.current_layer.geojson = feature
        self.ids.mapview.trigger_update(True)
        self.title = feature.get("properties", {}).get("title", "")
        self.is_editing = True
        self.current_path = [Coordinate(lon=c[0], lat=c[1]) for c in feature["geometry"]["coordinates"][0]]

class GeojsonEditor(App):
    mbtiles_fn = None
    geojson_fn = None

    def build(self):
        map_source = None
        if self.mbtiles_fn:
            map_source = MBTilesMapSource(self.mbtiles_fn)
        geojson = {"type": "FeatureCollection", "features": []}
        if self.geojson_fn:
            try:
                with open(self.geojson_fn) as fd:
                    geojson = json.load(fd)
            except:
                pass
        root = Editor(map_source=map_source,
                      geojson=geojson,
                      geojson_fn=self.geojson_fn)
        return root


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Geojson editor")
    parser.add_argument("-m", metavar="mbtiles", help="Custom mbtiles to user")
    parser.add_argument("geojson", help="Geojson file to edit")

    args = parser.parse_args()
    app = GeojsonEditor()
    app.mbtiles_fn = args.m
    app.geojson_fn = args.geojson
    app.run()

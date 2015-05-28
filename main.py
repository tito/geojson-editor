import json
from kivy.garden.mapview import MapView, Coordinate, MapMarker, MarkerMapLayer
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
        map_source: root.map_source or self.map_source
        snap_to_zoom: False

<EditorMarker>:
    anchor_y: 0.5
    source: "blue_dot.png"
""")

class EditorMarker(MapMarker):
    def on_touch_down(self, touch):
        ret = super(EditorMarker, self).on_touch_down(touch)
        if ret and touch.is_double_tap:
            self.editor.remove_marker(self)
            return False
        return ret

    def on_touch_move(self, touch):
        ret = super(EditorMarker, self).on_touch_move(touch)
        if ret:
            coord = self.mapview.get_latlon_at(*touch.pos)
            self.lon = coord.lon
            self.lat = coord.lat
            self.mapview.trigger_update(False)
            self.editor._update_geojson()
        return ret


class Editor(GridLayout):
    current_layer = None
    edit_last_move = None
    markers = []
    mode = StringProperty("polygon")
    is_editing = BooleanProperty(False)
    map_source = ObjectProperty()
    geojson_fn = StringProperty()
    title = StringProperty()

    def __init__(self, **kwargs):
        super(Editor, self).__init__(**kwargs)
        self.marker_layer = MarkerMapLayer()
        self.current_layer = GeoJsonMapLayer()
        self.result_layer = GeoJsonMapLayer()
        self.result_layer.geojson = kwargs["geojson"]
        self.geojson_fn = kwargs["geojson_fn"]
        self.ids.mapview.add_widget(self.current_layer)
        self.ids.mapview.add_widget(self.result_layer)
        self.ids.mapview.add_widget(self.marker_layer)

    def on_touch_down(self, touch):
        if self.ids.mapview.collide_point(*touch.pos):
            if touch.is_double_tap and not self.is_editing:
                feature = self.select_feature(*touch.pos)
                if feature:
                    self.edit_feature(feature)
                else:
                    touch.grab(self)
                    self.forward_to_object(touch)
                return True
            elif touch.is_double_tap and self.is_editing:
                if self.remove_marker_at(touch):
                    return True
                touch.grab(self)
                return self.forward_to_object(touch)
            elif not self.is_editing:
                self.select_feature(*touch.pos)
            return self.ids.mapview.on_touch_down(touch)
        return super(Editor, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current == self and self.is_editing:
            return self.forward_to_object(touch, move=True)
        return super(Editor, self).on_touch_move(touch)

    def switch_mode(self):
        if self.is_editing:
            self.finalize_object()
            return
        self.mode = "line" if self.mode == "polygon" else "polygon"

    def forward_to_object(self, touch, move=False):
        mapview = self.ids.mapview
        if not self.is_editing:
            self.is_editing = True
            self.clear_markers()
        coord = mapview.get_latlon_at(*touch.pos)
        if move:
            m = self.markers[-1]
        else:
            m = EditorMarker()
            m.mapview = mapview
            m.editor = self
            self.markers.append(m)
            self.marker_layer.add_widget(m)
            self.marker_layer.reposition()
        m.lat = coord.lat
        m.lon = coord.lon
        self._update_geojson()
        return True

    def clear_markers(self):
        while self.markers:
            self.remove_marker(self.markers.pop())

    def remove_marker(self, m):
        m.mapview = m.editor = None
        self.marker_layer.remove_widget(m)
        if m in self.markers:
            self.markers.remove(m)
        self._update_geojson()

    def remove_marker_at(self, touch):
        pos = self.ids.mapview.to_local(*touch.pos)
        for marker in self.markers[:]:
            if marker.collide_point(*pos):
                self.remove_marker(marker)
                return True

    def finalize_object(self):
        if self.markers:
            geojson = self.current_layer.geojson
            if "properties" not in geojson:
                geojson["properties"] = {"title": self.title}
            else:
                geojson["properties"]["title"] = self.title
            self.result_layer.geojson["features"].extend(geojson["features"])
            self.ids.mapview.trigger_update(True)
        self.clear_markers()
        self.is_editing = False
        self.title = ""
        self._update_geojson()

    def save_geojson(self):
        with open(self.geojson_fn, "wb") as fd:
            json.dump(self.result_layer.geojson, fd)

    def _update_geojson(self):
        features = []
        if self.mode == "polygon":
            geotype = "Polygon"
            geocoords = lambda x: [x]
        else:
            geotype = "LineString"
            geocoords = lambda x: x

        # current commited path
        if self.markers:
            coordinates = [[c.lon, c.lat] for c in self.markers]
            features.append({
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": geotype,
                    "coordinates": geocoords(coordinates)
                }
            })

        geojson = {"type": "FeatureCollection", "features": features}
        self.current_layer.geojson = geojson
        self.ids.mapview.trigger_update(True)

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
                if self.point_inside_polygon(coord.lon, coord.lat,
                                             geometry["coordinates"][0]):
                    return feature

    def edit_feature(self, feature):
        self.result_layer.geojson["features"].remove(feature)
        #self.current_layer.geojson = feature
        self.ids.mapview.trigger_update(True)
        self.title = feature.get("properties", {}).get("title", "")
        self.is_editing = True
        self.clear_markers()
        for c in feature["geometry"]["coordinates"][0]:
            m = EditorMarker(lon=c[0], lat=c[1])
            m.mapview = self.ids.mapview
            m.editor = self
            self.marker_layer.add_widget(m)
            self.markers.append(m)
        self._update_geojson()


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

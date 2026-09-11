import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { FIRE_CLASS_COLORS, type Hotspot, type IndustrialFacility } from "../../types";

export interface CommandMapProps {
  hotspots: Hotspot[];
  facilities?: IndustrialFacility[];
  selectedHotspot?: Hotspot | null;
  onSelectHotspot?: (hotspot: Hotspot) => void;
  showHeatmap?: boolean;
  showFacilities?: boolean;
  showClusters?: boolean;
}

export function CommandMap({ hotspots, facilities = [], selectedHotspot, onSelectHotspot,
  showHeatmap = false, showFacilities = true, showClusters = false }: CommandMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const latest = useRef({ hotspots, onSelectHotspot });
  latest.current = { hotspots, onSelectHotspot };
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [coords, setCoords] = useState({ lat: 20.59, lng: 78.96, zoom: 4.5 });

  useEffect(() => {
    if (!containerRef.current) return;
    try {
      const map = new maplibregl.Map({ container: containerRef.current,
        style: { version: 8, sources: { basemap: { type: "raster", tileSize: 256,
          tiles: [import.meta.env.VITE_BASEMAP_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png"], maxzoom: 19,
          attribution: import.meta.env.VITE_BASEMAP_ATTRIBUTION || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> | NASA FIRMS',
        } }, layers: [{ id: "basemap", type: "raster", source: "basemap", paint: { "raster-saturation": -0.85, "raster-brightness-min": 0.04, "raster-brightness-max": 0.35 } }] },
        center: [78.96, 20.59], zoom: 4.5,
      });
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl(), "top-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
      map.on("load", () => setReady(true));
      map.on("error", () => setError("Some map tiles could not load. Check your network connection."));
      map.on("moveend", () => {
        const center = map.getCenter();
        setCoords({ lat: +center.lat.toFixed(3), lng: +center.lng.toFixed(3), zoom: +map.getZoom().toFixed(1) });
      });
      map.on("click", "hotspots-points", e => {
        const id = e.features?.[0]?.properties?.id;
        const hotspot = latest.current.hotspots.find(h => h.id === id);
        if (hotspot) latest.current.onSelectHotspot?.(hotspot);
      });
      map.on("click", "hotspots-clusters", async e => {
        const feature = e.features?.[0];
        if (feature?.geometry.type !== "Point") return;
        const source = map.getSource("hotspots") as maplibregl.GeoJSONSource;
        const zoom = await source.getClusterExpansionZoom(feature.properties?.cluster_id);
        map.easeTo({ center: feature.geometry.coordinates as [number, number], zoom });
      });
      map.on("click", "facilities-points", e => {
        const feature = e.features?.[0];
        if (feature?.geometry.type !== "Point") return;
        new maplibregl.Popup().setLngLat(feature.geometry.coordinates as [number, number])
          .setText(`${feature.properties?.name || "Mapped facility"} — ${feature.properties?.facility_type || "industrial"} (OSM)`)
          .addTo(map);
      });
      map.on("mouseenter", "hotspots-points", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "hotspots-points", () => { map.getCanvas().style.cursor = ""; });
    } catch { setError("Map unavailable: this device needs WebGL support."); }
    return () => { mapRef.current?.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    // Recreate the source when clustering changes; setData cannot change clustering.
    for (const id of ["hotspots-heat", "hotspots-points", "hotspots-clusters"]) {
      if (map.getLayer(id)) map.removeLayer(id);
    }
    if (map.getSource("hotspots")) map.removeSource("hotspots");
    const data: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: hotspots.map(h => ({
      type: "Feature", geometry: { type: "Point", coordinates: [h.longitude, h.latitude] },
      properties: { id: h.id, frp: h.frp ?? 0, predicted_class: h.predicted_class || "uncertain" },
    })) };
    map.addSource("hotspots", { type: "geojson", data, cluster: showClusters, clusterRadius: 45, clusterMaxZoom: 12 });
    map.addLayer({ id: "hotspots-heat", type: "heatmap", source: "hotspots",
      filter: ["!", ["has", "point_count"]],
      paint: { "heatmap-opacity": showHeatmap ? 0.75 : 0, "heatmap-radius": 25,
        "heatmap-weight": ["interpolate", ["linear"], ["get", "frp"], 0, 0, 200, 1] } });
    map.addLayer({ id: "hotspots-points", type: "circle", source: "hotspots",
      filter: ["!", ["has", "point_count"]],
      paint: { "circle-radius": 6, "circle-stroke-width": 1.5, "circle-stroke-color": "#fff",
        "circle-opacity": showHeatmap ? 0.5 : 0.95,
        "circle-color": ["match", ["get", "predicted_class"],
          "accidental_industrial_fire", FIRE_CLASS_COLORS.accidental_industrial_fire,
          "persistent_industrial_source", FIRE_CLASS_COLORS.persistent_industrial_source,
          "forest_or_natural_fire", FIRE_CLASS_COLORS.forest_or_natural_fire,
          "agricultural_burning", FIRE_CLASS_COLORS.agricultural_burning,
          "mining_or_other", FIRE_CLASS_COLORS.mining_or_other, FIRE_CLASS_COLORS.uncertain] } });
    map.addLayer({ id: "hotspots-clusters", type: "circle", source: "hotspots", filter: ["has", "point_count"],
      paint: { "circle-color": "#0369a1", "circle-stroke-color": "#fff", "circle-stroke-width": 2,
        "circle-radius": ["step", ["get", "point_count"], 14, 25, 20, 100, 28] } });
  }, [ready, hotspots, showClusters, showHeatmap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const data: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: facilities
      .filter(f => f.latitude != null && f.longitude != null)
      .map(f => ({ type: "Feature", geometry: { type: "Point", coordinates: [f.longitude!, f.latitude!] },
        properties: { name: f.name, facility_type: f.facility_type } })) };
    const source = map.getSource("facilities") as maplibregl.GeoJSONSource | undefined;
    if (source) source.setData(data);
    else {
      map.addSource("facilities", { type: "geojson", data });
      map.addLayer({ id: "facilities-points", type: "circle", source: "facilities",
        paint: { "circle-radius": 5, "circle-color": "#0891b2", "circle-stroke-width": 2, "circle-stroke-color": "#164e63" } });
    }
    map.setLayoutProperty("facilities-points", "visibility", showFacilities ? "visible" : "none");
  }, [ready, facilities, showFacilities]);

  useEffect(() => {
    if (ready && selectedHotspot) mapRef.current?.flyTo({ center: [selectedHotspot.longitude, selectedHotspot.latitude], zoom: 10 });
  }, [ready, selectedHotspot]);

  return <div className="map-canvas-container" style={{ minHeight: 450 }}>
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "absolute" }} />
    {error && <div role="status" className="map-error">{error}</div>}
    <div className="map-hud"><span>LAT {coords.lat} · LON {coords.lng} · ZOOM {coords.zoom}</span>
      <span className="badge badge--info">{hotspots.length} observations · {facilities.length} mapped facilities</span>
    </div>
  </div>;
}

import { useRef, useEffect, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { fetchBoundaries } from '../api/client';
import { ParticleLayer } from '../lib/particles';
import { rasteriseScalar, type FieldSpec } from '../lib/fields';
import type { ORCAField, ORCAMapLayer } from '../types/api';

interface Props {
  routeLayer?: ORCAMapLayer | null;
  location?: { lat: number; lon: number; dest_lat?: number; dest_lon?: number } | null;
  field?: ORCAField | null;
  fieldSpec?: FieldSpec | null;
}

/* Key-free tile hosts, in preference order. Esri's Ocean Base is first because
 * it is the right basemap for this product: it shades bathymetry, so the sea
 * reads as sea rather than as empty space. */
const BASEMAPS = [
  { id: 'esri-ocean',
    url: 'https://services.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, GEBCO, NOAA · ORCA is not an official advisory',
    opacity: 0.92, saturation: -0.2 },
  { id: 'carto-dark',
    url: 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap © CARTO · ORCA is not an official advisory',
    opacity: 0.55, saturation: -0.35 },
  { id: 'osm',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors · ORCA is not an official advisory',
    opacity: 0.45, saturation: -0.6 }
];

export function MapWorkspace({ routeLayer, location, field, fieldSpec }: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const particlesRef = useRef<ParticleLayer | null>(null);
  const basemapRef = useRef(0);
  const failuresRef = useRef(0);
  const [styleLoaded, setStyleLoaded] = useState(false);

  /* -------------------------------------------------------------- init */
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    // The initial style contains NO remote source: MapLibre holds a style
    // unloaded until its sources resolve, so a blocked basemap would stall
    // style.load and nothing else would ever initialise (F-51).
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8, sources: {},
        layers: [{ id: 'bg', type: 'background',
                   paint: { 'background-color': '#050b14' } }]
      },
      center: [76.26, 9.93], zoom: 6.4, attributionControl: { compact: true }
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }),
                   'bottom-right');
    mapRef.current = map;

    // 'load' waits for TILES, not for the style, so poll for real readiness
    // and give up loudly rather than half-initialising (F-52).
    let cancelled = false;
    const deadline = Date.now() + 15000;
    const attempt = () => {
      if (cancelled || !mapRef.current) return;
      if (!map.isStyleLoaded()) {
        if (Date.now() > deadline) {
          console.warn('map style never became ready; running without layers');
          return;
        }
        setTimeout(attempt, 250);
        return;
      }
      addBasemap(map, 0);
      loadBoundaries(map);
      if (canvasRef.current) {
        particlesRef.current = new ParticleLayer(canvasRef.current, map);
      }
      setStyleLoaded(true);
    };
    map.once('style.load', attempt);
    attempt();

    map.on('error', (e: any) => {
      if (e?.error) console.warn('map:', e.error.message || e.error);
      const src = e?.sourceId || e?.source?.id;
      if (src === 'base' && ++failuresRef.current === 4) {
        addBasemap(map, basemapRef.current + 1);
      }
    });

    return () => {
      cancelled = true;
      particlesRef.current?.destroy();
      particlesRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  function addBasemap(map: maplibregl.Map, i: number) {
    basemapRef.current = i;
    failuresRef.current = 0;
    if (i >= BASEMAPS.length) {
      console.warn('no basemap loaded; the sea is drawn without one');
      return;
    }
    const b = BASEMAPS[i];
    try {
      if (map.getLayer('base')) map.removeLayer('base');
      if (map.getSource('base')) map.removeSource('base');
      map.addSource('base', {
        type: 'raster', tiles: [b.url], tileSize: 256, attribution: b.attribution
      });
      map.addLayer({
        id: 'base', type: 'raster', source: 'base',
        paint: { 'raster-opacity': b.opacity, 'raster-saturation': b.saturation }
      });
    } catch (e) {
      console.warn(`basemap ${b.id} failed:`, e);
      addBasemap(map, i + 1);
    }
  }

  function loadBoundaries(map: maplibregl.Map) {
    fetchBoundaries().then((gj) => {
      if (!mapRef.current || map.getSource('eez')) return;
      map.addSource('eez', { type: 'geojson', data: gj as any });
      map.addLayer({ id: 'eez-fill', type: 'fill', source: 'eez',
        paint: { 'fill-color': '#4fd1c5', 'fill-opacity': 0.045 } });
      map.addLayer({ id: 'eez-line', type: 'line', source: 'eez',
        paint: { 'line-color': '#4fd1c5', 'line-width': 1.1,
                 'line-opacity': 0.5, 'line-dasharray': [3, 2] } });
    }).catch(() => { /* boundaries are chrome; the verdict does not need them */ });
  }

  /* ------------------------------------------------------------- fields */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleLoaded) return;

    const removeScalar = () => {
      ['f-scalar'].forEach((id) => {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      });
    };

    if (!field || !fieldSpec) {
      particlesRef.current?.stop();
      removeScalar();
      return;
    }

    if (fieldSpec.vector) {
      removeScalar();
      particlesRef.current?.set(field);
    } else {
      particlesRef.current?.stop();
      const raster = rasteriseScalar(fieldSpec, field);
      removeScalar();
      if (raster) {
        map.addSource('f-scalar', {
          type: 'image', url: raster.url, coordinates: raster.coordinates as any
        });
        map.addLayer({
          id: 'f-scalar', type: 'raster', source: 'f-scalar',
          paint: { 'raster-opacity': 0.72, 'raster-fade-duration': 350 }
        }, map.getLayer('eez-fill') ? 'eez-fill' : undefined);
      }
    }
  }, [field, fieldSpec, styleLoaded]);

  /* -------------------------------------------------------------- route */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleLoaded) return;

    ['route-glow', 'route', 'here-origin', 'here-dest'].forEach((id) => {
      if (map.getLayer(id)) map.removeLayer(id);
    });
    if (map.getSource('route')) map.removeSource('route');
    if (!routeLayer) return;

    map.addSource('route', { type: 'geojson', data: routeLayer.data });
    map.addLayer({ id: 'route-glow', type: 'line', source: 'route',
      paint: { 'line-color': '#4fd1c5', 'line-width': 11,
               'line-opacity': 0.14, 'line-blur': 8 } });
    map.addLayer({ id: 'route', type: 'line', source: 'route',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#7dd3fc', 'line-width': 2.6,
               'line-dasharray': [0, 2.4, 3, 2.4] } });

    const seq: [number, number, number, number][] = [
      [0, 4, 3, 4], [0.5, 4, 2.5, 4], [1, 4, 2, 4], [1.5, 4, 1.5, 4],
      [2, 4, 1, 4], [2.5, 4, 0.5, 4], [3, 4, 0, 4]
    ];
    let step = 0;
    const timer = window.setInterval(() => {
      if (!mapRef.current || !map.getLayer('route')) return;
      map.setPaintProperty('route', 'line-dasharray', seq[step++ % seq.length]);
    }, 85);

    const bounds = new maplibregl.LngLatBounds();
    (routeLayer.data.geometry.coordinates as [number, number][])
      .forEach((c) => bounds.extend(c));
    const wide = window.innerWidth > 1120;
    map.fitBounds(bounds, {
      padding: wide ? { top: 90, bottom: 120, left: 460, right: 400 }
                    : { top: 130, bottom: 160, left: 30, right: 30 },
      duration: 900
    });

    return () => window.clearInterval(timer);
  }, [routeLayer, styleLoaded]);

  /* ------------------------------------------------------------ markers */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleLoaded || !location?.lat) return;

    const features: any[] = [{
      type: 'Feature', properties: { k: 'origin' },
      geometry: { type: 'Point', coordinates: [location.lon, location.lat] }
    }];
    if (location.dest_lat != null && location.dest_lon != null) {
      features.push({
        type: 'Feature', properties: { k: 'dest' },
        geometry: { type: 'Point', coordinates: [location.dest_lon, location.dest_lat] }
      });
    }
    const data = { type: 'FeatureCollection', features } as any;

    if (map.getSource('here')) {
      (map.getSource('here') as maplibregl.GeoJSONSource).setData(data);
    } else {
      map.addSource('here', { type: 'geojson', data });
      map.addLayer({ id: 'here-origin', type: 'circle', source: 'here',
        filter: ['==', 'k', 'origin'],
        paint: { 'circle-radius': 6,
                 'circle-color': '#4fd1c5',
                 'circle-stroke-width': 2,
                 'circle-stroke-color': 'rgba(255,255,255,.85)' } });
      map.addLayer({ id: 'here-dest', type: 'circle', source: 'here',
        filter: ['==', 'k', 'dest'],
        paint: { 'circle-radius': 6,
                 'circle-color': '#fbbf24',
                 'circle-stroke-width': 2,
                 'circle-stroke-color': 'rgba(255,255,255,.85)' } });
    }
    if (!routeLayer) map.easeTo({ center: [location.lon, location.lat], zoom: 7.2 });
  }, [location, routeLayer, styleLoaded]);

  return (
    <>
      <div ref={mapContainer} className="map-pane" />
      <canvas ref={canvasRef} className="particle-canvas" />
    </>
  );
}

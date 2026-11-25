"use client";

import "leaflet/dist/leaflet.css";
import { MapPin } from "lucide-react";
import { useEffect, useRef } from "react";

export interface MapMarker {
  name: string;
  lat: number;
  lng: number;
  category?: "place" | "hotel" | "transit" | "flight";
  day?: string;
  notes?: string;
  url?: string;
}

interface InteractiveMapProps {
  title?: string;
  markers: MapMarker[];
  drawRoute?: boolean;
  heightClass?: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  place: "#10b981", // emerald
  hotel: "#38bdf8", // sky
  transit: "#f59e0b", // amber
  flight: "#a78bfa", // violet
};

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function InteractiveMap({
  title,
  markers,
  drawRoute = true,
  heightClass = "h-72",
}: InteractiveMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  const validMarkers = markers.filter(
    (m) => typeof m.lat === "number" && typeof m.lng === "number" && Number.isFinite(m.lat) && Number.isFinite(m.lng),
  );

  useEffect(() => {
    const el = containerRef.current;
    if (!el || validMarkers.length === 0) return;

    let cancelled = false;
    let mapInstance: import("leaflet").Map | null = null;

    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !containerRef.current) return;

      mapInstance = L.map(containerRef.current, {
        zoomControl: true,
        attributionControl: true,
      });

      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: "&copy; OpenStreetMap &copy; CARTO",
        maxZoom: 19,
      }).addTo(mapInstance);

      const latLngs: Array<[number, number]> = [];

      validMarkers.forEach((m, idx) => {
        const pos: [number, number] = [m.lat, m.lng];
        latLngs.push(pos);
        const color = CATEGORY_COLORS[m.category || "place"] || CATEGORY_COLORS.place;

        const marker = L.circleMarker(pos, {
          radius: 7,
          color: "#0f172a",
          weight: 2,
          fillColor: color,
          fillOpacity: 0.95,
        }).addTo(mapInstance!);

        const mapsHref =
          m.url || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${m.lat},${m.lng}`)}`;
        const popupParts = [
          `<div style="font-family: system-ui, sans-serif; min-width: 150px;">`,
          `<div style="font-weight: 600; font-size: 13px; margin-bottom: 2px;">${idx + 1}. ${escapeHtml(m.name)}</div>`,
          m.day ? `<div style="font-size: 11px; color: #64748b;">${escapeHtml(m.day)}</div>` : "",
          m.notes ? `<div style="font-size: 11px; margin-top: 4px;">${escapeHtml(m.notes)}</div>` : "",
          `<a href="${escapeHtml(mapsHref)}" target="_blank" rel="noreferrer" style="display:inline-block; margin-top:6px; font-size:11px; color:#0284c7; text-decoration:underline;">Open in Maps</a>`,
          `</div>`,
        ];
        marker.bindPopup(popupParts.join(""));
      });

      if (drawRoute && latLngs.length > 1) {
        L.polyline(latLngs, {
          color: "#38bdf8",
          weight: 2.5,
          opacity: 0.75,
          dashArray: "6 6",
        }).addTo(mapInstance);
      }

      if (latLngs.length === 1) {
        mapInstance.setView(latLngs[0], 13);
      } else {
        mapInstance.fitBounds(L.latLngBounds(latLngs), { padding: [28, 28], maxZoom: 14 });
      }
    })();

    return () => {
      cancelled = true;
      if (mapInstance) {
        mapInstance.remove();
        mapInstance = null;
      }
    };
  }, [validMarkers, drawRoute]);

  if (validMarkers.length === 0) {
    return (
      <div className="my-2 rounded-2xl border border-slate-800 bg-slate-950/80 p-4 text-xs text-slate-400">
        No geographic coordinates available to plot on the map.
      </div>
    );
  }

  return (
    <div className="my-2 rounded-2xl border border-slate-800 bg-slate-950/90 overflow-hidden shadow-lg">
      <div className="px-4 py-2.5 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-slate-100">{title || "Interactive Trip Map"}</span>
          <span className="text-[11px] text-slate-400">({validMarkers.length} stops)</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" /> Place
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-sky-400" /> Hotel
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-500" /> Transit
          </span>
        </div>
      </div>
      <div ref={containerRef} className={`w-full ${heightClass} z-0`} />
    </div>
  );
}

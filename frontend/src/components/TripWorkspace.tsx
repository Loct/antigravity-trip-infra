"use client";

import {
  ArrowDown,
  ArrowUp,
  Calendar,
  ExternalLink,
  List,
  Map as MapIcon,
  MapPin,
  Pencil,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { InteractiveMap, MapMarker } from "./InteractiveMap";

export interface TripSummary {
  id?: string;
  tripId?: string;
  title?: string;
  startDate?: string;
  endDate?: string;
}

interface TripWorkspaceProps {
  selectedTrip?: TripSummary;
  selectedTripId: string;
  tripDetail: Record<string, unknown> | null;
  loadingDetail: boolean;
  onRefresh: () => void;
  fullWidth?: boolean;
}

function asString(val: unknown): string {
  return typeof val === "string" ? val.trim() : "";
}

interface DayItem {
  blockId?: number;
  sectionId?: number;
  isPlace?: boolean;
  label: string;
  url?: string;
}

export interface DaySection {
  id: number;
  title: string;
  items: DayItem[];
}

function buildPlaceUrl(place: Record<string, unknown> | undefined, label: string): string | undefined {
  if (!place) return undefined;
  const website = asString(place.website);
  if (website && /^https?:\/\//i.test(website)) return website;
  const placeId = asString(place.place_id);
  const query = encodeURIComponent(label || asString(place.formatted_address));
  if (placeId && query) {
    return `https://www.google.com/maps/search/?api=1&query=${query}&query_place_id=${encodeURIComponent(placeId)}`;
  }
  if (query) {
    return `https://www.google.com/maps/search/?api=1&query=${query}`;
  }
  return undefined;
}

export function extractDays(detail: Record<string, unknown> | null): DaySection[] {
  if (!detail) return [];
  const outer = detail.itinerary as Record<string, unknown> | undefined;
  const inner = (outer?.itinerary as Record<string, unknown> | undefined) || outer;
  const sections =
    (inner?.sections as Array<Record<string, unknown>>) ||
    (inner?.days as Array<Record<string, unknown>>) ||
    ((detail.trip as Record<string, unknown>)?.sections as Array<Record<string, unknown>>) ||
    [];

  if (!Array.isArray(sections)) return [];
  return sections.slice(0, 30).map((sec, idx) => {
    const sectionId = typeof sec.id === "number" ? sec.id : idx;
    const heading =
      asString(sec.displayHeading) ||
      asString(sec.heading) ||
      asString(sec.title) ||
      asString(sec.date) ||
      `Day ${idx + 1}`;
    const blocks = (sec.blocks as Array<Record<string, unknown>>) || (sec.places as Array<Record<string, unknown>>) || [];
    const items: DayItem[] = Array.isArray(blocks)
      ? blocks
          .map((b): DayItem | null => {
            const blockId = typeof b.id === "number" ? b.id : undefined;
            const place = b.place as Record<string, unknown> | undefined;
            const placeName = asString(place?.name);
            if (placeName) {
              return {
                blockId,
                sectionId,
                isPlace: true,
                label: placeName,
                url: buildPlaceUrl(place, placeName),
              };
            }

            const nameOrTitle = asString(b.name) || asString(b.title);
            if (nameOrTitle) {
              return {
                blockId,
                sectionId,
                isPlace: Boolean(place),
                label: nameOrTitle,
                url: asString(b.url) || buildPlaceUrl(place, nameOrTitle),
              };
            }

            const depart = b.depart as Record<string, unknown> | undefined;
            const arrive = b.arrive as Record<string, unknown> | undefined;
            if (depart || arrive) {
              const endpoint = (ep?: Record<string, unknown>) => {
                if (!ep) return "";
                const airport = ep.airport as Record<string, unknown> | undefined;
                const epPlace = ep.place as Record<string, unknown> | undefined;
                return (
                  asString(airport?.iata) ||
                  asString(airport?.cityName) ||
                  asString(epPlace?.name)
                );
              };
              const from = endpoint(depart);
              const to = endpoint(arrive);
              const route = from && to ? `${from} → ${to}` : from || to;
              const date = asString(depart?.date) || asString(arrive?.date);
              const flight = b.flightInfo as Record<string, unknown> | undefined;
              const flightNum = asString(flight?.flightNumber);
              const prefix = flightNum ? `${flightNum}: ` : "";
              const suffix = date ? ` (${date})` : "";
              if (route || flightNum) {
                const arrivePlace = arrive?.place as Record<string, unknown> | undefined;
                return {
                  blockId,
                  sectionId,
                  isPlace: false,
                  label: `${prefix}${route || "Scheduled"}${suffix}`,
                  url: buildPlaceUrl(arrivePlace, to || route),
                };
              }
            }

            const text = asString(b.text);
            return text ? { blockId, sectionId, isPlace: false, label: text } : null;
          })
          .filter((x): x is DayItem => x !== null)
      : [];
    return { id: sectionId, title: heading, items };
  });
}

function extractMarkers(detail: Record<string, unknown> | null): MapMarker[] {
  if (!detail) return [];
  const outer = detail.itinerary as Record<string, unknown> | undefined;
  const inner = (outer?.itinerary as Record<string, unknown> | undefined) || outer;
  const sections =
    (inner?.sections as Array<Record<string, unknown>>) ||
    (inner?.days as Array<Record<string, unknown>>) ||
    ((detail.trip as Record<string, unknown>)?.sections as Array<Record<string, unknown>>) ||
    [];

  if (!Array.isArray(sections)) return [];
  const markers: MapMarker[] = [];

  for (const sec of sections) {
    const dayTitle =
      asString(sec.displayHeading) || asString(sec.heading) || asString(sec.title) || asString(sec.date);
    const isHotelSec = /hotel|lodging|stay/i.test(dayTitle);
    const blocks = (sec.blocks as Array<Record<string, unknown>>) || (sec.places as Array<Record<string, unknown>>) || [];
    if (!Array.isArray(blocks)) continue;

    for (const b of blocks) {
      const pushPlace = (place: Record<string, unknown> | undefined, fallbackName: string, cat: MapMarker["category"]) => {
        if (!place) return;
        const loc = (place.geometry as Record<string, unknown> | undefined)?.location as
          | Record<string, unknown>
          | undefined;
        const lat = typeof loc?.lat === "number" ? loc.lat : undefined;
        const lng = typeof loc?.lng === "number" ? loc.lng : undefined;
        if (lat !== undefined && lng !== undefined) {
          const name = asString(place.name) || fallbackName;
          markers.push({
            name: name || "Stop",
            lat,
            lng,
            category: cat,
            day: dayTitle || undefined,
            url: buildPlaceUrl(place, name),
          });
        }
      };

      const place = b.place as Record<string, unknown> | undefined;
      if (place) {
        pushPlace(place, asString(b.name) || asString(b.title), isHotelSec ? "hotel" : "place");
      }

      const depart = b.depart as Record<string, unknown> | undefined;
      const arrive = b.arrive as Record<string, unknown> | undefined;
      if (depart?.place) pushPlace(depart.place as Record<string, unknown>, "Departure", "transit");
      if (arrive?.place) pushPlace(arrive.place as Record<string, unknown>, "Arrival", "transit");
    }
  }

  return markers;
}

export function TripWorkspace({
  selectedTrip,
  selectedTripId,
  tripDetail,
  loadingDetail,
  onRefresh,
  fullWidth = false,
}: TripWorkspaceProps) {
  const [viewMode, setViewMode] = useState<"list" | "map">("list");
  const [editMode, setEditMode] = useState(false);
  const [busyBlockId, setBusyBlockId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const days = extractDays(tripDetail);
  const markers = extractMarkers(tripDetail);

  const runTripMutation = async (toolName: string, args: Record<string, unknown>, blockId?: number) => {
    if (blockId != null) setBusyBlockId(blockId);
    setActionError(null);
    try {
      const res = await fetch("/api/mcp/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ toolName, args }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        setActionError(data.error || "Failed to update trip");
        return;
      }
      setConfirmDeleteId(null);
      onRefresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to update trip");
    } finally {
      setBusyBlockId(null);
    }
  };

  return (
    <section className="h-full flex flex-col bg-slate-950/70">
      <div className="px-4 py-2.5 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <MapPin className="w-4 h-4 text-emerald-400 shrink-0" />
          <h2 className="text-xs font-semibold text-slate-200 truncate">
            {selectedTrip?.title || "Trip Workspace"}
          </h2>
        </div>

        {selectedTripId && (
          <div className="flex items-center gap-2">
            {!fullWidth && (
              <div className="inline-flex rounded-xl bg-slate-900 p-0.5 border border-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setViewMode("list")}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium transition cursor-pointer ${
                    viewMode === "list" ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <List className="w-3.5 h-3.5" /> Itinerary
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("map")}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium transition cursor-pointer ${
                    viewMode === "map" ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <MapIcon className="w-3.5 h-3.5" /> Map ({markers.length})
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={() => {
                if (!fullWidth) setViewMode("list");
                setEditMode((v) => !v);
              }}
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border transition cursor-pointer ${
                editMode
                  ? "bg-amber-950 text-amber-200 border-amber-800/60"
                  : "bg-slate-900 border-slate-800 text-slate-300 hover:text-slate-100"
              }`}
            >
              <Pencil className="w-3 h-3" /> {editMode ? "Done" : "Arrange"}
            </button>
          </div>
        )}
      </div>

      {actionError && (
        <p className="mx-4 mt-2 text-[11px] text-rose-300 bg-rose-950/40 border border-rose-800/50 rounded-lg px-2.5 py-1.5">
          {actionError}
        </p>
      )}

      <div className="flex-1 overflow-y-auto p-4">
        {!selectedTripId ? (
          <div className="h-full flex items-center justify-center text-xs text-slate-500">
            Select a Wanderlog trip from the top bar to inspect its itinerary, map, and arrange stops.
          </div>
        ) : loadingDetail ? (
          <p className="text-xs text-slate-400">Loading itinerary from Wanderlog MCP...</p>
        ) : fullWidth ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {days.map((day, i) => (
                <div key={i} className="rounded-xl border border-slate-800/90 bg-slate-900/50 p-3 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                    <Calendar className="w-3.5 h-3.5 text-emerald-400" />
                    {day.title}
                  </div>
                  {day.items.length > 0 ? (
                    <ul className="space-y-1.5 pl-4 list-disc text-xs text-slate-400">
                      {day.items.map((item, j) => (
                        <li key={item.blockId ?? j} className="space-y-1">
                          <div className="flex items-center justify-between gap-1.5">
                            {item.url ? (
                              <a
                                href={item.url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 text-sky-300/90 hover:text-sky-200 hover:underline"
                              >
                                <span>{item.label}</span>
                                <ExternalLink className="w-2.5 h-2.5 shrink-0 opacity-70" />
                              </a>
                            ) : (
                              <span>{item.label}</span>
                            )}
                          </div>
                          {editMode && item.blockId != null && item.sectionId != null && (
                            <div className="flex flex-wrap items-center gap-1 pt-0.5">
                              {item.isPlace && (
                                <>
                                  <button
                                    type="button"
                                    disabled={busyBlockId === item.blockId || j === 0}
                                    onClick={() =>
                                      runTripMutation(
                                        "move_place",
                                        {
                                          trip_key: selectedTripId,
                                          place_id: item.blockId,
                                          from_section_id: item.sectionId,
                                          to_section_id: item.sectionId,
                                          position: Math.max(0, j - 1),
                                        },
                                        item.blockId,
                                      )
                                    }
                                    className="p-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-slate-200 cursor-pointer"
                                  >
                                    <ArrowUp className="w-3 h-3" />
                                  </button>
                                  <button
                                    type="button"
                                    disabled={busyBlockId === item.blockId || j === day.items.length - 1}
                                    onClick={() =>
                                      runTripMutation(
                                        "move_place",
                                        {
                                          trip_key: selectedTripId,
                                          place_id: item.blockId,
                                          from_section_id: item.sectionId,
                                          to_section_id: item.sectionId,
                                          position: j + 1,
                                        },
                                        item.blockId,
                                      )
                                    }
                                    className="p-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-slate-200 cursor-pointer"
                                  >
                                    <ArrowDown className="w-3 h-3" />
                                  </button>
                                </>
                              )}
                              {confirmDeleteId === item.blockId ? (
                                <button
                                  type="button"
                                  disabled={busyBlockId === item.blockId}
                                  onClick={() =>
                                    runTripMutation(
                                      "delete_itinerary_block",
                                      {
                                        trip_key: selectedTripId,
                                        block_id: item.blockId,
                                        section_id: item.sectionId,
                                        confirm: true,
                                      },
                                      item.blockId,
                                    )
                                  }
                                  className="px-1.5 py-0.5 rounded bg-rose-700 hover:bg-rose-600 text-[10px] font-semibold text-white cursor-pointer"
                                >
                                  Confirm
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  disabled={busyBlockId === item.blockId}
                                  onClick={() => setConfirmDeleteId(item.blockId!)}
                                  className="p-1 rounded bg-slate-800 hover:bg-rose-900/70 text-slate-400 hover:text-rose-200 cursor-pointer"
                                >
                                  <Trash2 className="w-3 h-3" />
                                </button>
                              )}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[11px] text-slate-500 pl-4">No places scheduled</p>
                  )}
                </div>
              ))}
            </div>
            <div className="lg:sticky lg:top-0">
              <InteractiveMap
                title={selectedTrip?.title || "Trip Map"}
                markers={markers}
                drawRoute={true}
                heightClass="h-[70vh]"
              />
            </div>
          </div>
        ) : viewMode === "map" ? (
          <InteractiveMap
            title={selectedTrip?.title || "Trip Map"}
            markers={markers}
            drawRoute={true}
            heightClass="h-[68vh]"
          />
        ) : days.length === 0 ? (
          <p className="text-xs text-slate-500">No itinerary days found yet for this trip.</p>
        ) : (
          <div className="space-y-3">
            {days.map((day, i) => (
            <div key={i} className="rounded-xl border border-slate-800/90 bg-slate-900/50 p-3 space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                <Calendar className="w-3.5 h-3.5 text-emerald-400" />
                {day.title}
              </div>
              {day.items.length > 0 ? (
                <ul className="space-y-1.5 pl-4 list-disc text-xs text-slate-400">
                  {day.items.map((item, j) => (
                    <li key={item.blockId ?? j} className="space-y-1">
                      <div className="flex items-center justify-between gap-1.5">
                        {item.url ? (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-sky-300/90 hover:text-sky-200 hover:underline"
                          >
                            <span>{item.label}</span>
                            <ExternalLink className="w-2.5 h-2.5 shrink-0 opacity-70" />
                          </a>
                        ) : (
                          <span>{item.label}</span>
                        )}
                      </div>

                      {editMode && item.blockId != null && item.sectionId != null && (
                        <div className="flex flex-wrap items-center gap-1 pt-0.5">
                          {item.isPlace && (
                            <>
                              <button
                                type="button"
                                disabled={busyBlockId === item.blockId || j === 0}
                                onClick={() =>
                                  runTripMutation(
                                    "move_place",
                                    {
                                      trip_key: selectedTripId,
                                      place_id: item.blockId,
                                      from_section_id: item.sectionId,
                                      to_section_id: item.sectionId,
                                      position: Math.max(0, j - 1),
                                    },
                                    item.blockId,
                                  )
                                }
                                title="Move up"
                                className="p-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-slate-200 cursor-pointer"
                              >
                                <ArrowUp className="w-3 h-3" />
                              </button>
                              <button
                                type="button"
                                disabled={busyBlockId === item.blockId || j === day.items.length - 1}
                                onClick={() =>
                                  runTripMutation(
                                    "move_place",
                                    {
                                      trip_key: selectedTripId,
                                      place_id: item.blockId,
                                      from_section_id: item.sectionId,
                                      to_section_id: item.sectionId,
                                      position: j + 1,
                                    },
                                    item.blockId,
                                  )
                                }
                                title="Move down"
                                className="p-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-slate-200 cursor-pointer"
                              >
                                <ArrowDown className="w-3 h-3" />
                              </button>
                              <select
                                defaultValue=""
                                disabled={busyBlockId === item.blockId}
                                onChange={(e) => {
                                  const targetSec = Number(e.target.value);
                                  if (!targetSec) return;
                                  runTripMutation(
                                    "move_place",
                                    {
                                      trip_key: selectedTripId,
                                      place_id: item.blockId,
                                      from_section_id: item.sectionId,
                                      to_section_id: targetSec,
                                      position: 0,
                                    },
                                    item.blockId,
                                  );
                                }}
                                className="rounded bg-slate-800 border border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-200 max-w-28"
                              >
                                <option value="">Move to...</option>
                                {days
                                  .filter((d) => d.id !== item.sectionId)
                                  .map((d) => (
                                    <option key={d.id} value={d.id}>
                                      {d.title}
                                    </option>
                                  ))}
                              </select>
                            </>
                          )}
                          {confirmDeleteId === item.blockId ? (
                            <button
                              type="button"
                              disabled={busyBlockId === item.blockId}
                              onClick={() =>
                                runTripMutation(
                                  "delete_itinerary_block",
                                  {
                                    trip_key: selectedTripId,
                                    block_id: item.blockId,
                                    section_id: item.sectionId,
                                    confirm: true,
                                  },
                                  item.blockId,
                                )
                              }
                              className="px-1.5 py-0.5 rounded bg-rose-700 hover:bg-rose-600 text-[10px] font-semibold text-white cursor-pointer"
                            >
                              Confirm Remove
                            </button>
                          ) : (
                            <button
                              type="button"
                              disabled={busyBlockId === item.blockId}
                              onClick={() => setConfirmDeleteId(item.blockId!)}
                              title="Remove item"
                              className="p-1 rounded bg-slate-800 hover:bg-rose-900/70 text-slate-400 hover:text-rose-200 cursor-pointer"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[11px] text-slate-500 pl-5">No places scheduled</p>
              )}
            </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

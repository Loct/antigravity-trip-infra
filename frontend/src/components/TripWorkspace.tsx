"use client";

import { Calendar, Compass, Hotel, MapPin, RefreshCw } from "lucide-react";

export interface TripSummary {
  id?: string;
  tripId?: string;
  title?: string;
  startDate?: string;
  endDate?: string;
}

interface TripWorkspaceProps {
  trips: TripSummary[];
  selectedTripId: string;
  onSelectTrip: (tripId: string) => void;
  tripDetail: Record<string, unknown> | null;
  loadingTrips: boolean;
  loadingDetail: boolean;
  onRefresh: () => void;
  onQuickPrompt: (prompt: string) => void;
}

function asString(val: unknown): string {
  return typeof val === "string" ? val.trim() : "";
}

function extractDays(detail: Record<string, unknown> | null): Array<{ title: string; items: string[] }> {
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
    const heading =
      asString(sec.displayHeading) ||
      asString(sec.heading) ||
      asString(sec.title) ||
      asString(sec.date) ||
      `Day ${idx + 1}`;
    const blocks = (sec.blocks as Array<Record<string, unknown>>) || (sec.places as Array<Record<string, unknown>>) || [];
    const items = Array.isArray(blocks)
      ? blocks
          .map((b) => {
            const placeName = asString((b.place as Record<string, unknown> | undefined)?.name);
            const flight = b.flightInfo as Record<string, unknown> | undefined;
            const flightLabel = asString(flight?.flightNumber) ? `Flight ${asString(flight?.flightNumber)}` : "";
            return (
              placeName ||
              asString(b.name) ||
              asString(b.title) ||
              flightLabel ||
              asString(b.text)
            );
          })
          .filter(Boolean)
      : [];
    return { title: heading, items };
  });
}

export function TripWorkspace({
  trips,
  selectedTripId,
  onSelectTrip,
  tripDetail,
  loadingTrips,
  loadingDetail,
  onRefresh,
  onQuickPrompt,
}: TripWorkspaceProps) {
  const days = extractDays(tripDetail);
  const selectedTrip = trips.find((t) => (t.id || t.tripId) === selectedTripId);

  return (
    <aside className="w-full lg:w-88 shrink-0 border-b lg:border-b-0 lg:border-r border-slate-800 bg-slate-950/90 flex flex-col max-h-[42vh] lg:max-h-screen">
      <div className="p-4 border-b border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MapPin className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-slate-100">Wanderlog Workspace</h2>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            title="Refresh trips"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingTrips || loadingDetail ? "animate-spin" : ""}`} />
          </button>
        </div>

        <select
          value={selectedTripId}
          onChange={(e) => onSelectTrip(e.target.value)}
          className="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-sky-500"
        >
          <option value="">Select a Wanderlog trip...</option>
          {trips.map((t) => {
            const id = t.id || t.tripId || "";
            return (
              <option key={id} value={id}>
                {t.title || id}
              </option>
            );
          })}
        </select>

        {selectedTrip && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() =>
                onQuickPrompt(`Run an AI Council cross-check on trip "${selectedTrip.title || selectedTripId}" (ID: ${selectedTripId}).`)
              }
              className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs font-medium bg-violet-950/70 hover:bg-violet-900/70 text-violet-200 border border-violet-800/60 px-2.5 py-1.5 rounded-lg transition cursor-pointer"
            >
              <Compass className="w-3.5 h-3.5" /> Council Check
            </button>
            <button
              type="button"
              onClick={() =>
                onQuickPrompt(
                  `Search Booking.com and Agoda hotels for trip "${selectedTrip.title || selectedTripId}"${
                    selectedTrip.startDate && selectedTrip.endDate
                      ? ` from ${selectedTrip.startDate} to ${selectedTrip.endDate}`
                      : ""
                  }.`,
                )
              }
              className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs font-medium bg-sky-950/70 hover:bg-sky-900/70 text-sky-200 border border-sky-800/60 px-2.5 py-1.5 rounded-lg transition cursor-pointer"
            >
              <Hotel className="w-3.5 h-3.5" /> Find Hotels
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {!selectedTripId ? (
          <p className="text-xs text-slate-500">Select a trip above to inspect its itinerary and run one-click checks.</p>
        ) : loadingDetail ? (
          <p className="text-xs text-slate-400">Loading itinerary from Wanderlog MCP...</p>
        ) : days.length === 0 ? (
          <p className="text-xs text-slate-500">No itinerary days found yet for this trip.</p>
        ) : (
          days.map((day, i) => (
            <div key={i} className="rounded-xl border border-slate-800/90 bg-slate-900/50 p-3 space-y-1.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                <Calendar className="w-3.5 h-3.5 text-emerald-400" />
                {day.title}
              </div>
              {day.items.length > 0 ? (
                <ul className="space-y-1 pl-5 list-disc text-xs text-slate-400">
                  {day.items.map((item, j) => (
                    <li key={j}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-[11px] text-slate-500 pl-5">No places scheduled</p>
              )}
            </div>
          ))
        )}
      </div>
    </aside>
  );
}

"use client";

import { useChat } from "@ai-sdk/react";
import { Compass, Hotel, LayoutPanelLeft, Loader2, MapPin, MessageSquare, Plane, RefreshCw, Send, Sparkles, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ApprovalCard } from "@/components/ApprovalCard";
import { BookedHotelCard, BookedHotelData } from "@/components/BookedHotelCard";
import { CouncilCard } from "@/components/CouncilCard";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { HotelComparisonCard } from "@/components/HotelComparisonCard";
import { InteractiveMap, MapMarker } from "@/components/InteractiveMap";
import { MarkdownContent } from "@/components/MarkdownContent";
import { RecommendedPlace, RecommendedPlacesCard } from "@/components/RecommendedPlacesCard";
import { extractDays, TripSummary, TripWorkspace } from "@/components/TripWorkspace";

const HOTEL_TOOLS = new Set(["search_hotels_dual_ota", "booking_search_hotels", "agoda_search_hotels"]);
const COUNCIL_TOOLS = new Set(["ai_council_ask", "ai_council_crosscheck", "ai_council_debate"]);
const MUTATION_TOOLS = new Set([
  "create_trip",
  "copy_trip",
  "add_place",
  "add_lodging",
  "add_flight",
  "add_train",
  "add_trip_expense",
  "update_place_visit_time",
  "update_place_notes",
  "update_flight",
  "update_lodging",
  "update_trip",
  "update_trip_expense",
  "move_place",
  "reorder_places",
  "remove_place",
  "delete_flight",
  "delete_itinerary_block",
  "delete_lodging",
  "delete_section",
  "delete_trip_expense",
  "clear_section_blocks",
  "set_trip_budget",
  "autofill_day",
  "optimize_route",
  "toggle_checklist_item",
  "add_checklist_items",
]);

function normalizeTripsPayload(raw: unknown): TripSummary[] {
  if (Array.isArray(raw)) return raw as TripSummary[];
  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.trips)) return obj.trips as TripSummary[];
    if (Array.isArray(obj.data)) return obj.data as TripSummary[];
  }
  return [];
}

export default function TravelPlannerPage() {
  const [trips, setTrips] = useState<TripSummary[]>([]);
  const [selectedTripId, setSelectedTripId] = useState<string>("");
  const [tripDetail, setTripDetail] = useState<Record<string, unknown> | null>(null);
  const [loadingTrips, setLoadingTrips] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [layoutMode, setLayoutMode] = useState<"split" | "trip" | "chat">("split");

  const loadTrips = useCallback(async () => {
    setLoadingTrips(true);
    try {
      const res = await fetch("/api/trips");
      if (res.ok) {
        const data = await res.json();
        const list = normalizeTripsPayload(data.trips);
        setTrips(list);
      }
    } catch {
      // Ignore transient load error
    } finally {
      setLoadingTrips(false);
    }
  }, []);

  const loadTripDetail = useCallback(async (id: string) => {
    if (!id) {
      setTripDetail(null);
      return;
    }
    setLoadingDetail(true);
    try {
      const res = await fetch(`/api/trips/${encodeURIComponent(id)}`);
      if (res.ok) {
        const data = await res.json();
        setTripDetail(data);
      }
    } catch {
      // Ignore transient load error
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    loadTrips();
  }, [loadTrips]);

  useEffect(() => {
    loadTripDetail(selectedTripId);
  }, [selectedTripId, loadTripDetail]);

  const { messages, input, handleInputChange, handleSubmit, append, addToolResult, isLoading, error } = useChat({
    api: "/api/chat",
    body: { selectedTripId },
  });

  const handleApproveMutation = async (toolCallId: string, toolName: string, args: Record<string, unknown>) => {
    const res = await fetch("/api/mcp/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ toolName, args }),
    });
    const data = await res.json();
    addToolResult({ toolCallId, result: data });
    if (selectedTripId) {
      loadTripDetail(selectedTripId);
    }
    loadTrips();
  };

  const handleDeclineMutation = (toolCallId: string) => {
    addToolResult({
      toolCallId,
      result: { cancelled: true, reason: "User declined this trip mutation." },
    });
  };

  const selectedTrip = trips.find((t) => (t.id || t.tripId) === selectedTripId);

  return (
    <div className="h-screen flex flex-col bg-[#090d16] text-slate-100 overflow-hidden">
      <header className="px-4 py-2.5 border-b border-slate-800 bg-slate-950/90 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center">
            <Plane className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="hidden sm:block">
            <h1 className="text-sm font-semibold text-slate-100 leading-tight">Antigravity Travel Planner</h1>
            <p className="text-[11px] text-slate-400">Wanderlog + Booking.com + Agoda + AI Council</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 flex-1 justify-center max-w-2xl">
          <select
            value={selectedTripId}
            onChange={(e) => setSelectedTripId(e.target.value)}
            className="min-w-52 max-w-xs flex-1 rounded-xl border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-sky-500"
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

          <button
            type="button"
            onClick={() => {
              loadTrips();
              if (selectedTripId) loadTripDetail(selectedTripId);
            }}
            title="Refresh trips"
            className="p-1.5 rounded-xl border border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200 transition cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingTrips || loadingDetail ? "animate-spin" : ""}`} />
          </button>

          {selectedTrip && (
            <>
              <button
                type="button"
                onClick={() => {
                  if (layoutMode === "trip") setLayoutMode("split");
                  append({
                    role: "user",
                    content: `Run an AI Council cross-check on trip "${selectedTrip.title || selectedTripId}" (ID: ${selectedTripId}).`,
                  });
                }}
                className="inline-flex items-center gap-1.5 text-xs font-medium bg-violet-950/70 hover:bg-violet-900/70 text-violet-200 border border-violet-800/60 px-2.5 py-1.5 rounded-xl transition cursor-pointer"
              >
                <Compass className="w-3.5 h-3.5" /> Council Check
              </button>
              <button
                type="button"
                onClick={() => {
                  if (layoutMode === "trip") setLayoutMode("split");
                  append({
                    role: "user",
                    content: `Search Booking.com and Agoda hotels for trip "${selectedTrip.title || selectedTripId}"${
                      selectedTrip.startDate && selectedTrip.endDate
                        ? ` from ${selectedTrip.startDate} to ${selectedTrip.endDate}`
                        : ""
                    }.`,
                  });
                }}
                className="inline-flex items-center gap-1.5 text-xs font-medium bg-sky-950/70 hover:bg-sky-900/70 text-sky-200 border border-sky-800/60 px-2.5 py-1.5 rounded-xl transition cursor-pointer"
              >
                <Hotel className="w-3.5 h-3.5" /> Find Hotels
              </button>
            </>
          )}
        </div>

        <div className="inline-flex rounded-xl bg-slate-900 p-0.5 border border-slate-800 text-xs">
          <button
            type="button"
            onClick={() => setLayoutMode("split")}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium transition cursor-pointer ${
              layoutMode === "split" ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <LayoutPanelLeft className="w-3.5 h-3.5" /> Split
          </button>
          <button
            type="button"
            onClick={() => setLayoutMode("trip")}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium transition cursor-pointer ${
              layoutMode === "trip" ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <MapPin className="w-3.5 h-3.5" /> Trip
          </button>
          <button
            type="button"
            onClick={() => setLayoutMode("chat")}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-medium transition cursor-pointer ${
              layoutMode === "chat" ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" /> Chat
          </button>
        </div>
      </header>

      <div className="flex-1 flex flex-col lg:flex-row min-h-0">
        {layoutMode !== "chat" && (
          <div
            className={
              layoutMode === "trip"
                ? "flex-1 min-h-0"
                : "w-full lg:w-[44%] xl:w-[42%] border-b lg:border-b-0 lg:border-r border-slate-800 min-h-0 h-[42vh] lg:h-full"
            }
          >
            <ErrorBoundary scope="Wanderlog Workspace">
              <TripWorkspace
                selectedTrip={selectedTrip}
                selectedTripId={selectedTripId}
                tripDetail={tripDetail}
                loadingDetail={loadingDetail}
                fullWidth={layoutMode === "trip"}
                onRefresh={() => {
                  loadTrips();
                  if (selectedTripId) loadTripDetail(selectedTripId);
                }}
              />
            </ErrorBoundary>
          </div>
        )}

        {layoutMode !== "trip" && (
          <main className="flex-1 flex flex-col min-h-0">

        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
          {messages.length === 0 && (
            <div className="max-w-xl mx-auto mt-10 rounded-2xl border border-slate-800 bg-slate-900/40 p-6 text-center space-y-4">
              <Sparkles className="w-7 h-7 text-indigo-400 mx-auto" />
              <h2 className="text-base font-semibold text-slate-100">Plan your next trip with live MCP tools</h2>
              <p className="text-xs text-slate-400 leading-relaxed">
                Search Booking.com & Agoda side-by-side, consult Claude & DeepSeek on your itinerary, or propose
                additions to Wanderlog with one-click approval.
              </p>
              <div className="flex flex-wrap justify-center gap-2 pt-1">
                {[
                  "Compare hotels in Tokyo from 2026-12-01 to 2026-12-05",
                  "List my Wanderlog trips",
                  "Check Booking.com and Agoda auth status",
                ].map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => append({ role: "user", content: example })}
                    className="text-xs bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-slate-200 px-3 py-1.5 rounded-xl transition cursor-pointer"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) => (
            <ErrorBoundary key={m.id} scope="Chat Message">
              <div className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-3xl w-full ${
                  m.role === "user"
                    ? "ml-auto max-w-xl rounded-2xl bg-indigo-600/25 border border-indigo-500/40 px-4 py-2.5 text-sm text-slate-100"
                    : "space-y-2"
                }`}
              >
                {m.content &&
                  (m.role === "user" ? (
                    <div className="text-sm text-slate-100 whitespace-pre-wrap leading-relaxed">{m.content}</div>
                  ) : (
                    <MarkdownContent content={m.content} />
                  ))}

                {m.toolInvocations?.map((inv) => {
                  if (inv.state === "result" && inv.toolName === "display_hotel_card") {
                    return <BookedHotelCard key={inv.toolCallId} data={(inv.result || {}) as BookedHotelData} />;
                  }

                  if (inv.state === "result" && inv.toolName === "display_trip_map") {
                    const mapData = (inv.result || {}) as {
                      title?: string;
                      drawRoute?: boolean;
                      markers?: MapMarker[];
                    };
                    return (
                      <InteractiveMap
                        key={inv.toolCallId}
                        title={mapData.title}
                        drawRoute={mapData.drawRoute ?? true}
                        markers={mapData.markers || []}
                        heightClass="h-80"
                      />
                    );
                  }

                  if (inv.state === "result" && inv.toolName === "display_place_recommendations") {
                    const recData = (inv.result || {}) as {
                      title?: string;
                      places?: RecommendedPlace[];
                    };
                    const tripSections = extractDays(tripDetail).map((d) => ({ id: d.id, title: d.title }));
                    return (
                      <RecommendedPlacesCard
                        key={inv.toolCallId}
                        title={recData.title}
                        places={recData.places || []}
                        sections={tripSections}
                        onProposeAdd={(place, targetSection) =>
                          append({
                            role: "user",
                            content: `Please propose adding "${place.name}"${
                              targetSection ? ` to "${targetSection}"` : ""
                            } in my selected Wanderlog trip.`,
                          })
                        }
                      />
                    );
                  }

                  if (MUTATION_TOOLS.has(inv.toolName)) {
                    return (
                      <ApprovalCard
                        key={inv.toolCallId}
                        toolCallId={inv.toolCallId}
                        toolName={inv.toolName}
                        args={(inv.args || {}) as Record<string, unknown>}
                        state={inv.state}
                        result={"result" in inv ? inv.result : undefined}
                        onApprove={handleApproveMutation}
                        onDecline={handleDeclineMutation}
                      />
                    );
                  }

                  if (inv.state === "result" && HOTEL_TOOLS.has(inv.toolName)) {
                    return (
                      <HotelComparisonCard
                        key={inv.toolCallId}
                        toolName={inv.toolName}
                        data={(inv.result || {}) as Record<string, unknown>}
                        onProposeHotel={(hotel, ci, co) =>
                          append({
                            role: "user",
                            content: `Please propose adding "${hotel.name}" (${ci || ""} to ${co || ""}) to my selected Wanderlog trip.`,
                          })
                        }
                      />
                    );
                  }

                  if (inv.state === "result" && COUNCIL_TOOLS.has(inv.toolName)) {
                    return (
                      <CouncilCard
                        key={inv.toolCallId}
                        toolName={inv.toolName}
                        data={(inv.result || {}) as Record<string, unknown>}
                      />
                    );
                  }

                  return (
                    <div
                      key={inv.toolCallId}
                      className="inline-flex items-center gap-1.5 text-[11px] text-slate-400 bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 mr-2"
                    >
                      {inv.state === "result" ? (
                        <Wrench className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <Loader2 className="w-3 h-3 animate-spin text-sky-400" />
                      )}
                      <span>{inv.toolName}</span>
                    </div>
                  );
                })}
              </div>
            </div>
            </ErrorBoundary>
          ))}

          {error && (
            <div className="rounded-xl border border-rose-800/60 bg-rose-950/30 p-3 text-xs text-rose-200">
              {error.message}
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="p-4 border-t border-slate-800 bg-slate-950/70">
          <div className="max-w-3xl mx-auto flex items-center gap-2">
            <input
              value={input}
              onChange={handleInputChange}
              placeholder="Ask to compare hotels, review an itinerary with AI Council, or add a place..."
              className="flex-1 rounded-xl border border-slate-800 bg-slate-900 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2.5 text-sm font-medium text-white transition cursor-pointer"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Send
            </button>
          </div>
        </form>
      </main>
        )}
      </div>
    </div>
  );
}

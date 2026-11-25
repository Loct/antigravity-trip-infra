import { NextResponse } from "next/server";
import { callMCPTool, createWanderlogMCPClient } from "@/lib/mcp";

interface ParsedTrip {
  id: string;
  title: string;
  placesCount?: string;
}

function parseTripsResponse(raw: unknown): ParsedTrip[] {
  if (Array.isArray(raw)) {
    return raw.map((t: any) => ({
      id: String(t.id || t.tripId || t.trip_key || ""),
      title: String(t.title || t.id || t.trip_key || ""),
    }));
  }
  if (typeof raw === "string") {
    const trips: ParsedTrip[] = [];
    for (const line of raw.split("\n")) {
      const m = line.trim().match(/^\d+\.\s+(.+?)\s+\(([a-zA-Z0-9_-]+)\)(?:\s*\|\s*(.+))?$/);
      if (m) {
        trips.push({
          title: m[1].trim(),
          id: m[2].trim(),
          placesCount: m[3]?.trim(),
        });
      }
    }
    return trips;
  }
  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.trips)) return parseTripsResponse(obj.trips);
    if (Array.isArray(obj.data)) return parseTripsResponse(obj.data);
  }
  return [];
}

export async function GET() {
  const client = await createWanderlogMCPClient();
  try {
    const tools = await client.tools();
    const raw = await callMCPTool(tools, "list_trips", {});
    return NextResponse.json({ trips: parseTripsResponse(raw) });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to load trips";
    return NextResponse.json({ error: message }, { status: 500 });
  } finally {
    await client.close();
  }
}

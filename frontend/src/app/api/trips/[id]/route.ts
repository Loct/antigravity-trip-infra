import { NextResponse } from "next/server";
import { callMCPTool, createWanderlogMCPClient } from "@/lib/mcp";

export async function GET(
  _req: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  const client = await createWanderlogMCPClient();
  try {
    const tools = await client.tools();
    const [trip, itinerary] = await Promise.all([
      callMCPTool(tools, "get_trip", { trip_key: id }),
      callMCPTool(tools, "get_itinerary", { trip_key: id }),
    ]);
    return NextResponse.json({ trip, itinerary });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to load trip details";
    return NextResponse.json({ error: message }, { status: 500 });
  } finally {
    await client.close();
  }
}

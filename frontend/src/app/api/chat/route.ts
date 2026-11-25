import { anthropic } from "@ai-sdk/anthropic";
import { convertToCoreMessages, streamText } from "ai";
import {
  BLOCKED_WANDERLOG_TOOLS,
  MUTATION_WANDERLOG_TOOLS,
  createAntigravityToolsMCPClient,
  createWanderlogMCPClient,
} from "@/lib/mcp";

export const maxDuration = 120;

const SYSTEM_PROMPT = `You are Antigravity Travel Planner, an expert AI travel assistant with native MCP tools.

Core Rules:
1. Always use MCP tools rather than guessing:
   - Use "search_hotels_dual_ota" whenever searching for hotels/lodging so Booking.com (Genius) and Agoda (AgodaVIP) are compared side-by-side.
   - Use "ai_council_ask", "ai_council_crosscheck", and "ai_council_debate" to collaborate with Claude & DeepSeek on itinerary quality, transit, dining, and opening hours.
   - Use "list_trips", "get_trip", "get_itinerary", and "get_trip_places" to inspect existing Wanderlog trips.
2. Approval-Gated Mutations:
   - Never delete trips.
   - Whenever you want to modify a Wanderlog trip (add_place, add_lodging, add_flight, update_place_visit_time, etc.), call the mutation tool directly — the UI will automatically pause and present an Approve / Cancel card to the user before executing it.
3. Keep responses concise, structured, and helpful.`;

export async function POST(req: Request) {
  const { messages, selectedTripId } = await req.json();

  const [wanderlogClient, agyClient] = await Promise.all([
    createWanderlogMCPClient(),
    createAntigravityToolsMCPClient(),
  ]);

  try {
    const [rawWanderlogTools, agyTools] = await Promise.all([
      wanderlogClient.tools(),
      agyClient.tools(),
    ]);

    // Filter out blocked tools and strip `execute` from mutation tools so the UI gates approval
    const gatedWanderlogTools: Record<string, any> = {};
    for (const [name, toolDef] of Object.entries(rawWanderlogTools)) {
      if (BLOCKED_WANDERLOG_TOOLS.has(name)) continue;
      if (MUTATION_WANDERLOG_TOOLS.has(name)) {
        const { execute: _omit, ...clientApprovalTool } = toolDef as any;
        gatedWanderlogTools[name] = clientApprovalTool;
      } else {
        gatedWanderlogTools[name] = toolDef;
      }
    }

    const tripContextNote = selectedTripId
      ? `\n\nThe user currently has Wanderlog trip ID "${selectedTripId}" open in the workspace panel.`
      : "";

    const result = streamText({
      model: anthropic(process.env.ANTHROPIC_MODEL || "claude-sonnet-4-20250514"),
      system: SYSTEM_PROMPT + tripContextNote,
      messages: convertToCoreMessages(messages),
      tools: {
        ...agyTools,
        ...gatedWanderlogTools,
      },
      maxSteps: 6,
      onFinish: async () => {
        await Promise.allSettled([wanderlogClient.close(), agyClient.close()]);
      },
    });

    return result.toDataStreamResponse();
  } catch (error) {
    await Promise.allSettled([wanderlogClient.close(), agyClient.close()]);
    const message = error instanceof Error ? error.message : "Failed to run chat";
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}

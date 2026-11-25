import { createAnthropic } from "@ai-sdk/anthropic";
import { convertToCoreMessages, streamText, tool } from "ai";
import { z } from "zod";

const anthropic = createAnthropic({
  fetch: async (url, init) => {
    if (init?.body && typeof init.body === "string") {
      try {
        const parsed = JSON.parse(init.body);
        if ("temperature" in parsed) {
          delete parsed.temperature;
          init = { ...init, body: JSON.stringify(parsed) };
        }
      } catch {
        // Pass through non-JSON bodies unchanged
      }
    }
    return fetch(url, init);
  },
});
import {
  BLOCKED_WANDERLOG_TOOLS,
  MUTATION_WANDERLOG_TOOLS,
  createAntigravityToolsMCPClient,
  createWanderlogMCPClient,
  normalizeMCPTools,
} from "@/lib/mcp";

export const maxDuration = 120;

const SYSTEM_PROMPT = `You are Antigravity Travel Planner, an expert AI travel assistant with native MCP tools.

Core Rules:
1. Always use MCP tools rather than guessing:
   - Use "search_hotels_dual_ota" whenever searching for hotels/lodging so Booking.com (Genius) and Agoda (AgodaVIP) are compared side-by-side.
   - Use "ai_council_ask", "ai_council_crosscheck", and "ai_council_debate" to collaborate with Claude & DeepSeek on itinerary quality, transit, dining, and opening hours.
   - Use "list_trips", "get_trip", "get_itinerary", and "get_trip_places" to inspect existing Wanderlog trips.
   - Whenever presenting a booked or planned hotel from a Wanderlog trip, ALWAYS call "display_hotel_card" so the UI renders a rich Hotel Card instead of a raw table.
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
    const [rawWanderlogTools, rawAgyTools] = await Promise.all([
      wanderlogClient.tools(),
      agyClient.tools(),
    ]);

    const agyTools = normalizeMCPTools(rawAgyTools);
    const gatedWanderlogTools = normalizeMCPTools(rawWanderlogTools, {
      blockTools: BLOCKED_WANDERLOG_TOOLS,
      requireApprovalFor: MUTATION_WANDERLOG_TOOLS,
    });

    const tripContextNote = selectedTripId
      ? `\n\nThe user currently has Wanderlog trip ID "${selectedTripId}" open in the workspace panel.`
      : "";

    const displayHotelCardTool = tool({
      description:
        "Render a rich Hotel Card in the UI for a booked or planned hotel from a Wanderlog trip.",
      parameters: z.object({
        name: z.string(),
        address: z.string().optional(),
        checkIn: z.string().optional(),
        checkOut: z.string().optional(),
        nights: z.number().optional(),
        confirmationNumber: z.string().optional(),
        bookedUnder: z.string().optional(),
        cost: z.string().optional(),
        rating: z.number().optional(),
        reviewCount: z.number().optional(),
        phone: z.string().optional(),
        provider: z.string().optional(),
        url: z.string().optional(),
        notes: z.string().optional(),
      }),
      execute: async (args) => args,
    });

    const result = streamText({
      model: anthropic(process.env.ANTHROPIC_MODEL || "claude-sonnet-4-20250514"),
      system: SYSTEM_PROMPT + tripContextNote,
      messages: convertToCoreMessages(messages),
      tools: {
        ...agyTools,
        ...gatedWanderlogTools,
        display_hotel_card: displayHotelCardTool,
      },
      maxSteps: 6,
      onError: ({ error }) => {
        console.error("[/api/chat] streamText error:", error);
      },
      onFinish: async () => {
        await Promise.allSettled([wanderlogClient.close(), agyClient.close()]);
      },
    });

    return result.toDataStreamResponse({
      getErrorMessage: (err) => {
        console.error("[/api/chat] response error:", err);
        return err instanceof Error ? err.message : String(err);
      },
    });
  } catch (error) {
    await Promise.allSettled([wanderlogClient.close(), agyClient.close()]);
    const message = error instanceof Error ? error.message : "Failed to run chat";
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}

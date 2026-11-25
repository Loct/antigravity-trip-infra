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
  callMCPTool,
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
   - Whenever the user asks for a map, route, or geographic overview of a trip or day, ALWAYS call "display_trip_map". For a full Wanderlog trip map, simply pass "tripKey" (e.g. "oocqlrcxztnlvaic") and the server will plot all stops automatically; only pass custom "markers" if plotting a custom subset. NEVER draw ASCII maps.
   - Whenever recommending restaurants, sights, cafes, or activities, ALWAYS call "display_place_recommendations" so the UI renders interactive recommendation cards with one-click "Add to Trip" buttons.
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

    const displayTripMapTool = tool({
      description:
        "Render an interactive Leaflet map with pins and optional route polyline in the chat UI. Pass tripKey to automatically plot all stops from a Wanderlog trip, or pass custom markers.",
      parameters: z.object({
        title: z.string().optional(),
        tripKey: z.string().optional(),
        drawRoute: z.boolean().optional(),
        markers: z
          .array(
            z.object({
              name: z.string(),
              lat: z.number(),
              lng: z.number(),
              category: z.enum(["place", "hotel", "transit", "flight"]).optional(),
              day: z.string().optional(),
              notes: z.string().optional(),
              url: z.string().optional(),
            }),
          )
          .optional(),
      }),
      execute: async (args) => {
        if (args.markers && args.markers.length > 0) {
          return args;
        }
        if (args.tripKey) {
          const raw = (await callMCPTool(rawWanderlogTools, "get_itinerary", {
            trip_key: args.tripKey,
          })) as Record<string, unknown> | null;
          const inner = (raw?.itinerary as Record<string, unknown> | undefined) || raw;
          const sections = (inner?.sections as Array<Record<string, unknown>>) || [];
          const markers: Array<Record<string, unknown>> = [];
          for (const sec of sections) {
            const day =
              (sec.displayHeading as string) || (sec.heading as string) || (sec.date as string) || undefined;
            const isHotel = Boolean(day && /hotel|lodging|stay/i.test(day));
            const blocks = (sec.blocks as Array<Record<string, unknown>>) || [];
            for (const b of blocks) {
              const pushLoc = (place: Record<string, unknown> | undefined, cat: string) => {
                const loc = (place?.geometry as Record<string, unknown> | undefined)?.location as
                  | Record<string, unknown>
                  | undefined;
                if (typeof loc?.lat === "number" && typeof loc?.lng === "number") {
                  markers.push({
                    name: (place?.name as string) || (b.name as string) || "Stop",
                    lat: loc.lat,
                    lng: loc.lng,
                    category: cat,
                    day,
                  });
                }
              };
              if (b.place) pushLoc(b.place as Record<string, unknown>, isHotel ? "hotel" : "place");
              const depart = b.depart as Record<string, unknown> | undefined;
              const arrive = b.arrive as Record<string, unknown> | undefined;
              if (depart?.place) pushLoc(depart.place as Record<string, unknown>, "transit");
              if (arrive?.place) pushLoc(arrive.place as Record<string, unknown>, "transit");
            }
          }
          return { ...args, markers };
        }
        return { ...args, markers: [] };
      },
    });

    const displayPlaceRecommendationsTool = tool({
      description:
        "Render interactive place/activity recommendation cards in the UI with Add-to-Trip buttons.",
      parameters: z.object({
        title: z.string().optional(),
        places: z.array(
          z.object({
            name: z.string(),
            category: z.string().optional(),
            rating: z.number().optional(),
            address: z.string().optional(),
            description: z.string().optional(),
            duration: z.string().optional(),
            estimatedCost: z.string().optional(),
            lat: z.number().optional(),
            lng: z.number().optional(),
            url: z.string().optional(),
          }),
        ),
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
        display_trip_map: displayTripMapTool,
        display_place_recommendations: displayPlaceRecommendationsTool,
      },
      maxSteps: 6,
      maxTokens: 8192,
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

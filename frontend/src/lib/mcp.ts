import { experimental_createMCPClient as createMCPClient } from "@ai-sdk/mcp";
import { Experimental_StdioMCPTransport as StdioMCPTransport } from "@ai-sdk/mcp/mcp-stdio";

export const BLOCKED_WANDERLOG_TOOLS = new Set([
  "delete_trip",
  "delete_trips",
  "nuke_trip_places",
  "server_logout",
  "block_user",
]);

export const MUTATION_WANDERLOG_TOOLS = new Set([
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

const WORKSPACE_DIR = process.env.WORKSPACE_DIR || "/workspace";

export async function createWanderlogMCPClient() {
  const transport = new StdioMCPTransport({
    command: "wanderlog",
    args: ["mcp", "--enable-write"],
    env: {
      ...process.env,
      WANDERLOG_AUTH_SESSION_COOKIE: process.env.WANDERLOG_AUTH_SESSION_COOKIE || "",
      WANDERLOG_AUTH_SESSION_XSRF_TOKEN: process.env.WANDERLOG_AUTH_SESSION_XSRF_TOKEN || "cookie_auth",
      WANDERLOG_DISABLE_KEYCHAIN: "1",
    } as Record<string, string>,
  });
  return createMCPClient({ transport });
}

export async function createAntigravityToolsMCPClient() {
  const transport = new StdioMCPTransport({
    command: "uv",
    args: ["run", "--directory", WORKSPACE_DIR, "scripts/mcp_server.py"],
    env: process.env as Record<string, string>,
  });
  return createMCPClient({ transport });
}

export async function callMCPTool(
  tools: Record<string, unknown>,
  toolName: string,
  args: Record<string, unknown> = {},
): Promise<unknown> {
  const tool = tools[toolName] as
    | { execute?: (a: Record<string, unknown>, ctx: { toolCallId: string; messages: never[] }) => PromiseLike<unknown> }
    | undefined;
  if (!tool?.execute) {
    throw new Error(`Tool "${toolName}" is unavailable on MCP server.`);
  }
  const raw = await tool.execute(args, { toolCallId: `${toolName}-${Date.now()}`, messages: [] });
  return extractMCPTextResult(raw);
}

export function extractMCPTextResult(result: unknown): unknown {
  if (!result || typeof result !== "object") return result;
  const r = result as { content?: Array<{ type?: string; text?: string }>; structuredContent?: unknown };
  if (r.structuredContent !== undefined) return r.structuredContent;
  if (Array.isArray(r.content)) {
    const textParts = r.content
      .filter((c) => c.type === "text" && typeof c.text === "string")
      .map((c) => c.text as string);
    const joined = textParts.join("\n").trim();
    if (!joined) return result;
    try {
      return JSON.parse(joined);
    } catch {
      return joined;
    }
  }
  return result;
}

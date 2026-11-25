import { NextResponse } from "next/server";
import {
  BLOCKED_WANDERLOG_TOOLS,
  MUTATION_WANDERLOG_TOOLS,
  callMCPTool,
  createWanderlogMCPClient,
} from "@/lib/mcp";

export async function POST(req: Request) {
  const { toolName, args } = (await req.json()) as {
    toolName?: string;
    args?: Record<string, unknown>;
  };

  if (!toolName || BLOCKED_WANDERLOG_TOOLS.has(toolName) || !MUTATION_WANDERLOG_TOOLS.has(toolName)) {
    return NextResponse.json(
      { error: `Tool "${toolName}" is not an allowed mutation tool.` },
      { status: 400 },
    );
  }

  const client = await createWanderlogMCPClient();
  try {
    const tools = await client.tools();
    const result = await callMCPTool(tools, toolName, args || {});
    return NextResponse.json({ ok: true, result });
  } catch (error) {
    const message = error instanceof Error ? error.message : "MCP execution failed";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  } finally {
    await client.close();
  }
}

import { NextResponse } from "next/server";
import { validateSPARQL, extractServiceEndpoints, checkServicePolicy } from "@/lib/sparql/validator";
import { loadContextPack } from "@/lib/context-packs/loader";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { query, pack_id } = body;

    if (!query || typeof query !== "string") {
      return NextResponse.json(
        { error: "Missing or invalid 'query' parameter" },
        { status: 400 }
      );
    }

    const pack = pack_id ? loadContextPack(pack_id) : null;
    if (pack_id && !pack) {
      return NextResponse.json(
        { error: `Context pack not found: ${pack_id}` },
        { status: 404 }
      );
    }

    const guardrails = pack?.guardrails || {
      forbid_ops: ["INSERT", "DELETE", "LOAD", "CLEAR", "DROP", "CREATE", "MOVE", "COPY", "ADD"],
      max_limit: 500,
    };

    const validation = validateSPARQL(query, guardrails);

    // Check SERVICE policy if pack is provided
    if (pack && pack.guardrails.allow_service) {
      const serviceEndpoints = extractServiceEndpoints(query);
      if (serviceEndpoints.length > 0) {
        // Get FRINK endpoints for allow_any_frink policy
        const frinkEndpoints = pack.endpoint_mode.federated_endpoint
          ? [pack.endpoint_mode.federated_endpoint]
          : [];

        const serviceCheck = checkServicePolicy(
          serviceEndpoints,
          pack.guardrails.service_policy,
          pack.guardrails.service_allowlist,
          frinkEndpoints
        );

        if (!serviceCheck.allowed) {
          validation.errors.push(`SERVICE policy violation: ${serviceCheck.reason}`);
          validation.valid = false;
        }
      }
    }

    return NextResponse.json({
      ok: validation.valid,
      errors: validation.errors,
      warnings: validation.warnings,
      normalized_query: validation.normalized_query,
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Validation failed" },
      { status: 500 }
    );
  }
}





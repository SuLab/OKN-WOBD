#!/usr/bin/env node

/**
 * LLM SPARQL Generation Testing Script
 * 
 * Tests the LLM-generated SPARQL (Lane B) components:
 * 1. LLM-generated SPARQL endpoint (Lane B)
 * 2. SPARQL repair functionality
 * 3. SPARQL validation
 * 4. Preflight probes
 * 5. Query execution with repair/preflight
 * 
 * Usage:
 *   node test-llm-sparql-generation.js [--with-llm] [--with-endpoint]
 * 
 * Options:
 *   --with-llm: Test LLM-generated SPARQL endpoint (requires ANTHROPIC_SHARED_API_KEY or OPENAI_SHARED_API_KEY)
 *   --with-endpoint: Test against actual FRINK endpoint
 */

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:3000";

async function test(name, fn) {
    try {
        console.log(`\n🧪 Testing: ${name}`);
        await fn();
        console.log(`✅ Passed: ${name}`);
        return true;
    } catch (error) {
        console.error(`❌ Failed: ${name}`);
        console.error(`   Error: ${error.message}`);
        if (error.response) {
            const text = await error.response.text().catch(() => "");
            console.error(`   Response: ${text.substring(0, 200)}`);
        }
        return false;
    }
}

async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
    });
    if (!response.ok) {
        const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
        error.response = response;
        throw error;
    }
    return response.json();
}

// Test 1: SPARQL Validation
async function testValidation() {
    const result = await fetchJSON(`${BASE_URL}/api/tools/sparql/validate`, {
        method: "POST",
        body: JSON.stringify({
            query: "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10",
            pack_id: "wobd",
        }),
    });

    if (!result.ok) {
        throw new Error(`Valid query was marked as invalid: ${result.errors.join(", ")}`);
    }

    // Test forbidden operation
    const invalidResult = await fetchJSON(`${BASE_URL}/api/tools/sparql/validate`, {
        method: "POST",
        body: JSON.stringify({
            query: "INSERT DATA { <s> <p> <o> }",
            pack_id: "wobd",
        }),
    });

    if (invalidResult.ok) {
        throw new Error("Invalid query (INSERT) was marked as valid");
    }

    console.log(`   Validation errors for INSERT: ${invalidResult.errors.length}`);
}

// Test 2: SPARQL Repair
async function testRepair() {
    // Test repair via API endpoint (we'll test the logic indirectly)
    // For direct testing, you'd need to compile TypeScript or use a test framework
    // This test verifies repair is available in the execution flow

    // Test with a query that might trigger repair
    const result = await fetchJSON(`${BASE_URL}/api/tools/sparql/execute`, {
        method: "POST",
        body: JSON.stringify({
            query: "SELECT ?s WHERE { ?s a ?type FILTER(STR(?type) = \"exact\") FILTER(STR(?s) = \"exact2\") } LIMIT 5",
            pack_id: "wobd",
            attempt_repair: true,
        }),
    });

    // Repair may or may not be triggered depending on whether query fails
    // Just verify the endpoint accepts the repair flag
    console.log(`   Repair flag accepted (query may or may not have needed repair)`);
}

// Test 3: Query Execution (without endpoint)
async function testExecutionValidation() {
    // Test that execution endpoint validates queries
    try {
        await fetchJSON(`${BASE_URL}/api/tools/sparql/execute`, {
            method: "POST",
            body: JSON.stringify({
                query: "INSERT DATA { <s> <p> <o> }",
                pack_id: "wobd",
            }),
        });
        throw new Error("Should have rejected INSERT query");
    } catch (error) {
        if (error.response && error.response.status === 400) {
            // Expected - validation should reject this
            return;
        }
        throw error;
    }
}

// Test 4: LLM-Generated SPARQL Endpoint (requires API key)
async function testLLMGeneratedSPARQL() {
    const apiKey = process.env.ANTHROPIC_SHARED_API_KEY || process.env.OPENAI_SHARED_API_KEY || 
                   process.env.ANTHROPIC_API_KEY || process.env.OPENAI_API_KEY;
    if (!apiKey) {
        throw new Error("ANTHROPIC_SHARED_API_KEY or OPENAI_SHARED_API_KEY not set. Skipping LLM-generated SPARQL test.");
    }

    const result = await fetchJSON(`${BASE_URL}/api/tools/nl/open-query`, {
        method: "POST",
        body: JSON.stringify({
            text: "Find datasets about COVID-19",
            pack_id: "wobd",
            use_shared: !!(process.env.ANTHROPIC_SHARED_API_KEY || process.env.OPENAI_SHARED_API_KEY),
            session_id: "test-session",
        }),
    });

    if (!result.query) {
        throw new Error("LLM-generated SPARQL endpoint should return a SPARQL query");
    }

    if (!result.query.includes("SELECT") && !result.query.includes("ASK")) {
        throw new Error("Generated query should be SELECT or ASK");
    }

    console.log(`   Generated query preview: ${result.query.substring(0, 100)}...`);
    console.log(`   Validation warnings: ${result.validation.warnings.length}`);
}

// Test 5: Query Execution with Repair (requires endpoint)
async function testExecutionWithRepair() {
    const endpoint = process.env.FRINK_ENDPOINT || "https://frink.apps.renci.org/federation/sparql";

    // Test with a query that might need repair
    const result = await fetchJSON(`${BASE_URL}/api/tools/sparql/execute`, {
        method: "POST",
        body: JSON.stringify({
            query: "SELECT ?dataset ?name WHERE { ?dataset a schema:Dataset ; schema:name ?name } LIMIT 10",
            pack_id: "wobd",
            mode: "federated",
            graphs: ["nde"],
            attempt_repair: true,
            run_preflight: false, // Skip preflight for faster test
        }),
    });

    if (result.error && !result.repair_attempt) {
        console.log("   Query failed but no repair was attempted (may be expected)");
    }

    if (result.repair_attempt) {
        console.log(`   Repair attempted: ${result.repair_attempt.success}`);
        if (result.repair_attempt.changes.length > 0) {
            console.log(`   Repair changes: ${result.repair_attempt.changes.join(", ")}`);
        }
    }
}

// Test 6: Context Pack Loading
async function testContextPack() {
    const result = await fetchJSON(`${BASE_URL}/api/tools/context/packs/wobd`);

    if (!result.id || result.id !== "wobd") {
        throw new Error("Context pack should have id 'wobd'");
    }

    if (!result.guardrails) {
        throw new Error("Context pack should have guardrails");
    }

    console.log(`   Pack version: ${result.version}`);
    console.log(`   Default graphs: ${result.graphs.default_shortnames.join(", ")}`);
}

// Test 7: Intent Classification
async function testIntentClassification() {
    const result = await fetchJSON(`${BASE_URL}/api/tools/nl/intent`, {
        method: "POST",
        body: JSON.stringify({
            text: "Find datasets about diabetes",
            pack_id: "wobd",
        }),
    });

    if (!result.task) {
        throw new Error("Intent should have a task");
    }

    if (!result.lane) {
        throw new Error("Intent should have a lane");
    }

    console.log(`   Task: ${result.task}`);
    console.log(`   Lane: ${result.lane}`);
    console.log(`   Confidence: ${result.confidence}`);
}

async function main() {
    const args = process.argv.slice(2);
    const withLLM = args.includes("--with-llm");
    const withEndpoint = args.includes("--with-endpoint");

    console.log("🚀 LLM SPARQL Generation Testing Suite");
    console.log(`   Base URL: ${BASE_URL}`);
    console.log(`   With LLM tests: ${withLLM}`);
    console.log(`   With endpoint tests: ${withEndpoint}`);

    const results = [];

    // Core tests (always run)
    results.push(await test("SPARQL Validation", testValidation));
    results.push(await test("SPARQL Repair", testRepair));
    results.push(await test("Query Execution Validation", testExecutionValidation));
    results.push(await test("Context Pack Loading", testContextPack));
    results.push(await test("Intent Classification", testIntentClassification));

    // Optional tests
    if (withLLM) {
        results.push(await test("LLM-Generated SPARQL (Lane B)", testLLMGeneratedSPARQL));
    } else {
        console.log("\n⏭️  Skipping LLM-generated SPARQL test (use --with-llm to enable)");
    }

    if (withEndpoint) {
        results.push(await test("Query Execution with Repair", testExecutionWithRepair));
    } else {
        console.log("\n⏭️  Skipping endpoint tests (use --with-endpoint to enable)");
    }

    // Summary
    const passed = results.filter(r => r).length;
    const total = results.length;

    console.log("\n" + "=".repeat(50));
    console.log(`📊 Test Results: ${passed}/${total} passed`);

    if (passed === total) {
        console.log("✅ All tests passed!");
        process.exit(0);
    } else {
        console.log("❌ Some tests failed");
        process.exit(1);
    }
}

// Check if server is running
fetch(`${BASE_URL}/api/tools/context/packs/wobd`)
    .then(() => main())
    .catch((error) => {
        console.error("❌ Cannot connect to server. Make sure it's running:");
        console.error(`   npm run dev`);
        console.error(`   Error: ${error.message}`);
        process.exit(1);
    });


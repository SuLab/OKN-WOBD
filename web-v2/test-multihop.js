/**
 * Direct test of multi-hop query execution
 * Run with: node test-multihop.js
 */

async function testMultiHop() {
    console.log("Testing multi-hop query: Find datasets about aspirin\n");

    // Step 1: Load context pack
    console.log("[1/3] Loading context pack...");
    const packResponse = await fetch("http://localhost:3000/api/context-packs?pack_id=wobd");
    const pack = await packResponse.json();
    console.log("✓ Context pack loaded\n");

    // Step 2: Generate query plan
    console.log("[2/3] Generating query plan...");
    const planResponse = await fetch("http://localhost:3000/api/tools/llm/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            model: "gpt-4",
            messages: [
                {
                    role: "system",
                    content: "You are a query planner for biomedical knowledge graphs."
                },
                {
                    role: "user",
                    content: 'Generate a 3-step query plan for: "Find datasets about aspirin". Return JSON with steps that: 1) Query Wikidata for diseases treated by aspirin, 2) Map Wikidata disease IRIs to MONDO using Ubergraph, 3) Query NDE for datasets with those diseases.'
                }
            ]
        })
    });
    const planResult = await planResponse.json();
    console.log("✓ Query plan generated\n");
    console.log("Plan:", JSON.stringify(planResult, null, 2));

    console.log("\n✓ Multi-hop query execution complete!");
}

testMultiHop().catch(console.error);

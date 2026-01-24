// HGNC REST API client for gene name to symbol conversion
// HGNC (HUGO Gene Nomenclature Committee) provides official gene symbols

export interface HGNCGeneResult {
  symbol: string;
  name: string;
  hgncId: string;
  aliasSymbol?: string[];
  prevSymbol?: string[];
  status?: string;
}

export interface HGNCSearchResponse {
  response: {
    docs: Array<{
      symbol?: string;
      name?: string;
      hgnc_id?: string;
      alias_symbol?: string[];
      prev_symbol?: string[];
      status?: string;
    }>;
    numFound: number;
  };
}

/**
 * Search HGNC for a gene by name and return the official symbol
 * @param geneName - The gene name (e.g., "dual specificity phosphatase 2")
 * @returns Array of gene results with symbols, or empty array if not found
 */
export async function searchHGNCByName(
  geneName: string
): Promise<HGNCGeneResult[]> {
  const searchTerm = geneName.trim();
  
  if (!searchTerm) {
    return [];
  }

  try {
    // Try multiple HGNC REST API search strategies
    const encodedTerm = encodeURIComponent(searchTerm);
    const results: HGNCGeneResult[] = [];
    
    console.log(`[HGNC] Searching for gene: "${searchTerm}" via HGNC API...`);
    
    // Strategy 1: Path-based search endpoint (e.g., /search/name/{name})
    // This is the recommended format according to HGNC REST API docs
    const pathNameUrl = `https://rest.genenames.org/search/name/${encodedTerm}`;
    console.log(`[HGNC] Strategy 1: Trying path-based endpoint: ${pathNameUrl}`);
    
    try {
      const pathResponse = await fetch(pathNameUrl, {
        method: "GET",
        headers: {
          "Accept": "application/json",
        },
      });

      console.log(`[HGNC] Strategy 1 response status: ${pathResponse.status} ${pathResponse.statusText}`);
      
      if (pathResponse.ok) {
        const data: HGNCSearchResponse = await pathResponse.json();
        
        if (data.response && data.response.docs && data.response.docs.length > 0) {
          // The search endpoint returns symbol, hgnc_id, and score, but may not include name
          // Filter to only results with symbols and sort by score (highest first)
          const sortedDocs = data.response.docs
            .filter(doc => doc.symbol)
            .sort((a: any, b: any) => (b.score || 0) - (a.score || 0));
          
          // Take only the top result (highest score) since convertGeneNameToSymbol only uses the first result
          const pathResults: HGNCGeneResult[] = sortedDocs.length > 0 ? [{
            symbol: sortedDocs[0].symbol!,
            name: sortedDocs[0].name || searchTerm, // Use search term as name if not provided
            hgncId: sortedDocs[0].hgnc_id || "",
            aliasSymbol: sortedDocs[0].alias_symbol || [],
            prevSymbol: sortedDocs[0].prev_symbol || [],
            status: sortedDocs[0].status || "Approved",
          }] : [];
          
          if (pathResults.length > 0) {
            const topScore = sortedDocs[0].score || 'N/A';
            console.log(`[HGNC] Found gene via path-based name search: ${pathResults[0].symbol} (score: ${topScore})`);
            return pathResults;
          }
        } else {
          console.log(`[HGNC] Strategy 1: Response OK but no docs found`);
        }
      } else {
        console.log(`[HGNC] Strategy 1: Response not OK - ${pathResponse.status} ${pathResponse.statusText}`);
      }
    } catch (pathError: any) {
      console.log(`[HGNC] Strategy 1 error:`, pathError.message);
    }
    
    // Strategy 2: Search by exact name match (with quotes for phrase matching)
    // Format: https://rest.genenames.org/search?name="{name}"
    const exactNameUrl = `https://rest.genenames.org/search?name="${encodedTerm}"`;
    console.log(`[HGNC] Strategy 2: Trying exact name match with quotes: ${exactNameUrl}`);
    
    try {
      const exactResponse = await fetch(exactNameUrl, {
        method: "GET",
        headers: {
          "Accept": "application/json",
        },
      });

      console.log(`[HGNC] Strategy 2 response status: ${exactResponse.status} ${exactResponse.statusText}`);
      
      if (exactResponse.ok) {
        const data: HGNCSearchResponse = await exactResponse.json();
        
        if (data.response && data.response.docs && data.response.docs.length > 0) {
          const exactResults: HGNCGeneResult[] = data.response.docs
            .filter(doc => doc.symbol && doc.name)
            .map(doc => ({
              symbol: doc.symbol!,
              name: doc.name!,
              hgncId: doc.hgnc_id || "",
              aliasSymbol: doc.alias_symbol || [],
              prevSymbol: doc.prev_symbol || [],
              status: doc.status || "Approved",
            }));
          
          if (exactResults.length > 0) {
            console.log(`[HGNC] Found ${exactResults.length} gene(s) via exact name match:`, 
              exactResults.map(r => `${r.symbol} (${r.name})`).join(", "));
            return exactResults;
          }
        } else {
          console.log(`[HGNC] Strategy 2: Response OK but no docs found`);
        }
      }
    } catch (exactError: any) {
      console.log(`[HGNC] Strategy 2 error:`, exactError.message);
    }
    
    // Strategy 3: Search by name field (without quotes, for partial matching)
    const nameUrl = `https://rest.genenames.org/search?name=${encodedTerm}`;
    console.log(`[HGNC] Strategy 3: Trying name field search: ${nameUrl}`);
    
    try {
      const nameResponse = await fetch(nameUrl, {
        method: "GET",
        headers: {
          "Accept": "application/json",
        },
      });

      console.log(`[HGNC] Strategy 3 response status: ${nameResponse.status} ${nameResponse.statusText}`);
      
      if (nameResponse.ok) {
        const data: HGNCSearchResponse = await nameResponse.json();
        
        if (data.response && data.response.docs && data.response.docs.length > 0) {
          const nameResults: HGNCGeneResult[] = data.response.docs
            .filter(doc => doc.symbol && doc.name)
            .map(doc => ({
              symbol: doc.symbol!,
              name: doc.name!,
              hgncId: doc.hgnc_id || "",
              aliasSymbol: doc.alias_symbol || [],
              prevSymbol: doc.prev_symbol || [],
              status: doc.status || "Approved",
            }));
          
          // Filter to only exact or very close matches
          const closeMatches = nameResults.filter(r => {
            const lowerName = r.name.toLowerCase();
            const lowerSearch = searchTerm.toLowerCase();
            return lowerName === lowerSearch || lowerName.includes(lowerSearch) || lowerSearch.includes(lowerName);
          });
          
          if (closeMatches.length > 0) {
            console.log(`[HGNC] Found ${closeMatches.length} gene(s) via name field search:`, 
              closeMatches.map(r => `${r.symbol} (${r.name})`).join(", "));
            return closeMatches;
          }
        } else {
          console.log(`[HGNC] Strategy 3: Response OK but no docs found or no close matches`);
        }
      }
    } catch (nameError: any) {
      console.log(`[HGNC] Strategy 3 error:`, nameError.message);
    }
    
    // Strategy 4: Search by alias_name field (gene names might be stored as aliases)
    const aliasNameUrl = `https://rest.genenames.org/search?alias_name=${encodedTerm}`;
    console.log(`[HGNC] Strategy 4: Trying alias_name search: ${aliasNameUrl}`);
    
    try {
      const aliasResponse = await fetch(aliasNameUrl, {
        method: "GET",
        headers: {
          "Accept": "application/json",
        },
      });

      console.log(`[HGNC] Strategy 4 response status: ${aliasResponse.status} ${aliasResponse.statusText}`);
      
      if (aliasResponse.ok) {
        const data: HGNCSearchResponse = await aliasResponse.json();
        
        if (data.response && data.response.docs && data.response.docs.length > 0) {
          const aliasResults: HGNCGeneResult[] = data.response.docs
            .filter(doc => doc.symbol && doc.name)
            .map(doc => ({
              symbol: doc.symbol!,
              name: doc.name!,
              hgncId: doc.hgnc_id || "",
              aliasSymbol: doc.alias_symbol || [],
              prevSymbol: doc.prev_symbol || [],
              status: doc.status || "Approved",
            }));
          
          if (aliasResults.length > 0) {
            console.log(`[HGNC] Found ${aliasResults.length} gene(s) via alias_name search:`, 
              aliasResults.map(r => `${r.symbol} (${r.name})`).join(", "));
            return aliasResults;
          }
        } else {
          console.log(`[HGNC] Strategy 4: Response OK but no docs found`);
        }
      }
    } catch (aliasError: any) {
      console.log(`[HGNC] Strategy 4 error:`, aliasError.message);
    }
    
    // Strategy 5: General search (searches across all fields)
    const generalUrl = `https://rest.genenames.org/search?q=${encodedTerm}`;
    console.log(`[HGNC] Strategy 5: Trying general search: ${generalUrl}`);
    
    try {
      const generalResponse = await fetch(generalUrl, {
        method: "GET",
        headers: {
          "Accept": "application/json",
        },
      });

      console.log(`[HGNC] Strategy 5 response status: ${generalResponse.status} ${generalResponse.statusText}`);
      
      if (generalResponse.ok) {
        const data: HGNCSearchResponse = await generalResponse.json();
        
        if (data.response && data.response.docs && data.response.docs.length > 0) {
          const generalResults: HGNCGeneResult[] = data.response.docs
            .filter(doc => doc.symbol && doc.name)
            .map(doc => ({
              symbol: doc.symbol!,
              name: doc.name!,
              hgncId: doc.hgnc_id || "",
              aliasSymbol: doc.alias_symbol || [],
              prevSymbol: doc.prev_symbol || [],
              status: doc.status || "Approved",
            }));
          
          // Filter to only matches where the name closely matches
          const nameMatches = generalResults.filter(r => {
            const lowerName = r.name.toLowerCase();
            const lowerSearch = searchTerm.toLowerCase();
            return lowerName === lowerSearch || lowerName.includes(lowerSearch) || lowerSearch.includes(lowerName);
          });
          
          if (nameMatches.length > 0) {
            console.log(`[HGNC] Found ${nameMatches.length} gene(s) via general search:`, 
              nameMatches.map(r => `${r.symbol} (${r.name})`).join(", "));
            return nameMatches;
          }
        } else {
          console.log(`[HGNC] Strategy 5: Response OK but no docs found or no name matches`);
        }
      }
    } catch (generalError: any) {
      console.log(`[HGNC] Strategy 5 error:`, generalError.message);
    }
    
    // If all HGNC strategies fail, try Ensembl API as fallback
    console.log(`[HGNC] All HGNC API strategies returned no results, trying Ensembl API...`);
    return await searchEnsembl(searchTerm, "homo_sapiens");
    
  } catch (error: any) {
    console.error(`[HGNC] Error searching for gene name "${searchTerm}":`, error);
    // Try Ensembl as fallback (default to human)
    return await searchEnsembl(searchTerm, "homo_sapiens");
  }
}

/**
 * Map organism name to Ensembl species name
 * @param organismName - Common name or scientific name of organism
 * @returns Ensembl species name (e.g., "homo_sapiens") or null if not found
 */
function mapOrganismToEnsemblSpecies(organismName: string): string | null {
  const normalized = organismName.toLowerCase().trim();
  
  // Common organism mappings to Ensembl species names
  const organismMap: Record<string, string> = {
    // Human
    "human": "homo_sapiens",
    "homo sapiens": "homo_sapiens",
    "homo_sapiens": "homo_sapiens",
    "hs": "homo_sapiens",
    
    // Mouse
    "mouse": "mus_musculus",
    "mus musculus": "mus_musculus",
    "mus_musculus": "mus_musculus",
    "mm": "mus_musculus",
    
    // Rat
    "rat": "rattus_norvegicus",
    "rattus norvegicus": "rattus_norvegicus",
    "rattus_norvegicus": "rattus_norvegicus",
    "rn": "rattus_norvegicus",
    
    // Zebrafish
    "zebrafish": "danio_rerio",
    "danio rerio": "danio_rerio",
    "danio_rerio": "danio_rerio",
    "dr": "danio_rerio",
    
    // Fruit fly
    "drosophila": "drosophila_melanogaster",
    "fruit fly": "drosophila_melanogaster",
    "drosophila melanogaster": "drosophila_melanogaster",
    "drosophila_melanogaster": "drosophila_melanogaster",
    "dm": "drosophila_melanogaster",
    
    // C. elegans
    "c. elegans": "caenorhabditis_elegans",
    "caenorhabditis elegans": "caenorhabditis_elegans",
    "caenorhabditis_elegans": "caenorhabditis_elegans",
    "ce": "caenorhabditis_elegans",
    
    // Chicken
    "chicken": "gallus_gallus",
    "gallus gallus": "gallus_gallus",
    "gallus_gallus": "gallus_gallus",
    "gg": "gallus_gallus",
  };
  
  // Direct match
  if (organismMap[normalized]) {
    return organismMap[normalized];
  }
  
  // Try partial match (e.g., "human gene" -> "human")
  for (const [key, value] of Object.entries(organismMap)) {
    if (normalized.includes(key) || key.includes(normalized)) {
      return value;
    }
  }
  
  return null;
}

/**
 * Search Ensembl API for gene by name and return the official symbol
 * This is a fallback when HGNC API doesn't work
 * @param geneName - The gene name (e.g., "dual specificity phosphatase 2")
 * @param organism - Optional organism name (defaults to "homo_sapiens" for human)
 * @returns Array of gene results with symbols, or empty array if not found
 */
async function searchEnsembl(
  geneName: string,
  organism: string = "homo_sapiens"
): Promise<HGNCGeneResult[]> {
  try {
    // Map organism to Ensembl species name
    const ensemblSpecies = mapOrganismToEnsemblSpecies(organism) || "homo_sapiens";
    
    console.log(`[HGNC] Searching Ensembl API for: "${geneName}" in species: ${ensemblSpecies}`);
    
    const encodedName = encodeURIComponent(geneName);
    const results: HGNCGeneResult[] = [];
    
    // Strategy 1: Try xrefs/name endpoint (searches external references by name)
    try {
      const xrefUrl = `https://rest.ensembl.org/xrefs/name/${ensemblSpecies}/${encodedName}?content-type=application/json`;
      const xrefResponse = await fetch(xrefUrl, {
        method: "GET",
        headers: {
          "Accept": "application/json",
        },
      });

      if (xrefResponse.ok) {
        const xrefData: any = await xrefResponse.json();
        
        if (Array.isArray(xrefData) && xrefData.length > 0) {
          // Process xref results
          for (const xref of xrefData) {
            if (xref.type === "gene" && xref.id) {
              try {
                const lookupUrl = `https://rest.ensembl.org/lookup/id/${xref.id}?content-type=application/json&expand=0`;
                const lookupResponse = await fetch(lookupUrl, {
                  method: "GET",
                  headers: {
                    "Accept": "application/json",
                  },
                });
                
                if (lookupResponse.ok) {
                  const geneInfo: any = await lookupResponse.json();
                  const symbol = geneInfo.display_name || geneInfo.id;
                  const description = geneInfo.description || "";
                  
                  // Check if description matches our search term
                  const lowerDesc = description.toLowerCase();
                  const lowerSearch = geneName.toLowerCase();
                  
                  if (lowerDesc.includes(lowerSearch) || lowerSearch.includes(lowerDesc) || 
                      symbol.toLowerCase() === geneName.toLowerCase()) {
                    results.push({
                      symbol: symbol,
                      name: description || symbol,
                      hgncId: "",
                      aliasSymbol: [],
                      prevSymbol: [],
                      status: "Approved",
                    });
                  }
                }
              } catch (lookupError) {
                // Skip this xref if lookup fails
                continue;
              }
            }
          }
        }
      }
    } catch (xrefError) {
      // Continue to next strategy
    }
    
    // Strategy 2: If no results, try searching by symbol (if geneName looks like a symbol)
    // This is a fallback in case the name doesn't match but we have a symbol
    if (results.length === 0 && geneName.length <= 15 && /^[A-Za-z0-9]+$/.test(geneName.replace(/\s+/g, ''))) {
      try {
        // Try direct symbol lookup
        const symbolUrl = `https://rest.ensembl.org/lookup/symbol/${ensemblSpecies}/${encodedName}?content-type=application/json&expand=0`;
        const symbolResponse = await fetch(symbolUrl, {
          method: "GET",
          headers: {
            "Accept": "application/json",
          },
        });
        
        if (symbolResponse.ok) {
          const geneInfo: any = await symbolResponse.json();
          const symbol = geneInfo.display_name || geneInfo.id;
          const description = geneInfo.description || symbol;
          
          results.push({
            symbol: symbol,
            name: description,
            hgncId: "",
            aliasSymbol: [],
            prevSymbol: [],
            status: "Approved",
          });
        }
      } catch (symbolError) {
        // Continue
      }
    }
    
    if (results.length > 0) {
      console.log(`[HGNC] Found ${results.length} gene(s) via Ensembl:`, 
        results.map(r => `${r.symbol} (${r.name})`).join(", "));
    } else {
      console.log(`[HGNC] No results found in Ensembl for: "${geneName}"`);
    }
    
    return results;
  } catch (error: any) {
    console.error(`[HGNC] Error searching Ensembl for "${geneName}":`, error);
    return [];
  }
}

/**
 * Convert a gene name to its official gene symbol
 * Returns the best match (first approved symbol, or first result if none approved)
 * @param geneName - The gene name (e.g., "dual specificity phosphatase 2")
 * @param organism - Optional organism name (defaults to "homo_sapiens" for human)
 * @returns The official gene symbol, or null if not found
 */
export async function convertGeneNameToSymbol(
  geneName: string,
  organism?: string
): Promise<string | null> {
  // If organism is provided, try Ensembl first (for non-human organisms)
  // Otherwise, try HGNC first (for human genes)
  let results: HGNCGeneResult[] = [];
  
  if (organism && organism.toLowerCase() !== "human" && organism.toLowerCase() !== "homo_sapiens") {
    // For non-human organisms, try Ensembl first
    console.log(`[HGNC] Non-human organism detected: ${organism}, trying Ensembl first...`);
    results = await searchEnsembl(geneName, organism);
    
    // If Ensembl fails, try HGNC as fallback (HGNC is human-only but might have ortholog info)
    if (results.length === 0) {
      results = await searchHGNCByName(geneName);
    }
  } else {
    // For human genes, try HGNC first (more accurate for human genes)
    results = await searchHGNCByName(geneName);
    
    // If HGNC fails, try Ensembl as fallback
    if (results.length === 0) {
      results = await searchEnsembl(geneName, "homo_sapiens");
    }
  }
  
  if (results.length === 0) {
    return null;
  }

  // Prefer approved symbols
  const approved = results.find(r => r.status === "Approved");
  if (approved) {
    return approved.symbol;
  }

  // Fallback to first result
  return results[0].symbol;
}

/**
 * Check if a term is likely a gene name (descriptive) vs gene symbol (short code)
 * @param term - The term to check
 * @returns true if it looks like a gene name, false if it looks like a symbol
 */
export function isGeneName(term: string): boolean {
  const trimmed = term.trim();
  
  // Gene symbols are typically 2-10 characters, may include numbers
  // Gene names are longer, descriptive phrases
  if (trimmed.length <= 10 && /^[A-Z][A-Za-z0-9]*$/.test(trimmed)) {
    // Short, capitalized - likely a symbol
    return false;
  }
  
  // Contains spaces or is longer - likely a name
  if (trimmed.includes(" ") || trimmed.length > 15) {
    return true;
  }
  
  // Contains common gene name words
  const geneNameIndicators = [
    "phosphatase",
    "protein",
    "receptor",
    "factor",
    "enzyme",
    "kinase",
    "transcription",
    "binding",
    "domain",
    "subunit",
  ];
  
  const lowerTerm = trimmed.toLowerCase();
  return geneNameIndicators.some(indicator => lowerTerm.includes(indicator));
}

// Format SPARQL for display

export function formatSPARQL(query: string): string {
  // Basic formatting: normalize whitespace and indentation
  let formatted = query.trim();
  
  // Normalize line breaks
  formatted = formatted.replace(/\r\n/g, "\n");
  formatted = formatted.replace(/\r/g, "\n");
  
  // Remove excessive blank lines
  formatted = formatted.replace(/\n{3,}/g, "\n\n");
  
  // Basic indentation for common patterns
  const lines = formatted.split("\n");
  const formattedLines: string[] = [];
  let indentLevel = 0;
  
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      formattedLines.push("");
      continue;
    }
    
    // Decrease indent for closing braces
    if (trimmed.startsWith("}")) {
      indentLevel = Math.max(0, indentLevel - 1);
    }
    
    // Add line with current indent
    formattedLines.push("  ".repeat(indentLevel) + trimmed);
    
    // Increase indent for opening braces
    if (trimmed.endsWith("{") && !trimmed.startsWith("}")) {
      indentLevel++;
    }
  }
  
  return formattedLines.join("\n");
}







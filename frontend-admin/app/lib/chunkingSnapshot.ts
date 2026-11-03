/** Only persisted chunking inputs, never search/ranking controls. */
export function chunkingSnapshot(config: Record<string, any> | null, summaryId: string, classificationId: string) {
  if (!config) return null;
  const keys = ["chunk_size", "chunk_overlap", "chunk_cross_page", "overlap_cross_page", "chunk_splitter_type",
    "chunking_strategy", "enrich_with_summary", "summary_custom_prompt", "semantic_params", "structure_params", "token_params", "agentic_params"];
  const value: Record<string, any> = {schema_version: 1};
  for (const key of keys) if (config[key] !== undefined) value[key] = config[key];
  if (config.enrich_with_summary && summaryId) value.summary_model_id = summaryId;
  if (config.chunking_strategy === "agentic" && classificationId) value.classification_model_id = classificationId;
  return value;
}

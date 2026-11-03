"use client";
const labels:Record<string,[string,string]>={
  chunk_size:["Velikost chunku (znaky)","Chunk size (characters)"], chunk_overlap:["Překryv (znaky)","Overlap (characters)"],
  chunk_cross_page:["Spojování stránek","Join pages"],overlap_cross_page:["Překryv mezi stránkami","Overlap across pages"],
  chunk_splitter_type:["Dělič textu","Text splitter"],chunking_strategy:["Strategie chunkování","Chunking strategy"],
  enrich_with_summary:["AI shrnutí v chunku","AI summary enrichment"],summary_custom_prompt:["Pravidla shrnutí","Summary instructions"],
  summary_model_id:["Model shrnutí","Summary model"],classification_model_id:["Model AI dělení","AI splitting model"],
  semantic_params:["Sémantické dělení","Semantic settings"],structure_params:["Strukturální dělení","Structural settings"],
  token_params:["Tokenové dělení","Token settings"],agentic_params:["AI dělení","AI splitting settings"],
  threshold_type:["Typ prahu","Threshold type"],threshold_value:["Hodnota prahu","Threshold value"],sentence_splitter:["Dělič vět","Sentence splitter"],
  buffer_size:["Okno vět","Sentence window"],max_size:["Maximální velikost (znaky)","Maximum size (characters)"],
  parser_type:["Typ struktury","Structure type"],preserve_tables:["Zachovat tabulky","Preserve tables"],preserve_lists:["Zachovat seznamy","Preserve lists"],
  heading_levels:["Úrovně nadpisů","Heading levels"],tokenizer_type:["Tokenizer","Tokenizer"],size_tokens:["Velikost (tokeny)","Size (tokens)"],
  overlap_tokens:["Překryv (tokeny)","Overlap (tokens)"],custom_prompt:["Vlastní pravidla dělení","Custom splitting instructions"],
  max_context_chars:["Velikost vstupu modelu (znaky)","Model input size (characters)"]
};
export function ChunkingSettingsView({value,cs}:{value:Record<string,any>;cs:boolean}) {
  return <dl className="grid grid-cols-[minmax(120px,1fr)_2fr] gap-x-4 gap-y-2 break-words">{Object.entries(value).filter(([key])=>!["schema_version","model_name"].includes(key)).map(([key,item])=><div key={key} className="contents"><dt className="text-zinc-400">{labels[key]?.[cs?0:1] || key}</dt><dd className="whitespace-pre-wrap">{item && typeof item === "object" && !Array.isArray(item) ? <ChunkingSettingsView value={item} cs={cs}/> : typeof item === "boolean" ? (item?(cs?"Ano":"Yes"):(cs?"Ne":"No")) : Array.isArray(item) ? item.join(", ") : item === null || item === "" ? "—" : String(item)}</dd></div>)}</dl>;
}

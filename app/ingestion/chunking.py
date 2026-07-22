import logging
from typing import Any, List, Optional
from app.ingestion.extraction import ExtractedPage

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a split chunk of text prepared for embedding generation."""
    def __init__(self, index: int, content: str, page_number: int, section_title: Optional[str] = None) -> None:
        self.index = index
        self.content = content
        self.page_number = page_number
        self.section_title = section_title


class RecursiveCharacterTextSplitter:
    """Split text recursively using a list of separators to keep paragraphs and sentences together."""

    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 250,
        chunk_cross_page: bool = False,
        overlap_cross_page: bool = False,
        chunk_splitter_type: str = "recursive",
        chunking_strategy: str = "standard",
        semantic_params: Optional[dict] = None,
        structure_params: Optional[dict] = None,
        token_params: Optional[dict] = None,
        agentic_params: Optional[dict] = None,
        embedding_provider: Optional[Any] = None,
        llm_provider: Optional[Any] = None,
    ) -> None:
        from typing import Any
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_cross_page = chunk_cross_page
        self.overlap_cross_page = overlap_cross_page
        self.chunk_splitter_type = chunk_splitter_type
        self.chunking_strategy = chunking_strategy
        self.semantic_params = semantic_params or {}
        self.structure_params = structure_params or {}
        self.token_params = token_params or {}
        self.agentic_params = agentic_params or {}
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider
        self.separators = ["\n\n", "\n", " ", ""]

    def _split_character_only_with_params(self, text: str, size: int, overlap: int) -> List[str]:
        chunks = []
        start = 0
        if size <= 0:
            return [text]
        step = size - overlap
        if step <= 0:
            step = 1
        while start < len(text):
            end = start + size
            chunk_str = text[start:end]
            if chunk_str.strip():
                chunks.append(chunk_str)
            if end >= len(text):
                break
            start += step
        return chunks

    def _split_by_tokens(self, text: str, size: int, overlap: int, tokenizer_type: str) -> List[str]:
        try:
            import tiktoken
            encoding = tiktoken.get_encoding(tokenizer_type)
            tokens = encoding.encode(text)
            chunks = []
            start = 0
            step = size - overlap
            if step <= 0:
                step = 1
            while start < len(tokens):
                end = start + size
                chunk_tokens = tokens[start:end]
                decoded = encoding.decode(chunk_tokens)
                if decoded.strip():
                    chunks.append(decoded)
                if end >= len(tokens):
                    break
                start += step
            return chunks
        except Exception as e:
            logger.warning(f"Failed to use tiktoken for token splitting: {e}. Falling back to character estimation.")
            return self._split_character_only_with_params(text, size * 4, overlap * 4)

    def _split_sentences(self, text: str, method: str) -> List[str]:
        if method == "nltk":
            try:
                import nltk
                return nltk.sent_tokenize(text)
            except Exception:
                pass
        elif method == "spacy":
            try:
                import spacy
                nlp = spacy.blank("en")
                nlp.add_pipe("sentencizer")
                doc = nlp(text)
                return [sent.text for sent in doc.sents]
            except Exception:
                pass
                
        import re
        sentence_end = re.compile(r'(?<=[.!?])\s+')
        splits = sentence_end.split(text)
        return [s.strip() for s in splits if s.strip()]

    def _split_semantic(self, text: str) -> List[str]:
        import math
        threshold_type = self.semantic_params.get("threshold_type", "percentile")
        threshold_value = self.semantic_params.get("threshold_value", 95.0)
        sentence_splitter = self.semantic_params.get("sentence_splitter", "nltk")
        buffer_size = self.semantic_params.get("buffer_size", 1)
        max_size = self.semantic_params.get("max_size", 3000)

        sentences = self._split_sentences(text, sentence_splitter)
        if not sentences:
            return [text]

        combined_sentences = []
        for i in range(len(sentences)):
            end_idx = min(i + buffer_size, len(sentences))
            combined_sentences.append(" ".join(sentences[i:end_idx]))

        embeddings = None
        if self.embedding_provider and hasattr(self.embedding_provider, "embed_documents"):
            try:
                import asyncio
                import concurrent.futures
                
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            lambda: asyncio.run(self.embedding_provider.embed_documents(combined_sentences))
                        )
                        embeddings = future.result()
                else:
                    embeddings = asyncio.run(self.embedding_provider.embed_documents(combined_sentences))
            except Exception as e:
                logger.error(f"Semantic splitter failed to compute embeddings: {e}")

        if not embeddings or len(embeddings) != len(combined_sentences):
            chunks = []
            curr = []
            curr_len = 0
            for s in sentences:
                if curr_len + len(s) > max_size and curr:
                    chunks.append(" ".join(curr))
                    curr = [s]
                    curr_len = len(s)
                else:
                    curr.append(s)
                    curr_len += len(s) + 1
            if curr:
                chunks.append(" ".join(curr))
            return chunks

        distances = []
        for i in range(len(embeddings) - 1):
            v1 = embeddings[i]
            v2 = embeddings[i+1]
            dot = sum(a*b for a, b in zip(v1, v2))
            norm1 = math.sqrt(sum(a*a for a in v1))
            norm2 = math.sqrt(sum(a*a for a in v2))
            similarity = dot / (norm1 * norm2) if (norm1 > 0 and norm2 > 0) else 1.0
            distances.append(1.0 - similarity)

        if not distances:
            return [text]

        try:
            sorted_dists = sorted(distances)
            mean_dist = sum(distances) / len(distances)
            variance = sum((x - mean_dist) ** 2 for x in distances) / len(distances)
            std_dist = math.sqrt(variance)

            if threshold_type == "percentile":
                idx = int(len(sorted_dists) * (threshold_value / 100.0))
                idx = min(max(0, idx), len(sorted_dists) - 1)
                limit = sorted_dists[idx]
            elif threshold_type == "standard_deviation":
                limit = mean_dist + threshold_value * std_dist
            else:
                limit = threshold_value
        except Exception:
            limit = 0.5

        chunks = []
        current_chunk = [sentences[0]]
        current_chunk_len = len(sentences[0])

        for i, dist in enumerate(distances):
            next_sentence = sentences[i+1]
            if dist > limit or (current_chunk_len + len(next_sentence) > max_size):
                chunks.append(" ".join(current_chunk))
                current_chunk = [next_sentence]
                current_chunk_len = len(next_sentence)
            else:
                current_chunk.append(next_sentence)
                current_chunk_len += len(next_sentence) + 1

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_structural(self, text: str, preserve_tables: bool, preserve_lists: bool, max_size: int) -> List[str]:
        import re
        blocks = re.split(r'(^(?:#|\s*##|\s*###|\s*####)\s+.*$)', text, flags=re.MULTILINE)
        chunks = []
        current_block = ""

        for block in blocks:
            if not block.strip():
                continue
            if block.strip().startswith("#") or (len(current_block) + len(block) > max_size):
                if current_block.strip():
                    chunks.append(current_block.strip())
                current_block = block
            else:
                current_block += "\n" + block

        if current_block.strip():
            chunks.append(current_block.strip())

        final_chunks = []
        for chunk in chunks:
            if len(chunk) > max_size:
                final_chunks.extend(self._split_text(chunk, self.separators))
            else:
                final_chunks.append(chunk)
        return final_chunks

    def _split_agentic(self, text: str) -> List[str]:
        generate_summaries = self.agentic_params.get("generate_summaries", False)
        custom_prompt = self.agentic_params.get("custom_prompt", "").strip()
        model_name = self.agentic_params.get("model_name", "gpt-4o-mini")

        splits = self._split_text(text, self.separators)
        if not splits:
            return [text]

        if generate_summaries or custom_prompt:
            final_splits = []
            for chunk in splits:
                if not chunk.strip():
                    continue

                summary_text = None
                if self.llm_provider and hasattr(self.llm_provider, "generate"):
                    try:
                        import asyncio
                        import concurrent.futures
                        from app.providers.llm import ChatMessage

                        system_instruction = (
                            "You are an expert AI document editor and summarizer.\n"
                            "Summarize the provided text passage in 1-2 concise sentences."
                        )
                        if custom_prompt:
                            system_instruction += (
                                f"\nCRITICAL INSTRUCTION FROM USER:\n"
                                f"Strictly follow these custom rules for output language, format, or focus:\n"
                                f"\"{custom_prompt}\""
                            )

                        messages = [
                            ChatMessage(role="system", content=system_instruction),
                            ChatMessage(role="user", content=f"Text passage:\n{chunk}")
                        ]

                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            loop = None

                        if loop and loop.is_running():
                            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                                future = executor.submit(
                                    lambda: asyncio.run(self.llm_provider.generate(messages, model_profile="flash"))
                                )
                                summary_text = future.result()
                        else:
                            summary_text = asyncio.run(self.llm_provider.generate(messages, model_profile="flash"))
                    except Exception as e:
                        logger.error(f"Agentic LLM prompt execution failed: {e}")

                if summary_text and summary_text.strip():
                    summary_clean = summary_text.strip()
                    summary_prefix = f"[AI Shrnutí: {summary_clean}]\n\n"
                    final_splits.append(summary_prefix + chunk)
                else:
                    words = chunk.split()[:8]
                    fallback_words = " ".join(words) + "..."
                    if custom_prompt:
                        summary_prefix = f"[AI Shrnutí ({custom_prompt}): {fallback_words}]\n\n"
                    else:
                        summary_prefix = f"[AI Shrnutí: {fallback_words}]\n\n"
                    final_splits.append(summary_prefix + chunk)
            return final_splits

        return splits

    def _split_character_only(self, text: str) -> List[str]:
        """Split text strictly by character count with overlap, ignoring paragraph/newline hierarchy."""
        chunks = []
        start = 0
        if self.chunk_size <= 0:
            return [text]
        step = self.chunk_size - self.chunk_overlap
        if step <= 0:
            step = 1
        while start < len(text):
            end = start + self.chunk_size
            chunk_str = text[start:end]
            if chunk_str.strip():
                chunks.append(chunk_str)
            if end >= len(text):
                break
            start += step
        return chunks

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Split text recursively."""
        final_chunks = []
        
        # Get first separator
        separator = separators[0]
        next_separators = separators[1:]
        
        # Split by separator
        if separator == "":
            splits = list(text)
        else:
            splits = text.split(separator)
            
        # Recombine splits
        current_chunk = []
        current_len = 0
        
        for split in splits:
            # If the single split is larger than chunk_size, split it recursively with remaining separators
            if len(split) > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunk_str = separator.join(current_chunk)
                    if chunk_str.strip():
                        final_chunks.append(chunk_str)
                    current_chunk = []
                    current_len = 0
                    
                if next_separators:
                    recursed = self._split_text(split, next_separators)
                    final_chunks.extend(recursed)
                else:
                    # No separators left, force-split by characters
                    start = 0
                    while start < len(split):
                        chunk_str = split[start:start + self.chunk_size]
                        if chunk_str.strip():
                            final_chunks.append(chunk_str)
                        if start + self.chunk_size >= len(split):
                            break
                        start += self.chunk_size - self.chunk_overlap
            else:
                # If adding this split exceeds chunk_size, flush and start a new chunk
                split_len = len(split) + (len(separator) if current_chunk else 0)
                if current_len + split_len > self.chunk_size:
                    chunk_str = separator.join(current_chunk)
                    if chunk_str.strip():
                        final_chunks.append(chunk_str)
                    
                    # Backtrack for overlap
                    overlap_splits = []
                    overlap_len = 0
                    for prev_split in reversed(current_chunk):
                        prev_len = len(prev_split) + (len(separator) if overlap_splits else 0)
                        if overlap_len + prev_len <= self.chunk_overlap:
                            overlap_splits.insert(0, prev_split)
                            overlap_len += prev_len
                        else:
                            break
                            
                    current_chunk = overlap_splits
                    current_len = overlap_len
                    
                current_chunk.append(split)
                current_len += len(split) + (len(separator) if len(current_chunk) > 1 else 0)
                
        if current_chunk:
            chunk_str = separator.join(current_chunk)
            if chunk_str.strip():
                if final_chunks:
                    prev = final_chunks[-1]
                    if prev.endswith(chunk_str) or chunk_str in prev:
                        pass # Pure overlap - skip!
                    else:
                        final_chunks.append(chunk_str)
                else:
                    final_chunks.append(chunk_str)
            
        return final_chunks

    def _run_split_strategy(self, text: str) -> List[str]:
        if self.chunking_strategy == "semantic":
            return self._split_semantic(text)
        elif self.chunking_strategy == "structure":
            preserve_tables = self.structure_params.get("preserve_tables", True)
            preserve_lists = self.structure_params.get("preserve_lists", True)
            max_size = self.structure_params.get("max_size", 4000)
            return self._split_structural(text, preserve_tables, preserve_lists, max_size)
        elif self.chunking_strategy == "token":
            size = self.token_params.get("size_tokens", 512)
            overlap = self.token_params.get("overlap_tokens", 64)
            tokenizer_type = self.token_params.get("tokenizer_type", "cl100k_base")
            return self._split_by_tokens(text, size, overlap, tokenizer_type)
        elif self.chunking_strategy == "agentic":
            return self._split_agentic(text)
        else:
            if self.chunk_splitter_type == "character":
                return self._split_character_only(text)
            else:
                return self._split_text(text, self.separators)

    def split_pages(self, pages: List[ExtractedPage]) -> List[DocumentChunk]:
        """Process page-by-page text blocks and return recursive overlapping chunks with section titles.

        Maintains accurate page numbering references and extracts section titles.
        """
        import re
        # Czech-friendly decimal numbering section header regex
        SECTION_REGEX = re.compile(r'^\s*(\d+(?:\.\d+)*\.?\s+[^\W\d_].*?)\s*$', re.MULTILINE)

        chunks = []
        chunk_counter = 0

        if self.chunk_cross_page:
            # CROSS-PAGE CHUNKING STRATEGY
            concat_text = ""
            page_boundaries = []  # List of tuples: (start_idx, end_idx, page_number, headers)
            for page in pages:
                start = len(concat_text)
                concat_text += page.text + "\n"
                end = len(concat_text)
                
                headers = []
                for match in SECTION_REGEX.finditer(page.text):
                    global_header_start = start + match.start()
                    headers.append((global_header_start, match.group(1).strip()))
                
                page_boundaries.append((start, end, page.page_number, headers))

            splits = self._run_split_strategy(concat_text)

            current_offset = 0
            active_section = None
            
            for content in splits:
                content_stripped = content.strip()
                if not content_stripped:
                    continue

                start_idx = concat_text.find(content_stripped, current_offset)
                if start_idx == -1:
                    start_idx = current_offset
                else:
                    current_offset = start_idx + len(content_stripped)

                chunk_page = 1
                chunk_headers = []
                for p_start, p_end, p_num, p_headers in page_boundaries:
                    if p_start <= start_idx < p_end:
                        chunk_page = p_num
                    chunk_headers.extend(p_headers)

                chunk_headers.sort(key=lambda x: x[0])
                
                chunk_section = active_section
                for h_start, h_title in chunk_headers:
                    if h_start <= start_idx:
                        chunk_section = h_title
                    else:
                        break

                if chunk_section != active_section:
                    active_section = chunk_section

                chunks.append(
                    DocumentChunk(
                        index=chunk_counter,
                        content=content_stripped,
                        page_number=chunk_page,
                        section_title=chunk_section,
                    )
                )
                chunk_counter += 1
        else:
            # PAGE-ISOLATED CHUNKING STRATEGY (default)
            active_section = None
            prev_page_overlap = ""
            for page in pages:
                text = page.text
                if not text.strip():
                    continue

                if self.overlap_cross_page and prev_page_overlap:
                    text_to_split = prev_page_overlap + "\n" + text
                else:
                    text_to_split = text

                headers = []
                for match in SECTION_REGEX.finditer(text):
                    headers.append((match.start(), match.group(1).strip()))

                page_splits = self._run_split_strategy(text_to_split)

                if self.overlap_cross_page and page_splits:
                    last_split = page_splits[-1]
                    if len(last_split) > self.chunk_overlap:
                        prev_page_overlap = last_split[-self.chunk_overlap:]
                    else:
                        prev_page_overlap = last_split
                else:
                    prev_page_overlap = ""

                current_offset = 0
                for content in page_splits:
                    content_stripped = content.strip()
                    if not content_stripped:
                        continue

                    start_idx = text.find(content_stripped, current_offset)
                    if start_idx == -1:
                        start_idx = current_offset
                    else:
                        current_offset = start_idx + len(content_stripped)

                    chunk_section = active_section
                    for h_start, h_title in headers:
                        if h_start <= start_idx:
                            chunk_section = h_title
                        else:
                            break

                    if chunk_section != active_section:
                        active_section = chunk_section

                    chunks.append(
                        DocumentChunk(
                            index=chunk_counter,
                            content=content_stripped,
                            page_number=page.page_number,
                            section_title=chunk_section,
                        )
                    )
                    chunk_counter += 1

        logger.info(f"Split {len(pages)} pages using strategy ({self.chunking_strategy}) into {len(chunks)} chunks.")
        return chunks

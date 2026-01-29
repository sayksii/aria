"""
TranslationStateManager - Overwrite-Draft Translation with Sliding Window

Simplified logic:
1. Committed sources are stable - we track the source sentences.
2. Committed translation is the translation of all committed sources (one string).
3. Draft is everything after committed - fully re-translated on every update.
4. When draft accumulates enough SOURCE sentences, promote them to committed.
"""

import re
from difflib import SequenceMatcher
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass, field

# Import logger - use try/except for standalone testing
try:
    from ..logger import debug, info, warning
except ImportError:
    # Fallback for testing without full package
    def debug(msg): print(f"[DEBUG] {msg}")
    def info(msg): print(f"[INFO] {msg}")
    def warning(msg): print(f"[WARN] {msg}")


@dataclass
class TranslationState:
    """Represents the current translation state."""
    committed_text: str = ""  # White text (stable, translated)
    draft_text: str = ""      # Green text (in progress, translated)


class TranslationStateManager:
    """
    Manages translation with overwrite-draft mechanism.
    
    Core Logic:
    1. Maintain committed sources (list of sentences that are stable).
    2. Maintain committed translation (single string for all committed).
    3. On each update:
       a. Find where committed content ends in new input (prefix matching).
       b. Everything after = draft portion.
       c. Translate the ENTIRE draft portion (overwrite, not append).
    4. When draft has enough source sentences, promote them to committed.
    """
    
    # Sentence delimiters for segmentation
    # Added commas (，,) and Japanese comma (、)
    SENTENCE_DELIMITERS = r'[.。？！?!\n，,、]'
    MAX_SENTENCE_LENGTH = 80  # Force split if sentence exceeds this
    
    # Buffer thresholds
    DRAFT_COMMIT_THRESHOLD = 6   # Restored to 6 as requested
    COMMIT_COUNT = 4             # Restored to 4: Commit 4 sentences at a time
    DRAFT_CHAR_THRESHOLD = 150   # Force commit if draft exceeds this many chars
    
    # Fuzzy matching threshold
    FUZZY_THRESHOLD = 0.65  # 65% similarity = match (Lowered for stability)
    
    # Max draft size (sentences) to prevent huge translation requests
    MAX_DRAFT_SENTENCES = 5
    
    def __init__(
        self,
        translator: Optional[Callable[[str], str]] = None,
    ):
        """
        Initialize the manager.
        
        Args:
            translator: Function to translate text (source -> target)
        """
        self.translator = translator
        
        # Committed state
        self._committed_sources: List[str] = []    # Source sentences that are locked
        self._committed_paragraphs: List[str] = [] # Translation paragraphs (each commit batch = 1 paragraph)
        
        # Draft state (volatile, overwritten each update)
        self._draft_sources: List[str] = []        # Source sentences pending
        self._draft_translation: str = ""          # Translation of draft sources
        self._last_processed_text: str = ""        # Cache for duplicate detection
    
    def process_text(self, full_source_text: str) -> TranslationState:
        """
        Process incoming source text and return translation state.
        
        Args:
            full_source_text: The complete source text from LiveCaptions
            
        Returns:
            TranslationState with committed (white) and draft (green) text
        """
        # Duplicate check: If text hasn't changed, don't re-process
        if full_source_text == self._last_processed_text:
            return self._build_state()
            
        self._last_processed_text = full_source_text
        
        if not full_source_text or not full_source_text.strip():
            return self._build_state()
        
        # Segment into sentences
        source_sentences = self._segment_sentences(full_source_text)
        
        if not source_sentences:
            return self._build_state()
        
        # Safeguard: If starting fresh with huge history, only take last 6 sentences
        # This prevents overwhelming the translator on initial startup
        if not self._committed_sources and len(source_sentences) > self.DRAFT_COMMIT_THRESHOLD:
            source_sentences = source_sentences[-self.DRAFT_COMMIT_THRESHOLD:]
        
        # Find where committed content ends
        committed_end_index = self._find_committed_end(source_sentences)
        
        # Everything after committed = draft portion
        draft_sources = source_sentences[committed_end_index:]
        
        # FIX: Check if draft is too large (lost sync or huge update)
        # If so, force-commit the excess without translation to catch up
        if len(draft_sources) > self.MAX_DRAFT_SENTENCES:
            skipped_count = len(draft_sources) - self.MAX_DRAFT_SENTENCES
            skipped_part = draft_sources[:skipped_count]
            draft_sources = draft_sources[skipped_count:]
            
            # Add skipped part to committed sources so we match them next time
            # But DO NOT add to committed_paragraphs (hiding them from UI)
            self._committed_sources.extend(skipped_part)
            warning(f"TSM: Draft too large ({skipped_count+len(draft_sources)}), skipped {skipped_count} sentences.")
            
        self._draft_sources = draft_sources
        
        if not draft_sources:
            # No new content, just return current state
            self._draft_translation = ""
            return self._build_state()
        
        # OVERWRITE draft: translate entire draft portion
        if self.translator:
            try:
                draft_text = " ".join(draft_sources)
                translated = self.translator(draft_text)
                self._draft_translation = translated or ""
            except Exception as e:
                warning(f"TSM: Translation error: {e}")
                self._draft_translation = ""
        
        # Check if we should commit some draft
        self._check_commit_threshold()
        
        return self._build_state()
    
    def _segment_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        if not text:
            return []
        
        # Split by sentence delimiters
        parts = re.split(self.SENTENCE_DELIMITERS, text)
        
        sentences = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # If part is too long, split by length
            if len(part) > self.MAX_SENTENCE_LENGTH:
                for i in range(0, len(part), self.MAX_SENTENCE_LENGTH):
                    chunk = part[i:i + self.MAX_SENTENCE_LENGTH].strip()
                    if chunk:
                        sentences.append(chunk)
            else:
                sentences.append(part)
        
        return sentences
    
    def _find_committed_end(self, source_sentences: List[str]) -> int:
        """
        Find where committed content ends in the source sentences.
        
        Returns the index after the last matched committed sentence.
        """
        if not self._committed_sources:
            return 0  # No committed content, everything is draft
        
        # Try to match committed sources in order
        matched_count = 0
        for i, committed_src in enumerate(self._committed_sources):
            if matched_count >= len(source_sentences):
                # Source is shorter than committed - this shouldn't happen
                self._committed_sources = self._committed_sources[:matched_count]
                self._retranslate_committed()
                break
            
            # Fuzzy match
            similarity = self._similarity(committed_src, source_sentences[matched_count])
            if similarity >= self.FUZZY_THRESHOLD:
                matched_count += 1
            else:
                # Mismatch at this position - committed content has diverged
                # Trim committed to only keep matched ones
                self._committed_sources = self._committed_sources[:i]
                self._retranslate_committed()
                break
        
        return matched_count
    
    def _retranslate_committed(self) -> None:
        """Re-translate all committed sources after trimming (rebuild paragraphs)."""
        if not self._committed_sources or not self.translator:
            self._committed_paragraphs.clear()
            return
        
        # When committed is trimmed, we need to rebuild as a single paragraph
        # (We lose the paragraph structure, but this is a rare edge case)
        try:
            text = " ".join(self._committed_sources)
            translated = self.translator(text) or ""
            self._committed_paragraphs = [translated] if translated else []
        except Exception as e:
            warning(f"TSM: Re-translation error: {e}")
    
    def _similarity(self, a: str, b: str) -> float:
        """Calculate similarity ratio between two strings."""
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def _check_commit_threshold(self) -> None:
        """Check if draft should be partially committed."""
        total_draft_sources = len(self._draft_sources)
        draft_char_length = sum(len(s) for s in self._draft_sources)
        
        # Trigger if:
        # 1. Enough sentences accumulated (standard case)
        # 2. OR draft is getting too long (run-on sentence protection)
        should_commit = (
            total_draft_sources >= self.DRAFT_COMMIT_THRESHOLD or 
            draft_char_length >= self.DRAFT_CHAR_THRESHOLD
        )
        
        if should_commit:
            # Determine how many to commit
            # If triggered by length but count is low, commit fewer but at least 1
            commit_target = self.COMMIT_COUNT
            if total_draft_sources < self.COMMIT_COUNT:
                commit_target = max(1, total_draft_sources - 1)  # Leave 1 if possible
            
            to_commit = self._draft_sources[:commit_target]
            
            # Add to committed sources
            self._committed_sources.extend(to_commit)
            
            # Translate the newly committed batch and add as a NEW PARAGRAPH
            if self.translator:
                try:
                    batch_text = " ".join(to_commit)
                    batch_translation = self.translator(batch_text) or ""
                    if batch_translation:
                        self._committed_paragraphs.append(batch_translation)
                except Exception as e:
                    warning(f"TSM: Commit translation error: {e}")
            
            # Remove from draft
            self._draft_sources = self._draft_sources[self.COMMIT_COUNT:]
            
            # Re-translate remaining draft
            if self._draft_sources and self.translator:
                try:
                    draft_text = " ".join(self._draft_sources)
                    self._draft_translation = self.translator(draft_text) or ""
                except Exception as e:
                    warning(f"TSM: Draft re-translation error: {e}")
            else:
                self._draft_translation = ""
    
    def _build_state(self) -> TranslationState:
        """Build the current translation state for display."""
        # Join paragraphs with single newline for tighter visual separation
        committed_text = "\n".join(self._committed_paragraphs)
        return TranslationState(
            committed_text=committed_text,
            draft_text=self._draft_translation
        )
    
    def reset(self) -> None:
        """Reset all state."""
        self._committed_sources.clear()
        self._committed_paragraphs.clear()
        self._draft_sources.clear()
        self._draft_translation = ""
        self._last_processed_text = ""
    
    def get_debug_info(self) -> dict:
        """Get debug information about current state."""
        return {
            "committed_sources": self._committed_sources.copy(),
            "committed_paragraphs": self._committed_paragraphs.copy(),
            "draft_sources": self._draft_sources.copy(),
            "draft_translation": self._draft_translation,
        }

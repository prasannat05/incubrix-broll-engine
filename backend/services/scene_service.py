import re
from collections import Counter
from dataclasses import dataclass
from backend.config import settings
from backend.services.audio_service import TranscriptSegment

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had",
    "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "Let",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on",
    "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over",
    "own", "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with", "would",
    "you", "your", "yours", "yourself", "yourselves", "also", "like", "make", "many",
    "into", "using", "every", "within", "across",
}

FALLBACK_VISUAL_NOUNS = ["nature", "technology", "city", "business", "ocean"]


@dataclass
class DetectedScene:
    scene_id: int
    start_time: float
    end_time: float
    text: str
    keywords: list[str]


class SceneService:
    """Splits scripts and timed transcripts into coherent scenes and extracts visual B-roll keywords."""

    def __init__(self, pause_threshold: float = settings.pause_threshold_seconds):
        self.pause_threshold = pause_threshold

    @staticmethod
    def split_script_into_units(script_text: str) -> list[str]:
        """
        Split plain script text into scene units by paragraph first,
        then by sentence boundaries for long paragraphs.
        """
        cleaned = script_text.strip()
        if not cleaned:
            return []

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", cleaned) if p.strip()]
        units: list[str] = []

        for para in paragraphs:
            sentences = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+|\n+", para)
                if s.strip()
            ]
            for sentence in sentences:
                if len(sentence.split()) > 28:
                    clauses = [
                        c.strip()
                        for c in re.split(r"(?<=[,;—:])\s+", sentence)
                        if c.strip()
                    ]
                    units.extend(clauses if len(clauses) > 1 else [sentence])
                else:
                    units.append(sentence)

        return units

    def detect_scenes_from_segments(
        self, segments: list[TranscriptSegment], max_scene_duration: float = 10.0
    ) -> list[DetectedScene]:
        """
        Group Whisper transcript segments into scenes based on:
        1. Pause duration between segments (>= pause_threshold)
        2. Sentence boundary punctuation (. ! ?)
        3. Maximum scene duration cap
        """
        if not segments:
            return []

        scenes: list[DetectedScene] = []
        current_texts: list[str] = [segments[0].text]
        scene_start = segments[0].start
        scene_end = segments[0].end

        for seg in segments[1:]:
            pause_gap = seg.start - scene_end
            combined_duration = seg.end - scene_start
            prev_ended_sentence = bool(re.search(r"[.!?][\"']?$", current_texts[-1].strip()))

            should_split = (
                pause_gap >= self.pause_threshold
                or combined_duration > max_scene_duration
                or (prev_ended_sentence and (scene_end - scene_start) >= 2.5)
            )

            if should_split:
                joined_text = " ".join(current_texts).strip()
                scene_id = len(scenes) + 1
                scenes.append(
                    DetectedScene(
                        scene_id=scene_id,
                        start_time=round(scene_start, 2),
                        end_time=round(scene_end, 2),
                        text=joined_text,
                        keywords=self.extract_keywords(joined_text, scene_id=scene_id),
                    )
                )
                current_texts = [seg.text]
                scene_start = seg.start
                scene_end = seg.end
            else:
                current_texts.append(seg.text)
                scene_end = seg.end

        if current_texts:
            joined_text = " ".join(current_texts).strip()
            scene_id = len(scenes) + 1
            scenes.append(
                DetectedScene(
                    scene_id=scene_id,
                    start_time=round(scene_start, 2),
                    end_time=round(max(scene_end, scene_start + 0.5), 2),
                    text=joined_text,
                    keywords=self.extract_keywords(joined_text, scene_id=scene_id),
                )
            )

        return scenes

    @staticmethod
    def extract_keywords(text: str, scene_id: int = 1, top_k: int = 4) -> list[str]:
        """
        Extract ranked search keywords from scene text using tokenization,
        stopword removal, length weighting, and visual fallback terms.
        """
        words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
        filtered = [w.strip("-") for w in words if w.strip("-") not in STOPWORDS and len(w.strip("-")) >= 3]

        if not filtered:
            fallback = FALLBACK_VISUAL_NOUNS[(scene_id - 1) % len(FALLBACK_VISUAL_NOUNS)]
            return [fallback, "cinematic", "background"]

        counts = Counter(filtered)
        scored = sorted(
            counts.keys(),
            key=lambda w: (counts[w] * 2.0 + min(len(w), 10) * 0.25, -filtered.index(w)),
            reverse=True,
        )

        selected = scored[:top_k]
        if len(selected) == 1:
            selected.append(FALLBACK_VISUAL_NOUNS[(scene_id - 1) % len(FALLBACK_VISUAL_NOUNS)])

        return selected

from typing import List, Dict
import textwrap
import heapq
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from string import punctuation

# Ensure required NLTK data is downloaded
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)


def summarize_text_local(text: str, sentence_count: int = 3) -> str:
    """
    Summarize text locally using NLTK frequency-based scoring.
    Keeps the most informative sentences while staying lightweight.
    """
    try:
        if not text.strip():
            return "[Empty text]"

        sentences = sent_tokenize(text)
        if len(sentences) <= sentence_count:
            return text  # No need to summarize short text

        stop_words = set(stopwords.words("english") + list(punctuation))
        words = word_tokenize(text.lower())

        # Build frequency table
        freq_table = {}
        for word in words:
            if word.isalpha() and word not in stop_words:
                freq_table[word] = freq_table.get(word, 0) + 1

        # Normalize frequencies
        max_freq = max(freq_table.values()) if freq_table else 1
        for word in freq_table:
            freq_table[word] /= max_freq

        # Score each sentence
        sentence_scores = {}
        for sent in sentences:
            for word in word_tokenize(sent.lower()):
                if word in freq_table:
                    sentence_scores[sent] = sentence_scores.get(sent, 0) + freq_table[word]

        # Select top N sentences
        summary_sentences = heapq.nlargest(sentence_count, sentence_scores, key=sentence_scores.get)
        summary = " ".join(summary_sentences)

        return summary if summary else textwrap.shorten(text, width=400, placeholder="...")

    except Exception as e:
        return f"[NLTK Summary Error] {str(e)}"


class ConversationMemory:
    def __init__(self, job_desc: str, resume: str, summarize_every=3):
        self.summary = "The conversation has just begun."
        self.recent_messages: List[Dict[str, str]] = []

        # 🔹 Summarize job description and resume using NLTK
        self.job_summary = summarize_text_local(job_desc, sentence_count=4)
        self.resume_summary = summarize_text_local(resume, sentence_count=4)

        self.turn_count = 0
        self.summarize_every = summarize_every

    async def add_message(self, role: str, content: str):
        """Add a message to recent conversation history."""
        self.recent_messages.append({"role": role, "content": content})
        self.turn_count += 1
        
        # Prevent memory overflow — keep the last 12 messages
        if len(self.recent_messages) > 12:
            self.recent_messages.pop(0)

    async def summarize(self):
        """Summarize the recent conversation using NLTK."""
        if not self.recent_messages:
            return

        text_to_summarize = (
            f"Previous summary:\n{self.summary}\n\n"
            f"Recent conversation:\n{self.format_messages_for_summary()}"
        )

        new_summary = summarize_text_local(text_to_summarize, sentence_count=4)
        self.summary = new_summary

        # ⚠️ Do NOT clear messages — we keep them for AI context

    def format_messages_for_summary(self) -> str:
        """Format conversation history for summarization."""
        return "\n".join(
            f"{msg['role'].upper()}: {msg['content']}" 
            for msg in self.recent_messages
        )

    def get_context(self, system_prompt: str) -> str:
        """Prepare the structured context passed to the AI model."""
        context = textwrap.dedent(f"""
        ===== SYSTEM INSTRUCTIONS =====
        {system_prompt}

        ===== JOB DESCRIPTION SUMMARY =====
        {self.job_summary}

        ===== CANDIDATE RESUME SUMMARY =====
        {self.resume_summary}

        ===== CONVERSATION SUMMARY =====
        {self.summary}
        """)

        # Include recent conversation history
        if self.recent_messages:
            context += "\n===== RECENT CONVERSATION HISTORY =====\n"
            for msg in self.recent_messages[-8:]:
                role = "Interviewer" if msg['role'].lower() == 'ai' else "Candidate"
                context += f"{role}: {msg['content'].strip()}\n"

        context += "\n===== YOUR NEXT RESPONSE ====="
        return context.strip()

    def debug_context(self, system_prompt: str) -> str:
        """Print the full AI context for debugging."""
        context = self.get_context(system_prompt)
        print("=== DEBUG CONTEXT SENT TO AI ===")
        print(context)
        print(f"Recent messages count: {len(self.recent_messages)}")
        print(f"Total turns: {self.turn_count}")
        print("=== END DEBUG ===")
        return context

    def get_conversation_stats(self) -> Dict:
        """Return conversation statistics."""
        return {
            "total_messages": len(self.recent_messages),
            "turn_count": self.turn_count,
            "recent_messages": [
                f"{msg['role']}: {msg['content'][:50]}..." 
                for msg in self.recent_messages[-3:]
            ],
            "summary_length": len(self.summary)
        }

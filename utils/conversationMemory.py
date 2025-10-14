from typing import List, Dict
import textwrap
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer


def summarize_text_local(text: str, sentence_count: int = 3) -> str:
    """Summarize long text locally using LexRank."""
    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LexRankSummarizer()
        summary_sentences = summarizer(parser.document, sentence_count)
        summary = " ".join(str(sentence) for sentence in summary_sentences)
        # Fallback if summarizer returns nothing
        return summary if summary else textwrap.shorten(text, width=400, placeholder="...")
    except Exception as e:
        return f"[Local Summary Error] {str(e)}"


class ConversationMemory:
    def __init__(self, job_desc: str, resume: str, summarize_every=3):
        self.summary = "The conversation has just begun."
        self.recent_messages: List[Dict[str, str]] = []

        # 🔹 Summarize job description and resume instead of truncating
        self.job_summary = summarize_text_local(job_desc, sentence_count=4)
        self.resume_summary = summarize_text_local(resume, sentence_count=4)

        self.turn_count = 0
        self.summarize_every = summarize_every

    async def add_message(self, role: str, content: str):
        self.recent_messages.append({"role": role, "content": content})
        # Limit stored messages to prevent memory overflow
        if len(self.recent_messages) > self.summarize_every * 2:
            self.recent_messages.pop(0)

    async def summarize(self):
        """Summarize recent conversation locally using Sumy."""
        if not self.recent_messages:
            return
        text_to_summarize = (
            f"Previous summary:\n{self.summary}\n\n"
            f"Recent conversation:\n{self.recent_messages}"
        )
        new_summary = summarize_text_local(text_to_summarize, sentence_count=4)
        self.summary = new_summary
        self.recent_messages = []

    
    def get_context(self, system_prompt: str) -> str:
        """Builds a structured and well-formatted context for the AI model."""
        context = textwrap.dedent(f"""
        ===== SYSTEM INSTRUCTIONS =====
        {system_prompt}

        ===== JOB DESCRIPTION SUMMARY =====
        {self.job_summary}

        ===== CANDIDATE RESUME SUMMARY =====
        {self.resume_summary}

        ===== CONVERSATION SUMMARY =====
        {self.summary}

        ===== RECENT CONVERSATION =====
        """)

        # Include only the most recent few messages to maintain context clarity
        for msg in self.recent_messages[-6:]:
            role = msg['role'].capitalize()
            context += f"{role}: {msg['content'].strip()}\n"

        context += "\n===== END OF CONTEXT ====="
        return context.strip()


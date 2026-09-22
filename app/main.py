"""CLI entry point: ask a question about the ingested filings and transcripts."""

import sys

from app.generation.generator import answer_question

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m app.main "<question>"')

    answer = answer_question(sys.argv[1])

    print(answer.answer)
    if answer.citations:
        print()
        print("Sources:")
        for citation in answer.citations:
            print(f"  {citation.company} {citation.document_type} {citation.date} - {citation.section}")

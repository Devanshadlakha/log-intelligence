"""
summarizer.py
─────────────
Uses GPT to generate a concise root cause analysis from a set of log entries.

Input:  list of log entries (with messages, levels, services, timestamps)
Output: plain English summary like:
  "The payment-service experienced repeated database connection timeouts
   starting at 14:32 UTC, likely caused by connection pool exhaustion.
   5 errors were recorded over 3 minutes, all originating from host-2."
"""

import os
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)


def _llm_call_with_retry(messages: list, max_tokens: int = 300, retries: int = 2) -> str | None:
    """
    Makes an LLM API call with retry on transient failures.

    Why retry? LLM APIs (Groq, OpenAI) occasionally return 429 (rate limit)
    or 503 (service unavailable). A single retry after 2s often succeeds.

    Args:
        messages:   list of message dicts for the chat API
        max_tokens: max response length
        retries:    number of retry attempts (default 2 = 3 total attempts)

    Returns:
        The response text, or None if all attempts fail.
    """
    for attempt in range(1, retries + 2):  # retries + 1 = total attempts
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.3,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"[summarizer] LLM error (attempt {attempt}/{retries + 1}): {e}")
            if attempt <= retries:
                time.sleep(2)

    return None  # all attempts failed


def generate_summary(logs: list[dict]) -> str:
    """
    Generates a root cause analysis summary from a list of log entries.

    Args:
        logs: list of log dicts with keys: message, level, service, timestamp, host

    Returns:
        A plain English summary string (2-4 sentences)
    """
    if not logs:
        return "No logs found for the given filters."

    # Prefer ERROR/WARN logs, but use all logs if no errors exist
    relevant_logs = [l for l in logs if l.get("level") in ["ERROR", "WARN"]]
    if relevant_logs:
        recent_logs = relevant_logs[:30]
    else:
        recent_logs = logs[:30]

    log_text = format_logs_for_prompt(recent_logs)

    total = len(logs)
    error_count = sum(1 for l in logs if l.get("level") == "ERROR")
    warn_count = sum(1 for l in logs if l.get("level") == "WARN")
    info_count = sum(1 for l in logs if l.get("level") == "INFO")
    services = list(set(l.get("service", "unknown") for l in logs))

    system_prompt = """
You are a senior DevOps engineer analyzing application logs.
Your job is to provide a concise, accurate analysis.

Guidelines:
- Be specific: mention service names, event types, timestamps
- Be concise: 3-5 sentences maximum
- Identify patterns: repeated events, timing, correlations
- If there are errors: identify root cause and impact
- If system is healthy (only INFO logs): summarize what's happening and confirm health status
- Use technical but clear language
- Do NOT use bullet points — write in paragraph form
"""

    user_prompt = f"""
Analyze these application logs and provide a summary:

Stats: {total} total logs — {error_count} errors, {warn_count} warnings, {info_count} info
Services: {', '.join(services)}

{log_text}

Provide a 3-5 sentence analysis.
If errors exist: mention which service(s) are affected, what type of errors, likely cause, and impact.
If no errors: summarize system activity and confirm operational status.
"""

    result = _llm_call_with_retry(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=300
    )

    if result:
        return result

    # Fallback: return a basic stats-based summary when LLM is unavailable
    return (
        f"Summary unavailable (AI service temporarily unreachable). "
        f"Showing raw logs: {total} total — {error_count} errors, "
        f"{warn_count} warnings, {info_count} info across "
        f"{', '.join(services)}."
    )


def answer_question(logs: list[dict], question: str) -> str:
    """
    Answers a general question about the logs using GPT.

    Args:
        logs: list of log dicts
        question: the user's natural language question

    Returns:
        A plain English answer string
    """
    if not logs:
        return "No logs available to answer your question. Try adjusting the time range."

    # Use up to 50 logs for context
    sample_logs = logs[:50]
    log_text = format_logs_for_prompt(sample_logs)

    # Build stats summary
    total = len(logs)
    error_count = sum(1 for l in logs if l.get("level") == "ERROR")
    warn_count = sum(1 for l in logs if l.get("level") == "WARN")
    info_count = sum(1 for l in logs if l.get("level") == "INFO")
    services = list(set(l.get("service", "unknown") for l in logs))

    system_prompt = """
You are a senior DevOps engineer and log analysis expert.
Answer the user's question based on the provided log data.

Guidelines:
- Be specific and data-driven — reference actual log entries, counts, services, and timestamps
- If the question asks about health, consider error rates and patterns
- If the question asks "why" or "what caused", analyze the error messages for root causes
- If the question asks about counts or stats, give exact numbers from the data
- Be concise but thorough — 3-6 sentences
- Use technical but clear language
"""

    user_prompt = f"""
Question: {question}

Log Statistics:
- Total logs: {total}
- Errors: {error_count}, Warnings: {warn_count}, Info: {info_count}
- Services: {', '.join(services)}

Sample Logs (most recent {len(sample_logs)} of {total}):
{log_text}

Answer the question based on the log data above.
"""

    result = _llm_call_with_retry(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=500
    )

    if result:
        return result

    return (
        f"Unable to answer — AI service temporarily unreachable. "
        f"Showing raw logs instead: {total} total ({error_count} errors, "
        f"{warn_count} warnings) across {', '.join(services)}."
    )


def generate_report(logs: list[dict], source: str = None) -> str:
    """
    Generates a comprehensive summary report for a set of logs.

    Args:
        logs: list of log dicts
        source: optional source category name for context

    Returns:
        A detailed report string
    """
    if not logs:
        return "No logs available to generate a report. Try adjusting the time range."

    sample_logs = logs[:50]
    log_text = format_logs_for_prompt(sample_logs)

    total = len(logs)
    error_count = sum(1 for l in logs if l.get("level") == "ERROR")
    warn_count = sum(1 for l in logs if l.get("level") == "WARN")
    info_count = sum(1 for l in logs if l.get("level") == "INFO")
    services = list(set(l.get("service", "unknown") for l in logs))

    source_label = f" for {source}" if source else ""

    system_prompt = """
You are a senior DevOps engineer generating a log analysis report.
Create a structured, comprehensive summary report.

Report format:
1. OVERVIEW — one sentence summary of system state (healthy/degraded/critical)
2. KEY METRICS — total logs, error rate, warning rate, active services
3. NOTABLE ISSUES — top errors or warnings with details (service, message pattern, frequency)
4. PATTERNS — any recurring issues, timing patterns, or correlations
5. RECOMMENDATIONS — actionable steps based on findings

Guidelines:
- Be data-driven and specific
- Mention actual service names, error messages, and timestamps
- If system is healthy, say so and highlight what's working
- Keep each section to 2-3 sentences max
"""

    user_prompt = f"""
Generate a summary report{source_label}.

Log Statistics:
- Total logs: {total}
- Errors: {error_count}, Warnings: {warn_count}, Info: {info_count}
- Services: {', '.join(services)}

Sample Logs (most recent {len(sample_logs)} of {total}):
{log_text}

Generate the report now.
"""

    result = _llm_call_with_retry(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=700
    )

    if result:
        return result

    return (
        f"Report unavailable — AI service temporarily unreachable. "
        f"Raw stats: {total} logs ({error_count} errors, {warn_count} warnings) "
        f"across {', '.join(services)}."
    )


def format_logs_for_prompt(logs: list[dict]) -> str:
    """Formats log entries as a compact string for the GPT prompt."""
    lines = []
    for log in logs:
        timestamp = str(log.get("timestamp", ""))[:19]  # trim to seconds
        level = log.get("level", "")
        service = log.get("service", "")
        message = log.get("message", "")
        lines.append(f"[{timestamp}] {level} {service}: {message}")

    return "\n".join(lines)


def get_affected_services(logs: list[dict]) -> str:
    """Returns a comma-separated list of unique affected services."""
    services = list(set(log.get("service", "unknown") for log in logs))
    return ", ".join(services)
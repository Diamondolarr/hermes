from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re
from typing import List
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings


USER_AGENT = "AI-SDR-Research/1.0"
MAX_HTML_LENGTH = 500_000
MAX_VISIBLE_TEXT_LENGTH = 20_000


class CompanyResearchServiceError(ValueError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiResearchPayload(BaseModel):
    description: str
    industry: str
    product_summary: str


@dataclass
class CompanyResearchResult:
    website: str
    description: str
    industry: str
    product_summary: str


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _trim_text(value: str, limit: int) -> str:
    cleaned = _clean_text(value)
    return cleaned[:limit]


def normalize_company_website(website: str) -> str:
    candidate = (website or "").strip()
    if not candidate:
        raise CompanyResearchServiceError(
            "Company website is required.", status_code=400
        )

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.netloc and parsed.path:
        candidate = f"https://{parsed.path}"
        parsed = urlparse(candidate)

    if not parsed.netloc:
        raise CompanyResearchServiceError("Invalid company website.", status_code=400)

    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    return f"{scheme}://{netloc}"


def websites_match(left: str, right: str) -> bool:
    try:
        return normalize_company_website(left) == normalize_company_website(right)
    except CompanyResearchServiceError:
        return _clean_text(left).lower() == _clean_text(right).lower()


class HomepageParser(HTMLParser):
    _IGNORED_TAGS = {"script", "style", "noscript", "svg"}
    _TEXT_TAGS = {"title", "h1", "h2", "h3", "p"}

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.og_description = ""
        self.headings: List[str] = []
        self.paragraphs: List[str] = []
        self._ignored_depth = 0
        self._active_tag = ""
        self._buffer: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = {key.lower(): (value or "") for key, value in attrs}
        tag = tag.lower()

        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if self._ignored_depth:
            return

        if tag == "meta":
            key = (
                attrs_dict.get("name")
                or attrs_dict.get("property")
                or attrs_dict.get("itemprop")
            ).lower()
            content = _clean_text(attrs_dict.get("content", ""))
            if key == "description" and content and not self.meta_description:
                self.meta_description = content
            if key in {"og:description", "twitter:description"} and content:
                self.og_description = content
            return

        if tag in self._TEXT_TAGS:
            self._active_tag = tag
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
            return

        if self._ignored_depth or tag != self._active_tag:
            return

        text = _clean_text(" ".join(self._buffer))
        self._active_tag = ""
        self._buffer = []
        if not text:
            return

        if tag == "title" and not self.title:
            self.title = text
        elif tag in {"h1", "h2", "h3"}:
            self.headings.append(text)
        elif tag == "p":
            self.paragraphs.append(text)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or not self._active_tag:
            return
        text = _clean_text(data)
        if text:
            self._buffer.append(text)


def _fallback_visible_text(html: str) -> str:
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.I | re.S,
    )
    html = re.sub(r"<[^>]+>", " ", html)
    return _clean_text(unescape(html))


def _fetch_homepage(url: str) -> tuple[str, str]:
    attempts = [url]
    if url.startswith("https://"):
        attempts.append(url.replace("https://", "http://", 1))

    headers = {"User-Agent": USER_AGENT}
    last_error = None
    for candidate in attempts:
        try:
            with httpx.Client(
                follow_redirects=True, headers=headers, timeout=15.0
            ) as client:
                response = client.get(candidate)
                response.raise_for_status()
                html = response.text[:MAX_HTML_LENGTH]
                return str(response.url), html
        except httpx.HTTPError as exc:
            last_error = exc

    raise CompanyResearchServiceError(
        "Unable to fetch the company website homepage.", status_code=502
    ) from last_error


def _build_research_prompt(
    company_name: str,
    company_website: str,
    parser: HomepageParser,
    visible_text: str,
) -> str:
    headings = parser.headings[:10]
    paragraphs = parser.paragraphs[:10]

    return f"""
You are a B2B company research assistant.

Analyze the company homepage content and return exactly one JSON object with these keys:
- description
- industry
- product_summary

Rules:
- Output valid JSON only.
- Do not include markdown or code fences.
- Keep description under 400 characters.
- Keep industry under 80 characters.
- Keep product_summary under 300 characters.
- Base the answer only on the supplied homepage content.
- If the company industry is unclear, use "Unknown".

Company name: {company_name}
Company website: {company_website}
Page title: {parser.title or "Unknown"}
Meta description: {parser.meta_description or "Unknown"}
Open Graph description: {parser.og_description or "Unknown"}
Headings: {" | ".join(headings) if headings else "None"}
Paragraph samples: {" | ".join(paragraphs) if paragraphs else "None"}

Homepage text:
{visible_text[:MAX_VISIBLE_TEXT_LENGTH]}
""".strip()


def _extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if not text:
        raise CompanyResearchServiceError(
            "Gemini returned an empty response.", status_code=502
        )

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        return match.group(0)
    return text


def _generate_research_payload(prompt: str) -> GeminiResearchPayload:
    if not settings.gemini_api_key:
        raise CompanyResearchServiceError(
            "GEMINI_API_KEY is not configured.", status_code=500
        )

    try:
        from google import genai
    except ImportError as exc:
        raise CompanyResearchServiceError(
            "Gemini SDK is not installed. Run `pip install -r requirements.txt`.",
            status_code=500,
        ) from exc

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"temperature": 0.2},
        )
    except Exception as exc:
        raise CompanyResearchServiceError(
            f"Gemini request failed for model `{settings.gemini_model}`: {exc}",
            status_code=502,
        ) from exc

    payload_text = _extract_json_payload(getattr(response, "text", "") or "")
    try:
        return GeminiResearchPayload.model_validate_json(payload_text)
    except ValidationError as exc:
        raise CompanyResearchServiceError(
            "Gemini returned an invalid JSON payload for company research.",
            status_code=502,
        ) from exc


def research_company(company_name: str, company_website: str) -> CompanyResearchResult:
    cleaned_name = _clean_text(company_name)
    if not cleaned_name:
        raise CompanyResearchServiceError("Company name is required.", status_code=400)

    normalized_input = normalize_company_website(company_website)
    resolved_url, html = _fetch_homepage(normalized_input)
    parser = HomepageParser()
    parser.feed(html)
    visible_text = _fallback_visible_text(html)

    prompt = _build_research_prompt(
        cleaned_name,
        normalized_input,
        parser,
        visible_text,
    )
    payload = _generate_research_payload(prompt)

    description = _trim_text(payload.description, 2000)
    product_summary = _trim_text(payload.product_summary, 1000)
    industry = _trim_text(payload.industry, 255) or "Unknown"

    if not description:
        description = (
            f"{cleaned_name} website was reachable, but Gemini did not return a usable description."
        )
    if not product_summary:
        product_summary = (
            f"{cleaned_name} offers products or services, but Gemini did not return a usable summary."
        )

    return CompanyResearchResult(
        website=normalize_company_website(resolved_url),
        description=description,
        industry=industry,
        product_summary=product_summary,
    )

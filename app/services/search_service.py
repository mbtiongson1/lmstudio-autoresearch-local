"""DuckDuckGo web search service"""
import requests


class SearchService:
    BASE_URL = "https://api.duckduckgo.com/"

    @staticmethod
    def search(query: str, max_chars: int = 400) -> str:
        """Search using DuckDuckGo instant answers API."""
        try:
            response = requests.get(
                SearchService.BASE_URL,
                params={"q": query, "format": "json", "no_html": 1},
                timeout=5
            )
            data = response.json()
            
            abstract = data.get("AbstractText", "")
            related = [t.get("Text", "") for t in data.get("RelatedTopics", [])[:3]]
            raw = abstract + " ".join(related)
            
            return raw[:max_chars] if raw.strip() else "No results found."
        except Exception as e:
            return f"Search error: {str(e)}"

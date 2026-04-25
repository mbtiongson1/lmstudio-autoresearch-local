"""Direct web fetch service with text extraction"""
import httpx
from bs4 import BeautifulSoup
import re


class SearchService:
    @staticmethod
    def search(query: str, max_chars: int = 1500) -> str:
        """Fetch content from a URL or search directly."""
        # Simple heuristic to check if it's a URL or search query
        is_url = query.startswith("http")
        url = query if is_url else f"https://duckduckgo.com/?q={query.replace(' ', '+')}"
        
        try:
            # We need a browser-like user agent
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            with httpx.Client(follow_redirects=True, timeout=10) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                
                # If we searched, we might want to get the first result link
                if not is_url:
                    # Very simple extraction of first result from DDG
                    soup = BeautifulSoup(response.text, 'html.parser')
                    results = soup.select('a[href^="http"]')
                    # Find a real link (not a DDG internal one)
                    for link in results:
                        href = link['href']
                        if "duckduckgo.com" not in href and "://" in href:
                            return SearchService.search(href, max_chars)
                    return "No results found."
                
                # If it's a URL, extract text
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script/style tags
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                text = soup.get_text(separator=' ')
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                
                return text[:max_chars] if text else "Could not extract text."
                
        except Exception as e:
            return f"Fetch/Search error: {str(e)}"

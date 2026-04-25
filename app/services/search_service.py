"""Direct web fetch service with text extraction"""
import httpx
from bs4 import BeautifulSoup
import re


class SearchService:
    @staticmethod
    def search(query: str, max_chars: int = 1500) -> str:
        """Fetch content from a URL or search directly using DDG HTML version."""
        # Use DDG's HTML-only version for easier scraping
        is_url = query.startswith("http")
        url = query if is_url else f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            with httpx.Client(follow_redirects=True, timeout=10) as client:
                response = client.post(url, data={'q': query.replace(' ', '+')}) if not is_url else client.get(url, headers=headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # If it's a search, extract first result link
                if not is_url:
                    # DDG HTML results have class 'result__url'
                    results = soup.select('a.result__url')
                    if results:
                        link = results[0]['href']
                        # Handle relative URLs or redirects
                        if link.startswith('/'):
                            link = 'https://duckduckgo.com' + link
                        # For DDG result redirects (e.g. /l/?uddg=...)
                        if 'uddg=' in link:
                            link = re.search(r'uddg=(.*?)&', link).group(1)
                            import urllib.parse
                            link = urllib.parse.unquote(link)
                        
                        return SearchService.search(link, max_chars)
                    return "No search results found."
                
                # If it's a URL, extract text
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                text = soup.get_text(separator=' ')
                text = re.sub(r'\s+', ' ', text).strip()
                
                return text[:max_chars] if text else "Could not extract text."
                
        except Exception as e:
            return f"Fetch/Search error: {str(e)}"

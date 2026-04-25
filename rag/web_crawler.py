import os
import re
import hashlib
import urllib.request
import urllib.error

class WebCrawlerPlugin:
    def __init__(self, cache_dir=".shadowlink_cache/web"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def is_url(self, path: str) -> bool:
        return path.startswith("http://") or path.startswith("https://")

    def crawl(self, url: str, force_refresh=False) -> str:
        """
        Crawls a URL, strips HTML tags, and saves the text to a local cache file.
        Returns the path to the cached text file, or empty string if failed.
        """
        url_hash = hashlib.md5(url.encode()).hexdigest()
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', url.split('://')[-1])[:50]
        filename = f"{safe_name}_{url_hash}.txt"
        cache_path = os.path.join(self.cache_dir, filename)

        if not force_refresh and os.path.exists(cache_path):
            return cache_path

        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')

            # Basic HTML stripping
            # Remove scripts and styles
            text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.IGNORECASE|re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.IGNORECASE|re.DOTALL)
            
            # Replace common block elements with newlines for readability
            text = re.sub(r'</(div|p|h[1-6]|li|tr|br|td|th|table|ul|ol)>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
            
            # Remove all other tags
            text = re.sub(r'<[^>]+>', ' ', text)
            
            # Unescape common HTML entities
            text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
            
            # Collapse multiple spaces and newlines
            lines = []
            for line in text.split('\n'):
                line = re.sub(r'\s+', ' ', line).strip()
                if line:
                    lines.append(line)
            
            clean_text = "\n".join(lines)
            
            if not clean_text:
                return ""

            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(f"Source URL: {url}\n\n{clean_text}")
                
            return cache_path
        except Exception as e:
            print(f"[WebCrawler] Failed to fetch {url}: {e}")
            return ""

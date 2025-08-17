"""
Ingestion service for extracting text from URLs
"""
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
import re
try:
    import trafilatura
    USE_TRAFILATURA = True
except ImportError:
    USE_TRAFILATURA = False
    import html2text


class IngestionService:
    """Service for ingesting content from URLs"""
    
    def __init__(self):
        self.timeout = httpx.Timeout(30.0)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; CL-SRS/1.0; +http://example.com/bot)"
        }
        if not USE_TRAFILATURA:
            self.h2t = html2text.HTML2Text()
            self.h2t.ignore_links = True
            self.h2t.ignore_images = True
            self.h2t.ignore_emphasis = False
            self.h2t.body_width = 0  # Don't wrap lines
    
    async def ingest_url(self, url: str) -> Dict[str, Any]:
        """
        Fetch and extract main text content from URL
        
        Args:
            url: URL to fetch content from
        
        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            # Validate URL format
            if not url.startswith(("http://", "https://")):
                return {
                    "status": "error",
                    "error": "Invalid URL format. Must start with http:// or https://",
                    "text": "",
                    "meta": {}
                }
            
            # Fetch the content
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, follow_redirects=True)
                response.raise_for_status()
            
            # Extract text using available library
            text, meta = self._extract_text(response.text, url)
            
            if not text or len(text.strip()) < 100:
                return {
                    "status": "error",
                    "error": "Could not extract sufficient text from the URL",
                    "text": "",
                    "meta": meta
                }
            
            return {
                "status": "success",
                "text": text,
                "meta": meta
            }
            
        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "error": f"HTTP error: {e.response.status_code}",
                "text": "",
                "meta": {"url": url}
            }
        except httpx.RequestError as e:
            return {
                "status": "error",
                "error": f"Request error: {str(e)}",
                "text": "",
                "meta": {"url": url}
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Unexpected error: {str(e)}",
                "text": "",
                "meta": {"url": url}
            }
    
    def _extract_text(self, html: str, url: str) -> tuple[str, Dict[str, Any]]:
        """
        Extract main text content from HTML
        
        Args:
            html: Raw HTML content
            url: Original URL for metadata
        
        Returns:
            Tuple of (extracted_text, metadata)
        """
        try:
            if USE_TRAFILATURA:
                # Use trafilatura for high-quality extraction
                text = trafilatura.extract(
                    html,
                    output_format='txt',
                    include_comments=False,
                    include_tables=True,
                    deduplicate=True,
                    url=url
                )
                
                # Get metadata
                metadata = trafilatura.extract_metadata(html)
                
                if text:
                    title = metadata.title if metadata and metadata.title else ""
                    if title and title not in text:
                        text = f"{title}\n\n{text}"
                    
                    meta = {
                        "url": url,
                        "title": title,
                        "word_count": len(text.split()),
                        "char_count": len(text),
                        "author": metadata.author if metadata and metadata.author else None,
                        "date": metadata.date if metadata and metadata.date else None
                    }
                    
                    return text, meta
            
            else:
                # Use html2text as fallback
                text = self.h2t.handle(html)
                
                # Clean up the text
                text = re.sub(r'\n{3,}', '\n\n', text)
                text = re.sub(r' {2,}', ' ', text)
                text = text.strip()
                
                # Try to extract title
                soup = BeautifulSoup(html, 'html.parser')
                title_elem = soup.find('title')
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                if title and title not in text:
                    text = f"{title}\n\n{text}"
                
                meta = {
                    "url": url,
                    "title": title,
                    "word_count": len(text.split()),
                    "char_count": len(text)
                }
                
                return text, meta
            
        except Exception as e:
            # Final fallback to BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            
            # Try to find main content areas
            main_content = None
            for selector in ['main', 'article', '[role="main"]', '#content', '.content']:
                main_content = soup.select_one(selector)
                if main_content:
                    break
            
            if not main_content:
                main_content = soup.body or soup
            
            # Extract text
            text = main_content.get_text(separator='\n', strip=True)
            
            # Clean excessive whitespace
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            
            # Get title
            title_elem = soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            if title and title not in text:
                text = f"{title}\n\n{text}"
            
            meta = {
                "url": url,
                "title": title,
                "word_count": len(text.split()),
                "char_count": len(text),
                "fallback_extraction": True
            }
            
            return text, meta
    
    async def ingest_text(self, text: str) -> Dict[str, Any]:
        """
        Process raw text input (when user pastes text instead of URL)
        
        Args:
            text: Raw text content
        
        Returns:
            Dictionary with processed text and metadata
        """
        # Clean and validate text
        text = text.strip()
        
        if len(text) < 50:
            return {
                "status": "error",
                "error": "Text too short. Please provide at least 50 characters.",
                "text": "",
                "meta": {}
            }
        
        # Create metadata
        meta = {
            "source": "direct_input",
            "word_count": len(text.split()),
            "char_count": len(text)
        }
        
        return {
            "status": "success",
            "text": text,
            "meta": meta
        }
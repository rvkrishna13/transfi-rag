import asyncio
import json
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict
import time
import re

@dataclass
class ProductPage:
    title: str
    url: str
    short_description: str
    long_description_raw: List[str]
    long_description_source_urls: List[str]
    scraped_at: float
    page_type: str = ""


class AsyncWebScraper:
    
    def __init__(self, max_concurrent: int = 10, delay: float = 0.1, max_depth: int = 20):
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.max_depth = max_depth
        self.session: Optional[aiohttp.ClientSession] = None
        self.total_subpages: int = 0
        self.pages_scraped_success: int = 0
        self.errors: List[Dict[str, str]] = []
        
        self.visited: Set[str] = set()
        self.urls_404: Set[str] = set()

    def record_error(self, kind: str, message: str, url: Optional[str] = None, status: Optional[int] = None):
        entry: Dict[str, str] = {"type": kind, "message": message}
        if url is not None:
            entry["url"] = url
        if status is not None:
            entry["status"] = str(status)
        self.errors.append(entry)
        
    async def __aenter__(self):
        """Enter async context and create session."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context and close session."""
        if self.session:
            await self.session.close()
    
    @staticmethod
    def extract_main_content(soup: BeautifulSoup) -> str:
        """Extract main content using site-specific selectors."""
        main_content = soup.find('div', class_='main_wrapper')
        return main_content.get_text(separator=" ", strip=True) if main_content else ""
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL by removing language prefixes."""
        parsed = urlparse(url)
        path = parsed.path
        path = re.sub(r'^/(en|en-us|en-gb)/', '/', path, flags=re.IGNORECASE)
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    
    def is_valid_url(self, url: str, base_domain: str, page_type: str) -> bool:
        """Return True if URL is valid to scrape for the given page type."""
        url = self.normalize_url(url)
        if url in self.visited or url in self.urls_404:
            return False
        
        parsed_url = urlparse(url)
        return (parsed_url.netloc == base_domain and parsed_url.path.startswith(f'/{page_type}'))
                
    
    def extract_internal_links(self, soup: BeautifulSoup, base_url: str, page_type: str) -> List[str]:
        """Extract internal links under the given page type."""
        domain = urlparse(base_url).netloc
        links = set()
        
        for link in soup.find_all('a', href=True):
            full_url = urljoin(base_url, link['href'])
            if self.is_valid_url(full_url, domain, page_type):
                links.add(full_url)
        return list(links)
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch page HTML; return None on non-200 or errors."""
        try:
            await asyncio.sleep(self.delay)
            async with self.session.get(url) as response:
                if response.status == 404:
                    self.record_error("http_404", "Not Found", url=url, status=404)
                    self.urls_404.add(url)
                    return None
                elif response.status != 200:
                    self.record_error("http_error", f"HTTP {response.status}", url=url, status=response.status)
                    return None
                
                return await response.text()
        except Exception as e:
            self.record_error("fetch_exception", str(e), url=url)
            return None
    
    def extract_sub_pages(self, soup: BeautifulSoup, start_url: str, page_type: str) -> List[Dict[str, str]]:
        """Extract sub-pages for a given page type from the main page."""
        sub_pages = []
        page_links = [x for x in soup.find_all('a') if f'/{page_type}' in x.get('href', '')]
        
        for page_link in page_links:
            try:
                href = page_link.get('href')
                if not href:
                    continue
                
                full_url = urljoin(start_url, href)
                title = page_link.get_text().strip()
                short_description = ""
                short_desc_tag = page_link.find_next_sibling('p')
                if short_desc_tag:
                    short_description = short_desc_tag.get_text(strip=True)
                
                sub_pages.append({
                    'url': full_url,
                    'title': title,
                    'short_description': short_description,
                    'page_type': page_type
                })
            except Exception as e:
                self.record_error("parse_link_error", str(e), url=start_url)
        return sub_pages
    
    def deduplicate_sub_pages(self, all_sub_pages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Remove duplicate URLs, preferring entries with descriptions."""
        seen_urls = {}
        
        for sub_page in all_sub_pages:
            url = sub_page['url']
            
            if url not in seen_urls:
                seen_urls[url] = sub_page
            elif sub_page['short_description'] and not seen_urls[url]['short_description']:
                seen_urls[url] = sub_page
        
        return list(seen_urls.values())
    
    async def dfs_scrape_related_pages(
        self, 
        main_url: str, 
        page_type: str
    ) -> (List[str], List[str]):
        """Depth-first scrape of related pages; returns raw HTML contents and their source URLs."""
        raw_contents = []
        raw_content_urls = []
        base_domain = urlparse(main_url).netloc
        
        async def scrape_page(url: str, current_depth: int = 0):
            if (current_depth > self.max_depth or 
                not self.is_valid_url(url, base_domain, page_type)):
                return
            
            self.visited.add(url)
            html = await self.fetch_page(url)
            if not html:
                return
            soup = BeautifulSoup(html, 'html.parser')
            if html:
                raw_contents.append(html)
                raw_content_urls.append(url)
            if current_depth < self.max_depth:
                internal_links = self.extract_internal_links(soup, url, page_type)
                unvisited_links = [link for link in internal_links if self.is_valid_url(link, base_domain, page_type)]
                if current_depth < 3 and len(unvisited_links) > 1:
                    tasks = [scrape_page(link, current_depth + 1) for link in unvisited_links]
                    await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    for link in unvisited_links:
                        await scrape_page(link, current_depth + 1)
        
        await scrape_page(main_url)
        return raw_contents, raw_content_urls
    
    async def process_sub_page(
        self, 
        sub_page: Dict[str, str]
    ) -> ProductPage:
        """Scrape a sub-page and collect DFS raw contents."""
        page_type = sub_page['page_type']
        raw_contents, raw_content_urls = await self.dfs_scrape_related_pages(
            sub_page['url'], 
            page_type
        )
        
        return ProductPage(
            title=sub_page['title'],
            url=sub_page['url'],
            short_description=sub_page['short_description'],
            long_description_raw=raw_contents,
            long_description_source_urls=raw_content_urls,
            scraped_at=time.time(),
            page_type=page_type
        )
    
    async def discover_and_scrape_pages(
        self, 
        start_url: str, 
        page_types: List[str]
    ) -> List[ProductPage]:
        """Discover sub-pages and scrape them with DFS."""
        html = await self.fetch_page(start_url)
        if not html:
            self.record_error("main_page_unreachable", "Failed to access main page", url=start_url)
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        all_sub_pages = []
        for page_type in page_types:
            sub_pages = self.extract_sub_pages(soup, start_url, page_type)
            all_sub_pages.extend(sub_pages)
        unique_sub_pages = self.deduplicate_sub_pages(all_sub_pages)
        self.total_subpages = len(unique_sub_pages)
        self.pages_scraped_success = len(unique_sub_pages)
        
        if not unique_sub_pages:
            return []
        
        return unique_sub_pages

    def get_stats(self) -> Dict[str, int]:
        """Return scraping statistics and captured errors."""
        return {
            'total_subpages': self.total_subpages,
            'pages_scraped_success': self.pages_scraped_success,
            'errors': self.errors,
        }

import re
from typing import List
import trafilatura
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from bs4 import BeautifulSoup as bs

class TextProcessor:
    def __init__(self):
        """
        max_workers: Number of workers. Defaults to CPU count.
        """
        self.max_workers = multiprocessing.cpu_count()

    def process_html_content(self, html_content: str) -> str:
        """Process single HTML content to markdown."""
        text = trafilatura.extract(
            html_content,
            include_tables=True,
            include_comments=False,
            output_format='markdown'  # or 'txt'
        )

        if not text:
            soup = bs(html_content, 'html.parser')
            
            for tag in soup(['script', 'style', 'nav', 'footer', 
                        'header', 'aside', 'iframe']):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        return text.strip()

    def process_html_contents(self, html_contents: List[str]) -> List[str]:
        """Process multiple HTML contents sequentially."""
        return [self.process_html_content(html) for html in html_contents]
    
    def process_in_parallel(self, html_contents_groups: List[List[str]]) -> List[List[str]]:
        """
        Process groups of HTML contents in parallel. Each thread handles one group (list[str]).
        Returns a list of results matching the group structure.
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            grouped_results = list(executor.map(self.process_html_contents, html_contents_groups))
        return grouped_results

    def process_in_batches(self, html_contents: List[List[str]], batch_size: int = 10) -> List[List[str]]:
        """
        Process large lists in batches to avoid memory issues.
        """
        results = []
       
        for i in range(0, len(html_contents), batch_size):
            batch = html_contents[i:i + batch_size]
            batch_results = self.process_in_parallel(batch)
            results.extend(batch_results)
        return results
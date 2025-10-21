#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import base64
import json
import time
import random
import re
import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class WorkingScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        })
    
    def create_filter_url(self, page_num):
        """Создает URL с фильтром."""
        filters = [{"code": "pageNumber", "value": page_num}]
        filters_json = json.dumps(filters)
        filters_b64 = base64.b64encode(filters_json.encode()).decode()
        return f"https://svoefermerstvo.ru/companies/root?filters={filters_b64}"
    
    def get_companies_from_page(self, page_num):
        """Получает компании со страницы."""
        url = self.create_filter_url(page_num)
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                logging.error(f"❌ Страница {page_num}: ошибка {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            org_links = soup.find_all('a', href=lambda x: x and '/organization/' in x)
            
            company_urls = set()
            for link in org_links:
                href = link.get('href')
                if href and '/organization/' in href:
                    if href.startswith('/'):
                        full_url = f"https://svoefermerstvo.ru{href}"
                    else:
                        full_url = href
                    clean_url = full_url.split('#')[0].split('?')[0]
                    company_urls.add(clean_url)
            
            return list(company_urls)
            
        except Exception as e:
            logging.error(f"❌ Ошибка страницы {page_num}: {e}")
            return []
    
    def extract_email_from_company(self, company_url):
        """Извлекает email со страницы компании."""
        try:
            response = self.session.get(company_url, timeout=10)
            if response.status_code != 200:
                return None
            
            # Ищем в формате "телефон | email"
            pipe_pattern = r'\+7\s?\(?\d{3}\)?\s?\d{3}[- ]?\d{2}[- ]?\d{2}\s*\|\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            pipe_matches = re.findall(pipe_pattern, response.text)
            
            if pipe_matches:
                email = pipe_matches[0]
                if self.is_valid_email(email):
                    return email
            
            # Fallback: ищем любые email
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            all_emails = re.findall(email_pattern, response.text)
            
            for email in all_emails:
                if self.is_valid_email(email):
                    return email
            
            return None
            
        except Exception as e:
            logging.debug(f"Ошибка извлечения из {company_url}: {e}")
            return None
    
    def is_valid_email(self, email):
        invalid_emails = {'office@rshb.ru'}
        return (email and len(email) > 5 and email not in invalid_emails and
                not email.endswith('.png') and not email.endswith('.jpg'))
    
    def run(self, start_page=1, max_pages=10):
        """Запускает парсер."""
        all_results = []
        
        for page in range(start_page, start_page + max_pages):
            logging.info(f"\\n📖 Страница {page}/{start_page + max_pages - 1}")
            
            company_urls = self.get_companies_from_page(page)
            logging.info(f"📊 Найдено компаний: {len(company_urls)}")
            
            page_emails = 0
            for company_url in company_urls:
                email = self.extract_email_from_company(company_url)
                if email:
                    all_results.append({"URL": company_url, "Email": email})
                    page_emails += 1
                    logging.info(f"✅ Найден: {email}")
                
                # Задержка между компаниями
                time.sleep(random.uniform(1, 2))
            
            # Сохраняем прогресс
            if all_results:
                df = pd.DataFrame(all_results)
                Path("working_results").mkdir(exist_ok=True)
                df.to_excel("working_results/emails.xlsx", index=False)
                logging.info(f"💾 Сохранено: {len(all_results)} email")
            
            logging.info(f"📧 На странице: {page_emails} email")
            
            # Задержка между страницами
            time.sleep(random.uniform(2, 4))
        
        logging.info(f"🎉 Завершено! Всего: {len(all_results)} email")
        return all_results

if __name__ == "__main__":
    scraper = WorkingScraper()
    # Тест на 5 страницах
    scraper.run(start_page=1, max_pages=5)

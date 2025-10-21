# Парсер для SvoeFermerstvo.ru

Веб-скрапер для сбора email-адресов компаний с сайта [svoefermerstvo.ru](https://svoefermerstvo.ru/)

## Возможности

- Сбор email-адресов со страниц организаций
- Две реализации:
  - `working_scraper.py` - Простой скрапер на requests (быстрый)
  - `run_parser.py` - Скрапер на Selenium с браузерной автоматизацией
- Сохранение прогресса и возобновление работы
- Экспорт в Excel формат
- Случайные задержки между запросами
- Обработка всплывающих окон (куки, выбор региона)

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Использование

### Простой скрапер (рекомендуется):
```bash
python3 working_scraper.py
```

### Selenium скрапер:
```bash
python3 run_parser.py --headless
```

## Требования

- beautifulsoup4
- requests
- pandas
- openpyxl
- selenium (для run_parser.py)

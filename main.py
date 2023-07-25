from datetime import datetime
import json
import math
import time
import random
import tempfile
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem


def get_user_agent():
    software_names = [SoftwareName.CHROME.value]
    operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]
    user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=100)
    user_agent = user_agent_rotator.get_random_user_agent()
    return user_agent


def get_pages_data(url: str, text='') -> requests:
    """Получаем данные со страницы."""
    options = webdriver.ChromeOptions()
    options.add_argument(f'user-agent={get_user_agent()}')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url=url)
        main_page = driver.page_source
        print(f'URL: {url} {text} - FINISH')
        time.sleep(random.randint(35, 45))
        return main_page
    except Exception as ex:
        print(ex)
    finally:
        driver.close()
        driver.quit()


def save_data_html(req: requests, file_name: str):
    """Сохраняем полученный requests в html файл."""
    with open(f'{file_name}.html', 'w') as file:
        file.write(req)


def open_html_file(file_name: str) -> str:
    """Открываем html файл."""
    with open(f'{file_name}.html') as file:
        return file.read()


def create_object_beautifulsoup(src: str) -> BeautifulSoup:
    """Создаем объект BeautifulSoup."""
    return BeautifulSoup(src, 'lxml')


def get_list_urls_letters(soup: BeautifulSoup) -> list[str]:
    """Получаем ссылки на страницы с городами по алфавиту."""
    urls_letters = []
    letters = soup.find_all('div', class_='part_title')
    for letter in letters:
        url = f'https://ru.restaurantguru.com/cities-Georgia-c/{quote(letter.text.strip()[0])}-t'
        urls_letters.append(url)
    return urls_letters


def get_list_urls_cities(urls: list[str]):
    """Получаем ссылки на список ресторанов отсортированных по городам."""
    list_urls_cities = []
    url_index = 1
    for url in urls:
        req = get_pages_data(
            url, f'Буква '
            f'{url_index} из {len(urls)}')
        soup = create_object_beautifulsoup(req)
        url_index += 1
        cities = soup.find('ul', {'class': 'cities-list clearfix clear scroll-container'}).find_all('li')
        for city in cities:
            city = city.find('a')
            city_url = city.get('href')
            city_name = city.text
            list_urls_cities.append({
                'city_url': city_url,
                'city_name': city_name
            })
    return list_urls_cities


def get_list_urls_restaurants(list_cities: list[dict]):
    """Получения все ссылок ресторанов."""
    list_urls_restaurants = {}
    url_index = 1
    for city in list_cities:
        req = get_pages_data(city['city_url'], f'{url_index}/{len(list_cities)}')
        soup = create_object_beautifulsoup(req)
        restaurants_count = soup.find('div', class_='wrap_top_title').find('span', class_='grey').text
        restaurants_count = int(restaurants_count.strip().replace('/', ''))
        if restaurants_count > 20:
            restaurant_list = []
            pages = restaurants_count / 20
            pages = math.ceil(pages)
            for page in range(2, pages + 1):
                req_page = get_pages_data(
                        f'{city["city_url"]}/{page}',
                        f'{url_index}/{len(list_cities)} - страница {page} из {pages}'
                    )
                soup = create_object_beautifulsoup(req_page)
                restaurants = soup.find(
                    'div', class_='restaurant_container'
                ).find_all(
                    'div', class_='restaurant_row'
                )
                for restaurant in restaurants:
                    restaurant_url = restaurant.get('data-review-href').split('/')
                    restaurant_list.append(f'https://ru.restaurantguru.com/{restaurant_url[-2]}')
            list_urls_restaurants[city['city_name']] = restaurant_list
        else:
            restaurant_list = []
            restaurants = soup.find(
                'div', class_='restaurant_container'
            ).find_all(
                'div', class_='restaurant_row'
            )
            for restaurant in restaurants:
                restaurant_url = restaurant.get('data-review-href').split('/')
                restaurant_list.append(f'https://ru.restaurantguru.com/{restaurant_url[-2]}')
            list_urls_restaurants[city['city_name']] = restaurant_list
        url_index += 1
    return list_urls_restaurants


def get_restaurant_info(list_restaurants: list[dict]):
    restaurants_info = {}
    city_index = 1
    restaurants_count = 0
    with tempfile.TemporaryDirectory() as directory:
        for city in list_restaurants:
            print(f'Город {city}, {city_index} из {len(list_restaurants)}.')
            restaurants_info[city] = {}
            url_index = 1
            path = directory + str(url_index)
            for restaurant_url in list_restaurants[city]:
                save_data_html(
                    get_pages_data(
                        restaurant_url,
                        f'Ресторан {url_index} из {len(list_restaurants[city])}.'
                    ),
                    path
                )
                restaurants_count += len(list_restaurants[city])
                soup = create_object_beautifulsoup(open_html_file(path))
                url_index += 1
                restaurant_name = soup.find(
                    'div', class_='title_container'
                ).find(
                    'h1', class_='notranslate'
                ).find('a').text
                try:
                    restaurant_description = soup.find(
                        'div', class_='description'
                    ).find('div').text
                except AttributeError:
                    restaurant_description = ''

                restaurants_info[city][restaurant_name] = {
                    'url': restaurant_url,
                    'description': restaurant_description
                }
            city_index += 1
    return [restaurants_count, restaurants_info]


def save_json_file(restaurants_info, name):
    with open(f'{name}.json', 'w', encoding='utf-8') as file:
        json.dump(restaurants_info, file, indent=4, ensure_ascii=False)


def main():

    url = 'https://ru.restaurantguru.com/cities-Georgia-c'
    start_time = datetime.now()
    print(f'Время запуска скрипта: {start_time.strftime("%H:%m")}\n'
          f'Запущен процесс сбора букв по которым производиться сортировка \n'
          f'и формирование на их основе ссылок для прохода.')
    file_name = f'restaurant_guru_{start_time.strftime("%d_%m_%Y_%H_%m")}'
    # Получаем страницу с алфавитной сортировкой.
    req = get_pages_data(url)
    # Создаем объект beautifulsoup на основе полученной страницы.
    soup = create_object_beautifulsoup(req)
    # Получаем из объекта bs список букв и на его основе
    # формируем список ссылок для сбора городов.
    letters_list_urls = get_list_urls_letters(soup)
    # Получаем ссылки на города.
    print(f'Процесс сбора и формирования окончен.\n'
          f'Всего ссылок сформировано: {len(letters_list_urls)}\n'
          f'Запущен процесс сбора городов со страниц алфавитной сортировки.')
    cities_list_urls = get_list_urls_cities(letters_list_urls)
    print(f'Окончен процесс сбора городов со страницы алфавитной сортировки.\n'
          f'Собрано городов: {len(cities_list_urls)}\n'
          f'Запущен процесс сбора ресторанов со страниц городов.')
    restaurants_list_urls = get_list_urls_restaurants(cities_list_urls)
    print(f'Окончен процесс сбора ресторанов со страниц городов.\n'
          f'Собрано ресторанов: {len(restaurants_list_urls)}\n'
          f'Запущен процесс сбора информации о ресторанах.')
    restaurant_info = get_restaurant_info(restaurants_list_urls)
    print(f'Процесс сбора информации о ресторанах окончен.\n'
          f'Всего ресторанов: {restaurant_info[0]}')
    save_json_file(restaurant_info, file_name)
    print('Json файл сформирован.')
    end_time = datetime.now()
    spent_time = end_time - start_time
    print(f'Время остановки скрипта: {start_time.strftime("%H:%m")}\n'
          f'Затрачено времени: {spent_time}')


if __name__ == '__main__':
    main()

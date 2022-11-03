import asyncio
import csv
import time
import re

import requests
import aiohttp

from bs4 import BeautifulSoup
from random import randint
from time import sleep





main_page = 'https://jobs.dou.ua/companies/'

companies_list = 'https://jobs.dou.ua/companies/xhr-load/?'

headers = {
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36',
    'accept': '*/*',
    'referer': 'https://jobs.dou.ua/companies/',
}

# companies_data = []

async def decode_email(e):
    de = ""
    k = int(e[:2], 16)
    for i in range(2, len(e)-1, 2):
        de += chr(int(e[i:i+2], 16)^k)
    return de


async def normalize_data(data, emails, phones):
    tick = 0
    data['description'] = ''.join(data['description'])
    for email, indx in zip(emails, range(len(emails))):
        if email not in data.values():
            data[f'email_{indx+1}'] = email
    for phone in phones:
        if len(phone) > 1:
            for p in phone:
                if p.strip() not in data.values():
                    data[f'phone_{tick+1}'] = p
                    tick += 1
        elif len(phone) == 1 and ''.join(phone).strip() not in data.values():
            data[f'phone_{tick+1}'] = ''.join(phone)
            tick += 1
    return data


def write_extract_file(output_filename: str, data: dict):
    """
    Write the extracted content into the file
    """
    try:
        if data:
            columns = list(data.keys())
            with open(f'{output_filename}', "a+", newline='') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(data.keys())
                writer.writerow(data.values())
    except FileNotFoundError:
        print("Output file not present", output_filename)
        print("Current dir: ", os.getcwd())
        raise FileNotFoundError


async def save_as_csv(company: dict):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, write_extract_file, 'dou.csv', company)


async def load_data(session, url, name):
    async with session.get(url, headers=headers) as company_profile:
        if company_profile.status == 404:
            return
        soup_profile = BeautifulSoup(await company_profile.text(), 'html.parser')
        try:
            site = soup_profile.find(class_="site").find('a').get('href')
        except AttributeError:
            site = ''
        print(name, f'status code: {company_profile.status}')
        try:
            size = soup_profile.find(text=re.compile('спеціалістів')).strip()
        except AttributeError:
            size = ''
        descriptions = soup_profile.find(class_='b-typo').find_all('p')
        descriptions_company = [description.text for description in descriptions if not description.find('img')]
        offices_url = soup_profile.find(class_='company-nav').find(text='Офіси').parent.get('href')
        async with session.get(offices_url, headers=headers) as response_offices:
            soup_offices = BeautifulSoup(await response_offices.text(), 'html.parser')
            emails = soup_offices.find_all(class_='mail')
            phones = soup_offices.find_all(class_='phones')
            emails_company = [
                await decode_email(email.find('a').get('href').split('#')[-1]) 
                for email in emails if email.find('a').has_attr('href')
            ]
            phones_company = [phone.text.strip().split('\n\t\t\t\t\t') for phone in phones]
            data = {
                'name': name, 
                'url': url, 
                'size': size, 
                'description': descriptions_company,
                'site': site
            }
            result = await normalize_data(data, emails_company, phones_company)
            print(result)
            # companies.append(result)
            await save_as_csv(result)
        

async def main():
    flag = True
    tick = 0
    num = 0
    async with aiohttp.ClientSession() as session:
        async with session.get(main_page, headers=headers) as resp:
            soup = BeautifulSoup(await resp.text(), 'html.parser')
            await asyncio.sleep(3)
            token_obj = soup.find('input', attrs={'name':'csrfmiddlewaretoken'})
            token = None
            if token_obj:
                token = token_obj['value']
            else:
                flag = False
        while flag:
            tasks = []
            print(f'num of page {num}')
            num += 1
            data = {
                'csrfmiddlewaretoken': token,
                'count': tick
            }
            tick += 20
            sleep(randint(3,7))
            async with session.post(companies_list, headers=headers, data=data) as res_comp:
                data = await res_comp.json()
                flag = not data['last']
                html = data['html']
                soup_companis = BeautifulSoup(html, 'html.parser')
                companies = soup_companis.find_all(class_='company')
                for company in companies:
                    url_company = company.find(class_='cn-a').get('href')
                    name = company.find(class_='cn-a').text
                    task = asyncio.create_task(load_data(session, url_company, name))
                    tasks.append(task)
                await asyncio.gather(*tasks)
                await asyncio.sleep(1)

asyncio.run(main())

# with open(f'dou.csv', 'w') as f:
#         writer = csv.writer(f)
#         for company in companies_data:
#             writer.writerow(company.keys())
#             writer.writerow(company.values())


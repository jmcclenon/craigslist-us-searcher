"""
Craigs list client to scrap ads from entire US
"""
import requests
import itertools
import re
import csv
from bs4 import BeautifulSoup

log = logging.getLogger()

__author__ = 'Oleksiy Ivanchuk (barjomet@barjomet.com)'


def decode_dict(dictionary):
    return dict((k, v or '' if isinstance(v, unicode) else (v or "").decode('utf8')) for k,v in dictionary.items())


def encode_dict(dictionary):
    return  dict((k, v or '' if isinstance(v, str) else (v or "").encode('utf8')) for k,v in dictionary.items())


class Client():
    def __init__(self):
        self.hosts = []
        self.results_urls = []
        self.results = []
        self.get_us_hosts()


    def get_us_hosts(self):
        log.info('Get craigslist US hosts')
        url = 'https://geo.craigslist.org/iso/us'
        schema = url.split('/')[0]
        response = requests.get('https://geo.craigslist.org/iso/us')
        soup = BeautifulSoup(response.text)
        try:
            for li_soup in soup.find('div', id='postingbody')\
                               .find('ul', id='list')\
                               .findAll('li'):
                self.hosts.append(''.join([schema, li_soup.find('a')['href']]))
            log.info('OK')
        except Exception as error:
            log.error('Unable to fetch US hosts: %s' % error)


    def parse_pagination(self, soup):
        try:
            qnc = int(soup.find('span', class_='totalcount').text)
            if qnc > 100:
                return [{'s' : (page+1)*100} for page in range(qnc / 100)]
        except:
            log.warning('No pagination found')
            return None


    def parse_search(self, soup, host):
        if not soup.find('div', class_='noresults'):
            try:
                qnc = int(soup.find('span', class_='totalcount').text)
                for counter, link in enumerate(soup.findAll('a', class_='hdrlnk')):
                    if counter > qnc:
                        break
                    result_url = {
                        'url' : host + link['href'],
                        'title' : link.text
                    }
                    self.results_urls.append(result_url)
                    log.info('Result URL #%s added: %s' % (len(self.results_urls), result_url))
            except Exception as error:
                log.error('Failed to get search results: %s' % error)

        else:
            log.warning('No results found')


    def search(self, search_url, query):
        payload = {
            'query': query
        }
        for host in self.hosts:
            url = '%s%s' % (host, search_url)
            response = requests.get(url, params=payload)
            log.info('GET %s' % response.url)
            soup = BeautifulSoup(response.text)
            pages = self.parse_pagination(soup)
            self.parse_search(soup, host)
            if pages:
                for page in pages:
                    payload.update(page)
                    response = requests.get(url, params=payload)
                    payload.pop('s')
                    log.info('GET %s' % response.url)
                    soup = BeautifulSoup(response.text)
                    self.parse_search(soup, host)


    def parse_ads(self):
        mailsrch = re.compile(r'[\w\-][\w\-\.]+@[\w\-][\w\-\.]+[a-zA-Z]{1,4}')
        phonesrch = re.compile(r'\(?\b([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b')
        sitesrch = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        for one in self.results_urls:
            log.info('Parsing: %s' % one.get('url'))
            response = requests.get(one.get('url'))
            soup = BeautifulSoup(response.text)
            try:
                host = '/'.join(one.get('url').split('/')[:3])
                link = soup.find('a', class_='showcontact')['href']
                contacts_response = requests.get(host+link)
                emails = list(set([email.lower() for email in mailsrch.findall(contacts_response.text)]))
                phones = list(set(phonesrch.findall(contacts_response.text)))
                sites = list(set(sitesrch.findall(contacts_response.text)))
                self.results.append({
                    'url' : one.get('url'),
                    'title' : one.get('title'),
                    'emails' : ', '.join(emails or []),
                    'sites' : ', '.join(sites or []),
                    'phones' : ','.join(['-'.join(phone) for phone in phones or []])
                })
            except Exception as error:
                log.error('Failed to get contact data: %s' % error)


    def save(self, what, filename):
        writer = csv.DictWriter(open(filename, 'wb'), what[0].keys(), quoting=csv.QUOTE_ALL)
        writer.writerow(dict((v,v) for v in what[0].keys()))
        for result in what:
            writer.writerow(encode_dict(result))


    def load(self, what, filename):
        f = open(filename, 'rt')
        try:
            reader = csv.DictReader(f)
            for row in reader:
                what.append(row)
        finally:
            f.close()


    def load_urls(self):
        self.load(self.results_urls, 'results_urls.csv')


    def save_urls(self):
        self.save(self.results_urls, 'results_urls.csv')


    def save_results(self):
        self.save(self.results, 'results.csv')

import requests
from bs4 import BeautifulSoup
import json

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
r = requests.get('https://www.shl.com/solutions/products/product-catalog/', headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

# let's look for script tags that contain json data
scripts = soup.find_all('script')
for s in scripts:
    if s.string and 'catalog' in s.string.lower() and '{' in s.string:
        print(f"Found a script with json? Length: {len(s.string)}")
        if 'Pre-packaged' in s.string or 'Individual' in s.string:
            print("Contains keywords!")
            with open('scratch_script.txt', 'w', encoding='utf-8') as f:
                f.write(s.string)
            break

# also let's look at the html list of products if any
products = soup.find_all(class_='product-item')
print(f"Product items found by class 'product-item': {len(products)}")
if len(products) == 0:
    products = soup.find_all('article')
    print(f"Article items found: {len(products)}")

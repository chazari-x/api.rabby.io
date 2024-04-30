import time
import random
import requests
import threading
from queue import Queue
from tqdm import tqdm
import urllib3

urllib3.disable_warnings()

class PrintThread(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue
       
    def run(self):
        while True:
            addr = self.queue.get()
            with open('results.txt', "a", encoding="utf-8") as ff:
                ff.write(addr)
            self.queue.task_done()

class EthereumDataFetcher(threading.Thread):
    def __init__(self, proxies, in_queue, out_queue):
        threading.Thread.__init__(self)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.proxies = proxies
        self.headers = {
            'Sec-Ch-Ua': '"Chromium";v="109", "Not_A Brand";v="99"',
            'X-Version': '0.92.41',
            'X-Api-Sign': '7981a21d78572063fa44e9978063fb3396a386852f2433c4d93e6cd8ed1869fc',
            'Sec-Ch-Ua-Mobile': '?0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.5414.120 Safari/537.36',
            'X-Api-Ts': '1702803867',
            'X-Api-Ver': 'v2',
            'Accept': 'application/json, text/plain, */*',
            'X-Api-Nonce': 'n_RT2KhwQF08JA3CwiTUOhUnel9ELZPGHDb2UgZLKh',
            'X-Client': 'Rabby',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    def run(self):
        while True:
            address = self.in_queue.get()
            result = self.fetch_data_for_address(address)
            if result:
                total_value = self.calculate_total_value(result)
                formatted_data = self.format_wallet_data({'address': address, 'data': result, 'total_value': total_value})
                self.out_queue.put(formatted_data)
                print(f"Address: {address} - Total Value: ${total_value:.2f}")
            else: print(f"Tokens not found: {address}")
            self.in_queue.task_done()

    def fetch_data(self, eth_address, url_template):
        url = url_template.format(eth_address)
        while True:
            try:
                sess = requests.session()
                proxy = random.choice(self.proxies)
                if proxy == "":  
                    print("An empty proxy was received from proxies | The request is being repeated")
                    continue
                sess.proxies = {'all': proxy}
                sess.headers = self.headers
                sess.verify = False
                response = sess.get(url)
                if response.status_code != 200: 
                    print("Response status code: {} | The request is being repeated".format(response.status_code))
                    continue
                return response.json()
            except Exception as e: 
                print("{} | The request is being repeated".format(e))
                continue

    def fetch_data_for_address(self, eth_address):
        url_template = "https://api.rabby.io/v1/user/cache_token_list?id={}"
        return self.fetch_data(eth_address, url_template)

    def query_ethereum_address(self, eth_address):
        url_template = 'https://api.rabby.io/v1/user/complex_protocol_list?id={}'
        return self.fetch_data(eth_address, url_template)

    def calculate_total_value(self, tokens):
        return sum(token.get('price', 0) * token.get('amount', 0) for token in tokens) if tokens else 0

    def format_wallet_data(self, wallet):
        formatted_data = f"Address: {wallet['address']} "

        if wallet['data']:
            for project in wallet['data']:
                if 'portfolio_item_list' in project:
                    for item in project['portfolio_item_list']:
                        if 'asset_token_list' in item:
                            for token in item['asset_token_list']:
                                price = token.get('price', 0)
                                raw_amount = token.get('raw_amount', 0)
                                decimals = 10 ** token.get('decimals', 18)
                                amount = raw_amount / decimals
                                usd_value = round(amount * price, 2)
                                if usd_value >= 30:
                                    formatted_data += f"{token['name']:<20} {token['symbol']:<10} {token['chain']:<10} {usd_value:>10.2f}$ "

        formatted_data += f"Total Value of Wallet: ${wallet['total_value']:.2f} "
        extra_data = self.query_ethereum_address(wallet['address'])
        data = ""
        if extra_data:
            for item in extra_data:
                if 'portfolio_item_list' in item:
                    for portfolio_item in item['portfolio_item_list']:
                        typex = portfolio_item["name"]
                        if 'stats' in portfolio_item and 'asset_usd_value' in portfolio_item['stats']:
                            asset_usd_value = portfolio_item['stats']['asset_usd_value']
                            symbol = portfolio_item['asset_token_list'][0]["symbol"]
                            if asset_usd_value >= 30:
                                data += f"-----{typex} {item['name']} \t| \t{symbol} Token Total Locked: {asset_usd_value:>10.2f}$ "

        if data != "": formatted_data += "Extra Data: " + data
        return formatted_data + "\n"

def load_proxies(file_path: str):
    if file_path == "": file_path = "prx.txt"

    proxies = []
    with open(file=file_path, mode="r", encoding="utf-8") as File:
        lines = File.read().split("\n")
    
    for line in lines:
        try: proxies.append(f"http://{line}")
        except ValueError: pass

    if proxies.__len__() < 1:
        raise Exception(f"can't load empty proxies file ({file_path})!")

    print("{} proxies loaded successfully!".format(proxies.__len__()))

    return proxies

def read_addresses_from_file(file_path: str):
    with open(file_path, encoding="utf-8") as f:
        addresses = f.read().splitlines()
        print("Loaded {} address".format(addresses.__len__()))
        return addresses

def main():
    addresses = read_addresses_from_file('addr.txt')
    proxy_list = load_proxies(input('Path to proxies: '))
    threads = int(input('Max threads: '))
    
    resultqueue = Queue()
    pathqueue = Queue()

    print("Starting the process threads...")

    # spawn threads to process
    for i in range(0, threads):
        thread = EthereumDataFetcher(proxy_list, pathqueue, resultqueue)
        thread.daemon = True
        thread.start()

    print("Starting the pring thread...")

    # spawn threads to print
    thread = PrintThread(resultqueue)
    thread.daemon = True
    thread.start()

    print("Writing addresses to a queue...")

    for address in addresses:
        pathqueue.put(address)

    print("All addresses in the queue")

    # wait for queue to get empty
    pathqueue.join()
    resultqueue.join()

if __name__ == "__main__": main()
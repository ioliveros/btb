from binance.client import Client
import time

api_key='98825baa84609a80cf875c6e51b21e63eda42759a68a92680240522c3b9f43f5'
api_secret='635fd956856fff8619b58f6e6967a676a9c5cd27d5f02a9116d934ee1c12e480'
client = Client(api_key, api_secret)

for i in range(1, 10):
    local_time1 = int(time.time() * 1000)
    server_time = client.get_server_time()
    diff1 = server_time['serverTime'] - local_time1
    local_time2 = int(time.time() * 1000)
    diff2 = local_time2 - server_time['serverTime']
    print("local1: %s server:%s local2: %s diff1:%s diff2:%s" % (local_time1, server_time['serverTime'], local_time2, diff1, diff2))
    time.sleep(2)

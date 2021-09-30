#!/usr/local/bin/python

from prometheus_client import start_http_server, Gauge

import logging
import os
import requests
import sys
import time

SOLVIEW_PERF_HEIGHT = Gauge('solview_perf_height', 'Height of performance sample')
SOLVIEW_PERF_TXS = Gauge('solview_perf_txs', 'Transactions in performance sample')
SOLVIEW_PERF_SLOTS = Gauge('solview_perf_slots', 'Slots in performance sample')
SOLVIEW_PERF_AVE_SLOT_TIME = Gauge('solview_perf_slot_time', 'Average slot time over performance sample window')
SOLVIEW_PERF_AVE_SLOT_TXS = Gauge('solview_perf_slots_txs', 'Average transactions per slow over sample window')
SOLVIEW_PERF_AVE_TXRATE = Gauge('solview_perf_txrate', 'Average transactions per second over sample window')
SOLVIEW_PERF_SKIP_RATE  = Gauge('solview_perf_skiprate', 'Cluster average skip rate')
SOLVIEW_PERF_SWSKIP_RATE  = Gauge('solview_perf_weightedskiprate', 'Cluster stake-weighted skip rate')
SOLVIEW_PERF_ACTIVE = Gauge('solview_perf_active_validators', 'Active validators')
SOLVIEW_PERF_DELINQUENT = Gauge('solview_perf_deliquent_validators', 'Delinquent validators')
SOLVIEW_PERF_ACTIVE_STAKE = Gauge('solview_perf_active_stake', 'Active stake')
SOLVIEW_PERF_DELINQUENT_STAKE = Gauge('solview_perf_deliquent_stake', 'Delinquent stake')

SOLVIEW_VALIDATOR_STAKE = Gauge('solview_validator_stake', 'Validator activated stake', ['nodePubkey', 'votePubkey'])
SOLVIEW_VALIDATOR_STATE = Gauge('solview_validator_status', 'Validator status', ['nodePubkey', 'votePubkey'])
SOLVIEW_VALIDATOR_COMMISSION = Gauge('solview_validator_commission', 'Validator commission rate', ['nodePubkey', 'votePubkey'])
SOLVIEW_VALIDATOR_EPOCH_CREDITS = Gauge('solview_validator_credits', 'Validator epoch credits', ['nodePubkey', 'votePubkey'])
SOLVIEW_VALIDATOR_LAST_VOTE = Gauge('solview_validator_last_vote', 'Validator last vote height', ['nodePubkey', 'votePubkey'])
SOLVIEW_VALIDATOR_ROOT_SLOT = Gauge('solview_validator_root_slot', 'Validator root slot', ['nodePubkey', 'votePubkey'])
SOLVIEW_VALIDATOR_BLOCKS_EXPECTED  = Gauge('solview_validator_slots_expected', 'Validator expected slots', ['nodePubkey'])
SOLVIEW_VALIDATOR_BLOCKS_MISSED  = Gauge('solview_validator_slots_missed', 'Validator missed slots', ['nodePubkey'])
SOLVIEW_VALIDATOR_SKIP_RATE  = Gauge('solview_validator_skip_rate', 'Validator block production skip rate', ['nodePubkey'])

SOLVIEW_VERSION_NODE = Gauge('solview_version_node', 'Node software version', ['nodePubkey'])
SOLVIEW_CLUSTER_VERSION_COUNT = Gauge('solview_version_cluster', 'Cluster software versions', ['version', 'version_int'])

SOLVIEW_ACCOUNTS_SOL = Gauge('solview_account_balance', 'SOL Balance for account', ['address'])
SOLVIEW_ACCOUNTS_SPL = Gauge('solview_account_splbalance', 'SPL Token balance for account', ['spl_address'])


logger = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s %(filename)s:%(lineno)-3s %(funcName)20s() | %(message)s")
logger.setLevel(logging.DEBUG)


'''
{'activatedStake': 30339798208, 'commission': 1, 'epochCredits': [[192, 168676, 0], [193, 402946, 168676],
[194, 497142, 402946]], 'epochVoteAccount': True, 'lastVote': 83989297,
'nodePubkey': 'BPJ15GZ5c53sryTuHqWwWjvZx18qy3B2QE1CvVBqPJL7', 'rootSlot': 83989229,
'votePubkey': 'Dro1hjqsT291n8uADuwuE761E2Q3hgdzFYVrWBnBM9Pd'}
'''
def vote_accounts(node_address):
    logger.debug("Sending vote accounts request to {}...".format(node_address))
    res = requests.post(node_address, json={'jsonrpc': '2.0', 'method': 'getVoteAccounts', 'id': 0, 'params': []}, headers={'Content-Type': 'application/json'}, timeout=(7, 33))
    data = res.json().get('result')
    if data is None or len(data) == 0:
      logger.error("getVoteAccounts call failed. Details: \n{}".format(data))
      return
    cluster_stake = [0,0]
    for status, status_code in {'current': 1, 'delinquent': 0}.items():
      for validator in data.get(status):

        nodePubkey = validator.get('nodePubkey')
        votePubkey = validator.get('votePubkey')
        cluster_stake[status_code] += validator.get('activatedStake')
        SOLVIEW_VALIDATOR_STATE.labels(nodePubkey, votePubkey).set(status_code)
        SOLVIEW_VALIDATOR_STAKE.labels(nodePubkey, votePubkey).set(validator.get('activatedStake'))
        SOLVIEW_VALIDATOR_COMMISSION.labels(nodePubkey, votePubkey).set(validator.get('commission'))
        if len(validator.get('epochCredits')) > 0:
          SOLVIEW_VALIDATOR_EPOCH_CREDITS.labels(nodePubkey, votePubkey).set(validator.get('epochCredits')[-1][1])
        else:
          SOLVIEW_VALIDATOR_EPOCH_CREDITS.labels(nodePubkey, votePubkey).set(0)
        SOLVIEW_VALIDATOR_LAST_VOTE.labels(nodePubkey, votePubkey).set(validator.get('lastVote'))
        SOLVIEW_VALIDATOR_ROOT_SLOT.labels(nodePubkey, votePubkey).set(validator.get('rootSlot'))
    SOLVIEW_PERF_ACTIVE_STAKE.set(cluster_stake[1])
    SOLVIEW_PERF_DELINQUENT_STAKE.set(cluster_stake[0])
    SOLVIEW_PERF_ACTIVE.set(len(data.get('current')))
    SOLVIEW_PERF_DELINQUENT.set(len(data.get('delinquent')))


'''
{"featureSet":3316993441,"gossip":"139.178.69.97:8001","pubkey":"47GkcpC6JFdQLFcS1ASMyUdxMST6HGiT1f54rGaWKeHr",
"rpc":null,"shredVersion":13490,"tpu":"139.178.69.97:8004","version":"1.6.22"}],"id":1}
'''
def cluster(node_address):
    logger.debug("Sending cluster request to {}...".format(node_address))
    res = requests.post(node_address, json={'jsonrpc': '2.0', 'method': 'getClusterNodes', 'id': 0, 'params': []}, headers={'Content-Type': 'application/json'}, timeout=(7, 33))
    data = res.json().get('result')
    if data is None or len(data) == 0:
      logger.error("getClusterNodes call failed. Details: \n{}".format(data))
      return
    cluster_versions = {}
    for node in data:
      if node.get('version') == None:
        int_version = 0
      else:
        int_version = int(''.join(map(lambda a: a.zfill(3), node.get('version').split('.'))))
      SOLVIEW_VERSION_NODE.labels(node.get('pubkey')).set(int_version)
      cluster_versions.update({int_version: cluster_versions.get(int_version, 0)+1})
    for iv, count in cluster_versions.items():
      major = int(iv/1000000)
      minor = int((iv%1000000)/1000)
      patch = int(iv%1000)
      SOLVIEW_CLUSTER_VERSION_COUNT.labels("{}.{}.{}".format(major,minor,patch), iv).set(count)


'''
curl http://localhost:8899 -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1, "method":"getBlockProduction"}'

  result:
    context:
      slot: INT
    value:
      byIdentity:
        PUBKEY: [ TOTAL, PRODUCED ]
'''
def skip_rates(node_address):
    logger.debug("Sending skip rates request to {}...".format(node_address))
    res = requests.post(node_address, json={'jsonrpc': '2.0', 'method': 'getBlockProduction', 'id': 0, 'params': []}, headers={'Content-Type': 'application/json'}, timeout=(7, 33))
    data = res.json().get('result')
    if data is None or len(data) == 0:
      logger.error("getBlockProduction call failed. Details: \n{}".format(data))
      return
    skip_rates = []
    total_slots = 0
    produced_slots = 0
    for node, (total, produced) in data.get('value').get('byIdentity').items():
      SOLVIEW_VALIDATOR_BLOCKS_EXPECTED.labels(node).set(total)
      SOLVIEW_VALIDATOR_BLOCKS_MISSED.labels(node).set(total-produced)
      skip_rates.append(1-(produced/total))
      total_slots += total
      produced_slots += produced
      SOLVIEW_VALIDATOR_SKIP_RATE.labels(node).set(1-(produced/total))

    SOLVIEW_PERF_SKIP_RATE.set(sum(skip_rates)/len(skip_rates))
    SOLVIEW_PERF_SWSKIP_RATE.set(1-(produced_slots/total_slots))


def performance(node_address):
    logger.debug("Sending performance request to {}...".format(node_address))
    res = requests.post(node_address, json={'jsonrpc': '2.0', 'method': 'getRecentPerformanceSamples', 'id': 0, 'params': [1]}, headers={'Content-Type': 'application/json'}, timeout=(7, 33))
    data = res.json().get('result')
    if data is None or len(data) == 0:
      logger.error("getRecentPerformanceSamples call failed. Details: \n{}".format(data))
      return
    SOLVIEW_PERF_HEIGHT.set(data[0].get('slot'))
    SOLVIEW_PERF_TXS.set(data[0].get('numTransactions'))
    SOLVIEW_PERF_SLOTS.set(data[0].get('numSlots'))
    if data[0].get('numSlots') > 0:
      SOLVIEW_PERF_AVE_SLOT_TIME.set(data[0].get('samplePeriodSecs')/data[0].get('numSlots'))
      SOLVIEW_PERF_AVE_SLOT_TXS.set(data[0].get('numTransactions')/data[0].get('numSlots'))
    SOLVIEW_PERF_AVE_TXRATE.set(data[0].get('numTransactions')/data[0].get('samplePeriodSecs'))


def watch_accounts(node_address, accounts):
    for address in accounts:
      '''
      curl http://localhost:8899 -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0", "id":1, "method":"getBalance", "params":["83astBRguLMdt2h5U1Tpdq5tjFoJ6noeGwaY3mDLVcri"]}'
      '''
      logger.debug("Sending watch accounts request for {} to {}...".format(address, node_address))
      res = requests.post(node_address, json={'jsonrpc': '2.0', 'method': 'getBalance', 'id': 0, 'params': [address]}, headers={'Content-Type': 'application/json'}, timeout=(7, 33))
      data = res.json().get('result')
      if data is None or len(data) == 0:
        logger.error("getBalance call failed. Details: \n{}".format(data))
        return
      SOLVIEW_ACCOUNTS_SOL.labels(address).set(data.get('value'))


def watch_spl_accounts(node_address, spl_accounts):
   for address in spl_accounts:
      logger.debug("Sending watch SPL accounts request for {} to {}...".format(address, node_address))
      res = requests.post(node_address, json={'jsonrpc': '2.0', 'method': 'getTokenAccountBalance', 'id': 0, 'params': [address]}, headers={'Content-Type': 'application/json'}, timeout=(7, 33))
      data = res.json().get('result')
      if data is None or len(data) == 0:
        logger.error("getTokenAccountBalance call failed. Details: \n{}".format(data))
        return

      SOLVIEW_ACCOUNTS_SPL.labels(address).set(data.get('value').get('uiAmount'))


def main():
    node_address = os.getenv('SOLVIEW_NODE_ADDRESS', "http://localhost:8899")
    port = int(os.getenv('SOLVIEW_PORT', 8000))
    addresses = list(filter(lambda x: x != '', os.getenv('SOLVIEW_ADDRESSES', '').split(',')))
    spl_addresses = list(filter(lambda x: x != '', os.getenv('SOLVIEW_SPL_ADDRESSES', '').split(',')))

    logger.info("Listening port: {}".format(port))
    logger.info("Node address: {}".format(node_address))
    logger.info("Solview addresses: {}".format(", ".join(addresses)))
    logger.info("SPL addresses: {}".format(", ".join(spl_addresses)))

    # Start up the server to expose the metrics.
    start_http_server(port)
    # Generate some requests.
    idx = 0
    while True:
      if idx%12 == 0:
        performance(node_address)
        cluster(node_address)
        watch_accounts(node_address, addresses)
        watch_spl_accounts(node_address, spl_addresses)
      vote_accounts(node_address)
      skip_rates(node_address)
      logger.debug("Sleeping...")
      time.sleep(5)


if __name__ == '__main__':
    logger.info("Starting Solview.")
    while True:
        try:
            main()
        except KeyboardInterrupt:
            sys.exit(0)
        except BrokenPipeError:
            sys.exit(0)
        except Exception:
          logger.exception("Exception occurred")
          sys.exit(10)

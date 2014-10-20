import hashlib
import os
import ecdsa
import ecdsa.der
import ecdsa.util
from bitcoin import *
import json
import requests

b58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
blockchain_api_code = os.environ['BLOCKCHAIN_API_CODE']

secure_key_length=60

def get_unspent(address):
  url='https://blockchain.info/unspent?active='+str(address)+"?api_code="+blockchain_api_code
  response = requests.get(url).content
  if response=='No free outputs to spend':
    return {}
  else:
    jsonresponse = json.loads(response)

    result=[]
    for x in jsonresponse['unspent_outputs']:
      r={}
      r['value']=x['value']
      r['output']=str(x['tx_hash'])+":"+str(x['tx_output_n'])
      result.append(r)
    return result

def base58encode(n):
    result = ''
    while n > 0:
        result = b58[n%58] + result
        n /= 58
    return result

def base256decode(s):
    result = 0
    for c in s:
        result = result * 256 + ord(c)
    return result

def countLeadingChars(s, ch):
    count = 0
    for c in s:
        if c == ch:
            count += 1
        else:
            break
    return count

def base58CheckEncode(version, payload):
    s = chr(version) + payload
    checksum = hashlib.sha256(hashlib.sha256(s).digest()).digest()[0:4]
    result = s + checksum
    leadingZeros = countLeadingChars(result, '\0')
    return '1' * leadingZeros + base58encode(base256decode(result))

def privateKeyToWif(key_hex):
    return base58CheckEncode(0x80, key_hex.decode('hex'))

def privateKeyToPublicKey(s):
    sk = ecdsa.SigningKey.from_string(s.decode('hex'), curve=ecdsa.SECP256k1)
    vk = sk.verifying_key
    return ('\04' + sk.verifying_key.to_string()).encode('hex')

def pubKeyToAddr(s):
    ripemd160 = hashlib.new('ripemd160')
    ripemd160.update(hashlib.sha256(s.decode('hex')).digest())
    return base58CheckEncode(0, ripemd160.digest())

def keyToAddr(s):
    return pubKeyToAddr(privateKeyToPublicKey(s))

def generate_subkeys():
    a=[]
    a.append(os.urandom(subkey_complexity).encode('hex')) #subkey1
    a.append(os.urandom(subkey_complexity).encode('hex')) #subkey2
    return a

def generate_privatekey(phrase):
    keysum=phrase
    secret_exponent=hashlib.sha256(keysum).hexdigest()
    privkey=privateKeyToWif(secret_exponent)
    return privkey

def generate_publickey(phrase):
    keysum=phrase
    secret_exponent=hashlib.sha256(keysum).hexdigest()
    public_key = privateKeyToPublicKey(secret_exponent)
    return public_key

def generate_publicaddress(phrase):
    public_key = generate_publickey(phrase)
    public_address = pubKeyToAddr(public_key)
    return public_address

def getunspent(publicaddress):  #REPLACE SOMEDAY WITH LOCAL
  url= "https://blockchain.info/unspent?active="+publicaddress
  a=requests.get(url)
  return json.loads(a.content)['unspent_outputs']

def txs_received_by_address(publicaddress):
  url='http://blockchain.info/address/'+str(publicaddress)+'?format=json'
  response=requests.get(url)
  transactions=json.loads(response.content)
  transactions=transactions['txs']

  receivedtxs=[]

  for tx in transactions:
    tome=False
    for outp in tx['out']:
      if 'addr' in outp:
        if outp['addr']==publicaddress:
          tome=True
    if tome:
      receivedtxs.append(tx)

  return receivedtxs

def txs_sent_by_address(publicaddress):
  url='http://blockchain.info/address/'+str(publicaddress)+'?format=json'
  response=requests.get(url)
  transactions=json.loads(response.content)
  transactions=transactions['txs']

  senttxs=[]

  for tx in transactions:
    fromme=False
    for inp in tx['inputs']:
      if inp['prev_out']['addr']==publicaddress:
        fromme=True
    if fromme:
      senttxs.append(tx)
  return senttxs


def find_opreturns_sent_by_address(publicaddress):
  txlist=txs_sent_by_address(publicaddress)
  scriptlist=[]
  for tx in txlist:

    n=0
    for out in tx['out']:
      n=n+1
      script=out['script']
      if script[0:2]=='6a':  #IS OP RETURN
        #print script
        txidentifier=str(tx['hash'])+":"+str(n)
        r=[]
        r.append(script[4:len(script)].decode('hex'))
        r.append(txidentifier)
        r.append(tx['block_height'])
        scriptlist.append(r)
  return scriptlist

def read_opreturns_sent_by_address(publicaddress):
  readdata=find_opreturns_sent_by_address(publicaddress)
  text=[]
  results=[]
  for x in readdata:
    text.append(x[0])
  n=0
  for x in text:
    strin=x[2:len(x)]
    x=x[0:2]
    print x
    try:
      intversion=int(x)
      #print intversion
      results.append([intversion,strin])
    except:
      a=0
  answer=''

  sortedresults=['']*100
  for x in results:
    sortedresults[x[0]]=x[1]

  for x in sortedresults:
    answer=answer+x

  return answer


def generate_secure_pair():
  randomkey=os.urandom(secure_key_length)
  public_key=generate_publickey(randomkey)
  public_address=generate_publicaddress(randomkey)
  private_key=generate_privatekey(randomkey)

  results = {}
  results['public_key']=public_key
  results['public_address']=public_address
  results['private_key']=private_key
  return results

def unspent_value(public_address):
  unspents=unspent(public_address)
  value=0.0
  for unsp in unspents:
    value=value+float(unsp['value'])
  value=value/100000000
  return value

b58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

import cointools
def checkphrase(phrase):
  a=generate_publicaddress(phrase)
  r=cointools.unspent(a)
  if len(r)>0:
    print r
    print phrase
    return phrase

def int_to_phrase(intcheck):
  r=intcheck
  d=[]
  while r>0:
    a=r%58
    d.append(a)
    r=r-a
    r=r/58
  e=''
  for x in d:
    e=e+str(b58[x])
  return e

import math
def check_int_range(loglimit):
  a=math.pow(58,loglimit)
  b=0
  while b<a:
    strin=int_to_phrase(b)
    val=checkphrase(strin)
    if not val is None:
      b=a
    else:
      print str(b)+"   "+str(strin)
    b=b+1

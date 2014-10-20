import requests
import json
import time
import leb128
import cointools
import databases
import node
import os

def get_current_block_localnode():
  count=node.connect("getblockcount",[])
  return int(count)

def get_current_block():
  try:
    response=requests.get("https://blockchain.info/q/getblockcount")
    result=int(str(response.content))
  except:
    result= databases.dbexecute("select lastblockdone from meta;", True)[0][0]
  return result

def get_transaction_list(blockn):
  response=requests.get("https://bitcoin.toshi.io/api/v0/blocks/"+str(blockn)+"/transactions")
  jsonresponse=json.loads(response.content)
  txs=jsonresponse['transactions']
  return txs

def tx_lookup_toshi(txhash):
  response=requests.get("https://bitcoin.toshi.io/api/v0/transactions/"+str(txhash))
  jsonresponse=json.loads(response.content)
  return jsonresponse

def tx_lookup(txhash):
  api_key = os.environ['CHAIN_API_KEY']
  url = "https://api.chain.com/v1/bitcoin/transactions/"+str(txhash)+"?api-key-id="+api_key
  response = requests.get(url)
  return json.loads(response.content)


def tx_lookup_node(txhash):
   print txhash
   c=node.connect('getrawtransaction',[txhash,1])
   return c

def script_to_coloraddress(script):
  ripehash=leb128.ripehash(script)
  answer=cointools.base58CheckEncode(0x05, ripehash.decode('hex'))
  return answer

def color_address(publicaddress):
  a=requests.get('https://blockexplorer.com/q/addresstohash/')
  hashed=a.content  #REPLACE THIS METHOD

def read_tx(txhash):
  r=tx_lookup(txhash)
  m=-1
  if 'outputs' in r:
    v=0
    for x in r['outputs']:
      if 'value' in x:
        v=v+x['value']
      if x['script_hex'][0:2]=='6a': #OP RETURN, only 1 per tx
        d=x['script_hex']
        m=d[2:len(d)]
        m=m.decode('hex')
        m=m[1:len(m)]
  return m, v

def op_return_in_block(n):
  a=requests.get("https://bitcoin.toshi.io/api/v0/blocks/"+str(n))
  blockdata=json.loads(a.content)
  txs=blockdata['transaction_hashes']

  messages=[]
  for tx in txs:
    n=read_tx(tx)
    m=n[0]
    if not m==-1:
      messages.append([tx,m,n[1]])
  return messages

def parse_colored_tx(metadata, txhash_with_index):
  hexmetadata=metadata.encode('hex')
  opcode=metadata[0:2]
  results={}
  if opcode=='OA':
      results['type']='OA'
      results['version']=metadata[2:4].encode('hex')
      results['asset_count']=int(metadata[4:5].encode('hex'),16)

      count=0
      d=[]
      for x in metadata[5:len(metadata)]:
        r=leb128.hexpiecetobinary(x.encode('hex'))
        d.append(r)
      e=[]
      r=[]
      for x in d:
        r.append(x)
        if x[0]=='0':
          e.append(r)
          r=[]
      f=[]

      n=0
      for x in e:
        if n<int(results['asset_count'])+1:
          f.append(leb128.decode(x))
          count=count+len(x)
        n=n+1

      results['asset_quantities']=f[0:len(f)-1]

      legit=True
      if len(results['asset_quantities'])<results['asset_count']:
        legit=False  #basically forced to agree with coinprism

      results['metadata_length']=f[len(f)-1]
      results['metadata']=metadata[5+count:len(metadata)]

      r=txhash_with_index.index(":")
      markerposition=int(txhash_with_index[r+1:len(txhash_with_index)])
      txhash=txhash_with_index[0:r]
      txdata=tx_lookup(txhash)
      txoutputs=txdata['outputs']
      results['issued']=[]

      for i in range(0,markerposition):
        h={}
        try:
          h['quantity']=results['asset_quantities'][i]
          print "checking script for "+str(txdata['inputs'][0]['transaction_hash'])
          #assumes first input is correct input
          script = txdata['outputs'][0]['script_hex']   #tx_lookup(txdata['inputs'][0]['transaction_hash'])['outputs'][txdata['inputs'][0]['vout']]['scriptPubKey']['hex']
          print script
          h['txhash_index']=txhash+":"+str(i)
          h['color_address']=script_to_coloraddress(script)
          h['destination_address']=txoutputs[i]['addresses'][0] #one dest per output
          h['btc']=int(txoutputs[i]['value'])
          h['previous_inputs']="source:"+str(txdata['inputs'][i]['addresses'][0])
          results['issued'].append(h)
        except:
          k=0

      results['transferred']=[]
      for i in range(markerposition+1, len(txoutputs)):
        if i<=len(results['asset_quantities']):
          h={}
          h['out_n']=i
          h['txhash_index']=txhash+":"+str(i)
          h['quantity']=results['asset_quantities'][i-1]

          h['previous_inputs']=[]
          for x in txdata['inputs']:
            h['previous_inputs'].append(str(x['output_hash'])+":"+str(x['output_index']))
          print txoutputs[i-1]
          h['destination_address']=txoutputs[i]['addresses'][0]
          h['btc']=int(txoutputs[i]['value'])
          results['transferred'].append(h)

  if legit:
    return results
  else:
    print "TRANSACTION FOUND WITH BAD ASSET COUNT "+str(txhash_with_index)
    return {}

def write_metadata(asset_quantities, otherdata):
  result='4f410100' #OA + version 0100
  assetcount=str(len(asset_quantities))
  if len(assetcount)==1:
    assetcount='0'+assetcount
  assetcount = str(hex(int(assetcount)))
  assetcount=assetcount[2:len(assetcount)]
  if len(assetcount)==1:
    assetcount="0"+assetcount
  result=result+assetcount

  for asset in asset_quantities:
    encoded=leb128.encode(asset)
    j=''
    for x in encoded:
      r=str(hex(int(x,2)))
      if len(r)==3:
        r='0'+r[2:3]
      else:
        r=r[2:len(r)]
      j=j+r
    result=result+j

  length=hex(len(otherdata))
  if len(length)==3:
    length=length[2:len(length)]
    length='0'+length
  else:
    length=length[2:len(length)]
  result=result+length
  result=result+otherdata.encode('hex')

  return result

def check_if_output_misspent(txhash, index):
  tx=tx_lookup_toshi(txhash)
  spent=False
  no_opreturnfound=True
  for x in tx['outputs']:
    if x['script'][0:9]=="OP_RETURN":
      no_opreturnfound=False
  if no_opreturnfound and tx['outputs'][index]['spent']:
    spent=True
  return spent

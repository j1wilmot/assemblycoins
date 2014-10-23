import os
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask import request, send_from_directory, render_template
from flask import make_response, redirect
import requests
import json
import ast
import time
import bitsource
import transactions
import addresses
import workertasks
import unicodedata
import databases
import random
import hashlib

app = Flask(__name__, static_url_path='', template_folder="static/explorer")
app.config['PROPAGATE_EXCEPTIONS']=True
dbname='barisser'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']  #"postgresql://localhost/"+dbname

#META
@app.route('/', methods=['GET'])
def home():
  return app.send_static_file('index.html')

@app.route('/docs', methods=['GET'])
def docs():
  return app.send_static_file('docs/index.html')

@app.route('/whitepaper', methods=['GET'])
def whitepaper():
  return app.send_static_file('whitepaper/index.html')

@app.route('/quickstart', methods=['GET'])
def quickstart():
  return app.send_static_file('quickstart/index.html')

@app.route('/addresses/<address>', methods=['GET'])
def gotoaddressexplorer(address=None):
  return render_template('addresses.html', the_address=address)

@app.route('/assets', methods=['GET'])
def seeallassets():
  return app.send_static_file('assets.html')

@app.route('/colors/<color>', methods=['GET'])
def gotocolorexplorer(color=None):
  return render_template('colors.html', the_color=color)

@app.route('/specifications', methods=['GET'])
def specs():
  return app.send_static_file('protocol/spec.html')

@app.route('/v1/blocks/count')
def getblockcount():
  result=bitsource.get_current_block()
  response=make_response(str(result), 200)
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/search/<searched>')
def search(searched=None):
  #decide what category search term belongs in
  if not searched==None:
    searched=str(searched)
    if len(searched)>50:
      #IS A TRANSACTION
      return redirect("https://assets.assembly.com/transactions/"+str(searched), code=200)
    elif len(searched)<50 and len(searched)>15 and searched[0]=='1':
      #IS A PUBLIC ADDRESS (not counting multisignature addresses)
      return redirect("https://assets.assembly.com/addresses/"+str(searched), code=200)
    elif searched[0]=='3':
      #IS A COLOR ADDRESS
      return redirect("https://assets.assembly.com/colors/"+str(searched), code=200)
    else:
      return redirect("https://www.youtube.com/watch?v=dQw4w9WgXcQ", code=200)

@app.route('/transactions/<tx_hash>')
def transactions_data(tx_hash=None):
  app.send_static_file('transactions.html')

# @app.route('/colors/<color>')
# def colors_data(color=None):
#
# @app.route('/addresses/<address>')
# def addresses_data(address=None):


#ADDRESSES

@app.route('/v1/addresses/brainwallet/<phrase>')
def brainwallet(phrase=None):
  public_address=addresses.generate_publicaddress(phrase)
  public_key=addresses.generate_publickey(phrase)
  private_key=addresses.generate_privatekey(phrase)
  jsonresponse={}
  jsonresponse['public_key']=public_key
  jsonresponse['public_address']=public_address
  jsonresponse['private_key']=private_key
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/addresses')
def makerandompair():
  pair=addresses.generate_secure_pair()
  pair=json.dumps(pair)
  response=make_response(str(pair), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/addresses/<public_address>/<color_address>')
def colorbalance(public_address=None, color_address=None):
  answer=databases.color_balance(public_address, color_address)
  jsonresponse={}
  jsonresponse[public_address]=answer
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/addresses/<public_address>')
def colorbalances(public_address=None):
  answer=databases.color_balance(public_address, None)
  jsonresponse={}
  jsonresponse['public_address']=public_address
  jsonresponse['assets']=[]
  issuer=""
  colorname=""
  for x in answer:
    r={}
    colordata=databases.dbexecute("select * from colors where color_address='"+str(x)+"';", True)
    if len(colordata)>0:
      colorname=colordata[0][3]
      issuer=colordata[0][1]
      if colorname=="color_name":
        colorname=""

    r['issuing_address']=str(issuer)
    r['color_name']=colorname
    r['color_address']=x
    r['quantity']=answer[x]
    jsonresponse['assets'].append(r)
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

#COLORS

@app.route('/v1/colors/created')
def showcreatedassets():
  created_assets = databases.dbexecute("select distinct coin_name, issued_amount, public_address from addresses where amount_received>=amount_expected;", True)
  jsonresponse={}
  jsonresponse['colors_created']=[]
  for x in created_assets:
    a={}
    a['coin_name'] = x[0]
    a['issued_amount'] = x[1]
    a['public_address']=x[2]
    jsonresponse['colors_created'].append(a)

  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/colors/name/<the_name>')
def searchbyname(the_name=None):
  the_name = the_name.replace ("_", " ")
  coloraddress= None
  result=databases.dbexecute("select color_address from colors where color_name='"+the_name+"';",True)
  if len(result)>0:
    coloraddress=result[0][0]
  jsonresponse={}
  jsonresponse['color_address']=coloraddress
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/colors/source/<source_address>')
def getcoloraddressfromsource(source_address=None):
  coloraddress = "not found"
  if not source_address == None:
    coloraddress = databases.dbexecute("select color_address from colors where source_address='"+str(source_address)+"'", True)

  jsonresponse['color_address']=coloraddress
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/colors/prepare', methods=['POST'])
def givenewaddress():
  pair=addresses.generate_secure_pair()
  public_address=pair['public_address']
  private_key=pair['private_key']

  jsoninput=json.loads(request.data)

  coin_name=jsoninput['coin_name']
  color_amount=jsoninput['issued_amount']
  dest_address=public_address
  description=jsoninput['description']
  email=jsoninput['email']
  fee_each=0.00005
  markup=1
  tosend=str(transactions.creation_cost(color_amount, coin_name, "", description, fee_each, markup))

  responsejson={}
  responsejson['name']=coin_name
  responsejson['minting_fee']=tosend
  responsejson['issuing_public_address']=public_address
  responsejson['issuing_private_key']=private_key
  responsejson=json.dumps(responsejson)

  amount_expected=str(int(float(tosend)*100000000))
  amount_received="0"
  amount_withdrawn="0"
  k=databases.add_address(public_address, private_key, amount_expected, amount_received, amount_withdrawn, coin_name, color_amount, dest_address, description, email)
  print k

  response=make_response(responsejson, 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/colors', methods=['POST'])   #WORKS
def givenewaddress_specifics():
  jsoninput=json.loads(request.data)

  public_address=str(jsoninput['public_address'])
  private_key=str(jsoninput['private_key'])

  coin_name=str(jsoninput['name'])
  color_amount=str(jsoninput['initial_coins'])
  dest_address=public_address
  description=str(jsoninput['description'])
  email=str(jsoninput['email'])

  fee_each=float(jsoninput['fee_each'])
  markup=0
  tosend=str(transactions.creation_cost(color_amount, coin_name, "", description, fee_each, markup))

  responsejson={}
  responsejson['name']=coin_name
  responsejson['minting_fee']=tosend
  responsejson['issuing_public_address']=public_address
  responsejson['issuing_private_key']=private_key
  responsejson=json.dumps(responsejson)

  amount_expected=str(int(float(tosend)*100000000))
  amount_received="0"
  amount_withdrawn="0"
  k=databases.add_address(public_address, private_key, amount_expected, amount_received, amount_withdrawn, coin_name, color_amount, dest_address, description, email)
  print k

  response=make_response(responsejson, 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/colors/<color_address>')
def colorholders(color_address=None):
  answer=databases.color_holders(color_address)
  if len(answer)==0:
    color_address=databases.first_coloraddress_from_sourceaddress(color_address)
    if not color_address is None:
      answer=databases.color_holders(color_address)
    else:
      answer=""

  colordata=databases.dbexecute("select * from colors where color_address='"+color_address+"';",True)
  source_address="not found"
  color_name="not found"
  if len(colordata)>0:
    source_address=colordata[0][1]
    color_name=colordata[0][3]
    if color_name=="color_name":
      color_name=""

  jsonresponse={}
  jsonresponse['owners']=[]
  jsonresponse['color_address']=color_address
  jsonresponse['issuing_address']=source_address
  jsonresponse['color_name']=color_name

  for x in answer:
    r={}
    r['public_address']=x['public_address']
    r['quantity']=x['quantity']
    jsonresponse['owners'].append(r)

  answer=json.dumps(jsonresponse)
  response=make_response(str(answer), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

#MESSAGES
@app.route('/v1/opreturns/<blockn>')           #DEPRECATED, NOT SUPPORTED
def opreturns_in_block(blockn=None):
    print blockn
    blockn=int(blockn)
    message=bitsource.op_return_in_block(blockn)
    # jsonresponse={}
    # jsonresponse['block_height']=int(blockn)
    # jsonresponse['op_returns']=[]
    # for x in message:
    #   r={}
    #   r['transaction_hash']=x[0]
    #   r['message']=x[1]
    #   r['btc']=x[2]
    #   jsonresponse['op_returns'].append(r)
    #
    # answer=json.dumps(jsonresponse)
    response=make_response(str(message), 200)
    response.headers['Content-Type'] = 'application/json'
    response.headers['Access-Control-Allow-Origin']= '*'
    return response

@app.route('/v1/messages/<address>')
def readmultistatements(address=None):
  result=addresses.read_opreturns_sent_by_address(address)
  jsonresponse={}
  jsonresponse['statements']=result
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/messages/raw/<address>')
def opreturns_sent_by_address(address=None):
  results=addresses.find_opreturns_sent_by_address(address)
  jsonresponse={}
  jsonresponse['op_returns']=results
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(jsonresponse, 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/messages', methods=['POST'])
def newdeclaration():
  jsoninput=json.loads(request.data)

  fromaddr=str(jsoninput['public_address'])
  fee_each=str(jsoninput['fee_each'])
  privatekey=str(jsoninput['private_key'])
  message=str(jsoninput['message'])
  print message
  results=transactions.declaration_tx(fromaddr, fee_each, privatekey, message)
  print results
  jsonresponse={}
  jsonresponse['transaction_id']=results
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/messages/web', methods=['POST'])
def newwebdeclaration():
  jsoninput=json.loads(request.data)
  fromaddr=str(jsoninput['public_address'])
  fee_each=jsoninput['fee_each']
  privatekey=str(jsoninput['private_key'])
  tx=''
  if 'plain_message' in jsoninput:
    message=str(jsoninput['plain_message'])
    dest=fromaddr
    specific_inputs=addresses.unspent(fromaddr)
    tx = transactions.send_op_return(fromaddr, dest, fee_each, message, privatekey, specific_inputs)
    print tx
  elif 'hash_message' in jsoninput:
    hashmessage=str(jsoninput['hash_message'])

    message=hashlib.sha256(hashmessage).digest()
    dest=fromaddr
    specific_inputs=addresses.unspent(fromaddr)
    tx = transactions.send_op_return(fromaddr, dest, fee_each, message, privatekey, specific_inputs)
    print tx

  jsonresponse={}
  jsonresponse['transaction_hash']=tx
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response



#TXS
@app.route('/v1/transactions/parsed/<blockn>')
def oas_in_block(blockn=None):
  oas=workertasks.oa_in_block(int(blockn))
  answer={}
  answer['parsed_transactions']=[]
  for x in oas:
    r={}
    r['transaction_hash_with_index']=x[0]
    r['parsed_colored_info']=x[1]
    answer['parsed_transactions'].append(r)
  answer=json.dumps(answer)
  response=make_response(str(answer), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/transactions/colored', methods=['POST'])
def transfer_transaction_serverside():
  jsoninput=json.loads(request.data)

  fromaddr=str(jsoninput['public_address'])
  dest=str(jsoninput['recipient'])
  fee=float(jsoninput['fee'])
  private_key=str(jsoninput['private_key'])
  coloramt=int(jsoninput['coloramt'])

  inputs=str(jsoninput['inputs'])
  inputs=ast.literal_eval(inputs)
  inputcoloramt=int(jsoninput['inputcoloramt'])
  print fromaddr
  print dest
  print fee
  print private_key
  print coloramt
  print inputs
  print inputcoloramt
  othermeta=''
  result= transactions.create_transfer_tx(fromaddr, dest, fee, private_key, coloramt, inputs, inputcoloramt, othermeta)
  response=make_response(str(result), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/transactions/raw/<transaction_hash>')
def getrawtransaction(transaction_hash=None):
  transaction_hash=transaction_hash.encode('ascii')
  response=bitsource.tx_lookup(str(transaction_hash))
  jsonresponse={}
  jsonresponse['raw_transaction']=response
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/transactions/issue', methods=['POST'])    #WORKS
def issuenewcoinsserverside():   #TO ONE RECIPIENT ADDRESS
  jsoninput=json.loads(request.data)

  private_key=str(jsoninput['private_key'])
  public_address=str(jsoninput['public_address'])
  more_coins=int(jsoninput['more_coins'])
  recipient=str(jsoninput['recipient'])
  fee_each=str(jsoninput['fee_each'])
  name=str(jsoninput['name'])
  othermeta=str(name)

  specific_inputs = addresses.get_unspent(public_address)
  #REMOVE COLORED OUTPUTS FROM THIS
  for x in specific_inputs:
    txhash_index = x['output']
    found = databases.dbexecute("select * from outputs where spent='False' and txhash_index='"+str(txhash_index)+"' and destination_address='"+str(public_address)+"';",True)
    nfound = len(found)
    if nfound>0:
      specific_inputs.remove(x)

  print specific_inputs
  response=transactions.create_issuing_tx(public_address, recipient, fee_each, private_key, more_coins, specific_inputs, othermeta)
  jsonresponse={}
  jsonresponse['transaction_hash']=response
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/transactions/issue/client', methods = ['POST'])      #WORKS
def issuenewcoins_clientside():
  jsoninput=json.loads(request.data)

  issuing_address=str(jsoninput['issuing_address'])
  more_coins=jsoninput['more_coins']
  coin_recipients=str(jsoninput['coin_recipients'])
  othermeta='COIN NAME HERE'

  fee=0.00005
  print coin_recipients
  print more_coins
  print issuing_address
  print fee
  print othermeta
  tx=transactions.create_issuing_tx_unsigned(issuing_address, coin_recipients, fee, more_coins,othermeta)
  jsonresponse={}
  jsonresponse['transaction_hash']=tx
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/transactions/transfer/deprecated', methods=['POST'])
def transfercoins_serverside():
  jsoninput=json.loads(request.data)

  fromaddr=str(jsoninput['from_public_address'])
  privatekey=str(jsoninput['from_private_key'])
  coloramt=int(jsoninput['amount'])
  source_address=str(jsoninput['source_address'])
  destination=str(jsoninput['to_public_address'])
  fee=0.00005
  othermeta="Transfer"
  result=transactions.transfer_tx(fromaddr, destination, fee, privatekey, source_address, coloramt, othermeta)
  jsonresponse={}
  jsonresponse['transaction_hash']=result[0]
  jsonresponse['source_address']=source_address
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/transactions/transfer', methods=['POST'])
def schedule_transfer():
  jsoninput=json.loads(request.data)
  fromaddr=str(jsoninput['from_public_address'])
  dest=str(jsoninput['to_public_address'])
  fee_each=float(jsoninput['fee_each'])
  fee_each=str(int(fee_each*100000000))
  privatekey=str(jsoninput['from_private_key'])
  sourceaddress=str(jsoninput['issuing_address'])
  coloramt=str(jsoninput['transfer_amount'])

  r=str(random.random())
  random_id=str(hashlib.sha256(r).hexdigest())

  callback_url=None
  if 'callback_url' in jsoninput:
    callback_url=jsoninput['callback_url']
    dbstring="insert into tx_queue (first_tried_at_block, success, from_public, from_private, destination, fee_each, source_address, transfer_amount, callback_url, randomid) values ('-1','False"+"','"+fromaddr+"','"+privatekey+"','"+dest+"','"+fee_each+"','"+sourceaddress+"','"+coloramt+"','"+callback_url+"','"+str(random_id)+"');"
  else:
    dbstring="insert into tx_queue (first_tried_at_block, success, from_public, from_private, destination, fee_each, source_address, transfer_amount, randomid) values ('-1','False"+"','"+fromaddr+"','"+privatekey+"','"+dest+"','"+fee_each+"','"+sourceaddress+"','"+coloramt+"','"+str(random_id)+"');"

  databases.dbexecute(dbstring,False)

  jsonresponse={}
  jsonresponse['result']="Queued"
  jsonresponse['id']=random_id
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/transactions/transfer/many', methods=['POST'])
def transfer_many_serverside():
  jsoninput=json.loads(request.data)
  fromaddr=str(jsoninput['from_public_address'])
  dest_array=jsoninput['destinations']
  fee_each=float(jsoninput['fee_each'])
  privatekey=str(jsoninput['from_private_key'])
  sourceaddress=str(jsoninput['issuing_address'])
  coloramt_array=jsoninput['transfer_amounts']
  results=transactions.multiple_transfer_txs(fromaddr, dest_array, fee_each, privatekey, sourceaddress, coloramt_array)
  jsonresponse={}
  jsonresponse['transaction_hashes']=results
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/transactions', methods = ['POST'])
def pushtx():
  jsoninput=json.loads(request.data)

  txhex=str(jsoninput['transaction_hex'])
  response=transactions.pushtx(txhex)
  jsonresponse={}
  jsonresponse['transaction_hash']=response
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(jsonresponse, 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/transactions/<tx_hash>')
def colortxs(tx_hash=None):
  dbstring="SELECT * FROM outputs WHERE txhash='"+str(tx_hash)+"';"
  result=databases.dbexecute(dbstring,True)
  response={}
  response['outputs']=[]
  for x in result:
    jsonresponse={}
    jsonresponse['btc']=x[0]
    jsonresponse['color_amount']=x[1]
    jsonresponse['color_address']=x[2]
    jsonresponse['spent']=x[3]
    jsonresponse['spent_at_txhash']=x[4]
    jsonresponse['destination_address']=x[5]
    jsonresponse['txhash']=x[6]
    jsonresponse['txhash_index']=x[7]
    jsonresponse['blockmade']=x[8]
    jsonresponse['previous_input']=x[9]
    jsonresponse['blockspent']=x[10]
    response['outputs'].append(jsonresponse)
  results=json.dumps(response)
  response=make_response(str(results), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

@app.route('/v1/transactions/recent/<txs_n>') #WORKS
def color_txs_in_block(txs_n=None):
  if txs_n==None:
    txs_n=10

  dbstring="SELECT * FROM outputs ORDER BY blockmade DESC limit "+str(txs_n)+";"
  print dbstring
  results=databases.dbexecute(dbstring,True)
  response={}
  response['outputs']=[]
  for x in results:
    jsonresponse={}
    jsonresponse['btc']=x[0]
    jsonresponse['color_amount']=x[1]
    jsonresponse['color_address']=x[2]
    jsonresponse['spent']=x[3]
    jsonresponse['spent_at_txhash']=x[4]
    jsonresponse['destination_address']=x[5]
    jsonresponse['txhash']=x[6]
    jsonresponse['txhash_index']=x[7]
    jsonresponse['blockmade']=x[8]
    jsonresponse['previous_input']=x[9]
    jsonresponse['blockspent']=x[10]
    response['outputs'].append(jsonresponse)
  results=json.dumps(response)
  response=make_response(str(results), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response


#BITCOIN
@app.route('/v1/btc', methods=['POST'])
def sendbtc():
  jsoninput=json.loads(request.data)
  public_address=str(jsoninput['public_address'])
  destination=str(jsoninput['destination'])
  private_key=str(jsoninput['private_key'])
  amount=str(int(jsoninput['amount']*100000000))
  r=str(random.random())
  random_id=str(hashlib.sha256(r).hexdigest())

  fee=str(5000)
  dbstring="insert into tx_queue (first_tried_at_block, success, from_public, from_private, destination, fee_each, source_address, transfer_amount, randomid) values ('-1', 'False', '"+public_address+"','"+str(private_key)+"','"+destination+"','"+fee+"', '', '"+str(amount)+"','"+str(random_id)+"');"
  print dbstring
  databases.dbexecute(dbstring,False)

  jsonresponse={}
  jsonresponse['result']="Queued"
  jsonresponse['id']=random_id
  jsonresponse=json.dumps(jsonresponse)
  response=make_response(str(jsonresponse), 200)
  response.headers['Content-Type'] = 'application/json'
  response.headers['Access-Control-Allow-Origin']= '*'
  return response

#OTHER FUNCTIONS

def update_meta_db(lastblockprocessed, additional_txs):
  meta = databases.meta_db.Meta.query.all().first()

  meta.lastblockprocessed=lastblockprocessed
  meta.numberoftransactions=meta.numberoftransactions+1

  db.session.commit()

working=True

def workerstuff():
  if working:
    print "I am trying to work now"
    workertasks.more_blocks(50)
    workertasks.checkaddresses()
    #try:
    workertasks.tx_queue_batches()

  else:
    print "working is off"

if __name__ == '__main__':
  app.run()

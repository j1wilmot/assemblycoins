import addresses
import requests
import json
from bitcoin import *
import bitsource
import cointools
import databases
import time
import node

from memory_profiler import profile

dust=601*0.00000001
max_op_length=37 #in bytes

def find_suitable_inputs(public_address, amount_needed, spend_dust, sought_for_tag):
  inputs=cointools.unspent(public_address)
  amount_needed=int(amount_needed*100000000)
  result=[]
  totalin=0
  n=0
  for ins in inputs:
    if totalin<amount_needed:
      if not spend_dust and inputs[n]['value']>dust*100000000:
        result.append(inputs[n])
        totalin=totalin+inputs[n]['value']
      elif spend_dust:
        result.append(inputs[n])
        totalin=totalin+inputs[n]['value']
    n=n+1
  return result

def make_raw_transaction(fromaddress,amount,destination, fee):

      fee=int(float(fee)*100000000)
      amount=int(float(amount)*100000000)
      unspents=find_suitable_inputs(fromaddress, amount+fee, False, '')

      print "FOUND INPUTS:"
      print unspents
      print ''

      ins=[]
      outs=[]
      totalin=0

      for uns in unspents:
        totalin=totalin+uns['value']
        ins.append(uns)

      print totalin
      print str(amount+fee)

      if totalin>=amount+fee:
        outs.append({'value': amount, 'address': destination})
      extra=totalin-amount-fee
      if extra>=dust*100000000:
        outs.append({'value':extra, 'address':fromaddress})

      tx=mktx(ins,outs)
      #print tx
      return tx

def make_raw_one_input(fromaddress,amount,destination,fee, specific_inputs):  #NEEDS REWORKING
  fee=int(float(fee)*100000000)
  amount=int(float(amount)*100000000)
  #unspents=unspent(fromaddress)
  #unspents=[unspents[input_n]]
  unspents=specific_inputs

  ins=[]
  outs=[]
  totalin=0

  print 'unspents below'
  print unspents
  print ''

  if not unspents=="failed":
    for uns in unspents:
      if 'value' in uns:
        totalin=totalin+uns['value']
        ins.append(uns)
  else:
    unspents=[]

  print "TOTALIN: "+str(totalin)
  print "AMOUNT: "+str(amount)
  print "FEE: "+str(fee)

  if totalin>=amount+fee:
    if amount>=int(dust*100000000):
      outs.append({'value': amount, 'address': destination})
  extra=totalin-amount-fee
  if extra>=dust*100000000:
    outs.append({'value':extra, 'address':fromaddress})

  print ins
  print ''
  print outs
  print ''

  try:
    tx=mktx(ins,outs)
    print tx
  except:
    tx='failed'
    print "something went wrong with writing TX"
    print "inputs were: "
    print ins
    print ''
    print "outputs were:"
    print outs

  return tx

def make_raw_multiple_outputs(fromaddress, output_n, output_amount_each, destination, fee):
  outputs=[]
  for i in range(0,output_n):
    outputs.append({'value': int(output_amount_each*100000000), 'address': destination})

  fee=int(fee*100000000)

  unspents=unspent(fromaddress)  #using vitalik's version could be problematic

  totalout=0
  for x in outputs:
    totalout=totalout+x['value']
  ins=[]
  ok=False
  outs=[]
  totalfound=0
  for unsp in unspents:
    ins.append(unsp)
    totalfound=totalfound+unsp['value']
  change_amount=totalfound-totalout-fee
  outs=outputs
  if change_amount>int(dust*100000000):
    outs.append({'value': change_amount, 'address': fromaddress})

  print 'ins'
  print ins
  print ''
  print 'outs'
  print outs

  tx=mktx(ins,outs)

  return tx

def make_multiple_outputs(fromaddress, privatekey, output_n, value_each,  total_fee):  #WORKS
  tx=make_raw_multiple_outputs(fromaddress, output_n, value_each, fromaddress, total_fee)
  tx2=sign_tx(tx, privatekey)
  response=pushtx(tx2)
  free_outputs=[]
  for i in range(0,output_n):
    outputdata={}
    outputdata['output']=str(response)+":"+str(i)
    outputdata['value']= int(value_each*100000000)
    free_outputs.append(outputdata)
  print ''
  print free_outputs
  return free_outputs

def make_op_return_script(message):
   #OP RETURN SCRIPT
   hex_message=message.encode('hex')
   hex_message_length=hex(len(message))

   r=2
   f=''
   while r<len(hex_message_length):
      f=f+hex_message_length[r]
      r=r+1
   if len(f)<2:
      f='0'+f

   b='6a'+f+hex_message
   return b

def add_op_return(unsigned_raw_tx, message, position_n):
  deserialized_tx=deserialize(unsigned_raw_tx)

  newscript=make_op_return_script(message)

  newoutput={}
  newoutput['value']=0
  newoutput['script']=newscript

  if position_n>=len(deserialized_tx['outs']):
    deserialized_tx['outs'].append(newoutput)
  else:
    deserialized_tx['outs'].insert(position_n,newoutput)
  #deserialized_tx['outs'].append(newoutput)

  reserialized_tx=serialize(deserialized_tx)

  return reserialized_tx

def sign_tx(unsigned_raw_tx, privatekey):
  tx2=unsigned_raw_tx

  detx=deserialize(tx2)
  input_length=len(detx['ins'])

  for i in range(0,input_length):
    tx2=sign(tx2,i,privatekey)

  return tx2

def pushtx_toshi(rawtx):
  print "Trying to push: "+ str(rawtx)
  d={}
  d['hex']=rawtx
  d=json.dumps(d)
  response=requests.put("https://bitcoin.toshi.io/api/v0/transactions", data=d)
  print "Push Response was "+str(response.content)
  return response.content

def pushtx(rawtx):
  url="https://api.chain.com/v1/bitcoin/transactions"
  data = {}

  authstuff=(os.environ['CHAIN_API_KEY'], os.environ['CHAIN_API_KEY_SECRET'] )

  print "PUSHING RAW TX:"
  print rawtx
  print ''

  data['hex'] = rawtx
  jsondata=json.dumps(data)
  response=requests.post(url, data=jsondata, auth=authstuff)
  print "Push Response was "+str(response.content)
  jsonresponse=json.loads(response.content)
  if 'transaction_hash' in jsonresponse:
    return str(jsonresponse['transaction_hash'])
  else:
    return "None"

def pushtx_local(rawtx):
  print "Trying to push: "+ str(rawtx)
  response=node.connect('sendrawtransaction',[rawtx])
  print "Push Response was "+str(response)

  return response

def send_op_return(fromaddr, dest, fee, message, privatekey, specific_inputs):
  tx=make_raw_one_input(fromaddr, dust, dest, fee, specific_inputs)
  if not tx=='failed':
    tx2=add_op_return(tx,message,1)
    tx3=sign_tx(tx2,privatekey)
    print tx3
    response=pushtx(tx3)
    print tx3
    print "Response: "+str(response)
    return response
  else:
    return "failed"

def create_issuing_tx(fromaddr, dest, fee, privatekey, coloramt, specific_inputs, othermeta):
  #ONLY HAS ONE ISSUE
  amt=dust
  tx=make_raw_one_input(fromaddr,amt,dest,fee, specific_inputs)
  if not tx=='failed':
    asset_quantities= [coloramt]
    metadata=bitsource.write_metadata(asset_quantities, othermeta).decode('hex')
    position_n=1

    tx2=add_op_return(tx, metadata, position_n)
    print tx2
    tx3=sign_tx(tx2,privatekey)
    print tx3

    response=pushtx(tx3)
    print response
    return response
  else:
    print "failed"
    return "failed"

def create_issuing_tx_unsigned(fromaddr, dest, fee, coloramt, othermeta):
  #ONLY HAS ONE ISSUE
  amt=dust
  tx=make_raw_transaction(fromaddr,amt,dest,fee)

  asset_quantities= [coloramt]

  metadata=bitsource.write_metadata(asset_quantities, othermeta).decode('hex')
  position_n=1

  tx2=add_op_return(tx, metadata, position_n)
  print tx2
  return tx2

def declaration_tx(fromaddr, fee_each, privatekey, message):
  n_transactions=len(message)/max_op_length+1
  continu=True
  responses=[]
  #PREPARE OUTPUTS
  fee_each=float(fee_each)
  value_each=fee_each+dust
  specific_inputs=make_multiple_outputs(fromaddr, privatekey, n_transactions+1, value_each, fee_each)

  for n in range(0,n_transactions):
    if continu:
      indexstart=max_op_length*n
      indexend=indexstart+max_op_length
      if indexend>len(message):
        indexend=len(message)
      specific_input=specific_inputs[n:n+1]
      submessage=str(n)+" "+message[indexstart:indexend]
      #print submessage
      r=send_op_return(fromaddr, fromaddr, fee_each, submessage, privatekey,specific_input)
      print r
      if r is None:
        continu=False
      else:
        responses.append(r)
  return specific_inputs

def create_transfer_tx(fromaddr, dest, fee, privatekey, coloramt, inputs, inputcoloramt, othermeta):
  fee=int(fee*100000000)
  sum_inputs=0
  for x in inputs:
    sum_inputs=x['value']+sum_inputs
    print x['value']
  print "SUM INPUTS: "+str(sum_inputs)

  outputs=[]
  transfer={}
  transfer['value']=int(dust*100000000)
  transfer['address']=dest
  outputs.append(transfer)
  colorchange={}
  colorchange['value']=int(dust*100000000)
  colorchange['address']=fromaddr
  outputs.append(colorchange)
  btcchange={}
  btcchange['value']=int(sum_inputs-fee-2*int(dust*100000000))
  print "BTCCHANGE "+str(btcchange['value'])
  btcchange['address']=fromaddr
  if btcchange['value']>=int(dust*100000000):
    outputs.append(btcchange)

  tx=mktx(inputs,outputs)

  asset_quantities=[coloramt, inputcoloramt-coloramt]
  print "METADATA"
  print asset_quantities
  print othermeta
  print ""
  message=bitsource.write_metadata(asset_quantities, othermeta)
  message=message.decode('hex')
  tx2=add_op_return(tx,message, 0)  #JUST TRANSFERS

  for i in range(len(inputs)):
    tx2=sign_tx(tx2,privatekey)
  print tx2
  response=pushtx(tx2)

  free_outputs=[]
  j=1
  for x in outputs:
    r={}
    r['value']=x['value']
    if not response is None:
      r['output']=str(response)+":"+str(j)
      free_outputs.append(r)
    j=j+1

  return response, free_outputs

def create_transfer_tx_multiple(fromaddr, dest_array, fee_each, privatekey, coloramt_array, inputs, inputcoloramt, othermeta):
  global outputs, tx, tx2
  fee=int(fee_each*100000000)
  suminputs=0
  for x in inputs:
    suminputs=x['value']+suminputs
  outputs=[]
  n=0
  leftover_color=inputcoloramt
  leftover_btc=suminputs
  for dest in dest_array:
    transfer={}
    transfer['value']=int(dust*100000000)
    transfer['address']=dest
    outputs.append(transfer)
    leftover_btc=leftover_btc-int(100000000*dust*2)
    leftover_color=leftover_color-coloramt_array[n]
    n=n+1
  colorchange={}
  colorchange['value']=int(dust*100000000)
  colorchange['address']=fromaddr
  outputs.append(colorchange)
  leftover_btc=leftover_btc-int(dust*100000000)-fee
  btcchange={}
  btcchange['value']=leftover_btc
  btcchange['address']=fromaddr
  if leftover_btc>int(dust*100000000):
    outputs.append(btcchange)

  # print ''
  # print ''
  # print "CREATE TX TRANSFER MULTIPLE"
  # print 'inputs'
  # print inputs
  # print ''
  # print 'outputs'
  # print outputs
  # print ''

  tx=mktx(inputs, outputs)
  #
  # print 'tx'
  # print tx

  asset_quantities=coloramt_array
  if leftover_color>0:
    asset_quantities.append(leftover_color)
  print asset_quantities
  message=bitsource.write_metadata(asset_quantities, othermeta)
  message=message.decode('hex')
  tx2=add_op_return(tx,message, 0)  #JUST TRANSFERS
  #
  # print 'tx2'
  # print tx2

  for i in range(len(inputs)):
    tx2=sign_tx(tx2,privatekey)
  print tx2
  response=pushtx(tx2)
  return response


def find_transfer_inputs(fromaddr, coloraddress, coloramt, btc):
  if coloraddress is None:
    coloraddress="none"
  available_inputs=databases.dbexecute("SELECT * FROM OUTPUTS WHERE spent='False' and destination_address='"+fromaddr+"' and color_address='"+coloraddress+"';",True)
  other_inputs=addresses.get_unspent(fromaddr)
  totalfound=0
  btc=int(btc*100000000)
  totalavailable=0
  btcfound=0
  btcavailable=0
  answer=[]
  totalinputamt=0
  for x in available_inputs:
    totalavailable=totalavailable+x[1]
  for x in other_inputs:
    btcavailable=btcavailable+x['value']

  if totalavailable>=coloramt and btcavailable>=btc:
    n=0
    while totalfound<coloramt and n<len(available_inputs):
      r={}
      r['output']=available_inputs[n][7]
      r['value']=available_inputs[n][0]
      btcfound=btcfound+r['value']
      totalinputamt=totalinputamt+r['value']
      totalfound=totalfound+available_inputs[n][1]
      answer.append(r)
      n=n+1
    n=0
    while btcfound<btc and n<len(other_inputs):
      r={}
      if n<len(other_inputs):
        r=other_inputs[n]

        found=False
        for x in answer:
          if x['output']==r['output']:
            found=True

        if other_inputs[n]['value']>dust and not found:
          btcfound=btcfound+other_inputs[n]['value']
          answer.append(r)
      n=n+1

  return answer, totalfound

def transfer_tx(fromaddr, dest, fee, privatekey, sourceaddress, coloramt, othermeta):
  btcneeded=fee+dust*4
  coloraddress=databases.first_coloraddress_from_sourceaddress(sourceaddress)
  result=''
  if len(coloraddress)>0:
    coloramt=int(coloramt)
    inputdata=find_transfer_inputs(fromaddr, coloraddress, coloramt, btcneeded)
    inputs=inputdata[0]
    inputcoloramt=inputdata[1]
    result=create_transfer_tx(fromaddr, dest, fee, privatekey, coloramt, inputs, inputcoloramt, othermeta)
  return result

#MANY AT ONCE
def transfer_tx_multiple(fromaddr, dest_array, fee_each, privatekey, sourceaddress, coloramt_array, othermeta):
  m=len(dest_array)
  btcneeded=fee_each*(1)+dust*m
  coloraddress=databases.first_coloraddress_from_sourceaddress(sourceaddress)
  result="No Color Found"
  inputcoloramt=0
  responses=[]
  if not coloraddress is None:
    if len(coloraddress)>0:
      print "finding inputs for "
      print str(fromaddr)+" / "+ str(coloraddress)+" / " +str(sum(coloramt_array))+" / "+str(btcneeded)
      inputs=find_transfer_inputs(fromaddr, coloraddress, sum(coloramt_array), btcneeded)
      print "inputs"
      print inputs
      print ""
      inputcoloramt=inputs[1]
      inputs=inputs[0]
      result=create_transfer_tx_multiple(fromaddr, dest_array, fee_each, privatekey, coloramt_array, inputs, inputcoloramt, "")
  return result, inputcoloramt

#WORKS, LOOPING VERSION
def multiple_transfer_txs(fromaddr, dest_array, fee_each, privatekey, sourceaddress, coloramt_array):

  m=len(dest_array)
  btcneeded=m*(fee_each+dust*4)
  coloraddress=databases.first_coloraddress_from_sourceaddress(sourceaddress)
  result="No Color Found"
  responses=[]
  if len(coloraddress)>0:
    coloramt=sum(coloramt_array)
    inputdata=find_transfer_inputs(fromaddr, coloraddress, coloramt, btcneeded)
    inputs=inputdata[0]
    inputcoloramt=inputdata[1]
    n=0
    while n<len(coloramt_array) and inputcoloramt>0:
      print "What I'm inputting: "+str(inputs)
      print ""
      d=create_transfer_tx(fromaddr, dest_array[n], fee_each, privatekey, coloramt_array[n], inputs,inputcoloramt,"")
      r=d[1]
      print r
      inputs=r[1:len(r)]
      print inputs
      responses.append(d[0])
      inputcoloramt=inputcoloramt-coloramt_array[n]
      print "new input color amt: "+str(inputcoloramt)
      n=n+1
  return responses

def formation_message(colornumber, colorname, description):
  message={}
  message['name']=colorname
  message['total']=colornumber
  message['desc']=description
  message=str(json.dumps(message))
  # message="I declare "+str(colorname)+" with ticker: "+str(ticker)+'\nTotal Issued: '+str(colornumber)
  # message=message+'\n'+str(description)
  return message

def creation_cost(colornumber, colorname, ticker, description, fee_each, markup):
  message=formation_message(colornumber, colorname, description)
  n_transactions=len(message)/max_op_length+1
  cost=fee_each  #making outputs
  cost=cost+n_transactions*(fee_each+dust)  #declaration statements
  cost=cost + dust+fee_each #Issuance to single person
  cost=cost*(1.0+markup)
  return cost

def make_new_coin(fromaddr, colornumber, colorname, destination, fee_each, private_key, description):
  message=formation_message(colornumber, colorname, description)
  txs=declaration_tx(fromaddr, fee_each, private_key, message)
  specific_inputs=txs[len(txs)-1:len(txs)]
  tx1 = create_issuing_tx(fromaddr, destination, fee_each, private_key, colornumber, specific_inputs, colorname)
  print "issuing response heard: "+str(tx1)
  response={}
  response['transaction_hash']=tx1
  response['specific_inputs']=specific_inputs
  response=json.dumps(response)
  return response
  #return tx1, specific_inputs
